FROM postgres:16.14-bookworm

COPY --from=restic/restic:0.19.1 /usr/bin/restic /usr/local/bin/restic
RUN apt-get update \
    && apt-get install --no-install-recommends --yes python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10002 avicola-backup \
    && useradd --system --uid 10002 --gid avicola-backup --home-dir /tmp --shell /usr/sbin/nologin avicola-backup \
    && install -d --owner=avicola-backup --group=avicola-backup --mode=0700 /opt/avicola/deploy/backup

COPY --chown=avicola-backup:avicola-backup deploy/backup/*.py /opt/avicola/deploy/backup/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp RESTIC_CACHE_DIR=/tmp/restic-cache
WORKDIR /opt/avicola
USER 10002:10002
ENTRYPOINT ["/usr/bin/python3", "-m", "deploy.backup.backup"]
