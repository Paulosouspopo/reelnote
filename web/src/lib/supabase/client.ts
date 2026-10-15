"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { env } from "../env";

// Type explicite : `ReturnType<typeof createBrowserClient>` se résout en `any` (fonction surchargée et générique).
let client: SupabaseClient | undefined;

/** Client navigateur : clé publishable + session de l'utilisateur. La RLS fait le reste. */
export function getSupabase(): SupabaseClient {
  client ??= createBrowserClient(env.supabaseUrl, env.supabaseKey);
  return client;
}
