-- =============================================================================
-- Stockage des miniatures
-- Bucket privé ; chemin = {user_id}/{reel_id}.webp
-- Le worker écrit avec la clé secrète ; l'app lit via des URLs signées.
-- =============================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('thumbnails', 'thumbnails', false, 1048576, array['image/webp', 'image/jpeg'])
on conflict (id) do nothing;

create policy thumbnails_read_own
  on storage.objects
  for select
  to authenticated
  using (
    bucket_id = 'thumbnails'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
