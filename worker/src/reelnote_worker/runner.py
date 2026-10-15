"""Boucle principale du worker.

* Réveil immédiat via LISTEN/NOTIFY, avec un sondage de secours.
* Un job à la fois par processus (la transcription est gourmande en CPU) :
  pour aller plus vite, on lance plusieurs conteneurs.
* Arrêt propre sur SIGTERM/SIGINT : le job en cours se termine.
* Maintenance périodique : jobs bloqués, nettoyage du stockage.
* Fichier « heartbeat » pour le healthcheck Docker.
"""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from pathlib import Path
from types import FrameType

from .errors import PipelineError
from .models import Job
from .pipeline import ReelPipeline
from .ports import JobQueue, ObjectStore, ReelRepository

log = logging.getLogger(__name__)

GENERIC_ERROR_MESSAGE = "Une erreur inattendue est survenue. Tu peux réessayer."


class Runner:
    def __init__(
        self,
        *,
        queue: JobQueue,
        repo: ReelRepository,
        pipeline: ReelPipeline,
        store: ObjectStore,
        worker_id: str,
        poll_interval_s: float,
        stale_job_timeout_s: int,
        maintenance_interval_s: int,
        heartbeat_file: Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._queue = queue
        self._repo = repo
        self._pipeline = pipeline
        self._store = store
        self._worker_id = worker_id
        self._poll_interval_s = poll_interval_s
        self._stale_job_timeout_s = stale_job_timeout_s
        self._maintenance_interval_s = maintenance_interval_s
        self._heartbeat_file = heartbeat_file
        self._sleep = sleep
        self._stopping = False
        self._last_maintenance = 0.0

    # -- cycle de vie -----------------------------------------------------------

    def install_signal_handlers(self) -> None:
        def handler(signum: int, _frame: FrameType | None) -> None:
            log.info("arrêt demandé, fin du job en cours", extra={"signal": signum})
            self._stopping = True

        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

    def stop(self) -> None:
        self._stopping = True

    def run_forever(self) -> None:
        log.info("worker démarré", extra={"worker_id": self._worker_id})
        backoff = 1.0
        while not self._stopping:
            try:
                self._beat()
                self._maybe_maintenance()
                if not self.run_once():
                    self._queue.wait_for_jobs(self._poll_interval_s)
                backoff = 1.0
            except Exception:
                # Base injoignable, coupure réseau… : on attend et on recommence.
                log.exception("erreur de boucle, nouvelle tentative", extra={"retry_in_s": backoff})
                self._sleep(backoff)
                backoff = min(backoff * 2, 60.0)
        log.info("worker arrêté")

    def run_once(self) -> bool:
        """Traite au plus un job. Renvoie True si un job a été traité."""
        job = self._queue.claim(self._worker_id)
        if job is None:
            return False
        self._handle(job)
        return True

    # -- traitement d'un job -----------------------------------------------------

    def _handle(self, job: Job) -> None:
        ctx = {"job_id": job.id, "reel_id": str(job.reel_id), "attempt": job.attempts}
        try:
            self._pipeline.process(job)
        except PipelineError as exc:
            will_retry = self._queue.fail(job.id, f"{exc.code}: {exc.detail}", retryable=exc.retryable)
            log.warning(
                "échec du traitement",
                extra={**ctx, "error_code": exc.code, "detail": exc.detail, "will_retry": will_retry},
            )
            self._record_failure(job, exc.code, exc.user_message, will_retry)
        except Exception as exc:
            will_retry = self._queue.fail(job.id, f"unexpected: {exc!r}", retryable=True)
            log.exception("erreur inattendue", extra={**ctx, "will_retry": will_retry})
            self._record_failure(job, "unexpected", GENERIC_ERROR_MESSAGE, will_retry)
        else:
            self._queue.complete(job.id)

    def _record_failure(self, job: Job, code: str, message: str, will_retry: bool) -> None:
        if will_retry:
            self._repo.mark_retrying(job.reel_id)
        else:
            self._repo.mark_failed(job.reel_id, code, message)

    # -- maintenance -------------------------------------------------------------

    def _maybe_maintenance(self) -> None:
        now = time.monotonic()
        if now - self._last_maintenance < self._maintenance_interval_s:
            return
        self._last_maintenance = now

        recovered = self._queue.requeue_stale(self._stale_job_timeout_s)
        if recovered:
            log.warning("jobs bloqués récupérés", extra={"count": recovered})

        garbage = self._queue.pop_storage_garbage(limit=100)
        if garbage:
            try:
                self._store.delete([path for _, _, path in garbage])
                self._queue.ack_storage_garbage([gid for gid, _, _ in garbage])
                log.info("miniatures supprimées", extra={"count": len(garbage)})
            except Exception:
                log.warning("nettoyage du stockage reporté", exc_info=True)

    def _beat(self) -> None:
        if self._heartbeat_file is not None:
            try:
                self._heartbeat_file.touch()
            except OSError:
                log.debug("heartbeat impossible", exc_info=True)
