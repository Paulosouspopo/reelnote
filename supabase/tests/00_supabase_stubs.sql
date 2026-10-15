-- =============================================================================
-- Simule le strict nécessaire de l'environnement Supabase sur un Postgres
-- standard (rôles, auth.uid(), schémas extensions/storage, publication realtime)
-- pour tester les migrations en CI sans lancer toute la stack Supabase.
-- NE PAS appliquer sur un vrai projet Supabase.
-- =============================================================================
\set ON_ERROR_STOP 1

create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;

create schema auth;
create table auth.users (
  id    uuid primary key default gen_random_uuid(),
  email text
);
create function auth.uid() returns uuid
language sql stable
as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;

create schema extensions;
grant usage on schema extensions to anon, authenticated;

create schema storage;
create table storage.buckets (
  id                 text primary key,
  name               text not null,
  public             boolean default false,
  file_size_limit    bigint,
  allowed_mime_types text[]
);
create table storage.objects (
  id        uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets (id),
  name      text not null
);
alter table storage.objects enable row level security;
create function storage.foldername(name text) returns text[]
language sql immutable
as $$
  select (string_to_array(name, '/'))[1:greatest(array_length(string_to_array(name, '/'), 1) - 1, 0)]
$$;
grant usage on schema storage to anon, authenticated;
grant select on storage.objects to authenticated;

create publication supabase_realtime;

-- Petit utilitaire d'assertion pour les tests
create schema test_helpers;
grant usage on schema test_helpers to public;
create function test_helpers.assert(p_condition boolean, p_message text) returns void
language plpgsql
as $$
begin
  if p_condition is distinct from true then
    raise exception 'ASSERTION FAILED: %', p_message;
  end if;
end;
$$;
grant execute on function test_helpers.assert(boolean, text) to public;
