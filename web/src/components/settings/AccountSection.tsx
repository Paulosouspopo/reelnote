"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getSupabase } from "@/lib/supabase/client";

export function AccountSection() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    getSupabase()
      .auth.getUser()
      .then(({ data }) => setEmail(data.user?.email ?? null));
  }, []);

  async function signOut() {
    await getSupabase().auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <section>
      <h2 className="section-title">Compte</h2>
      <div className="panel stack">
        {email && (
          <p className="small muted" style={{ margin: 0 }}>
            Connecté avec {email}
          </p>
        )}
        <button type="button" className="button button--quiet button--block" onClick={signOut}>
          Se déconnecter
        </button>
      </div>
    </section>
  );
}
