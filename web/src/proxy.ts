import type { NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/proxy";

export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Tout sauf : l'API d'ingestion (authentifiée par jeton), le service worker,
     * le manifeste, les icônes et les fichiers statiques de Next.js.
     */
    "/((?!api/ingest|_next/static|_next/image|sw\\.js|manifest\\.webmanifest|icons/|offline\\.html|favicon\\.ico).*)",
  ],
};
