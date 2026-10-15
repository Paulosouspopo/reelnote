"use client";

import { useEffect, useState } from "react";

import { disablePush, enablePush, getPushState, type PushState } from "@/lib/push";

const DESCRIPTIONS: Record<PushState, string> = {
  unsupported: "Ce navigateur ne gère pas les notifications.",
  "needs-install":
    "Sur iPhone, ajoute d'abord Reelnote à l'écran d'accueil (Safari, bouton Partager, « Sur l'écran d'accueil »), puis ouvre-la depuis l'icône.",
  "not-configured": "Les notifications ne sont pas configurées sur ce serveur (clé VAPID absente).",
  denied: "Notifications refusées. Réactive-les dans Réglages iOS, Notifications, Reelnote.",
  enabled: "Tu reçois une notification dès qu'une fiche est prête.",
  disabled: "Reçois une notification dès qu'une fiche est prête.",
};

export function PushSection() {
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPushState()
      .then(setState)
      .catch(() => setState("unsupported"));
  }, []);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      setState(state === "enabled" ? await disablePush() : await enablePush());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Une erreur est survenue.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2 className="section-title">Notifications</h2>
      <div className="panel stack">
        <p className="small muted" style={{ margin: 0 }}>
          {state ? DESCRIPTIONS[state] : "Vérification…"}
        </p>
        {(state === "enabled" || state === "disabled") && (
          <button
            type="button"
            className={`button button--block${state === "enabled" ? " button--quiet" : ""}`}
            disabled={busy}
            onClick={toggle}
          >
            {state === "enabled" ? "Désactiver sur cet appareil" : "Activer les notifications"}
          </button>
        )}
        {error && <p className="notice notice--error">{error}</p>}
      </div>
    </section>
  );
}
