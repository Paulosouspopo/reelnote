"""Healthcheck Docker : le worker est sain si sa boucle a battu récemment.

Un job peut durer quelques minutes (transcription) : la tolérance est large.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

MAX_AGE_S = float(os.environ.get("HEALTHCHECK_MAX_AGE_S", "600"))


def main() -> int:
    path = Path(os.environ.get("HEARTBEAT_FILE", "/tmp/reelnote-heartbeat"))  # noqa: S108
    try:
        age = time.time() - path.stat().st_mtime
    except FileNotFoundError:
        return 1
    return 0 if age < MAX_AGE_S else 1


if __name__ == "__main__":
    sys.exit(main())
