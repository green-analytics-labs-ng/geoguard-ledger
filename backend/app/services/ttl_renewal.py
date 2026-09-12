"""Root TTL renewal: keeps anchored Merkle roots from being archived.

A Merkle root is a Persistent ledger entry, so Soroban charges ongoing rent for
it and archives it once its TTL runs out. Archiving corrupts nothing — the root
is still recoverable — but `verify_inclusion` stops answering for every dataset
in the batch, which silently breaks the guarantee the ledger is supposed to make.
Something therefore has to renew roots *before* their TTL runs out.

Batching is what makes that tractable: renewing one root covers an entire batch,
instead of chasing one entry per dataset.

This module owns the expiry arithmetic and the orchestration; the on-chain call
and its operational signer live in :mod:`app.services.soroban`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.batch import Batch
from app.services.soroban import renew_root_ttl_on_chain

logger = logging.getLogger(__name__)

# Soroban ledgers close roughly every 5 seconds. The contract's TTL budgets are
# expressed in ledgers, so this constant is the bridge to wall-clock expiry.
LEDGER_SECONDS = 5


def ensure_utc(moment: datetime) -> datetime:
    """Treat a naive timestamp as UTC.

    SQLite (used by the test suite) drops ``tzinfo`` on round-trip, so datetimes
    read back from the database can be naive even though they were written as
    UTC. Normalizing here keeps comparisons from raising on aware/naive mixes.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def ledgers_to_timedelta(ledgers: int) -> timedelta:
    """Convert a ledger count to the wall-clock span it represents."""
    return timedelta(seconds=ledgers * LEDGER_SECONDS)


def root_ttl_horizon() -> timedelta:
    """How long a root stays alive after being anchored or renewed."""
    return ledgers_to_timedelta(settings.ttl_renewal_extend_to_ledgers)


def renewal_window() -> timedelta:
    """How close to expiry a root has to be before the job renews it."""
    return timedelta(days=settings.ttl_renewal_window_days)


def initial_root_expiry(anchored_at: datetime) -> datetime:
    """Expiry a freshly anchored root receives from the contract's write-time bump.

    The contract extends a new root to ``ROOT_TTL_EXTEND_TO`` ledgers when it is
    written, so its deadline is a fixed offset from the anchor time.
    """
    return ensure_utc(anchored_at) + root_ttl_horizon()


def renewal_enabled() -> bool:
    """Whether the job is switched on *and* has an account to pay with."""
    return settings.ttl_renewal_enabled and bool(settings.ttl_renewal_signer_secret)


@dataclass
class RenewalOutcome:
    """What happened to one root during a run."""

    batch_id: str
    merkle_root: str
    renewed: bool
    tx_hash: str | None = None
    error: str | None = None


@dataclass
class RenewalSummary:
    """Aggregate result of a renewal run."""

    considered: int = 0
    renewed: int = 0
    failed: int = 0
    dry_run: bool = False
    outcomes: list[RenewalOutcome] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Serialize for logging or a command's output."""
        return {
            "considered": self.considered,
            "renewed": self.renewed,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "outcomes": [
                {
                    "batch_id": outcome.batch_id,
                    "merkle_root": outcome.merkle_root,
                    "renewed": outcome.renewed,
                    "tx_hash": outcome.tx_hash,
                    "error": outcome.error,
                }
                for outcome in self.outcomes
            ],
        }


async def select_roots_due(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta | None = None,
    limit: int | None = None,
) -> list[Batch]:
    """Anchored roots whose TTL falls inside the renewal window, soonest first.

    Only ``anchored`` batches qualify: a pending root was never written to the
    ledger, and a failed one has no entry to renew.
    """
    moment = ensure_utc(now or datetime.now(UTC))
    cutoff = moment + (window if window is not None else renewal_window())
    max_roots = limit if limit is not None else settings.ttl_renewal_max_roots_per_run

    result = await db.execute(
        select(Batch)
        .where(Batch.status == "anchored")
        .where(Batch.root_ttl_expires_at.is_not(None))
        .where(Batch.root_ttl_expires_at <= cutoff)
        .order_by(Batch.root_ttl_expires_at.asc())
        .limit(max_roots)
    )
    return list(result.scalars().all())


async def renew_due_roots(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> RenewalSummary:
    """Renew every root approaching expiry, committing per root.

    Each root is handled independently so one bad root cannot stall the run: a
    failure is recorded against that batch and the job moves on, because the
    alternative is that a single unreachable root blocks renewal for all the
    others and they expire too.

    Args:
        db: Session used to read the roots and record the outcomes.
        now: Evaluation time; defaults to the current time.
        window: Renewal window override, mainly for tests.
        limit: Most roots to renew in this run.
        dry_run: Report what would be renewed without spending fees.

    Returns:
        A :class:`RenewalSummary` describing the run.
    """
    moment = ensure_utc(now or datetime.now(UTC))
    batches = await select_roots_due(db, now=moment, window=window, limit=limit)
    summary = RenewalSummary(considered=len(batches), dry_run=dry_run)

    if dry_run:
        for batch in batches:
            summary.outcomes.append(
                RenewalOutcome(
                    batch_id=batch.batch_id,
                    merkle_root=batch.merkle_root,
                    renewed=False,
                )
            )
        return summary

    for batch in batches:
        batch.ttl_renewal_attempts += 1

        try:
            receipt = await renew_root_ttl_on_chain(
                batch.merkle_root,
                settings.ttl_renewal_extend_to_ledgers,
            )
        except Exception as exc:  # noqa: BLE001 - one bad root must not stop the run
            message = str(exc)[:500]
            batch.ttl_renewal_error = message
            await db.commit()
            summary.failed += 1
            summary.outcomes.append(
                RenewalOutcome(
                    batch_id=batch.batch_id,
                    merkle_root=batch.merkle_root,
                    renewed=False,
                    error=message,
                )
            )
            logger.warning(
                "Root TTL renewal failed: batch=%s root=%s attempts=%d error=%s",
                batch.batch_id,
                batch.merkle_root,
                batch.ttl_renewal_attempts,
                message,
            )
            continue

        # Renewal pushes the deadline out by the full horizon from now.
        batch.root_ttl_expires_at = moment + root_ttl_horizon()
        batch.last_ttl_renewed_at = moment
        batch.ttl_renewal_tx_hash = receipt["tx_hash"]
        batch.ttl_renewal_error = None
        await db.commit()

        summary.renewed += 1
        summary.outcomes.append(
            RenewalOutcome(
                batch_id=batch.batch_id,
                merkle_root=batch.merkle_root,
                renewed=True,
                tx_hash=receipt["tx_hash"],
            )
        )
        logger.info(
            "Root TTL renewed: batch=%s root=%s tx=%s expires_at=%s",
            batch.batch_id,
            batch.merkle_root,
            receipt["tx_hash"],
            batch.root_ttl_expires_at.isoformat(),
        )

    return summary


async def get_ttl_status(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Summarize how much life the anchored roots have left.

    Expiry here is the deadline *recorded* from the contract's TTL budgets when a
    root was anchored or renewed — it is not read back from the ledger. That
    makes this a drift detector rather than ground truth: if the contract's
    budgets ever change, these deadlines go stale and the job's assumptions
    become visible here instead of failing silently.

    Returns:
        Counts and deadlines suitable for monitoring.
    """
    moment = ensure_utc(now or datetime.now(UTC))
    cutoff = moment + renewal_window()

    async def count_anchored(*conditions: Any) -> int:
        query = (
            select(func.count())
            .select_from(Batch)
            .where(Batch.status == "anchored")
            .where(*conditions)
        )
        result = await db.execute(query)
        return int(result.scalar_one())

    total = await count_anchored()
    without_expiry = await count_anchored(Batch.root_ttl_expires_at.is_(None))
    due = await count_anchored(
        Batch.root_ttl_expires_at.is_not(None),
        Batch.root_ttl_expires_at <= cutoff,
    )
    past_expiry = await count_anchored(
        Batch.root_ttl_expires_at.is_not(None),
        Batch.root_ttl_expires_at <= moment,
    )
    failing = await count_anchored(Batch.ttl_renewal_error.is_not(None))

    next_expiry_result = await db.execute(
        select(func.min(Batch.root_ttl_expires_at)).where(Batch.status == "anchored")
    )
    next_expiry = next_expiry_result.scalar_one_or_none()

    last_renewed_result = await db.execute(
        select(func.max(Batch.last_ttl_renewed_at)).where(Batch.status == "anchored")
    )
    last_renewed = last_renewed_result.scalar_one_or_none()

    # Deadlines read back from an aggregate can arrive naive (SQLite drops the
    # offset), so normalize before serializing — the payload must not change
    # shape depending on which database is behind it.
    return {
        "enabled": renewal_enabled(),
        "signer_configured": bool(settings.ttl_renewal_signer_secret),
        "renewal_window_days": settings.ttl_renewal_window_days,
        "root_lifetime_days": round(root_ttl_horizon().total_seconds() / 86_400, 2),
        "anchored_roots": total,
        "roots_without_recorded_expiry": without_expiry,
        "roots_due_for_renewal": due,
        "roots_past_recorded_expiry": past_expiry,
        "roots_with_renewal_error": failing,
        "next_expiry_at": ensure_utc(next_expiry).isoformat() if next_expiry else None,
        "last_renewed_at": ensure_utc(last_renewed).isoformat() if last_renewed else None,
    }
