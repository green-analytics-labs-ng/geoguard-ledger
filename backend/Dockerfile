FROM python:3.11-slim

# Install system dependencies required for scipy, numpy, and scikit-learn
# compiled C extensions (BLAS, LAPACK, gfortran)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libblas-dev \
    liblapack-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./

# Dependencies first, with the project itself held back: this layer stays
# cached while application code changes. The project is installed below, once
# its source is on disk — building it needs `app/` and README.md present.
RUN uv sync --frozen --no-install-project

COPY . .

RUN uv sync --frozen

EXPOSE 8000

# Migrations run before the server accepts a request, because the app no longer
# creates its own schema: a database that is behind fails here, at boot, with
# Alembic's own diagnostics, rather than at the first query. `exec` replaces the
# shell so uvicorn is PID 1 and receives stop signals directly.
CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
