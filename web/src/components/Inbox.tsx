"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { KIND_ORDER, KINDS, type CardKind } from "@/lib/card";
import { getSupabase } from "@/lib/supabase/client";
import { useThumbnails } from "@/lib/thumbnails";
import { REEL_LIST_COLUMNS, USER_STATUS_LABELS, type ReelListItem, type UserStatus } from "@/lib/types";

import { AddLinkSheet } from "./AddLinkSheet";
import { ReelRow } from "./ReelRow";

const PAGE_SIZE = 40;
const TABS: UserStatus[] = ["inbox", "todo", "done", "archived"];
const EMPTY_STATES: Record<UserStatus, { emoji: string; text: string }> = {
  inbox: { emoji: "📥", text: "Rien de nouveau. Partage un reel depuis Instagram avec le Raccourci Reelnote." },
  todo: { emoji: "🎯", text: "Aucune fiche à tester. Garde ici ce que tu veux vraiment essayer." },
  done: { emoji: "✅", text: "Les fiches que tu as testées arriveront ici." },
  archived: { emoji: "🗄️", text: "Aucune fiche archivée." },
};

async function fetchCounts(supabase: ReturnType<typeof getSupabase>): Promise<Partial<Record<UserStatus, number>>> {
  const results = await Promise.all(
    (["inbox", "todo"] as const).map((status) =>
      supabase.from("reels").select("id", { count: "exact", head: true }).eq("user_status", status),
    ),
  );
  return { inbox: results[0]?.count ?? 0, todo: results[1]?.count ?? 0 };
}

export function Inbox({ userId }: { userId: string }) {
  const supabase = getSupabase();
  const [tab, setTab] = useState<UserStatus>("inbox");
  const [kind, setKind] = useState<CardKind | "all">("all");
  const [query, setQuery] = useState("");
  const [reels, setReels] = useState<ReelListItem[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [counts, setCounts] = useState<Partial<Record<UserStatus, number>>>({});
  const searching = query.trim().length >= 2;

  // --- chargement -------------------------------------------------------------
  const fetchPage = useCallback(
    async (before?: string) => {
      let request = supabase
        .from("reels")
        .select(REEL_LIST_COLUMNS)
        .eq("user_status", tab)
        .order("created_at", { ascending: false })
        .limit(PAGE_SIZE);
      if (kind !== "all") request = request.eq("kind", kind);
      if (before) request = request.lt("created_at", before);
      const { data } = await request;
      return (data ?? []) as unknown as ReelListItem[];
    },
    [supabase, tab, kind],
  );

  const refreshCounts = useCallback(() => {
    void fetchCounts(supabase).then(setCounts);
  }, [supabase]);

  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(
      async () => {
        setLoading(true);
        let rows: ReelListItem[];
        if (searching) {
          const { data } = await supabase.rpc("search_reels", { p_query: query, p_limit: 50 });
          rows = ((data ?? []) as ReelListItem[]).filter((r) => kind === "all" || r.kind === kind);
          if (!cancelled) setHasMore(false);
        } else {
          rows = await fetchPage();
          if (!cancelled) setHasMore(rows.length === PAGE_SIZE);
        }
        if (!cancelled) {
          setReels(rows);
          setLoading(false);
        }
      },
      searching ? 250 : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [supabase, fetchPage, searching, query, kind]);

  useEffect(() => {
    let cancelled = false;
    void fetchCounts(supabase).then((counts) => {
      if (!cancelled) setCounts(counts);
    });
    return () => {
      cancelled = true;
    };
  }, [supabase]);

  async function loadMore() {
    const last = reels.at(-1);
    if (!last) return;
    const rows = await fetchPage(last.created_at);
    setReels((current) => [...current, ...rows]);
    setHasMore(rows.length === PAGE_SIZE);
  }

  // --- temps réel : les fiches en préparation se mettent à jour seules --------
  useEffect(() => {
    const channel = supabase
      .channel(`reels:${userId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "reels", filter: `user_id=eq.${userId}` },
        (payload) => {
          if (payload.eventType === "DELETE") {
            const id = (payload.old as { id?: string }).id;
            setReels((current) => current.filter((r) => r.id !== id));
          } else {
            const row = payload.new as ReelListItem;
            setReels((current) => {
              const exists = current.some((r) => r.id === row.id);
              // En recherche : on met à jour les résultats affichés sans en ajouter ni en retirer
              if (searching) return exists ? current.map((r) => (r.id === row.id ? { ...r, ...row } : r)) : current;
              const visible = row.user_status === tab && (kind === "all" || row.kind === kind || !row.kind);
              if (!visible) return current.filter((r) => r.id !== row.id);
              if (exists) return current.map((r) => (r.id === row.id ? { ...r, ...row } : r));
              return [row, ...current];
            });
          }
          refreshCounts();
        },
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [supabase, userId, tab, kind, searching, refreshCounts]);

  const thumbnails = useThumbnails(useMemo(() => reels.map((r) => r.thumbnail_path), [reels]));
  const empty = EMPTY_STATES[tab];

  return (
    <main className="page">
      <div className="topbar">
        <span />
        <Link href="/settings" className="icon-button" aria-label="Réglages">
          ⚙︎
        </Link>
      </div>
      <h1 className="large-title">Mes fiches</h1>

      <div className="search">
        <span className="search__icon" aria-hidden="true">
          ⌕
        </span>
        <input
          className="field"
          type="search"
          placeholder="Rechercher dans toutes les fiches"
          aria-label="Rechercher"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {!searching && (
        <div className="segmented" role="group" aria-label="Statut">
          {TABS.map((status) => (
            <button key={status} type="button" aria-pressed={tab === status} onClick={() => setTab(status)}>
              {USER_STATUS_LABELS[status]}
              {counts[status] ? <span className="segmented__count">{counts[status]}</span> : null}
            </button>
          ))}
        </div>
      )}

      <div className="chips" role="group" aria-label="Type de contenu">
        <button type="button" className="chip" aria-pressed={kind === "all"} onClick={() => setKind("all")}>
          Tout
        </button>
        {KIND_ORDER.map((k) => (
          <button
            key={k}
            type="button"
            className="chip"
            data-kind={k}
            aria-pressed={kind === k}
            onClick={() => setKind(kind === k ? "all" : k)}
          >
            {KINDS[k].emoji} {KINDS[k].plural}
          </button>
        ))}
      </div>

      {!loading && reels.length === 0 ? (
        <div className="empty">
          <div className="empty__emoji" aria-hidden="true">
            {searching ? "🔎" : empty.emoji}
          </div>
          <p>{searching ? "Aucune fiche ne correspond à ta recherche." : empty.text}</p>
        </div>
      ) : (
        <ul className="reel-list" aria-busy={loading}>
          {reels.map((reel) => (
            <ReelRow
              key={reel.id}
              reel={reel}
              thumbnailUrl={reel.thumbnail_path ? thumbnails[reel.thumbnail_path] : undefined}
            />
          ))}
        </ul>
      )}

      {hasMore && (
        <button
          type="button"
          className="button button--quiet button--block"
          style={{ marginTop: 16 }}
          onClick={loadMore}
        >
          Afficher plus
        </button>
      )}

      <AddLinkSheet />
    </main>
  );
}
