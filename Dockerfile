FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

ENV PYTHONPATH=/app/src
ENV MAPTAP_DB=/app/maptap.db

CMD ["sh", "-c", ".venv/bin/uvicorn maptap.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
