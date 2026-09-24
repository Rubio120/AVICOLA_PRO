FROM golang:1.26.8-trixie AS restic-builder
ARG GO_VERSION=1.26.8
ARG RESTIC_VERSION=0.19.1
ARG RESTIC_COMMIT=6aa3a516ce654808a1f28f9fa21e9b7c8e6e90bf
ENV GOTOOLCHAIN=local
WORKDIR /src/restic
RUN apt-get update \
    && apt-get install --no-install-recommends --yes python3 python-is-python3 \
    && rm -rf /var/lib/apt/lists/*
RUN git init \
    && git remote add origin https://github.com/restic/restic.git \
    && git fetch --depth 1 origin "refs/tags/v${RESTIC_VERSION}:refs/tags/v${RESTIC_VERSION}" \
    && test "$(git rev-parse "v${RESTIC_VERSION}^{commit}")" = "${RESTIC_COMMIT}" \
    && git checkout --detach "${RESTIC_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${RESTIC_COMMIT}"
RUN go mod edit \
    -require=golang.org/x/crypto@v0.55.0 \
    -require=golang.org/x/net@v0.56.0 \
    -require=golang.org/x/text@v0.39.0 \
    -require=google.golang.org/grpc@v1.83.2 \
    && go mod tidy
ENV GOCACHE=/tmp/go-build-cache
# Run the upstream test suite with root build privileges and its Python test helper.
# The OCI build sandbox does not expose /dev/fuse; Restic's runtime does not use FUSE.
# Root can read chmod-restricted fixtures, invalidating these permission-denial tests.
RUN go test ./... -skip 'TestMount|TestScannerError|TestBackupErrors|TestArchiverErrorReporting/(file-unreadable|file-unreadable-ignore-error|file-subdir-unreadable|file-subdir-unreadable-ignore-error)'
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -ldflags="-s -w" -o /out/restic ./cmd/restic
RUN set -eu; \
    expected="go${GO_VERSION}"; \
    actual="$(go version | awk '{print $3}')"; \
    if [ "$actual" != "$expected" ]; then \
        echo >&2 "Go compiler mismatch: expected $expected, got $actual"; \
        exit 1; \
    fi; \
    go version -m /out/restic | tee /tmp/restic-buildinfo; \
    if ! grep -Fx "/out/restic: ${expected}" /tmp/restic-buildinfo; then \
        echo >&2 "Restic binary toolchain mismatch: expected $expected"; \
        exit 1; \
    fi

FROM postgres:16.15-trixie

COPY --from=restic-builder /out/restic /usr/local/bin/restic
RUN apt-get update \
    && apt-get upgrade --yes \
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
