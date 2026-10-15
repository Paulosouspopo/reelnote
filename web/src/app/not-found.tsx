import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page">
      <div className="empty">
        <div className="empty__emoji" aria-hidden="true">
          🗂️
        </div>
        <p>Cette fiche n&apos;existe pas ou a été supprimée.</p>
        <Link href="/" className="button">
          Retour aux fiches
        </Link>
      </div>
    </main>
  );
}
