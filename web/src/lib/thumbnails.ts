"use client";

import { useEffect, useReducer } from "react";

import { getSupabase } from "./supabase/client";

const TTL_SECONDS = 60 * 60;
const cache = new Map<string, { url: string; expires: number }>();

/** Chemins sans URL signée encore valable au moins une minute. */
function staleOf(paths: string[]): string[] {
  const limit = Date.now() + 60_000;
  return paths.filter((p) => (cache.get(p)?.expires ?? 0) <= limit);
}

function remember(items: { path: string | null; signedUrl: string | null }[]) {
  const expires = Date.now() + TTL_SECONDS * 1000;
  for (const item of items) {
    if (item.path && item.signedUrl) cache.set(item.path, { url: item.signedUrl, expires });
  }
}

/**
 * URLs signées des miniatures (bucket privé), demandées par lots et mises en
 * cache en mémoire pour la durée de validité de la signature.
 */
export function useThumbnails(paths: (string | null)[]): Record<string, string> {
  const [, refresh] = useReducer((n: number) => n + 1, 0);
  const wanted = [...new Set(paths.filter((p): p is string => Boolean(p)))].sort();
  const key = wanted.join("|");

  useEffect(() => {
    let cancelled = false;
    const missing = staleOf(key ? key.split("|") : []);
    if (missing.length === 0) return;

    getSupabase()
      .storage.from("thumbnails")
      .createSignedUrls(missing, TTL_SECONDS)
      .then(({ data }) => {
        remember(data ?? []);
        if (!cancelled) refresh();
      });

    return () => {
      cancelled = true;
    };
  }, [key]);

  const urls: Record<string, string> = {};
  for (const path of wanted) {
    const hit = cache.get(path);
    if (hit) urls[path] = hit.url;
  }
  return urls;
}
