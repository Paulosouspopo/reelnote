"use client";

import { useRef, useState, type FormEvent } from "react";

import { extractReelLinks, toRpcItems } from "@/lib/links";
import { getSupabase } from "@/lib/supabase/client";
import type { IngestResultItem } from "@/lib/types";

/** Ajout manuel d'un ou plusieurs liens (utile sans le Raccourci, ou pour importer d'anciens reels). */
export function AddLinkSheet() {
  const dialog = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const found = extractReelLinks(text).length;

  function open() {
    setMessage(null);
    dialog.current?.showModal();
  }

  async function paste() {
    try {
      setText(await navigator.clipboard.readText());
    } catch {
      setMessage({ text: "Accès au presse-papiers refusé : colle le lien dans le champ.", error: true });
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const links = extractReelLinks(text);
    if (links.length === 0) {
      setMessage({ text: "Aucun lien Instagram ou YouTube Shorts reconnu.", error: true });
      return;
    }
    setBusy(true);
    const { data, error } = await getSupabase().rpc("add_reels", { p_items: toRpcItems(links) });
    setBusy(false);
    if (error) {
      setMessage({
        text:
          error.code === "PT429"
            ? "Beaucoup d'ajouts en une heure : réessaie plus tard."
            : "L'ajout a échoué. Réessaie.",
        error: true,
      });
      return;
    }
    const items = (data ?? []) as IngestResultItem[];
    const added = items.filter((i) => i.created).length;
    setText("");
    setMessage({
      text: added
        ? `${added} reel${added > 1 ? "s" : ""} ajouté${added > 1 ? "s" : ""}. Les fiches arrivent dans une minute.`
        : "Déjà dans ta liste.",
    });
  }

  return (
    <>
      <button type="button" className="fab" onClick={open} aria-label="Ajouter un reel">
        +
      </button>
      <dialog ref={dialog} className="sheet" aria-labelledby="add-title" onClose={() => setMessage(null)}>
        <form className="stack" onSubmit={submit}>
          <h2 id="add-title" className="sheet__title">
            Ajouter un reel
          </h2>
          <p className="small muted" style={{ margin: 0 }}>
            Colle un lien, ou plusieurs d&apos;un coup pour importer tes anciens reels.
          </p>
          <textarea
            className="field"
            placeholder="https://www.instagram.com/reel/…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-label="Liens de reels"
          />
          <div className="row">
            <button type="button" className="button button--quiet" onClick={paste}>
              Coller
            </button>
            <button className="button" style={{ flex: 1 }} disabled={busy || found === 0}>
              {busy ? "Ajout…" : found > 1 ? `Ajouter ${found} reels` : "Ajouter"}
            </button>
          </div>
          {message && (
            <p className={`notice${message.error ? " notice--error" : ""}`} role="status">
              {message.text}
            </p>
          )}
          <button type="button" className="button button--quiet button--block" onClick={() => dialog.current?.close()}>
            Fermer
          </button>
        </form>
      </dialog>
    </>
  );
}
