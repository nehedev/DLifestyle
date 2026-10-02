FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000