/**
 * Reconnaissance des liens de reels dans un texte partagé.
 *
 * Le Raccourci iOS peut envoyer une URL seule, un texte contenant une URL,
 * ou plusieurs liens d'un coup (import des anciens reels) : on extrait tout
 * ce qui ressemble à un reel, on normalise et on déduplique.
 *
 * Le serveur reconstruit lui-même l'URL canonique à partir de
 * (platform, externalId) : ce module ne sert qu'à reconnaître et nettoyer.
 */

export type Platform = "instagram" | "youtube";

export interface ReelLink {
  platform: Platform;
  externalId: string;
  /** URL d'origine nettoyée (sans paramètres de suivi) */
  sourceUrl: string;
}

export const MAX_LINKS_PER_REQUEST = 25;

const URL_PATTERN = /https?:\/\/[^\s<>"'`]+/gi;
const INSTAGRAM_PATH = /^\/(?:[A-Za-z0-9._]+\/)?(?:reels?|p|tv)\/([A-Za-z0-9_-]{5,64})(?:\/|$)/;
const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;

function normalizeHost(host: string): string {
  return host.toLowerCase().replace(/^(www\.|m\.)/, "");
}

export function parseReelUrl(raw: string): ReelLink | null {
  let url: URL;
  try {
    // Les textes partagés finissent parfois par une ponctuation collée au lien
    url = new URL(raw.replace(/[).,;!?»]+$/, ""));
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;

  const host = normalizeHost(url.hostname);

  if (host === "instagram.com" || host === "instagr.am") {
    const match = INSTAGRAM_PATH.exec(url.pathname);
    if (!match?.[1]) return null;
    const externalId = match[1];
    return {
      platform: "instagram",
      externalId,
      sourceUrl: `https://www.instagram.com${url.pathname.replace(/\/?$/, "/")}`,
    };
  }

  if (host === "youtube.com" || host === "youtu.be") {
    let id: string | null = null;
    if (host === "youtu.be") {
      id = url.pathname.slice(1).split("/")[0] ?? null;
    } else if (url.pathname.startsWith("/shorts/")) {
      id = url.pathname.split("/")[2] ?? null;
    } else if (url.pathname === "/watch") {
      id = url.searchParams.get("v");
    }
    if (!id || !YOUTUBE_ID.test(id)) return null;
    return { platform: "youtube", externalId: id, sourceUrl: `https://www.youtube.com/shorts/${id}` };
  }

  return null;
}

export function extractReelLinks(text: string): ReelLink[] {
  const seen = new Set<string>();
  const links: ReelLink[] = [];
  for (const candidate of text.match(URL_PATTERN) ?? []) {
    const link = parseReelUrl(candidate);
    if (!link) continue;
    const key = `${link.platform}:${link.externalId}`;
    if (seen.has(key)) continue;
    seen.add(key);
    links.push(link);
    if (links.length >= MAX_LINKS_PER_REQUEST) break;
  }
  return links;
}

/** Format attendu par les RPC `ingest_reels` et `add_reels`. */
export function toRpcItems(links: ReelLink[]) {
  return links.map((link) => ({
    platform: link.platform,
    external_id: link.externalId,
    source_url: link.sourceUrl,
  }));
}
