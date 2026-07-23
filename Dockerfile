# Zelos Runtime — Multi-stage Docker build
# Stage 1: slim production image (~80 MB)

FROM python:3.12-slim AS base

LABEL org.opencontainers.image.title="Zelos Runtime"
LABEL org.opencontainers.image.description="Open Multi-Agent Orchestration Runtime"
LABEL org.opencontainers.image.version="0.7.0"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Non-root user
RUN groupadd -r zelos && useradd -r -g zelos -d /app zelos

WORKDIR /app

# Copy source
COPY zelos/ ./zelos/
COPY zelos_sdk/ ./zelos_sdk/
COPY zelos.yaml ./
COPY start.py ./
COPY README.md ./

# Zelos core needs zero pip packages — pure Python stdlib
RUN chown -R zelos:zelos /app

USER zelos

EXPOSE 9876

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9876/api/v1/health')" || exit 1

CMD ["python3", "start.py"]


# ── Dev image (includes test tooling) ──
FROM base AS dev

USER root
RUN pip install --no-cache-dir pytest pytest-cov ruff
USER zelos
