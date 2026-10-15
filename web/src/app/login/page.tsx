"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { getSupabase } from "@/lib/supabase/client";

/**
 * Connexion par code reçu par e-mail (et non par lien magique) : sur iPhone,
 * l'app installée sur l'écran d'accueil ne partage pas sa session avec Safari,
 * un lien ouvrirait donc la session au mauvais endroit.
 */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"email" | "code">("email");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await getSupabase().auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: true },
    });
    setBusy(false);
    if (error) {
      setError(
        error.status === 429
          ? "Trop de demandes. Attends une minute avant de redemander un code."
          : "Impossible d'envoyer le code. Vérifie l'adresse e-mail.",
      );
      return;
    }
    setStep("code");
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await getSupabase().auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "email" });
    setBusy(false);
    if (error) {
      setError("Code incorrect ou expiré. Vérifie le dernier e-mail reçu.");
      return;
    }
    router.replace("/");
    router.refresh();
  }

  return (
    <main className="login">
      <div className="login__stack" aria-hidden="true">
        <span data-kind="recipe" />
        <span data-kind="place" />
        <span data-kind="learning" />
      </div>
      <h1 className="large-title">Reelnote</h1>
      <p className="muted" style={{ marginTop: -8, marginBottom: 28 }}>
        Partage un reel, récupère une fiche claire. Plus rien ne se perd dans tes enregistrements.
      </p>

      {step === "email" ? (
        <form className="stack" onSubmit={sendCode}>
          <label htmlFor="email" className="visually-hidden">
            Adresse e-mail
          </label>
          <input
            id="email"
            className="field"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="ton@email.com"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="button button--block" disabled={busy || !email}>
            {busy ? "Envoi…" : "Recevoir un code"}
          </button>
        </form>
      ) : (
        <form className="stack" onSubmit={verify}>
          <p className="small muted" style={{ margin: 0 }}>
            Code envoyé à <strong>{email}</strong>.
          </p>
          <label htmlFor="code" className="visually-hidden">
            Code reçu par e-mail
          </label>
          <input
            id="code"
            className="field code-input"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6,10}"
            maxLength={10}
            placeholder="123456"
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          />
          <button className="button button--block" disabled={busy || code.length < 6}>
            {busy ? "Vérification…" : "Se connecter"}
          </button>
          <button type="button" className="button button--quiet button--block" onClick={() => setStep("email")}>
            Changer d&apos;adresse
          </button>
        </form>
      )}

      {error && (
        <p className="notice notice--error" role="alert" style={{ marginTop: 16 }}>
          {error}
        </p>
      )}
    </main>
  );
}
