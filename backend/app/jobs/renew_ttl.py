"""Renew anchored entries whose TTL is about to run out.

On-chain anchors are Persistent ledger entries that Soroban archives once their
TTL lapses. Archiving makes verification stop answering for whatever the entry
covered, so this job renews entries approaching expiry, acting as their rent
payer. It covers both kinds:

- a batch's **root**, which keeps every dataset in that batch verifiable;
- a dataset's own **record**, when it was anchored individually.

Run it on a schedule — cron, a systemd timer, or a Kubernetes CronJob:

    python -m app.jobs.renew_ttl --dry-run   # see what would be renewed
    python -m app.jobs.renew_ttl             # renew for real

The job is safe to run repeatedly: a successful renewal moves the entry's
recorded deadline out of the window, so the next run skips it. Two overlapping
runs can both attempt the same entry; the contract treats the second call as a
no-op, so nothing is extended twice, though that attempt still pays a fee. Keep
the schedule tighter than the window (30 days by default) and overlap is
effectively impossible in practice.

Exit codes, so a scheduler's alerting can act on them:

    0  ran cleanly (including "nothing was due")
    1  at least one renewal failed; the failing entry is recorded on its row
    2  the job is disabled or has no signing account configured
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.services.ttl_renewal import renew_expiring_entries, renewal_enabled, ttl_horizon

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_RENEWAL_FAILED = 1
EXIT_NOT_CONFIGURED = 2


async def run(*, dry_run: bool = False, limit: int | None = None) -> int:
    """Perform one renewal pass and return the process exit code."""
    if not renewal_enabled():
        reason = (
            "TTL_RENEWAL_ENABLED is false"
            if not settings.ttl_renewal_enabled
            else "TTL_RENEWAL_SIGNER_SECRET is not set"
        )
        logger.error(
            "TTL renewal is not configured (%s). Anchored roots and records will "
            "eventually be archived and stop verifying.",
            reason,
        )
        return EXIT_NOT_CONFIGURED

    async with AsyncSessionLocal() as db:
        run_result = await renew_expiring_entries(db, limit=limit, dry_run=dry_run)

    logger.info(
        "TTL renewal pass complete: considered=%d renewed=%d failed=%d dry_run=%s",
        run_result.considered,
        run_result.renewed,
        run_result.failed,
        dry_run,
    )

    if dry_run:
        for summary in (run_result.roots, run_result.records):
            for outcome in summary.outcomes:
                logger.info(
                    "would renew kind=%s id=%s key=%s",
                    summary.kind,
                    outcome.entry_id,
                    outcome.entry_key,
                )

    return EXIT_RENEWAL_FAILED if run_result.failed else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run one renewal pass."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list the entries that would be renewed without spending any fees",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "renew at most this many entries across both kinds in this run "
            f"(default: TTL_RENEWAL_MAX_ENTRIES_PER_RUN="
            f"{settings.ttl_renewal_max_entries_per_run})"
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logger.info(
        "TTL renewal starting: window=%dd lifetime=%.1fd contract=%s",
        settings.ttl_renewal_window_days,
        ttl_horizon().total_seconds() / 86_400,
        settings.contract_id or "(unset)",
    )

    return asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    sys.exit(main())
