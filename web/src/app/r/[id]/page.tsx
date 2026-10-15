import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cache } from "react";

import { ReelDetail } from "@/components/ReelDetail";
import { createClient } from "@/lib/supabase/server";
import type { Reel } from "@/lib/types";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type Params = { params: Promise<{ id: string }> };

// cache : une seule requête pour generateMetadata et la page
const loadReel = cache(async (id: string) => {
  if (!UUID.test(id)) return null;
  const supabase = await createClient();
  // La RLS garantit qu'on ne lit que ses propres reels
  const { data } = await supabase.from("reels").select("*").eq("id", id).maybeSingle();
  if (!data) return null;
  const reel = data as Reel;
  let thumbnailUrl: string | null = null;
  if (reel.thumbnail_path) {
    const { data: signed } = await supabase.storage.from("thumbnails").createSignedUrl(reel.thumbnail_path, 3600);
    thumbnailUrl = signed?.signedUrl ?? null;
  }
  return { reel, thumbnailUrl };
});

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const result = await loadReel(id);
  return { title: result?.reel.title ?? "Fiche" };
}

export default async function ReelPage({ params }: Params) {
  const { id } = await params;
  const result = await loadReel(id);
  if (!result) notFound();
  // key : après un rafraîchissement (fiche prête), le composant repart des données serveur
  return <ReelDetail key={result.reel.updated_at} reel={result.reel} thumbnailUrl={result.thumbnailUrl} />;
}
