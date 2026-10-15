import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";

import { AccountSection } from "@/components/settings/AccountSection";
import { PushSection } from "@/components/settings/PushSection";
import { ShortcutSection } from "@/components/settings/ShortcutSection";

export const metadata: Metadata = { title: "Réglages" };

export default async function SettingsPage() {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const protocol = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const endpoint = `${protocol}://${host}/api/ingest`;

  return (
    <main className="page">
      <div className="topbar">
        <Link href="/" className="topbar__back">
          ‹ Fiches
        </Link>
      </div>
      <h1 className="large-title">Réglages</h1>
      <ShortcutSection endpoint={endpoint} />
      <PushSection />
      <AccountSection />
    </main>
  );
}
