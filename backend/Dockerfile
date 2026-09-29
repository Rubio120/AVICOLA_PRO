FROM python:3.13.15-alpine3.24 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable \
    && uv pip install --python /opt/venv/bin/python --no-deps setuptools==84.0.0

FROM python:3.13.15-alpine3.24 AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apk upgrade --no-cache \
    && python -m pip install --no-cache-dir --upgrade setuptools==84.0.0 \
    && addgroup -S -g 10001 avicola \
    && adduser -S -D -H -u 10001 -G avicola -h /app -s /bin/false avicola
COPY --from=builder --chown=avicola:avicola /opt/venv /opt/venv
COPY --chown=avicola:avicola deploy/entrypoints/backend.py /app/entrypoints/backend.py
COPY --chown=avicola:avicola backend/alembic.ini /app/alembic.ini
COPY --chown=avicola:avicola backend/migrations /app/migrations

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"]
ENTRYPOINT ["python", "/app/entrypoints/backend.py"]
CMD ["uvicorn", "avicola_pro.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
