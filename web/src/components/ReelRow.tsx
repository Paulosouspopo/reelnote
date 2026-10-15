import Link from "next/link";

import { KINDS } from "@/lib/card";
import { timeAgo } from "@/lib/format";
import { STAGE_LABELS, STAGE_ORDER, type ReelListItem } from "@/lib/types";

export function ReelRow({ reel, thumbnailUrl }: { reel: ReelListItem; thumbnailUrl?: string }) {
  const kind = reel.kind ?? undefined;
  const pending = reel.status === "queued" || reel.status === "processing";
  const failed = reel.status === "failed";

  return (
    <li>
      <Link
        href={`/r/${reel.id}`}
        className={`reel-row${failed ? " reel-row--failed" : ""}`}
        data-kind={kind}
        aria-busy={pending || undefined}
      >
        <div className="reel-row__thumb" aria-hidden="true">
          {thumbnailUrl ? (
            <img src={thumbnailUrl} alt="" loading="lazy" decoding="async" />
          ) : (
            <span>{reel.emoji ?? (failed ? "⚠️" : "⏳")}</span>
          )}
        </div>

        <div className="reel-row__body">
          {pending ? (
            <>
              <span className="reel-row__title">Fiche en préparation</span>
              <span className="reel-row__tldr">
                {reel.status === "queued"
                  ? (reel.error_message ?? "En attente du traitement")
                  : `${reel.stage ? STAGE_LABELS[reel.stage] : "Démarrage"}…`}
              </span>
              <Progress stage={reel.status === "processing" ? reel.stage : null} />
            </>
          ) : failed ? (
            <>
              <span className="reel-row__title">Fiche impossible à créer</span>
              <span className="reel-row__tldr">{reel.error_message ?? "Une erreur est survenue."}</span>
            </>
          ) : (
            <>
              <span className="reel-row__title">{reel.title}</span>
              {reel.tldr && <span className="reel-row__tldr">{reel.tldr}</span>}
              <span className="reel-row__meta">
                {kind && (
                  <span className="kind-tab">
                    {KINDS[kind].emoji} {KINDS[kind].label}
                  </span>
                )}
                <span>{timeAgo(reel.created_at)}</span>
                {reel.is_favorite && (
                  <span className="reel-row__star" aria-label="Favori">
                    ★
                  </span>
                )}
              </span>
            </>
          )}
        </div>
      </Link>
    </li>
  );
}

function Progress({ stage }: { stage: ReelListItem["stage"] }) {
  const current = stage ? STAGE_ORDER.indexOf(stage) : -1;
  return (
    <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={5} aria-valuenow={current + 1}>
      {STAGE_ORDER.map((s, i) => (
        <span key={s} data-done={i < current} data-current={i === current} />
      ))}
    </div>
  );
}
