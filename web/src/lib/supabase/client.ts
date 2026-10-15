"use client";

import { createBrowserClient } from "@supabase/ssr";

import { env } from "../env";

let client: ReturnType<typeof createBrowserClient> | undefined;

/** Client navigateur : clé publishable + session de l'utilisateur. La RLS fait le reste. */
export function getSupabase() {
  client ??= createBrowserClient(env.supabaseUrl, env.supabaseKey);
  return client;
}
