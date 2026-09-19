#!/usr/bin/env python3
"""Check that the schema comes from the migration step, and only from there.

Three regressions are guarded here, all of which have happened in this
repository:

1. **The app creating its own schema.** `Base.metadata.create_all` on startup made
   an empty database work, but left it with no `alembic_version` row — so no
   migration could ever be applied to it again, and `alembic upgrade head` failed
   with `relation "datasets" already exists`. The app must not create tables.

2. **Migrations running in the boot command.** `alembic upgrade head && uvicorn`
   looks convenient and is a race: it runs once *per replica*, so instances
   starting together apply the same DDL concurrently. Migrations belong in their
   own step, and the command the backend actually starts with must not run them.

3. **The migration step going missing, or drifting from the boot command.** The
   two commands are read out of the files that ship — the compose service that
   runs `alembic upgrade`, and the Dockerfile's CMD (or the compose `command:`
   that replaces it) — and run in order against an empty scratch database, which
   must end up serving with every model table present, stamped at head, and free
   of drift.

Checks 1 and 3 run against scratch databases created on the server in
`DATABASE_URL`, and dropped again afterwards. Nothing else there is touched.

Usage:
    cd backend && uv run python ../scripts/check_boot_migrations.py

Exits 0 when both hold, 1 otherwise.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import asyncpg  # noqa: E402

try:
    import yaml  # noqa: E402
except ImportError:  # pragma: no cover - the check must not pass quietly
    raise SystemExit(
        "PyYAML is needed to read the migration step out of docker-compose.yml. It "
        "arrives with uvicorn[standard]; declare it in the dev dependencies if that "
        "ever stops being true."
    ) from None

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.batch import Batch  # noqa: E402,F401  (registers its table)
from app.models.dataset import Dataset  # noqa: E402,F401

# The container's command is run as-is, so this is the port it serves on.
CONTAINER_PORT = 8000
# The server in check 1 gets its own port, in case 8000 is already taken.
BARE_PORT = 8123

# How long to wait for a server to start answering. A cold job spends most of
# this importing the model stack, and starting uvicorn with --reload.
STARTUP_TIMEOUT_SECONDS = 90


# ── Database helpers ──────────────────────────────────────────────


def _at_database(url: str, database: str) -> str:
    """Point a Postgres URL at another database, keeping its driver suffix."""
    return urlunsplit(urlsplit(url)._replace(path=f"/{database}"))


def _as_dsn(url: str) -> str:
    """The same URL as a plain asyncpg DSN (SQLAlchemy's driver suffix dropped)."""
    return url.replace("postgresql+asyncpg", "postgresql")


async def _execute(dsn: str, query: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(query)
    finally:
        await conn.close()


async def _fetchval(dsn: str, query: str) -> object:
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchval(query)
    finally:
        await conn.close()


async def _public_tables(dsn: str) -> set[str]:
    rows = await _fetchval(
        dsn,
        "SELECT coalesce(array_agg(tablename), '{}') FROM pg_tables WHERE schemaname = 'public'",
    )
    return set(rows or [])


def _model_tables() -> set[str]:
    """Every table the models declare, so the expectation cannot go stale."""
    return set(Base.metadata.tables)


# ── Server helpers ────────────────────────────────────────────────


class Server:
    """A server process started for one check, killed as a group afterwards."""

    def __init__(self, command: str, database_url: str, log_path: Path) -> None:
        self.command = command
        self.database_url = database_url
        self.log_path = log_path
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        # `start_new_session` gives the server its own process group: `uvicorn
        # --reload` runs a child, so killing the group is what stops it all.
        self.log = self.log_path.open("wb")
        self.process = subprocess.Popen(
            self.command,
            shell=True,
            cwd=BACKEND_DIR,
            env={
                **os.environ,
                "DATABASE_URL": self.database_url,
                # These checks exercise boot and schema, not auth, and they start
                # the shipped command with only this environment (compose's env is
                # not inherited). Give the app the same development opt-in the dev
                # stack uses so it can boot with no API_KEYS configured.
                "ALLOW_UNAUTHENTICATED_WRITES": "true",
            },
            stdout=self.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=15)
        self.log.close()

    def log_tail(self, lines: int = 15) -> str:
        """The end of the server's output, for when a check fails."""
        try:
            text = self.log_path.read_text(errors="replace").splitlines()
        except OSError:
            return "(no output captured)"
        return "\n".join(text[-lines:]) or "(no output captured)"


def _wait_for_status(url: str, timeout: float = STARTUP_TIMEOUT_SECONDS) -> int:
    """Poll until the server answers, returning the status it answered with."""
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code  # the server answered, with an error
        except Exception as exc:  # noqa: BLE001 — refused while it is still booting
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(f"nothing answered {url} within {timeout:.0f}s ({last_error})")


# ── The shipped commands, read from the files that own them ───────


def _as_command(value: object) -> str | None:
    """A compose command as one shell string, however it was written."""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        # Compose itself normalises `command: uv run alembic upgrade head` to a list.
        return " ".join(shlex.quote(part) for part in value)
    return None


def _compose_services() -> dict[str, object]:
    """The compose services, keyed by name."""
    parsed = yaml.safe_load(COMPOSE_FILE.read_text())
    services = (parsed or {}).get("services")
    if not isinstance(services, dict) or not services:
        raise SystemExit(f"{COMPOSE_FILE} declares no services.")
    return services


def _image_boot_command() -> str:
    """The shell command the backend image runs, straight from its Dockerfile."""
    dockerfile = BACKEND_DIR / "Dockerfile"
    match = re.search(r"^CMD\s+(\[.*\])\s*$", dockerfile.read_text(), re.MULTILINE)
    if match is None:
        raise SystemExit(
            f"{dockerfile} has no JSON-form CMD. This check runs the image's own boot "
            "command, so it has to be able to read it."
        )

    argv = json.loads(match.group(1))
    if not isinstance(argv, list) or not argv or not all(isinstance(part, str) for part in argv):
        raise SystemExit(
            f"Expected a JSON array of strings in {dockerfile}'s CMD, found {argv!r}. "
            "This check runs that command against an empty database."
        )
    if argv[:2] == ["sh", "-c"] and len(argv) == 3:
        return argv[2]
    # Exec form: quote it back into the single string this check runs.
    return " ".join(shlex.quote(part) for part in argv)


def _backend_boot_command() -> str:
    """What the backend actually starts with.

    A `command:` in compose replaces the image's CMD, so the effective command is
    whichever of the two is set — and this has to test the one that really runs,
    not the image's idea of it.
    """
    service = _compose_services().get("backend")
    if isinstance(service, dict):
        command = _as_command(service.get("command"))
        if command:
            return command
    return _image_boot_command()


def _migration_command() -> str:
    """The migration step as it ships: the compose service that upgrades the schema.

    Found by what it runs rather than by name, so renaming the service keeps this
    working while deleting the step does not.
    """
    for service in _compose_services().values():
        if not isinstance(service, dict):
            continue
        command = _as_command(service.get("command"))
        if command and "alembic" in command and "upgrade" in command:
            return command
    raise AssertionError(
        f"{COMPOSE_FILE} has no service running `alembic upgrade`, so nothing applies "
        "migrations. They have to be their own step — see docs/deployment.md."
    )


# ── The checks ────────────────────────────────────────────────────


async def _recreate_database(admin_dsn: str, database: str) -> None:
    # FORCE so a connection left by a previous failed run cannot wedge this one.
    await _execute(admin_dsn, f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
    await _execute(admin_dsn, f'CREATE DATABASE "{database}"')


async def check_app_does_not_create_schema(url: str, admin_dsn: str, database: str) -> None:
    """Starting the app on an empty database must not create a schema."""
    await _recreate_database(admin_dsn, database)

    server = Server(
        command=f"uv run uvicorn app.main:app --host 127.0.0.1 --port {BARE_PORT}",
        database_url=_at_database(url, database),
        log_path=Path(f"/tmp/{database}-server.log"),
    )
    server.start()
    try:
        status = _wait_for_status(f"http://127.0.0.1:{BARE_PORT}/api/v1/datasets")
        if status < 500:
            raise AssertionError(
                f"the app answered HTTP {status} with no schema present, so it is "
                "creating tables itself — which leaves the database with no recorded "
                "revision and impossible to migrate.\n"
                f"--- server output ---\n{server.log_tail()}"
            )

        created = await _public_tables(_as_dsn(_at_database(url, database)))
        if created:
            raise AssertionError(
                f"the app created {sorted(created)} on startup. The schema belongs to "
                "Alembic; tables created here can never be upgraded.\n"
                f"--- server output ---\n{server.log_tail()}"
            )
    finally:
        server.stop()


async def check_boot_command_leaves_migrations_out(
    _url: str, _admin_dsn: str, _database: str
) -> None:
    """The boot command must not run migrations. This one needs no database."""
    command = _backend_boot_command()
    if "alembic" in command:
        raise AssertionError(
            f"the backend's boot command runs Alembic:\n    {command}\n"
            "A boot-time migration runs once per replica, so instances starting "
            "together apply the same DDL concurrently. Migrations belong in their own "
            "step — the `migrate` service in docker-compose.yml, or a pre-rollout job "
            "in production."
        )


async def check_deploy_step_then_boot(url: str, admin_dsn: str, database: str) -> None:
    """The migration step, then the boot command, must leave a database serving."""
    await _recreate_database(admin_dsn, database)

    database_url = _at_database(url, database)
    dsn = _as_dsn(database_url)

    # The deploy step, run the way compose runs it: its own process, exactly once,
    # before any server starts.
    step = subprocess.run(
        _migration_command(),
        shell=True,
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
    )
    if step.returncode != 0:
        raise AssertionError(
            "the migration step failed against an empty database:\n"
            f"{step.stdout.strip()}\n{step.stderr.strip()}"
        )

    server = Server(
        command=_backend_boot_command(),
        database_url=database_url,
        log_path=Path(f"/tmp/{database}-server.log"),
    )
    server.start()
    try:
        try:
            status = _wait_for_status(f"http://127.0.0.1:{CONTAINER_PORT}/api/v1/datasets")
        except TimeoutError as exc:
            raise AssertionError(
                "the boot command never answered, even though the migration step "
                f"succeeded.\n--- server output ---\n{server.log_tail()}"
            ) from exc
        if status != 200:
            raise AssertionError(
                f"the boot command served HTTP {status} for a database-backed request "
                "after the migration step ran, so the two no longer agree on the "
                f"schema.\n--- server output ---\n{server.log_tail()}"
            )

        tables = await _public_tables(dsn)
        missing = _model_tables() - tables
        if missing:
            raise AssertionError(
                f"the migration step left the schema incomplete; missing {sorted(missing)}"
            )

        stamped = await _fetchval(dsn, "SELECT version_num FROM alembic_version")
        if stamped is None:
            raise AssertionError(
                "the migration step left the database unstamped (no alembic_version "
                "row) — the state that makes `alembic upgrade head` impossible from "
                "then on."
            )

        head = subprocess.run(
            ["uv", "run", "alembic", "heads"],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()[0]
        if stamped != head:
            raise AssertionError(
                f"the migration step left the database on {stamped}, not the head "
                f"revision {head}: migrations did not run."
            )
    finally:
        server.stop()

    # A schema the models disagree with is drift the next migration would trip on.
    check = subprocess.run(
        ["uv", "run", "alembic", "check"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        raise AssertionError(
            f"the migrated schema does not match the models:\n"
            f"{check.stdout.strip()}\n{check.stderr.strip()}"
        )


async def main() -> int:
    url = os.environ.get("DATABASE_URL") or settings.database_url
    admin_dsn = _as_dsn(_at_database(url, "postgres"))

    try:
        await _fetchval(admin_dsn, "SELECT 1")
    except OSError as exc:
        print(f"Cannot reach Postgres at {admin_dsn}: {exc}", file=sys.stderr)
        print("Start one first (docker compose up -d db).", file=sys.stderr)
        return 1

    checks = [
        ("the app does not create its own schema", check_app_does_not_create_schema),
        ("the boot command does not run migrations", check_boot_command_leaves_migrations_out),
        ("the migration step prepares what the boot command serves", check_deploy_step_then_boot),
    ]
    databases = [f"geoguard_bootcheck_{index}" for index in range(len(checks))]

    failures: list[tuple[str, str]] = []
    for (name, check), database in zip(checks, databases, strict=True):
        print(f"→ {name}")
        try:
            await check(url, admin_dsn, database)
        except (AssertionError, TimeoutError) as exc:
            failures.append((name, str(exc)))
            print(f"  FAILED\n{exc}\n")
        else:
            print("  ok")

    for database in databases:
        try:
            await _execute(admin_dsn, f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
        except OSError as exc:  # cleanup must not mask the result
            print(f"  (could not drop {database}: {exc})", file=sys.stderr)

    if failures:
        print(f"\n❌ {len(failures)} of {len(checks)} boot checks failed:")
        for name, message in failures:
            print(f"  - {name}: {message.splitlines()[0]}")
        return 1

    print(f"\n✅ All {len(checks)} boot checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
