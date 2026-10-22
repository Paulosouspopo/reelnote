const relative = new Intl.RelativeTimeFormat("fr", { numeric: "auto" });
const dateFormat = new Intl.DateTimeFormat("fr", { day: "numeric", month: "short", year: "numeric" });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

/** « il y a 3 jours », « hier », « à l'instant » */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = (new Date(iso).getTime() - now.getTime()) / 1000;
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "à l'instant";
}

/** Au-delà de quelques minutes en file, le worker est sûrement arrêté (PC éteint). */
export function waitingMessage(createdAt: string, now: Date = new Date()): string {
  const minutes = (now.getTime() - new Date(createdAt).getTime()) / 60_000;
  return minutes < 5
    ? "En attente du traitement…"
    : "Toujours en attente : l'ordinateur qui crée les fiches est sans doute éteint. Elle sera prête à son réveil.";
}

export function formatDate(iso: string): string {
  return dateFormat.format(new Date(iso));
}

export function formatMinutes(minutes: number | null | undefined): string | null {
  if (!minutes) return null;
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m}` : `${h} h`;
}

export function formatDuration(seconds: number | null | undefined): string | null {
  if (!seconds) return null;
  const s = Math.round(seconds);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")}`;
}

/** Retire les valeurs vides d'une liste, avec le bon type. */
export function compact<T>(values: (T | null | undefined | false | "")[]): T[] {
  return values.filter((v): v is T => Boolean(v));
}
