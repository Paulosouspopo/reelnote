"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { KINDS } from "@/lib/card";
import { formatDuration, timeAgo, waitingMessage } from "@/lib/format";
import { getSupabase } from "@/lib/supabase/client";
import { STAGE_LABELS, USER_STATUS_LABELS, type Reel, type UserStatus } from "@/lib/types";
import { useSheet } from "@/lib/useSheet";

import { KindSection } from "./KindSection";

const STATUS_BUTTONS: { status: UserStatus; label: string }[] = [
  { status: "inbox", label: "Nouveau" },
  { status: "todo", label: USER_STATUS_LABELS.todo },
  { status: "done", label: "Fait" },
  { status: "archived", label: "Archivé" },
];

export function ReelDetail({ reel: initial, thumbnailUrl }: { reel: Reel; thumbnailUrl: string | null }) {
  const router = useRouter();
  const supabase = getSupabase();
  const [reel, setReel] = useState(initial);
  const [note, setNote] = useState(initial.note ?? "");
  const [saveError, setSaveError] = useState<string | null>(null);
  const menu = useRef<HTMLDialogElement>(null);
  useSheet(menu);
  const card = reel.card;
  const kind = reel.kind ?? undefined;
  const ready = reel.status === "ready" && card !== null;

  // Fiche en préparation : on suit son avancement en direct
  useEffect(() => {
    if (reel.status === "ready") return;
    const channel = supabase
      .channel(`reel:${reel.id}`)
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "reels", filter: `id=eq.${reel.id}` },
        (p) => {
          const next = p.new as Reel;
          if (next.status === "ready") router.refresh();
          else setReel((current) => ({ ...current, ...next }));
        },
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [supabase, router, reel.id, reel.status]);

  async function update(fields: Partial<Pick<Reel, "user_status" | "is_favorite" | "note">>) {
    const previous = reel;
    setReel({ ...reel, ...fields }); // optimiste
    setSaveError(null);
    const { error } = await supabase.from("reels").update(fields).eq("id", reel.id);
    if (error) {
      setReel(previous);
      setSaveError("Modification non enregistrée. Vérifie ta connexion.");
    }
  }

  async function retry() {
    menu.current?.close();
    const { error } = await supabase.rpc("retry_reel", { p_reel_id: reel.id });
    if (!error) setReel({ ...reel, status: "queued", stage: null, error_message: null });
  }

  async function remove() {
    if (!window.confirm("Supprimer cette fiche ? Cette action est définitive.")) return;
    const { error } = await supabase.from("reels").delete().eq("id", reel.id);
    if (error) {
      setSaveError("Suppression impossible. Réessaie.");
      return;
    }
    router.replace("/");
    router.refresh();
  }

  async function share() {
    menu.current?.close();
    const text = [reel.title, reel.tldr, reel.canonical_url].filter(Boolean).join("\n\n");
    if (navigator.share) await navigator.share({ title: reel.title ?? "Reelnote", text }).catch(() => undefined);
    else await navigator.clipboard.writeText(text);
  }

  const sourceLabel = reel.platform === "instagram" ? "Voir sur Instagram" : "Voir sur YouTube";

  return (
    <main className="page" data-kind={kind}>
      <div className="topbar">
        <Link href="/" className="topbar__back">
          ‹ Fiches
        </Link>
        <div>
          {ready && (
            <button
              type="button"
              className="icon-button"
              aria-pressed={reel.is_favorite}
              aria-label={reel.is_favorite ? "Retirer des favoris" : "Ajouter aux favoris"}
              onClick={() => update({ is_favorite: !reel.is_favorite })}
              style={{ color: reel.is_favorite ? "var(--k-product)" : "var(--ink-3)" }}
            >
              {reel.is_favorite ? "★" : "☆"}
            </button>
          )}
          <button
            type="button"
            className="icon-button"
            aria-label="Plus d'actions"
            onClick={() => menu.current?.showModal()}
          >
            ⋯
          </button>
        </div>
      </div>

      {!ready || !card ? (
        <Pending reel={reel} onRetry={retry} />
      ) : (
        <>
          <header className="hero">
            <div className="hero__top">
              <div>
                {kind && (
                  <span className="kind-tab">
                    {KINDS[kind].emoji} {KINDS[kind].label}
                  </span>
                )}
                <div className="hero__emoji" style={{ marginTop: 14 }} aria-hidden="true">
                  {card.emoji}
                </div>
              </div>
              {thumbnailUrl && <img className="hero__thumb" src={thumbnailUrl} alt="" />}
            </div>
            <h1 className="hero__title">{card.title}</h1>
            <div className="hero__meta">
              {reel.author_handle && <span>@{reel.author_handle}</span>}
              {formatDuration(reel.duration_s) && <span>{formatDuration(reel.duration_s)}</span>}
              <span suppressHydrationWarning>Ajouté {timeAgo(reel.created_at)}</span>
            </div>
          </header>

          <p className="lede">{card.tldr}</p>

          {card.caution && (
            <aside className="callout callout--caution">
              <span className="callout__icon" aria-hidden="true">
                ⚠️
              </span>
              <div>
                <p className="callout__title">À vérifier</p>
                <p>{card.caution}</p>
              </div>
            </aside>
          )}

          {card.action && (
            <aside className="callout">
              <span className="callout__icon" aria-hidden="true">
                🎯
              </span>
              <div>
                <p className="callout__title">À essayer</p>
                <p>{card.action}</p>
                {reel.user_status === "inbox" && (
                  <button
                    type="button"
                    className="button button--quiet"
                    style={{ marginTop: 10, minHeight: 40 }}
                    onClick={() => update({ user_status: "todo" })}
                  >
                    Garder dans « À tester »
                  </button>
                )}
              </div>
            </aside>
          )}

          <h2 className="section-title">À retenir</h2>
          <ul className="points">
            {card.key_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>

          <KindSection reelId={reel.id} details={card.details} />

          <h2 className="section-title">Ma note</h2>
          <textarea
            className="field"
            placeholder="Ce que tu veux retenir, adapter, tester…"
            value={note}
            maxLength={5000}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => note !== (reel.note ?? "") && update({ note: note || null })}
          />

          {reel.tags.length > 0 && (
            <ul className="tags" aria-label="Mots-clés">
              {reel.tags.map((tag) => (
                <li key={tag}>{tag}</li>
              ))}
            </ul>
          )}

          {reel.transcript && (
            <details className="disclosure" style={{ marginTop: 20 }}>
              <summary>Transcription complète</summary>
              <p>{reel.transcript}</p>
            </details>
          )}
        </>
      )}

      {saveError && (
        <p className="notice notice--error" role="alert" style={{ marginTop: 16 }}>
          {saveError}
        </p>
      )}

      {ready && (
        <nav className="status-bar" aria-label="Statut de la fiche">
          <div className="segmented">
            {STATUS_BUTTONS.map(({ status, label }) => (
              <button
                key={status}
                type="button"
                aria-pressed={reel.user_status === status}
                onClick={() => update({ user_status: status })}
              >
                {label}
              </button>
            ))}
          </div>
        </nav>
      )}

      <dialog ref={menu} className="sheet" aria-label="Actions">
        <div className="menu">
          <a href={reel.canonical_url} target="_blank" rel="noopener noreferrer">
            ↗ {sourceLabel}
          </a>
          {ready && (
            <button type="button" onClick={share}>
              ⤴ Partager la fiche
            </button>
          )}
          {(ready || reel.status === "failed") && (
            <button type="button" onClick={retry}>
              ↻ {ready ? "Régénérer la fiche" : "Réessayer"}
            </button>
          )}
          <button type="button" className="danger" onClick={remove}>
            Supprimer
          </button>
          <button type="button" onClick={() => menu.current?.close()}>
            Annuler
          </button>
        </div>
      </dialog>
    </main>
  );
}

function Pending({ reel, onRetry }: { reel: Reel; onRetry: () => void }) {
  if (reel.status === "failed") {
    return (
      <div className="empty">
        <div className="empty__emoji" aria-hidden="true">
          ⚠️
        </div>
        <p>{reel.error_message ?? "La fiche n'a pas pu être créée."}</p>
        <button type="button" className="button" onClick={onRetry}>
          Réessayer
        </button>
      </div>
    );
  }
  return (
    <div className="empty" role="status">
      <div className="empty__emoji" aria-hidden="true">
        ⏳
      </div>
      <p>
        {reel.status === "processing" && reel.stage
          ? `${STAGE_LABELS[reel.stage]}…`
          : (reel.error_message ?? waitingMessage(reel.created_at))}
      </p>
      <p className="small">Tu peux fermer l&apos;app : une notification te préviendra.</p>
    </div>
  );
}
