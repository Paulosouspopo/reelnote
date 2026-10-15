"use client";

import { useCallback, useEffect, useState } from "react";

import { timeAgo } from "@/lib/format";
import { getSupabase } from "@/lib/supabase/client";
import type { IngestToken } from "@/lib/types";

/**
 * Jetons du Raccourci iOS : un par appareil, révocables.
 * Le jeton en clair n'est affiché qu'une fois, juste après sa création.
 */
async function fetchTokens(supabase: ReturnType<typeof getSupabase>): Promise<IngestToken[]> {
  const { data } = await supabase
    .from("ingest_tokens")
    .select("id, name, token_prefix, created_at, last_used_at, revoked_at")
    .is("revoked_at", null)
    .order("created_at", { ascending: false });
  return (data ?? []) as IngestToken[];
}

export function ShortcutSection({ endpoint }: { endpoint: string }) {
  const supabase = getSupabase();
  const [tokens, setTokens] = useState<IngestToken[]>([]);
  const [fresh, setFresh] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    void fetchTokens(supabase).then(setTokens);
  }, [supabase]);

  useEffect(() => {
    let cancelled = false;
    void fetchTokens(supabase).then((tokens) => {
      if (!cancelled) setTokens(tokens);
    });
    return () => {
      cancelled = true;
    };
  }, [supabase]);

  async function create() {
    setError(null);
    const { data, error } = await supabase.rpc("create_ingest_token", { p_name: "iPhone" });
    if (error) {
      setError("Création impossible (10 jetons actifs maximum).");
      return;
    }
    setFresh((data as { token: string }).token);
    load();
  }

  async function revoke(id: string) {
    if (!window.confirm("Révoquer ce jeton ? Le Raccourci qui l'utilise cessera de fonctionner.")) return;
    await supabase.rpc("revoke_ingest_token", { p_id: id });
    load();
  }

  async function copy(label: string, value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  }

  return (
    <section>
      <h2 className="section-title">Raccourci iPhone</h2>
      <div className="panel stack">
        <p className="small muted" style={{ margin: 0 }}>
          Le Raccourci « Reelnote » apparaît dans le menu Partager d&apos;Instagram et envoie le reel ici.
        </p>

        {fresh ? (
          <div className="stack">
            <p className="small" style={{ margin: 0 }}>
              <strong>Copie ce jeton maintenant</strong>, il ne sera plus affiché.
            </p>
            <div className="secret">{fresh}</div>
            <div className="row">
              <button type="button" className="button" style={{ flex: 1 }} onClick={() => copy("token", fresh)}>
                {copied === "token" ? "Copié ✓" : "Copier le jeton"}
              </button>
              <button type="button" className="button button--quiet" onClick={() => setFresh(null)}>
                Terminé
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="button button--block" onClick={create}>
            Créer un jeton
          </button>
        )}

        {error && <p className="notice notice--error">{error}</p>}

        {tokens.length > 0 && (
          <div>
            {tokens.map((token) => (
              <div key={token.id} className="token">
                <div>
                  <div className="item__name">
                    {token.name} <span className="item__sub">{token.token_prefix}…</span>
                  </div>
                  <div className="item__sub">
                    {token.last_used_at ? `Utilisé ${timeAgo(token.last_used_at)}` : "Jamais utilisé"}
                  </div>
                </div>
                <button type="button" className="button button--danger" onClick={() => revoke(token.id)}>
                  Révoquer
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <h2 className="section-title">Créer le Raccourci</h2>
      <div className="panel stack">
        <ol className="howto">
          <li>Ouvre l&apos;app Raccourcis, touche +, nomme le raccourci « Reelnote ».</li>
          <li>Touche ⓘ puis active « Afficher dans la feuille de partage ». Types acceptés : URL et Texte.</li>
          <li>Ajoute l&apos;action « Obtenir le contenu de l&apos;URL » avec l&apos;adresse ci-dessous.</li>
          <li>
            Méthode POST. En-tête <strong>Authorization</strong> = <strong>Bearer</strong> suivi d&apos;un espace et de
            ton jeton.
          </li>
          <li>Corps de la requête : JSON, champ « url » = Entrée du raccourci.</li>
          <li>Ajoute « Obtenir la valeur du dictionnaire » (clé « message ») puis « Afficher la notification ».</li>
        </ol>
        <div className="secret">{endpoint}</div>
        <button type="button" className="button button--quiet button--block" onClick={() => copy("url", endpoint)}>
          {copied === "url" ? "Copiée ✓" : "Copier l'adresse"}
        </button>
      </div>
    </section>
  );
}
