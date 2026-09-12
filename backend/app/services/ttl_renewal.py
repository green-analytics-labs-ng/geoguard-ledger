"""Root and record TTL renewal: keeps anchored entries from being archived.

On-chain anchors live in Persistent ledger entries, so Soroban charges ongoing
rent for them and archives them once their TTL runs out. Archiving corrupts
nothing — the entry is recoverable — but verification stops answering for
whatever it covered, which silently breaks the guarantee the ledger exists to
make. Something therefore has to renew entries *before* their TTL runs out.

There are two kinds of entry, and both need this:

- a batch's Merkle **root**, which covers every dataset in the batch at once;
- a **record** for a dataset anchored on its own via ``anchor_hash``.

The renewal shape is identical for both — one persistent entry, one key, a
target ledger count — so the selection and renewal loops here are written once
and parameterised by :class:`EntryKind`. The on-chain call and its operational
signer live in :mod:`app.services.soroban`.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.batch import Batch
from app.models.dataset import Dataset
from app.services.soroban import renew_record_ttl_on_chain, renew_root_ttl_on_chain

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


def ttl_horizon() -> timedelta:
    """How long an entry stays alive after being anchored or renewed.

    Both entry kinds are written with the same budget, matching the contract's
    ``ROOT_TTL_EXTEND_TO`` and ``RECORD_TTL_EXTEND_TO``.
    """
    return ledgers_to_timedelta(settings.ttl_renewal_extend_to_ledgers)


def renewal_window() -> timedelta:
    """How close to expiry an entry has to be before the job renews it."""
    return timedelta(days=settings.ttl_renewal_window_days)


def initial_ttl_expiry(anchored_at: datetime) -> datetime:
    """Expiry a freshly anchored entry receives from the contract's write-time bump.

    Both ``anchor_hash`` and ``anchor_root`` extend a new entry to the full
    budget when it is written, so its deadline is a fixed offset from the anchor
    time.
    """
    return ensure_utc(anchored_at) + ttl_horizon()


def renewal_enabled() -> bool:
    """Whether the job is switched on *and* has an account to pay with."""
    return settings.ttl_renewal_enabled and bool(settings.ttl_renewal_signer_secret)


@dataclass(frozen=True)
class EntryKind:
    """A kind of expiring on-chain entry the job keeps alive.

    ``model`` is typed loosely because the two ORM models are only related
    structurally: both expose a status, a key, an expiry column and the same
    renewal bookkeeping columns.
    """

    label: str
    model: Any
    id_attr: str
    key_attr: str
    expiry_attr: str
    # Extra SQL condition an entry must satisfy to be renewable at all.
    eligible: Callable[[Any], Any] | None = None


# The on-chain call is passed at the call site rather than held here, so the
# description of an entry kind stays a pure description.
RenewCall = Callable[[str, int], Awaitable[dict[str, Any]]]

ROOT_ENTRY = EntryKind(
    label="root",
    model=Batch,
    id_attr="batch_id",
    key_attr="merkle_root",
    expiry_attr="root_ttl_expires_at",
)
RECORD_ENTRY = EntryKind(
    label="record",
    model=Dataset,
    id_attr="dataset_id",
    key_attr="dataset_hash",
    expiry_attr="ttl_expires_at",
    # A batched dataset is covered by its batch root and has no `Record(hash)`
    # entry of its own, so renewing it would fail on-chain with HashNotFound.
    # Stated explicitly rather than relying on its deadline staying NULL.
    eligible=lambda model: model.batch_id.is_(None),
)


@dataclass
class RenewalOutcome:
    """What happened to one entry during a run."""

    entry_id: str
    entry_key: str
    renewed: bool
    tx_hash: str | None = None
    error: str | None = None


@dataclass
class RenewalSummary:
    """Aggregate result of a renewal pass over one entry kind."""

    kind: str = ""
    considered: int = 0
    renewed: int = 0
    failed: int = 0
    dry_run: bool = False
    outcomes: list[RenewalOutcome] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Serialize for logging or a command's output."""
        return {
            "kind": self.kind,
            "considered": self.considered,
            "renewed": self.renewed,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "outcomes": [
                {
                    "entry_id": outcome.entry_id,
                    "entry_key": outcome.entry_key,
                    "renewed": outcome.renewed,
                    "tx_hash": outcome.tx_hash,
                    "error": outcome.error,
                }
                for outcome in self.outcomes
            ],
        }


@dataclass
class RenewalRun:
    """Result of a full pass, covering both entry kinds."""

    roots: RenewalSummary
    records: RenewalSummary

    @property
    def considered(self) -> int:
        return self.roots.considered + self.records.considered

    @property
    def renewed(self) -> int:
        return self.roots.renewed + self.records.renewed

    @property
    def failed(self) -> int:
        return self.roots.failed + self.records.failed

    def as_dict(self) -> dict[str, Any]:
        return {
            "considered": self.considered,
            "renewed": self.renewed,
            "failed": self.failed,
            "roots": self.roots.as_dict(),
            "records": self.records.as_dict(),
        }


def _base_conditions(kind: EntryKind) -> list[Any]:
    """Conditions every renewable entry of this kind must satisfy."""
    conditions = [kind.model.status == "anchored"]
    if kind.eligible is not None:
        conditions.append(kind.eligible(kind.model))
    return conditions


async def _select_due(
    db: AsyncSession,
    kind: EntryKind,
    *,
    now: datetime,
    window: timedelta,
    limit: int,
) -> list[Any]:
    """Anchored entries of one kind whose TTL is inside the window, soonest first."""
    expires = getattr(kind.model, kind.expiry_attr)  # noqa: B009 - dynamic column

    result = await db.execute(
        select(kind.model)
        .where(*_base_conditions(kind))
        .where(expires.is_not(None))
        .where(expires <= now + window)
        .order_by(expires.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def select_roots_due(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta | None = None,
    limit: int | None = None,
) -> list[Batch]:
    """Anchored batch roots approaching expiry, soonest first."""
    return await _select_due(
        db,
        ROOT_ENTRY,
        now=ensure_utc(now or datetime.now(UTC)),
        window=window if window is not None else renewal_window(),
        limit=limit if limit is not None else settings.ttl_renewal_max_entries_per_run,
    )


async def select_records_due(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta | None = None,
    limit: int | None = None,
) -> list[Dataset]:
    """Anchored dataset records approaching expiry, soonest first."""
    return await _select_due(
        db,
        RECORD_ENTRY,
        now=ensure_utc(now or datetime.now(UTC)),
        window=window if window is not None else renewal_window(),
        limit=limit if limit is not None else settings.ttl_renewal_max_entries_per_run,
    )


async def _renew_due(
    db: AsyncSession,
    kind: EntryKind,
    renew: RenewCall,
    *,
    now: datetime,
    window: timedelta | None,
    limit: int,
    dry_run: bool,
) -> RenewalSummary:
    """Renew every entry of one kind approaching expiry, committing per entry.

    Each entry is handled independently so one bad entry cannot stall the run: a
    failure is recorded against that row and the job moves on, because the
    alternative is that a single unreachable entry blocks renewal for all the
    others and they expire too.
    """
    if limit <= 0:
        return RenewalSummary(kind=kind.label, dry_run=dry_run)

    entries = await _select_due(
        db,
        kind,
        now=now,
        window=window if window is not None else renewal_window(),
        limit=limit,
    )
    summary = RenewalSummary(kind=kind.label, considered=len(entries), dry_run=dry_run)

    if dry_run:
        for entry in entries:
            summary.outcomes.append(
                RenewalOutcome(
                    entry_id=getattr(entry, kind.id_attr),
                    entry_key=getattr(entry, kind.key_attr),
                    renewed=False,
                )
            )
        return summary

    for entry in entries:
        entry_id = getattr(entry, kind.id_attr)
        entry_key = getattr(entry, kind.key_attr)
        entry.ttl_renewal_attempts += 1

        try:
            receipt = await renew(entry_key, settings.ttl_renewal_extend_to_ledgers)
        except Exception as exc:  # noqa: BLE001 - one bad entry must not stop the run
            message = str(exc)[:500]
            entry.ttl_renewal_error = message
            await db.commit()
            summary.failed += 1
            summary.outcomes.append(
                RenewalOutcome(
                    entry_id=entry_id,
                    entry_key=entry_key,
                    renewed=False,
                    error=message,
                )
            )
            logger.warning(
                "TTL renewal failed: kind=%s id=%s key=%s attempts=%d error=%s",
                kind.label,
                entry_id,
                entry_key,
                entry.ttl_renewal_attempts,
                message,
            )
            continue

        # Renewal pushes the deadline out by the full horizon from now.
        setattr(entry, kind.expiry_attr, now + ttl_horizon())  # noqa: B010 - dynamic column
        entry.last_ttl_renewed_at = now
        entry.ttl_renewal_tx_hash = receipt["tx_hash"]
        entry.ttl_renewal_error = None
        await db.commit()

        summary.renewed += 1
        summary.outcomes.append(
            RenewalOutcome(
                entry_id=entry_id,
                entry_key=entry_key,
                renewed=True,
                tx_hash=receipt["tx_hash"],
            )
        )
        logger.info(
            "TTL renewed: kind=%s id=%s key=%s tx=%s",
            kind.label,
            entry_id,
            entry_key,
            receipt["tx_hash"],
        )

    return summary


async def renew_due_roots(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> RenewalSummary:
    """Renew batch roots approaching expiry."""
    return await _renew_due(
        db,
        ROOT_ENTRY,
        renew_root_ttl_on_chain,
        now=ensure_utc(now or datetime.now(UTC)),
        window=window,
        limit=limit if limit is not None else settings.ttl_renewal_max_entries_per_run,
        dry_run=dry_run,
    )


async def renew_due_records(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> RenewalSummary:
    """Renew individually anchored dataset records approaching expiry."""
    return await _renew_due(
        db,
        RECORD_ENTRY,
        renew_record_ttl_on_chain,
        now=ensure_utc(now or datetime.now(UTC)),
        window=window,
        limit=limit if limit is not None else settings.ttl_renewal_max_entries_per_run,
        dry_run=dry_run,
    )


async def renew_expiring_entries(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window: timedelta | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> RenewalRun:
    """Renew every entry approaching expiry, across both entry kinds.

    Roots go first: one root covers an entire batch, so it is the cheapest way
    to keep the most datasets verifiable. ``limit`` bounds the run as a whole
    rather than applying per kind, because its job is to cap how much the run
    can spend on fees.

    Args:
        db: Session used to read the entries and record the outcomes.
        now: Evaluation time; defaults to the current time.
        window: Renewal window override, mainly for tests.
        limit: Most entries to renew across both kinds in this run.
        dry_run: Report what would be renewed without spending fees.

    Returns:
        A :class:`RenewalRun` describing both passes.
    """
    moment = ensure_utc(now or datetime.now(UTC))
    budget = limit if limit is not None else settings.ttl_renewal_max_entries_per_run

    roots = await _renew_due(
        db,
        ROOT_ENTRY,
        renew_root_ttl_on_chain,
        now=moment,
        window=window,
        limit=budget,
        dry_run=dry_run,
    )
    records = await _renew_due(
        db,
        RECORD_ENTRY,
        renew_record_ttl_on_chain,
        now=moment,
        window=window,
        limit=max(budget - roots.considered, 0),
        dry_run=dry_run,
    )

    return RenewalRun(roots=roots, records=records)


async def _kind_status(db: AsyncSession, kind: EntryKind, now: datetime) -> dict[str, Any]:
    """Counts and deadlines for one entry kind."""
    expires = getattr(kind.model, kind.expiry_attr)  # noqa: B009 - dynamic column

    async def count(*conditions: Any) -> int:
        query = (
            select(func.count())
            .select_from(kind.model)
            .where(*_base_conditions(kind))
            .where(*conditions)
        )
        result = await db.execute(query)
        return int(result.scalar_one())

    next_result = await db.execute(select(func.min(expires)).where(*_base_conditions(kind)))
    next_expiry = next_result.scalar_one_or_none()

    renewed_result = await db.execute(
        select(func.max(kind.model.last_ttl_renewed_at)).where(*_base_conditions(kind))
    )
    last_renewed = renewed_result.scalar_one_or_none()

    # Deadlines read back from an aggregate can arrive naive (SQLite drops the
    # offset), so normalize before serializing — the payload must not change
    # shape depending on which database is behind it.
    return {
        "anchored": await count(),
        "without_recorded_expiry": await count(expires.is_(None)),
        "due_for_renewal": await count(expires.is_not(None), expires <= now + renewal_window()),
        "past_recorded_expiry": await count(expires.is_not(None), expires <= now),
        "with_renewal_error": await count(kind.model.ttl_renewal_error.is_not(None)),
        "next_expiry_at": ensure_utc(next_expiry).isoformat() if next_expiry else None,
        "last_renewed_at": ensure_utc(last_renewed).isoformat() if last_renewed else None,
    }


async def get_ttl_status(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Summarize how much life the anchored entries have left, by kind.

    Expiry here is the deadline *recorded* when an entry was anchored or renewed
    — it is not read back from the ledger. That makes this a drift detector
    rather than ground truth: if the contract's budgets ever change, these
    deadlines go stale and the job's assumptions become visible here instead of
    failing silently.

    Returns:
        Configuration plus per-kind counts and deadlines, suitable for monitoring.
    """
    moment = ensure_utc(now or datetime.now(UTC))

    return {
        "enabled": renewal_enabled(),
        "signer_configured": bool(settings.ttl_renewal_signer_secret),
        "renewal_window_days": settings.ttl_renewal_window_days,
        "entry_lifetime_days": round(ttl_horizon().total_seconds() / 86_400, 2),
        "roots": await _kind_status(db, ROOT_ENTRY, moment),
        "records": await _kind_status(db, RECORD_ENTRY, moment),
    }
