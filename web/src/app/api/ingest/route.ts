/**
 * POST /api/ingest — point d'entrée du Raccourci iOS.
 *
 * Authentification : en-tête `Authorization: Bearer rn_…` (jeton personnel).
 * Corps accepté : JSON {"url": "…"} | {"text": "…"} | {"urls": [...]}, ou texte brut.
 *
 * Cette route ne détient aucun secret : elle reconnaît les liens puis appelle
 * la RPC `ingest_reels` avec la clé publishable. La base vérifie le jeton
 * (hashé), applique la limite de débit et crée les jobs.
 *
 * La réponse contient toujours un `message` lisible, affiché tel quel par le
 * Raccourci dans une notification.
 */
import { createClient } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

import { env } from "@/lib/env";
import { extractReelLinks, toRpcItems } from "@/lib/links";
import type { IngestResultItem } from "@/lib/types";

const MAX_BODY_BYTES = 32 * 1024;
const TOKEN_PATTERN = /^rn_[0-9a-f]{64}$/;

function reply(status: number, message: string, extra: Record<string, unknown> = {}) {
  return NextResponse.json(
    { ok: status < 400, message, ...extra },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

function textFromBody(raw: string): string {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      const { url, text, urls } = parsed as { url?: unknown; text?: unknown; urls?: unknown };
      const parts = [url, text, ...(Array.isArray(urls) ? urls : [])];
      return parts.filter((p): p is string => typeof p === "string").join("\n");
    }
  } catch {
    // Pas du JSON : on traite le corps comme du texte brut.
  }
  return raw;
}

function summarize(items: IngestResultItem[]): string {
  const added = items.filter((i) => i.created).length;
  const known = items.filter((i) => !i.created);
  if (items.length === 1 && added === 1) return "Ajouté ✓ Ta fiche sera prête dans une minute environ.";
  if (items.length === 1 && known[0]) {
    return known[0].title ? `Déjà dans ta liste : ${known[0].title}` : "Déjà dans ta liste, traitement en cours.";
  }
  const parts = [];
  if (added) parts.push(`${added} reel${added > 1 ? "s" : ""} ajouté${added > 1 ? "s" : ""}`);
  if (known.length) parts.push(`${known.length} déjà dans ta liste`);
  return `${parts.join(", ")} ✓`;
}

export async function POST(request: NextRequest) {
  const header = request.headers.get("authorization") ?? "";
  const token = header.replace(/^Bearer\s+/i, "").trim();
  if (!TOKEN_PATTERN.test(token)) {
    return reply(401, "Jeton manquant ou mal copié. Vérifie le Raccourci (Réglages de l'app).");
  }

  const length = Number(request.headers.get("content-length") ?? 0);
  if (length > MAX_BODY_BYTES) return reply(413, "Requête trop volumineuse.");
  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return reply(413, "Requête trop volumineuse.");

  const links = extractReelLinks(textFromBody(raw));
  if (links.length === 0) {
    return reply(422, "Aucun lien de reel reconnu. Partage depuis Instagram ou YouTube Shorts.");
  }

  const supabase = createClient(env.supabaseUrl, env.supabaseKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error, status } = await supabase.rpc("ingest_reels", { p_token: token, p_items: toRpcItems(links) });

  if (error) {
    // Les erreurs SQL « PTxyz » sont traduites par PostgREST en statut HTTP xyz
    const code = error.code?.startsWith("PT") ? Number(error.code.slice(2)) : status;
    switch (code) {
      case 401:
        return reply(401, "Jeton invalide ou révoqué. Crée-en un nouveau dans les Réglages de l'app.");
      case 429:
        return reply(429, "Beaucoup de reels en peu de temps : réessaie dans une heure.");
      case 400:
        return reply(422, "Lien non pris en charge.");
      default:
        console.error("ingest_reels failed", { code: error.code, message: error.message });
        return reply(502, "Service momentanément indisponible, réessaie dans un instant.");
    }
  }

  const items = (data ?? []) as IngestResultItem[];
  return reply(202, summarize(items), { items });
}
