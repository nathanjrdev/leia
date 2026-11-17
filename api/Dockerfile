# API da Léia (FastAPI + LangGraph + modelos de busca). Contexto de build: a raiz do repositório,
# porque a carga lê data/catalogo.json e a config procura o .env na raiz.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    HF_HOME=/cache/huggingface

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv

WORKDIR /app/api
# Dependências primeiro (camada em cache enquanto o lock não muda).
COPY api/pyproject.toml api/uv.lock api/.python-version api/README.md ./
RUN uv sync --frozen --group ml --no-dev --no-install-project

COPY api/ ./
COPY data/ /app/data/
RUN uv sync --frozen --group ml --no-dev

EXPOSE 8000
# Migra, carrega o catálogo e os embeddings (idempotente: só faz o que falta) e sobe a API.
# Uma instância só: o limitador de abuso é em memória (docs/deploy.md).
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync python -m leia_api.carga && exec uv run --no-sync uvicorn leia_api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
