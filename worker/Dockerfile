# syntax=docker/dockerfile:1.7
# Image du worker Reelnote : Python + ffmpeg + Deno (requis par yt-dlp pour YouTube).

FROM denoland/deno:bin AS deno

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    HEARTBEAT_FILE=/tmp/reelnote-heartbeat \
    XDG_CACHE_HOME=/tmp/.cache \
    DENO_DIR=/tmp/.deno

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deno /deno /usr/local/bin/deno

# Utilisateur non privilégié
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /models \
    && chown app:app /models

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

USER app
VOLUME ["/models"]

HEALTHCHECK --interval=60s --timeout=5s --start-period=120s --retries=3 \
  CMD ["python", "-m", "reelnote_worker.healthcheck"]

CMD ["python", "-m", "reelnote_worker"]
