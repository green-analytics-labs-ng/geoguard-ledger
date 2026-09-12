"""Renew Merkle roots whose TTL is about to run out.

Anchored roots are Persistent ledger entries that Soroban archives once their
TTL lapses, which would make every dataset in the batch unverifiable. This job
renews the ones approaching expiry, acting as the batch's rent payer.

Run it on a schedule — cron, a systemd timer, or a Kubernetes CronJob:

    python -m app.jobs.renew_root_ttl --dry-run   # see what would be renewed
    python -m app.jobs.renew_root_ttl             # renew for real

The job is safe to run repeatedly: a successful renewal moves the root's
recorded deadline out of the window, so the next run skips it. Two overlapping
runs can both attempt the same root; the contract treats the second call as a
no-op, so nothing is extended twice, though that attempt still pays a fee. Keep
the schedule tighter than the window (30 days by default) and overlap is
effectively impossible in practice.

Exit codes, so a scheduler's alerting can act on them:

    0  ran cleanly (including "nothing was due")
    1  at least one renewal failed; the failing root is recorded on the batch
    2  the job is disabled or has no signing account configured
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.services.ttl_renewal import (
    renew_due_roots,
    renewal_enabled,
    root_ttl_horizon,
)

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
            "Root TTL renewal is not configured (%s). Every anchored root will "
            "eventually be archived and stop verifying.",
            reason,
        )
        return EXIT_NOT_CONFIGURED

    async with AsyncSessionLocal() as db:
        summary = await renew_due_roots(db, limit=limit, dry_run=dry_run)

    logger.info(
        "Root TTL renewal pass complete: considered=%d renewed=%d failed=%d dry_run=%s",
        summary.considered,
        summary.renewed,
        summary.failed,
        summary.dry_run,
    )

    if dry_run:
        for outcome in summary.outcomes:
            expiry_note = "would renew"
            logger.info("%s batch=%s root=%s", expiry_note, outcome.batch_id, outcome.merkle_root)

    return EXIT_RENEWAL_FAILED if summary.failed else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run one renewal pass."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list the roots that would be renewed without spending any fees",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "renew at most this many roots in this run "
            f"(default: TTL_RENEWAL_MAX_ROOTS_PER_RUN="
            f"{settings.ttl_renewal_max_roots_per_run})"
        ),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logger.info(
        "Root TTL renewal starting: window=%dd lifetime=%.1fd contract=%s",
        settings.ttl_renewal_window_days,
        root_ttl_horizon().total_seconds() / 86_400,
        settings.contract_id or "(unset)",
    )

    return asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    sys.exit(main())
