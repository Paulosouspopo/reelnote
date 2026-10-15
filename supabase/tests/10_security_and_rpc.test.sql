-- =============================================================================
-- Tests de sécurité (RLS, privilèges) et des RPC.
-- Lancés par supabase/tests/run.sh sur un Postgres jetable.
-- =============================================================================
\set ON_ERROR_STOP 1
\set user_a '''aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'''
\set user_b '''bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'''

begin;

insert into auth.users (id, email) values
  (:user_a, 'a@example.com'),
  (:user_b, 'b@example.com');

-- ---------------------------------------------------------------------------
-- 1. Jeton d'ingestion
-- ---------------------------------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claim.sub', :user_a, true);

select (public.create_ingest_token('iPhone de A')) ->> 'token' as token_a \gset

select set_config('reelnote.test_token', :'token_a', true);
select test_helpers.assert(:'token_a' ~ '^rn_[0-9a-f]{64}$', 'token format');
select test_helpers.assert(
  (select count(*) from public.ingest_tokens) = 1,
  'A voit son jeton'
);
select test_helpers.assert(
  (select token_prefix from public.ingest_tokens limit 1) = left(:'token_a', 10),
  'préfixe affichable'
);

-- Le hash n'est jamais lisible par le client
do $$
begin
  begin
    perform token_hash from public.ingest_tokens;
    raise exception 'ASSERTION FAILED: token_hash should not be readable';
  exception when insufficient_privilege then null;
  end;
end;
$$;

-- ---------------------------------------------------------------------------
-- 2. Ingestion via le Raccourci (rôle anon + jeton)
-- ---------------------------------------------------------------------------
reset role;
set local role anon;
select set_config('request.jwt.claim.sub', '', true);

select public.ingest_reels(:'token_a',
  '[{"platform":"instagram","external_id":"C1abcDEF","source_url":"https://www.instagram.com/reel/C1abcDEF/?igsh=xyz"}]'::jsonb
) as res \gset
select test_helpers.assert((:'res'::jsonb -> 0 ->> 'created')::boolean, 'reel créé');
select test_helpers.assert((:'res'::jsonb -> 0 ->> 'status') = 'queued', 'statut queued');
select :'res'::jsonb -> 0 ->> 'id' as reel_id \gset

-- Doublon : pas de second reel
select public.ingest_reels(:'token_a',
  '[{"platform":"instagram","external_id":"C1abcDEF","source_url":"https://www.instagram.com/reel/C1abcDEF/"}]'::jsonb
) as res2 \gset
select test_helpers.assert(not (:'res2'::jsonb -> 0 ->> 'created')::boolean, 'doublon détecté');
select test_helpers.assert((:'res2'::jsonb -> 0 ->> 'id') = :'reel_id', 'même id');

-- Jeton invalide
do $$
begin
  begin
    perform public.ingest_reels('rn_' || repeat('0', 64), '[{"platform":"instagram","external_id":"Cxxxxxx","source_url":"https://x"}]');
    raise exception 'ASSERTION FAILED: invalid token accepted';
  exception when sqlstate 'PT401' then null;
  end;
end;
$$;

-- Entrées invalides : tableau vide, plateforme inconnue, identifiant hostile, URL non https
do $$
declare
  v_token text := current_setting('reelnote.test_token');
  v_bad   jsonb;
begin
  foreach v_bad in array array[
    '[]'::jsonb,
    '[{"platform":"tiktok","external_id":"C1abcDEF","source_url":"https://x"}]'::jsonb,
    '[{"platform":"instagram","external_id":"../../etc","source_url":"https://x"}]'::jsonb,
    '[{"platform":"instagram","external_id":"C1abcDEF","source_url":"javascript:alert(1)"}]'::jsonb
  ] loop
    begin
      perform public.ingest_reels(v_token, v_bad);
      raise exception 'ASSERTION FAILED: invalid input accepted: %', v_bad;
    exception when sqlstate 'PT400' then null;
    end;
  end loop;
end;
$$;

-- anon ne lit rien directement
do $$
begin
  begin
    perform 1 from public.reels;
    raise exception 'ASSERTION FAILED: anon can read reels';
  exception when insufficient_privilege then null;
  end;
end;
$$;

-- ---------------------------------------------------------------------------
-- 3. Un job a été créé, une seule fois
-- ---------------------------------------------------------------------------
reset role;
select test_helpers.assert(
  (select count(*) from internal.jobs where reel_id = :'reel_id') = 1,
  'un seul job pour le reel'
);
select test_helpers.assert(
  (select canonical_url from public.reels where id = :'reel_id') = 'https://www.instagram.com/reel/C1abcDEF/',
  'URL canonique construite côté serveur'
);

-- ---------------------------------------------------------------------------
-- 4. Isolation entre utilisateurs (RLS)
-- ---------------------------------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claim.sub', :user_b, true);
select test_helpers.assert((select count(*) from public.reels) = 0, 'B ne voit pas les reels de A');
select test_helpers.assert((select count(*) from public.ingest_tokens) = 0, 'B ne voit pas les jetons de A');

update public.reels set user_status = 'done' where id = :'reel_id';
delete from public.reels where id = :'reel_id';

reset role;
select test_helpers.assert(
  (select user_status from public.reels where id = :'reel_id') = 'inbox',
  'B ne peut pas modifier le reel de A'
);

-- ---------------------------------------------------------------------------
-- 5. Le propriétaire ne modifie que les colonnes "utilisateur"
-- ---------------------------------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claim.sub', :user_a, true);

update public.reels set user_status = 'todo', is_favorite = true, note = 'à tester ce week-end' where id = :'reel_id';
select test_helpers.assert(
  (select user_status from public.reels where id = :'reel_id') = 'todo',
  'A met à jour son statut'
);

do $$
begin
  begin
    update public.reels set title = 'pirate', status = 'ready';
    raise exception 'ASSERTION FAILED: A can overwrite worker columns';
  exception when insufficient_privilege then null;
  end;
end;
$$;

do $$
begin
  begin
    insert into public.reels (user_id, platform, external_id, source_url, canonical_url)
    values (auth.uid(), 'instagram', 'Czzzzzz', 'https://x', 'https://x');
    raise exception 'ASSERTION FAILED: direct insert allowed';
  exception when insufficient_privilege then null;
  end;
end;
$$;

do $$
begin
  begin
    perform 1 from internal.jobs;
    raise exception 'ASSERTION FAILED: internal schema reachable';
  exception when insufficient_privilege then null;
  end;
end;
$$;

-- ---------------------------------------------------------------------------
-- 6. Cycle de vie d'un job côté worker
-- ---------------------------------------------------------------------------
reset role;

select id as job_id from internal.claim_job('test-worker') \gset
select test_helpers.assert(:'job_id' is not null, 'job réclamé');
select test_helpers.assert(
  (select status from internal.jobs where id = :job_id) = 'running',
  'job en cours'
);
select test_helpers.assert(
  (select count(*) from internal.claim_job('other-worker')) = 0,
  'un job en cours ne peut pas être réclamé deux fois'
);

select test_helpers.assert(internal.fail_job(:job_id, 'boom', true), 'erreur transitoire => retry');
select test_helpers.assert(
  (select status = 'queued' and run_after > now() from internal.jobs where id = :job_id),
  'retry planifié avec backoff'
);
select test_helpers.assert(
  (select count(*) from internal.claim_job('test-worker')) = 0,
  'pas réclamable avant run_after'
);

select test_helpers.assert(not internal.fail_job(:job_id, 'private', false), 'erreur définitive => pas de retry');
select test_helpers.assert(
  (select status from internal.jobs where id = :job_id) = 'failed',
  'job en échec définitif'
);

-- Le worker écrit la fiche ; la recherche plein texte la retrouve sans accents
update public.reels
set status = 'ready', title = 'Le café glacé parfait', tldr = 'Recette rapide de cold brew',
    tags = array['café', 'boisson'], kind = 'recipe'
where id = :'reel_id';

set local role authenticated;
select set_config('request.jwt.claim.sub', :user_a, true);
select test_helpers.assert(
  (select count(*) from public.search_reels('cafe glac')) = 1,
  'recherche par préfixe insensible aux accents'
);
select test_helpers.assert(
  (select count(*) from public.search_reels('pizza')) = 0,
  'recherche sans résultat'
);
select set_config('request.jwt.claim.sub', :user_b, true);
select test_helpers.assert(
  (select count(*) from public.search_reels('cafe')) = 0,
  'la recherche respecte la RLS'
);

-- ---------------------------------------------------------------------------
-- 7. Réessayer / repartager un reel en échec
-- ---------------------------------------------------------------------------
reset role;
update public.reels set status = 'failed', error_code = 'download_failed' where id = :'reel_id';

set local role authenticated;
select set_config('request.jwt.claim.sub', :user_a, true);
select public.retry_reel(:'reel_id');

reset role;
select test_helpers.assert(
  (select status from public.reels where id = :'reel_id') = 'queued',
  'reel remis en file'
);
select test_helpers.assert(
  (select count(*) from internal.jobs where reel_id = :'reel_id' and status = 'queued') = 1,
  'nouveau job créé'
);

-- Job bloqué (worker tué) => récupéré
select id as job2 from internal.claim_job('dying-worker') \gset
update internal.jobs set locked_at = now() - interval '1 hour' where id = :job2;
select test_helpers.assert(internal.requeue_stale_jobs(interval '15 minutes') = 1, 'job bloqué récupéré');
select test_helpers.assert(
  (select status from internal.jobs where id = :job2) = 'queued',
  'job bloqué remis en file'
);
select internal.complete_job(:job2);

-- ---------------------------------------------------------------------------
-- 8. Suppression : la miniature part au nettoyage
-- ---------------------------------------------------------------------------
update public.reels set thumbnail_path = :'user_a' || '/' || :'reel_id' || '.webp' where id = :'reel_id';

set local role authenticated;
select set_config('request.jwt.claim.sub', :user_a, true);
delete from public.reels where id = :'reel_id';

reset role;
select test_helpers.assert(
  (select count(*) from internal.storage_garbage where path like '%' || :'reel_id' || '%') = 1,
  'miniature marquée pour suppression'
);
select test_helpers.assert(
  (select count(*) from internal.jobs where reel_id = :'reel_id') = 0,
  'jobs supprimés en cascade'
);

-- ---------------------------------------------------------------------------
-- 9. Limite de débit
-- ---------------------------------------------------------------------------
set local role anon;
do $$
declare
  i int;
  v_token text := current_setting('reelnote.test_token');
begin
  for i in 1..61 loop  -- la limite est de 60 par heure
    perform public.ingest_reels(v_token, jsonb_build_array(jsonb_build_object(
      'platform', 'instagram',
      'external_id', 'Crate' || lpad(i::text, 4, '0'),
      'source_url', 'https://www.instagram.com/reel/Crate' || i || '/')));
  end loop;
  raise exception 'ASSERTION FAILED: rate limit not enforced';
exception when sqlstate 'PT429' then null;
end;
$$;

reset role;
select 'ALL TESTS PASSED' as result;
rollback;
