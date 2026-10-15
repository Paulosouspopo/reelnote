"use client";

import { useEffect, useReducer } from "react";

import { getSupabase } from "./supabase/client";

const TTL_SECONDS = 60 * 60;
const cache = new Map<string, { url: string; expires: number }>();

function isFresh(path: string, now: number) {
  return (cache.get(path)?.expires ?? 0) > now + 60_000;
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
    const now = Date.now();
    const missing = (key ? key.split("|") : []).filter((p) => !isFresh(p, now));
    if (missing.length === 0) return;

    getSupabase()
      .storage.from("thumbnails")
      .createSignedUrls(missing, TTL_SECONDS)
      .then(({ data }) => {
        for (const item of data ?? []) {
          if (item.path && item.signedUrl) {
            cache.set(item.path, { url: item.signedUrl, expires: now + TTL_SECONDS * 1000 });
          }
        }
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
