FROM python:3.11-slim AS lint
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --extra dev --no-install-project

COPY . .
# Run ruff then tests; fail build if either fails
RUN uv run ruff check .
RUN uv run pytest

FROM python:3.11-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY . .
CMD ["sh", "-c", "uv run uvicorn main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}"]
