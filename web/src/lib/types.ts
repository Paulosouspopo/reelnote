/**
 * Types des lignes de la base utilisées par l'app.
 *
 * Après la mise en place, on pourra générer les types complets avec :
 *   npx supabase gen types typescript --project-id <id> > src/lib/database.types.ts
 * et typer les clients Supabase avec.
 */
import type { CardKind, ReelCard } from "./card";
import type { Platform } from "./links";

export type ReelStatus = "queued" | "processing" | "ready" | "failed";
export type ReelStage = "downloading" | "extracting" | "transcribing" | "analyzing" | "finalizing";
export type UserStatus = "inbox" | "todo" | "done" | "archived";

export interface Reel {
  id: string;
  user_id: string;
  platform: Platform;
  external_id: string;
  source_url: string;
  canonical_url: string;
  status: ReelStatus;
  stage: ReelStage | null;
  error_code: string | null;
  error_message: string | null;
  author_handle: string | null;
  author_name: string | null;
  caption: string | null;
  duration_s: number | null;
  posted_at: string | null;
  thumbnail_path: string | null;
  transcript: string | null;
  kind: CardKind | null;
  title: string | null;
  emoji: string | null;
  tldr: string | null;
  key_points: string[];
  tags: string[];
  card: ReelCard | null;
  caution: string | null;
  user_status: UserStatus;
  is_favorite: boolean;
  note: string | null;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Colonnes chargées dans la liste (sans la transcription ni la fiche complète). */
export const REEL_LIST_COLUMNS =
  "id, user_id, platform, external_id, source_url, canonical_url, status, stage, error_code, error_message, " +
  "author_handle, author_name, thumbnail_path, kind, title, emoji, tldr, tags, user_status, is_favorite, " +
  "created_at, updated_at";

export type ReelListItem = Pick<
  Reel,
  | "id"
  | "user_id"
  | "platform"
  | "external_id"
  | "source_url"
  | "canonical_url"
  | "status"
  | "stage"
  | "error_code"
  | "error_message"
  | "author_handle"
  | "author_name"
  | "thumbnail_path"
  | "kind"
  | "title"
  | "emoji"
  | "tldr"
  | "tags"
  | "user_status"
  | "is_favorite"
  | "created_at"
  | "updated_at"
>;

export interface IngestToken {
  id: string;
  name: string;
  token_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface IngestResultItem {
  id: string;
  created: boolean;
  status: ReelStatus;
  title: string | null;
}

export const USER_STATUS_LABELS: Record<UserStatus, string> = {
  inbox: "Nouveaux",
  todo: "À tester",
  done: "Faits",
  archived: "Archivés",
};

export const STAGE_LABELS: Record<ReelStage, string> = {
  downloading: "Téléchargement",
  extracting: "Lecture de la vidéo",
  transcribing: "Transcription",
  analyzing: "Rédaction de la fiche",
  finalizing: "Finalisation",
};

export const STAGE_ORDER: ReelStage[] = ["downloading", "extracting", "transcribing", "analyzing", "finalizing"];
