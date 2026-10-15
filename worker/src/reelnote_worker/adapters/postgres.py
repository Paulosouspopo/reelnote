"""Accès Postgres (Supabase) : file de jobs et dépôt des reels.

Le worker se connecte directement à la base via le « session pooler » de
Supabase (nécessaire pour LISTEN/NOTIFY). Toute la logique de concurrence
(réclamation d'un job, backoff, jobs bloqués) est en SQL, dans les fonctions
du schéma `internal` : atomique et testée (supabase/tests).
"""

from __future__ import annotations

import logging
import time
from typing import Any, LiteralString
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..models import AnalysisResult, Job, PushSubscription, ReelSource, SourceMetadata, Stage, Transcript

log = logging.getLogger(__name__)

_RETRY_MESSAGE = "Petit souci, nouvelle tentative automatique bientôt."


class PostgresStore:
    """Implémente les ports `JobQueue` et `ReelRepository`."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg.Connection[dict[str, Any]] | None = None
        self._listen_conn: psycopg.Connection[Any] | None = None

    # -- connexions ---------------------------------------------------------------

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(
            self._dsn,
            autocommit=True,
            row_factory=dict_row,
            prepare_threshold=None,  # compatible avec les poolers (Supavisor/PgBouncer)
            connect_timeout=10,
            application_name="reelnote-worker",
        )

    def _execute(
        self, sql: LiteralString, params: dict[str, Any] | tuple[Any, ...] | None = None
    ) -> psycopg.Cursor[Any]:
        if self._conn is None or self._conn.closed or self._conn.broken:
            self._conn = self._connect()
        try:
            return self._conn.execute(sql, params)
        except psycopg.OperationalError:
            self._conn = None  # reconnexion au prochain appel
            raise

    def close(self) -> None:
        for conn in (self._conn, self._listen_conn):
            if conn is not None and not conn.closed:
                conn.close()

    # -- JobQueue -------------------------------------------------------------------

    def claim(self, worker_id: str) -> Job | None:
        row = self._execute("select * from internal.claim_job(%s)", (worker_id,)).fetchone()
        if row is None:
            return None
        return Job(
            id=row["id"], reel_id=row["reel_id"], attempts=row["attempts"], max_attempts=row["max_attempts"]
        )

    def complete(self, job_id: int) -> None:
        self._execute("select internal.complete_job(%s)", (job_id,))

    def fail(self, job_id: int, error: str, *, retryable: bool) -> bool:
        row = self._execute(
            "select internal.fail_job(%s, %s, %s) as retry", (job_id, error, retryable)
        ).fetchone()
        return bool(row and row["retry"])

    def requeue_stale(self, timeout_s: int) -> int:
        row = self._execute(
            "select internal.requeue_stale_jobs(make_interval(secs => %s)) as n", (timeout_s,)
        ).fetchone()
        return int(row["n"]) if row else 0

    def wait_for_jobs(self, timeout_s: float) -> None:
        """Attend une notification de nouveau job, ou l'expiration du délai."""
        try:
            if self._listen_conn is None or self._listen_conn.closed or self._listen_conn.broken:
                self._listen_conn = psycopg.connect(self._dsn, autocommit=True, connect_timeout=10)
                self._listen_conn.execute("LISTEN reelnote_jobs")
            for _ in self._listen_conn.notifies(timeout=timeout_s, stop_after=1):
                break
        except psycopg.OperationalError:
            log.warning("LISTEN indisponible, repli sur le sondage", exc_info=True)
            self._listen_conn = None
            time.sleep(min(timeout_s, 5.0))

    def pop_storage_garbage(self, limit: int) -> list[tuple[int, str, str]]:
        rows = self._execute(
            "select id, bucket, path from internal.storage_garbage order by id limit %s", (limit,)
        ).fetchall()
        return [(r["id"], r["bucket"], r["path"]) for r in rows]

    def ack_storage_garbage(self, ids: list[int]) -> None:
        if ids:
            self._execute("delete from internal.storage_garbage where id = any(%s)", (ids,))

    # -- ReelRepository ---------------------------------------------------------------

    def get_source(self, reel_id: UUID) -> ReelSource | None:
        row = self._execute(
            "select id, user_id, platform, external_id, canonical_url from public.reels where id = %s",
            (reel_id,),
        ).fetchone()
        return ReelSource(**row) if row else None

    def set_stage(self, reel_id: UUID, stage: Stage) -> None:
        self._execute(
            "update public.reels set status = 'processing', stage = %s, "
            "error_code = null, error_message = null where id = %s",
            (stage, reel_id),
        )

    def save_result(
        self,
        reel_id: UUID,
        *,
        metadata: SourceMetadata,
        transcript: Transcript | None,
        analysis: AnalysisResult,
        thumbnail_path: str | None,
    ) -> None:
        card = analysis.card
        self._execute(
            """
            update public.reels set
              status = 'ready', stage = null, error_code = null, error_message = null,
              author_handle = %(author_handle)s, author_name = %(author_name)s,
              caption = %(caption)s, duration_s = %(duration_s)s, posted_at = %(posted_at)s,
              thumbnail_path = coalesce(%(thumbnail_path)s, thumbnail_path),
              transcript = %(transcript)s, transcript_lang = %(transcript_lang)s,
              kind = %(kind)s, title = %(title)s, emoji = %(emoji)s, tldr = %(tldr)s,
              key_points = %(key_points)s, tags = %(tags)s, card = %(card)s, caution = %(caution)s,
              analysis_version = %(analysis_version)s, analysis_model = %(analysis_model)s,
              input_tokens = %(input_tokens)s, output_tokens = %(output_tokens)s,
              processed_at = now()
            where id = %(id)s
            """,
            {
                "id": reel_id,
                "author_handle": metadata.author_handle,
                "author_name": metadata.author_name,
                "caption": metadata.caption,
                "duration_s": metadata.duration_s,
                "posted_at": metadata.posted_at,
                "thumbnail_path": thumbnail_path,
                "transcript": transcript.text if transcript else None,
                "transcript_lang": transcript.language if transcript else None,
                "kind": card.kind,
                "title": card.title,
                "emoji": card.emoji,
                "tldr": card.tldr,
                "key_points": card.key_points,
                "tags": card.tags,
                "card": Jsonb(card.model_dump(mode="json")),
                "caution": card.caution,
                "analysis_version": analysis.prompt_version,
                "analysis_model": analysis.model,
                "input_tokens": analysis.input_tokens,
                "output_tokens": analysis.output_tokens,
            },
        )

    def mark_failed(self, reel_id: UUID, code: str, message: str) -> None:
        self._execute(
            "update public.reels set status = 'failed', stage = null, error_code = %s, error_message = %s "
            "where id = %s",
            (code, message, reel_id),
        )

    def mark_retrying(self, reel_id: UUID) -> None:
        self._execute(
            "update public.reels set status = 'queued', stage = null, error_code = null, error_message = %s "
            "where id = %s",
            (_RETRY_MESSAGE, reel_id),
        )

    def list_push_subscriptions(self, user_id: UUID) -> list[PushSubscription]:
        rows = self._execute(
            "select id, endpoint, p256dh, auth from public.push_subscriptions where user_id = %s", (user_id,)
        ).fetchall()
        return [PushSubscription(**row) for row in rows]

    def delete_push_subscription(self, subscription_id: UUID) -> None:
        self._execute("delete from public.push_subscriptions where id = %s", (subscription_id,))
