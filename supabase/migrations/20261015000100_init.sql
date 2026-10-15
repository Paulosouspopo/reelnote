-- =============================================================================
-- Reelnote — schéma initial
--
-- Principes :
--   * Toute donnée utilisateur porte un user_id et est protégée par RLS.
--   * Les tables techniques (file de jobs, nettoyage) vivent dans le schéma
--     "internal", qui n'est PAS exposé par l'API REST de Supabase.
--   * Les écritures sensibles passent par des fonctions SECURITY DEFINER
--     avec search_path vide et des noms entièrement qualifiés.
--   * Le navigateur ne détient jamais de secret : seulement la clé publishable.
-- =============================================================================

create schema if not exists internal;
revoke all on schema internal from public;
revoke all on schema internal from anon, authenticated;

create extension if not exists pgcrypto with schema extensions;
create extension if not exists unaccent with schema extensions;

-- -----------------------------------------------------------------------------
-- Recherche plein texte en français, insensible aux accents ("cafe" = "café")
-- -----------------------------------------------------------------------------
create text search configuration public.french_unaccent (copy = pg_catalog.french);
alter text search configuration public.french_unaccent
  alter mapping for hword, hword_part, word
  with extensions.unaccent, french_stem;

-- -----------------------------------------------------------------------------
-- Types
-- -----------------------------------------------------------------------------
-- Cycle de vie technique d'un reel (géré par le worker)
create type public.reel_status as enum ('queued', 'processing', 'ready', 'failed');
create type public.reel_stage  as enum ('downloading', 'extracting', 'transcribing', 'analyzing', 'finalizing');
-- Cycle de vie côté utilisateur ("inbox zero")
create type public.user_status as enum ('inbox', 'todo', 'done', 'archived');
-- Jobs
create type internal.job_status as enum ('queued', 'running', 'succeeded', 'failed');

-- -----------------------------------------------------------------------------
-- Utilitaires
-- -----------------------------------------------------------------------------
create or replace function internal.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- URL canonique construite côté serveur : on ne fait jamais confiance
-- à une URL fournie par le client pour ce que le worker va télécharger.
create or replace function internal.canonical_url(p_platform text, p_external_id text)
returns text
language sql
immutable
set search_path = ''
as $$
  select case p_platform
    when 'instagram' then 'https://www.instagram.com/reel/' || p_external_id || '/'
    when 'youtube'   then 'https://www.youtube.com/shorts/' || p_external_id
  end;
$$;

-- =============================================================================
-- reels : une ligne = un reel partagé par un utilisateur
-- =============================================================================
create table public.reels (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users (id) on delete cascade,

  -- Source
  platform        text not null check (platform in ('instagram', 'youtube')),
  external_id     text not null check (external_id ~ '^[A-Za-z0-9_-]{5,64}$'),
  source_url      text not null check (source_url ~ '^https://' and char_length(source_url) <= 2048),
  canonical_url   text not null check (char_length(canonical_url) <= 512),

  -- Traitement (écrit par le worker)
  status          public.reel_status not null default 'queued',
  stage           public.reel_stage,
  error_code      text,
  error_message   text,

  -- Métadonnées de la source
  author_handle   text,
  author_name     text,
  caption         text,
  duration_s      numeric(7, 2),
  posted_at       timestamptz,
  thumbnail_path  text,

  -- Contenu extrait
  transcript      text,
  transcript_lang text,

  -- Fiche générée
  kind            text check (kind in ('recipe', 'workout', 'place', 'media', 'product', 'tip', 'learning', 'other')),
  title           text,
  emoji           text,
  tldr            text,
  key_points      text[] not null default '{}',
  tags            text[] not null default '{}' check (cardinality(tags) <= 12),
  card            jsonb,
  caution         text,

  -- Traçabilité de l'analyse (pour régénérer quand le prompt évolue)
  analysis_version text,
  analysis_model   text,
  input_tokens     integer,
  output_tokens    integer,

  -- Couche utilisateur
  user_status     public.user_status not null default 'inbox',
  is_favorite     boolean not null default false,
  note            text check (char_length(note) <= 5000),

  -- Recherche (maintenue par trigger)
  search          tsvector,

  processed_at    timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  constraint reels_unique_per_user unique (user_id, platform, external_id)
);

comment on table public.reels is 'Reels partagés par les utilisateurs et leur fiche résumée.';
comment on column public.reels.card is 'Fiche complète validée par le worker (schéma versionné par analysis_version).';

create index reels_user_created_idx on public.reels (user_id, created_at desc);
create index reels_user_status_idx  on public.reels (user_id, user_status, created_at desc);
create index reels_search_idx       on public.reels using gin (search);
create index reels_tags_idx         on public.reels using gin (tags);
create index reels_pending_idx      on public.reels (status) where status in ('queued', 'processing');

create trigger reels_touch_updated_at
  before update on public.reels
  for each row execute function internal.touch_updated_at();

-- Index de recherche pondéré : titre > résumé/tags > légende/auteur > transcription
create or replace function internal.reels_build_search()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.search :=
       setweight(to_tsvector('public.french_unaccent', coalesce(new.title, '')), 'A')
    || setweight(to_tsvector('public.french_unaccent',
         coalesce(new.tldr, '') || ' ' || array_to_string(new.tags, ' ') || ' ' || array_to_string(new.key_points, ' ')), 'B')
    || setweight(to_tsvector('public.french_unaccent',
         coalesce(new.caption, '') || ' ' || coalesce(new.author_handle, '') || ' ' || coalesce(new.note, '')), 'C')
    || setweight(to_tsvector('public.french_unaccent', left(coalesce(new.transcript, ''), 20000)), 'D');
  return new;
end;
$$;

create trigger reels_build_search
  before insert or update of title, tldr, tags, key_points, caption, author_handle, note, transcript
  on public.reels
  for each row execute function internal.reels_build_search();

-- =============================================================================
-- ingest_tokens : jetons personnels utilisés par le Raccourci iOS
-- Seul le hash SHA-256 est stocké ; le jeton en clair n'est montré qu'une fois.
-- =============================================================================
create table public.ingest_tokens (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  name          text not null check (char_length(name) between 1 and 60),
  token_prefix  text not null,
  token_hash    bytea not null unique,
  created_at    timestamptz not null default now(),
  last_used_at  timestamptz,
  revoked_at    timestamptz
);

create index ingest_tokens_user_idx on public.ingest_tokens (user_id) where revoked_at is null;

-- =============================================================================
-- push_subscriptions : abonnements Web Push (un par appareil)
-- =============================================================================
create table public.push_subscriptions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  endpoint      text not null unique check (endpoint ~ '^https://' and char_length(endpoint) <= 1024),
  p256dh        text not null check (char_length(p256dh) <= 256),
  auth          text not null check (char_length(auth) <= 128),
  user_agent    text check (char_length(user_agent) <= 512),
  created_at    timestamptz not null default now(),
  last_used_at  timestamptz
);

create index push_subscriptions_user_idx on public.push_subscriptions (user_id);

-- =============================================================================
-- internal.jobs : file de traitement (Postgres + FOR UPDATE SKIP LOCKED)
-- =============================================================================
create table internal.jobs (
  id            bigint generated always as identity primary key,
  reel_id       uuid not null references public.reels (id) on delete cascade,
  type          text not null default 'process_reel' check (type in ('process_reel')),
  status        internal.job_status not null default 'queued',
  attempts      integer not null default 0,
  max_attempts  integer not null default 4 check (max_attempts between 1 and 10),
  run_after     timestamptz not null default now(),
  locked_by     text,
  locked_at     timestamptz,
  last_error    text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index jobs_claimable_idx on internal.jobs (run_after) where status = 'queued';
-- Garantit qu'un reel n'est jamais traité deux fois en parallèle
create unique index jobs_one_active_per_reel on internal.jobs (reel_id) where status in ('queued', 'running');

create trigger jobs_touch_updated_at
  before update on internal.jobs
  for each row execute function internal.touch_updated_at();

-- Réveille instantanément les workers qui écoutent (LISTEN reelnote_jobs)
create or replace function internal.jobs_notify()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  perform pg_notify('reelnote_jobs', new.id::text);
  return new;
end;
$$;

create trigger jobs_notify
  after insert or update of status on internal.jobs
  for each row when (new.status = 'queued')
  execute function internal.jobs_notify();

-- Fichiers à supprimer du stockage (miniatures des reels effacés)
create table internal.storage_garbage (
  id          bigint generated always as identity primary key,
  bucket      text not null,
  path        text not null,
  created_at  timestamptz not null default now()
);

-- SECURITY DEFINER : déclenché par un utilisateur qui n'a aucun droit sur internal
create or replace function internal.reels_collect_garbage()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if old.thumbnail_path is not null then
    insert into internal.storage_garbage (bucket, path) values ('thumbnails', old.thumbnail_path);
  end if;
  return old;
end;
$$;

create trigger reels_collect_garbage
  after delete on public.reels
  for each row execute function internal.reels_collect_garbage();

-- =============================================================================
-- Row Level Security
-- =============================================================================
alter table public.reels              enable row level security;
alter table public.ingest_tokens      enable row level security;
alter table public.push_subscriptions enable row level security;
alter table internal.jobs             enable row level security;
alter table internal.storage_garbage  enable row level security;

-- Privilèges explicites (on ne se repose pas sur les privilèges par défaut)
revoke all on public.reels, public.ingest_tokens, public.push_subscriptions from anon, authenticated;
revoke all on all tables in schema internal from anon, authenticated;

-- reels : lecture et suppression de ses propres reels ;
-- mise à jour limitée aux colonnes "utilisateur" (privilèges par colonne).
grant select, delete on public.reels to authenticated;
grant update (user_status, is_favorite, note, tags) on public.reels to authenticated;

create policy reels_select_own on public.reels
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy reels_update_own on public.reels
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy reels_delete_own on public.reels
  for delete to authenticated
  using ((select auth.uid()) = user_id);

-- ingest_tokens : lecture des métadonnées seulement, jamais du hash.
grant select (id, name, token_prefix, created_at, last_used_at, revoked_at) on public.ingest_tokens to authenticated;

create policy ingest_tokens_select_own on public.ingest_tokens
  for select to authenticated
  using ((select auth.uid()) = user_id);

-- push_subscriptions : l'enregistrement passe par une RPC (upsert par endpoint)
grant select, delete on public.push_subscriptions to authenticated;

create policy push_subscriptions_select_own on public.push_subscriptions
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy push_subscriptions_delete_own on public.push_subscriptions
  for delete to authenticated
  using ((select auth.uid()) = user_id);

-- =============================================================================
-- Fonctions métier
-- =============================================================================

-- Insère (ou retrouve) des reels pour un utilisateur et crée leurs jobs.
-- p_items : [{"platform": "instagram", "external_id": "Cxyz123", "source_url": "https://..."}]
create or replace function internal.enqueue_reels(p_user_id uuid, p_items jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_item        jsonb;
  v_platform    text;
  v_external_id text;
  v_source_url  text;
  v_reel        public.reels%rowtype;
  v_created     boolean;
  v_recent      integer;
  v_results     jsonb := '[]'::jsonb;
  c_max_items     constant integer := 25;
  c_max_per_hour  constant integer := 60;
begin
  if p_user_id is null then
    raise exception 'not authenticated' using errcode = 'PT401';
  end if;

  if jsonb_typeof(p_items) <> 'array'
     or jsonb_array_length(p_items) = 0
     or jsonb_array_length(p_items) > c_max_items then
    raise exception 'items must be an array of 1 to % elements', c_max_items using errcode = 'PT400';
  end if;

  -- Limite de débit : protège le budget IA si un jeton fuite
  select count(*) into v_recent
  from public.reels
  where user_id = p_user_id and created_at > now() - interval '1 hour';

  if v_recent + jsonb_array_length(p_items) > c_max_per_hour then
    raise exception 'rate limit exceeded' using errcode = 'PT429';
  end if;

  for v_item in select * from jsonb_array_elements(p_items) loop
    v_platform    := v_item ->> 'platform';
    v_external_id := v_item ->> 'external_id';
    v_source_url  := v_item ->> 'source_url';

    if v_platform not in ('instagram', 'youtube')
       or v_external_id is null or v_external_id !~ '^[A-Za-z0-9_-]{5,64}$'
       or v_source_url is null or v_source_url !~ '^https://' or char_length(v_source_url) > 2048 then
      raise exception 'invalid item: %', left(v_item::text, 200) using errcode = 'PT400';
    end if;

    insert into public.reels (user_id, platform, external_id, source_url, canonical_url)
    values (p_user_id, v_platform, v_external_id, v_source_url,
            internal.canonical_url(v_platform, v_external_id))
    on conflict on constraint reels_unique_per_user do nothing
    returning * into v_reel;

    v_created := found;

    if v_created then
      insert into internal.jobs (reel_id) values (v_reel.id);
    else
      select * into v_reel
      from public.reels
      where user_id = p_user_id and platform = v_platform and external_id = v_external_id;

      -- Repartager un reel en échec = réessayer
      if v_reel.status = 'failed' then
        perform internal.requeue_reel(v_reel.id);
        v_reel.status := 'queued';
      end if;
    end if;

    v_results := v_results || jsonb_build_object(
      'id', v_reel.id,
      'created', v_created,
      'status', v_reel.status,
      'title', v_reel.title
    );
  end loop;

  return v_results;
end;
$$;

-- Remet un reel en file (échec, ou régénération après évolution du prompt)
create or replace function internal.requeue_reel(p_reel_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.reels
  set status = 'queued', stage = null, error_code = null, error_message = null
  where id = p_reel_id;

  insert into internal.jobs (reel_id)
  values (p_reel_id)
  on conflict (reel_id) where status in ('queued', 'running') do nothing;
end;
$$;

-- ---------------------------------------------------------------------------
-- RPC publiques
-- ---------------------------------------------------------------------------

-- Ingestion depuis le Raccourci iOS (jeton personnel, sans session)
create or replace function public.ingest_reels(p_token text, p_items jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid;
begin
  if p_token is null or p_token !~ '^rn_[0-9a-f]{64}$' then
    raise exception 'invalid token' using errcode = 'PT401';
  end if;

  update public.ingest_tokens
  set last_used_at = now()
  where token_hash = extensions.digest(p_token, 'sha256')
    and revoked_at is null
  returning user_id into v_user_id;

  if v_user_id is null then
    raise exception 'invalid token' using errcode = 'PT401';
  end if;

  return internal.enqueue_reels(v_user_id, p_items);
end;
$$;

-- Ajout manuel depuis l'app (session utilisateur)
create or replace function public.add_reels(p_items jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  return internal.enqueue_reels((select auth.uid()), p_items);
end;
$$;

-- Réessayer / régénérer un de ses reels
create or replace function public.retry_reel(p_reel_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_status public.reel_status;
begin
  select status into v_status
  from public.reels
  where id = p_reel_id and user_id = (select auth.uid());

  if v_status is null then
    raise exception 'reel not found' using errcode = 'PT404';
  end if;

  if v_status in ('queued', 'processing') then
    return;
  end if;

  perform internal.requeue_reel(p_reel_id);
end;
$$;

-- Crée un jeton d'ingestion ; renvoie le jeton en clair UNE seule fois
create or replace function public.create_ingest_token(p_name text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
  v_token   text;
  v_id      uuid;
  v_active  integer;
begin
  if v_user_id is null then
    raise exception 'not authenticated' using errcode = 'PT401';
  end if;

  if p_name is null or char_length(trim(p_name)) not between 1 and 60 then
    raise exception 'invalid name' using errcode = 'PT400';
  end if;

  select count(*) into v_active
  from public.ingest_tokens
  where user_id = v_user_id and revoked_at is null;

  if v_active >= 10 then
    raise exception 'too many active tokens' using errcode = 'PT400';
  end if;

  v_token := 'rn_' || encode(extensions.gen_random_bytes(32), 'hex');

  insert into public.ingest_tokens (user_id, name, token_prefix, token_hash)
  values (v_user_id, trim(p_name), left(v_token, 10), extensions.digest(v_token, 'sha256'))
  returning id into v_id;

  return jsonb_build_object('id', v_id, 'token', v_token);
end;
$$;

create or replace function public.revoke_ingest_token(p_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.ingest_tokens
  set revoked_at = now()
  where id = p_id and user_id = (select auth.uid()) and revoked_at is null;
end;
$$;

-- Enregistre (ou réattribue) l'abonnement push de l'appareil courant
create or replace function public.register_push_subscription(
  p_endpoint text, p_p256dh text, p_auth text, p_user_agent text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'not authenticated' using errcode = 'PT401';
  end if;

  insert into public.push_subscriptions (user_id, endpoint, p256dh, auth, user_agent)
  values (v_user_id, p_endpoint, p_p256dh, p_auth, left(p_user_agent, 512))
  on conflict (endpoint) do update
  set user_id = excluded.user_id,
      p256dh = excluded.p256dh,
      auth = excluded.auth,
      user_agent = excluded.user_agent;
end;
$$;

-- Recherche (RLS s'applique : SECURITY INVOKER), avec préfixes pour la frappe
create or replace function public.search_reels(p_query text, p_limit integer default 30)
returns setof public.reels
language plpgsql
stable
security invoker
set search_path = ''
as $$
declare
  v_tsquery tsquery;
  v_terms   text;
begin
  select string_agg(quote_literal(term) || ':*', ' & ')
  into v_terms
  from (
    select term
    from regexp_split_to_table(lower(coalesce(p_query, '')), '[^[:alnum:]]+') as term
    where char_length(term) >= 2
    limit 8
  ) t;

  if v_terms is null then
    return;
  end if;

  v_tsquery := to_tsquery('public.french_unaccent', v_terms);

  return query
  select r.*
  from public.reels r
  where r.search @@ v_tsquery
  order by ts_rank_cd(r.search, v_tsquery) desc, r.created_at desc
  limit least(greatest(coalesce(p_limit, 30), 1), 100);
end;
$$;

-- ---------------------------------------------------------------------------
-- Fonctions du worker (non exposées : schéma internal)
-- ---------------------------------------------------------------------------

-- Réclame le prochain job disponible, de façon atomique et concurrente
create or replace function internal.claim_job(p_worker_id text)
returns setof internal.jobs
language sql
set search_path = ''
as $$
  update internal.jobs j
  set status = 'running',
      attempts = j.attempts + 1,
      locked_by = p_worker_id,
      locked_at = now()
  where j.id = (
    select id
    from internal.jobs
    where status = 'queued' and run_after <= now()
    order by run_after, id
    for update skip locked
    limit 1
  )
  returning j.*;
$$;

create or replace function internal.complete_job(p_job_id bigint)
returns void
language sql
set search_path = ''
as $$
  update internal.jobs
  set status = 'succeeded', locked_by = null, locked_at = null, last_error = null
  where id = p_job_id;
$$;

-- Échec : nouvelle tentative avec backoff exponentiel, ou échec définitif.
-- Renvoie true si le job sera réessayé.
create or replace function internal.fail_job(p_job_id bigint, p_error text, p_retryable boolean)
returns boolean
language plpgsql
set search_path = ''
as $$
declare
  v_job   internal.jobs%rowtype;
  v_retry boolean;
begin
  select * into v_job from internal.jobs where id = p_job_id for update;
  v_retry := p_retryable and v_job.attempts < v_job.max_attempts;

  update internal.jobs
  set status = case when v_retry then 'queued'::internal.job_status else 'failed'::internal.job_status end,
      run_after = case when v_retry
                       then now() + make_interval(secs => least(30 * power(4, v_job.attempts - 1), 3600))
                       else run_after end,
      locked_by = null,
      locked_at = null,
      last_error = left(p_error, 2000)
  where id = p_job_id;

  return v_retry;
end;
$$;

-- Récupère les jobs bloqués (worker tué en plein traitement)
create or replace function internal.requeue_stale_jobs(p_timeout interval)
returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  with stale as (
    update internal.jobs
    set status = case when attempts >= max_attempts then 'failed'::internal.job_status else 'queued'::internal.job_status end,
        locked_by = null,
        locked_at = null,
        last_error = 'stale: worker did not finish in time'
    where status = 'running' and locked_at < now() - p_timeout
    returning reel_id, status
  ),
  reels_updated as (
    update public.reels r
    set status = case when s.status = 'failed' then 'failed'::public.reel_status else 'queued'::public.reel_status end,
        stage = null,
        error_code = case when s.status = 'failed' then 'stale' end,
        error_message = case when s.status = 'failed'
                             then 'Le traitement a été interrompu plusieurs fois. Tu peux réessayer.' end
    from stale s
    where r.id = s.reel_id
    returning r.id
  )
  select count(*) into v_count from stale;

  return v_count;
end;
$$;

-- ---------------------------------------------------------------------------
-- Droits d'exécution (tout est fermé par défaut, puis ouvert au strict besoin)
-- ---------------------------------------------------------------------------
revoke execute on all functions in schema internal from public, anon, authenticated;

revoke execute on function public.ingest_reels(text, jsonb)                          from public, anon, authenticated;
revoke execute on function public.add_reels(jsonb)                                   from public, anon, authenticated;
revoke execute on function public.retry_reel(uuid)                                   from public, anon, authenticated;
revoke execute on function public.create_ingest_token(text)                          from public, anon, authenticated;
revoke execute on function public.revoke_ingest_token(uuid)                          from public, anon, authenticated;
revoke execute on function public.register_push_subscription(text, text, text, text) from public, anon, authenticated;
revoke execute on function public.search_reels(text, integer)                        from public, anon, authenticated;

grant execute on function public.ingest_reels(text, jsonb)                          to anon, authenticated;
grant execute on function public.add_reels(jsonb)                                   to authenticated;
grant execute on function public.retry_reel(uuid)                                   to authenticated;
grant execute on function public.create_ingest_token(text)                          to authenticated;
grant execute on function public.revoke_ingest_token(uuid)                          to authenticated;
grant execute on function public.register_push_subscription(text, text, text, text) to authenticated;
grant execute on function public.search_reels(text, integer)                        to authenticated;

-- Les fonctions de déclencheurs et utilitaires internes appelées depuis les
-- fonctions SECURITY DEFINER s'exécutent avec les droits du propriétaire.

-- =============================================================================
-- Realtime : l'app voit le statut d'un reel évoluer en direct (RLS respectée)
-- =============================================================================
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.reels;
  end if;
end;
$$;
