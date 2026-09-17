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

# The server only serves. Migrations are a separate step — the `migrate` service
# in docker-compose.yml locally, a pre-rollout job in production — because a
# boot-time `alembic upgrade head` runs once *per replica*, and replicas starting
# together would race each other through the same DDL. docs/deployment.md has the
# runbook. The app still does not create its own schema, so a database that is
# behind fails at the first query with UndefinedTableError rather than quietly
# acquiring tables no migration accounts for.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
