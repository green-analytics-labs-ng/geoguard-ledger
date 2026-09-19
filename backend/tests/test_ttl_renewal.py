"""Tests for anchored-entry TTL renewal: service, entry selection, and job.

The renewal job is the only thing standing between an anchored entry and Soroban
archiving it, so these tests cover the expiry arithmetic, which entries get
selected (including the ones that must *not* be), what a run records, and — most
importantly — that a failing entry does not stop the others from being renewed.
"""

import asyncio
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from stellar_sdk import Account, Keypair, StrKey, TransactionBuilder, TransactionEnvelope, scval

from app.config import settings
from app.jobs import renew_ttl as renewal_job
from app.models.batch import Batch
from app.models.dataset import Dataset
from app.services import soroban, ttl_renewal
from app.services.ttl_renewal import (
    ensure_utc,
    initial_ttl_expiry,
    ledgers_to_timedelta,
    renew_due_records,
    renew_due_roots,
    renew_expiring_entries,
    renewal_enabled,
    select_records_due,
    select_roots_due,
    ttl_horizon,
)
from app.services.ttl_renewal import (
    get_ttl_status as build_ttl_status,
)
from tests.conftest import MOCK_TX_HASH, TestSessionLocal

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"

# What the contract's write-time bumps grant a new entry, and the margin below a
# renewal target at which the contract stops honouring a call as a no-op.
CONTRACT_TTL_EXTEND_TO = 3_110_400
CONTRACT_TTL_RENEWAL_MARGIN = 100_000
LEDGERS_PER_DAY = 86_400 // ttl_renewal.LEDGER_SECONDS


async def _add_batch(
    *,
    status: str = "anchored",
    expires_in: timedelta | None = timedelta(days=10),
    ttl_renewal_error: str | None = None,
    ttl_renewal_attempts: int = 0,
    last_ttl_renewed_at: datetime | None = None,
    now: datetime | None = None,
) -> str:
    """Insert a batch directly, so selection logic can be exercised precisely."""
    moment = now or datetime.now(UTC)
    batch_id = str(uuid.uuid4())

    async with TestSessionLocal() as db:
        db.add(
            Batch(
                batch_id=batch_id,
                submitter_address=TEST_ADDRESS,
                merkle_root=secrets.token_hex(32),
                leaf_count=2,
                status=status,
                anchored_at=moment,
                root_ttl_expires_at=None if expires_in is None else moment + expires_in,
                ttl_renewal_error=ttl_renewal_error,
                ttl_renewal_attempts=ttl_renewal_attempts,
                last_ttl_renewed_at=last_ttl_renewed_at,
            )
        )
        await db.commit()

    return batch_id


async def _add_dataset(
    *,
    status: str = "anchored",
    expires_in: timedelta | None = timedelta(days=10),
    batch_id: str | None = None,
    ttl_renewal_error: str | None = None,
    ttl_renewal_attempts: int = 0,
    last_ttl_renewed_at: datetime | None = None,
    now: datetime | None = None,
) -> str:
    """Insert a dataset directly, standalone unless a batch id is supplied."""
    moment = now or datetime.now(UTC)
    dataset_id = str(uuid.uuid4())

    async with TestSessionLocal() as db:
        db.add(
            Dataset(
                dataset_id=dataset_id,
                submitter_address=TEST_ADDRESS,
                dataset_hash=secrets.token_hex(32),
                status=status,
                anomaly_score=0.1,
                batch_id=batch_id,
                anchored_at=moment,
                ttl_expires_at=None if expires_in is None else moment + expires_in,
                ttl_renewal_error=ttl_renewal_error,
                ttl_renewal_attempts=ttl_renewal_attempts,
                last_ttl_renewed_at=last_ttl_renewed_at,
            )
        )
        await db.commit()

    return dataset_id


async def _get_batch(batch_id: str) -> Batch:
    async with TestSessionLocal() as db:
        batch = await db.get(Batch, batch_id)
        assert batch is not None
        return batch


async def _get_dataset(dataset_id: str) -> Dataset:
    async with TestSessionLocal() as db:
        dataset = await db.get(Dataset, dataset_id)
        assert dataset is not None
        return dataset


async def _renew(**kwargs):
    async with TestSessionLocal() as db:
        return await renew_due_roots(db, **kwargs)


async def _renew_records(**kwargs):
    async with TestSessionLocal() as db:
        return await renew_due_records(db, **kwargs)


async def _renew_all(**kwargs):
    async with TestSessionLocal() as db:
        return await renew_expiring_entries(db, **kwargs)


async def _status(now: datetime | None = None):
    async with TestSessionLocal() as db:
        return await build_ttl_status(db, now=now)


async def _due_roots(**kwargs):
    async with TestSessionLocal() as db:
        return await select_roots_due(db, **kwargs)


async def _due_records(**kwargs):
    async with TestSessionLocal() as db:
        return await select_records_due(db, **kwargs)


# ── Expiry arithmetic ─────────────────────────────────────────────


def test_ledgers_convert_to_wall_clock_time():
    """A ledger budget becomes the wall-clock span it buys."""
    assert ledgers_to_timedelta(0) == timedelta(0)
    assert ledgers_to_timedelta(LEDGERS_PER_DAY) == timedelta(days=1)
    assert ledgers_to_timedelta(CONTRACT_TTL_EXTEND_TO) == timedelta(days=180)


def test_new_entry_expiry_is_the_contract_budget_after_anchoring():
    """Both anchor paths bump to the full budget, so expiry is anchored_at + that."""
    anchored = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    assert initial_ttl_expiry(anchored) == anchored + timedelta(days=180)


def test_expiry_math_treats_naive_timestamps_as_utc():
    """SQLite drops tzinfo, so naive reads must not break comparisons."""
    naive = datetime(2026, 1, 1, 12, 0)
    aware = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    assert ensure_utc(naive) == aware
    assert ensure_utc(aware) == aware
    assert initial_ttl_expiry(naive) == aware + timedelta(days=180)


def test_configured_budget_mirrors_the_contract():
    """The config mirrors contract constants, so drift here would silently mis-renew.

    Not a tautology: these are the numbers in
    contracts/geoguard-ledger/src/storage.rs (for both roots and records), and
    changing the contract without changing this config would make the job renew
    against the wrong budget.
    """
    assert settings.ttl_renewal_extend_to_ledgers == CONTRACT_TTL_EXTEND_TO
    assert ttl_horizon() == timedelta(days=180)


def test_renewal_window_stays_inside_the_contracts_effective_range():
    """The job must ask for a renewal while the contract still honours it.

    Both `extend_ttl` and `extend_root_ttl` no-op unless the entry's remaining
    TTL is below `extend_to - TTL_RENEWAL_MARGIN`, so a window wider than that
    would leave entries that never actually get renewed — appearing healthy
    while heading for archival.
    """
    effective_ceiling_days = (
        CONTRACT_TTL_EXTEND_TO - CONTRACT_TTL_RENEWAL_MARGIN
    ) / LEDGERS_PER_DAY

    assert 0 < settings.ttl_renewal_window_days < effective_ceiling_days


def test_renewal_requires_both_the_switch_and_a_signer(monkeypatch):
    """Renewal spends fees, so it stays off unless explicitly armed."""
    monkeypatch.setattr(settings, "ttl_renewal_enabled", False)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "S" + "A" * 55)
    assert renewal_enabled() is False

    monkeypatch.setattr(settings, "ttl_renewal_enabled", True)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "")
    assert renewal_enabled() is False

    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "S" + "A" * 55)
    assert renewal_enabled() is True


# ── Due selection: roots ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_selects_only_roots_inside_the_window():
    """A root still far from expiry is left alone."""
    now = datetime.now(UTC)
    due = await _add_batch(expires_in=timedelta(days=3), now=now)
    not_due = await _add_batch(expires_in=timedelta(days=90), now=now)

    selected = {batch.batch_id for batch in await _due_roots(now=now)}

    assert due in selected
    assert not_due not in selected


@pytest.mark.asyncio
async def test_already_expired_roots_are_selected():
    """A root past its recorded deadline still has to be renewed."""
    now = datetime.now(UTC)
    overdue = await _add_batch(expires_in=timedelta(days=-5), now=now)

    assert overdue in {batch.batch_id for batch in await _due_roots(now=now)}


@pytest.mark.asyncio
async def test_skips_roots_that_have_no_recorded_deadline():
    """A NULL deadline means nothing to compare against, so it must not be renewed blindly."""
    now = datetime.now(UTC)
    no_deadline = await _add_batch(expires_in=None, now=now)

    assert no_deadline not in {batch.batch_id for batch in await _due_roots(now=now)}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "failed"])
async def test_skips_unanchored_roots(status):
    """Only an anchored root has a ledger entry worth renewing."""
    now = datetime.now(UTC)
    batch_id = await _add_batch(status=status, expires_in=timedelta(days=1), now=now)

    assert batch_id not in {batch.batch_id for batch in await _due_roots(now=now)}


@pytest.mark.asyncio
async def test_renews_the_soonest_expiring_roots_first_up_to_the_limit():
    """Ordering lets a capped run rescue the roots closest to archival."""
    now = datetime.now(UTC)
    soonest = await _add_batch(expires_in=timedelta(days=1), now=now)
    middle = await _add_batch(expires_in=timedelta(days=5), now=now)
    latest = await _add_batch(expires_in=timedelta(days=9), now=now)

    selected = [batch.batch_id for batch in await _due_roots(now=now, limit=2)]

    assert selected == [soonest, middle]
    assert latest not in selected


# ── Due selection: records ────────────────────────────────────────


@pytest.mark.asyncio
async def test_selects_standalone_datasets_nearing_expiry():
    now = datetime.now(UTC)
    due = await _add_dataset(expires_in=timedelta(days=2), now=now)
    not_due = await _add_dataset(expires_in=timedelta(days=120), now=now)

    selected = {dataset.dataset_id for dataset in await _due_records(now=now)}

    assert due in selected
    assert not_due not in selected


@pytest.mark.asyncio
async def test_never_selects_a_batched_dataset():
    """A batched dataset has no record of its own, so renewing it would fail on-chain.

    Its coverage comes from the batch root, which the root pass handles. Even if
    a deadline somehow got written, `eligible` must keep it out of the record pass.
    """
    now = datetime.now(UTC)
    batch_id = await _add_batch(expires_in=timedelta(days=1), now=now)
    # Give the batched dataset a deadline it should never be judged on.
    batched = await _add_dataset(expires_in=timedelta(days=1), batch_id=batch_id, now=now)

    assert batched not in {dataset.dataset_id for dataset in await _due_records(now=now)}


@pytest.mark.asyncio
async def test_record_selection_ignores_status_and_missing_deadlines():
    now = datetime.now(UTC)
    pending = await _add_dataset(status="pending", expires_in=timedelta(days=1), now=now)
    no_deadline = await _add_dataset(expires_in=None, now=now)

    selected = {dataset.dataset_id for dataset in await _due_records(now=now)}

    assert pending not in selected
    assert no_deadline not in selected


# ── Renewal runs: roots ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_root_renewal_pushes_the_deadline_out_and_records_the_receipt():
    now = datetime.now(UTC)
    batch_id = await _add_batch(expires_in=timedelta(days=2), now=now)
    root = (await _get_batch(batch_id)).merkle_root

    with patch.object(
        ttl_renewal, "renew_root_ttl_on_chain", return_value={"tx_hash": MOCK_TX_HASH, "ledger": 42}
    ) as renew:
        summary = await _renew(now=now)

    assert summary.considered == 1
    assert summary.renewed == 1
    assert summary.failed == 0
    assert renew.call_count == 1
    # The key itself and the configured budget, so a wrong argument cannot renew
    # against a deadline the contract will not honour.
    assert renew.call_args.args == (root, settings.ttl_renewal_extend_to_ledgers)

    batch = await _get_batch(batch_id)
    assert ensure_utc(batch.root_ttl_expires_at) == now + ttl_horizon()
    assert ensure_utc(batch.last_ttl_renewed_at) == now
    assert batch.ttl_renewal_tx_hash == MOCK_TX_HASH
    assert batch.ttl_renewal_attempts == 1
    assert batch.ttl_renewal_error is None


@pytest.mark.asyncio
async def test_root_renewal_clears_a_previous_failure():
    """A root that recovers must not keep reporting an error forever."""
    now = datetime.now(UTC)
    batch_id = await _add_batch(
        expires_in=timedelta(days=1),
        ttl_renewal_error="RPC unreachable",
        ttl_renewal_attempts=3,
        now=now,
    )

    with patch.object(
        ttl_renewal, "renew_root_ttl_on_chain", return_value={"tx_hash": MOCK_TX_HASH, "ledger": 7}
    ):
        await _renew(now=now)

    batch = await _get_batch(batch_id)
    assert batch.ttl_renewal_error is None
    assert batch.ttl_renewal_attempts == 4


@pytest.mark.asyncio
async def test_a_failing_root_does_not_stop_the_others():
    """One unreachable root must not let the rest expire too."""
    now = datetime.now(UTC)
    broken = await _add_batch(expires_in=timedelta(days=1), now=now)
    healthy = await _add_batch(expires_in=timedelta(days=2), now=now)
    broken_root = (await _get_batch(broken)).merkle_root

    def _fails_for_one_root(root: str, extend_to: int) -> dict:
        if root == broken_root:
            raise RuntimeError("RPC unreachable")
        return {"tx_hash": MOCK_TX_HASH, "ledger": 9}

    with patch.object(
        ttl_renewal, "renew_root_ttl_on_chain", side_effect=_fails_for_one_root
    ) as renew:
        summary = await _renew(now=now)

    assert renew.call_count == 2
    assert summary.considered == 2
    assert summary.renewed == 1
    assert summary.failed == 1

    broken_batch = await _get_batch(broken)
    assert broken_batch.ttl_renewal_error == "RPC unreachable"
    assert broken_batch.ttl_renewal_attempts == 1
    # Its deadline is untouched, so the next run retries it.
    assert ensure_utc(broken_batch.root_ttl_expires_at) == now + timedelta(days=1)

    healthy_batch = await _get_batch(healthy)
    assert healthy_batch.ttl_renewal_error is None
    assert healthy_batch.ttl_renewal_tx_hash == MOCK_TX_HASH


@pytest.mark.asyncio
async def test_dry_run_reports_without_spending_fees():
    now = datetime.now(UTC)
    batch_id = await _add_batch(expires_in=timedelta(days=1), now=now)

    with patch.object(ttl_renewal, "renew_root_ttl_on_chain") as renew:
        summary = await _renew(now=now, dry_run=True)

    assert renew.call_count == 0
    assert summary.dry_run is True
    assert summary.considered == 1
    assert summary.renewed == 0
    assert [outcome.entry_id for outcome in summary.outcomes] == [batch_id]

    batch = await _get_batch(batch_id)
    assert batch.ttl_renewal_attempts == 0
    assert ensure_utc(batch.root_ttl_expires_at) == now + timedelta(days=1)


@pytest.mark.asyncio
async def test_summary_serializes_outcomes_for_logging():
    now = datetime.now(UTC)
    batch_id = await _add_batch(expires_in=timedelta(days=1), now=now)
    root = (await _get_batch(batch_id)).merkle_root

    with patch.object(
        ttl_renewal, "renew_root_ttl_on_chain", return_value={"tx_hash": MOCK_TX_HASH, "ledger": 3}
    ):
        summary = await _renew(now=now)

    payload = summary.as_dict()

    assert payload["kind"] == "root"
    assert payload["renewed"] == 1
    assert payload["outcomes"] == [
        {
            "entry_id": batch_id,
            "entry_key": root,
            "renewed": True,
            "tx_hash": MOCK_TX_HASH,
            "error": None,
        }
    ]


# ── Renewal runs: records ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_renewal_uses_the_dataset_hash_as_the_entry_key():
    """`extend_ttl` is keyed by dataset hash, so passing anything else fails on-chain."""
    now = datetime.now(UTC)
    dataset_id = await _add_dataset(expires_in=timedelta(days=2), now=now)
    dataset_hash = (await _get_dataset(dataset_id)).dataset_hash

    with patch.object(
        ttl_renewal,
        "renew_record_ttl_on_chain",
        return_value={"tx_hash": MOCK_TX_HASH, "ledger": 11},
    ) as renew:
        summary = await _renew_records(now=now)

    assert renew.call_args.args == (dataset_hash, settings.ttl_renewal_extend_to_ledgers)
    assert summary.kind == "record"
    assert summary.renewed == 1

    dataset = await _get_dataset(dataset_id)
    assert ensure_utc(dataset.ttl_expires_at) == now + ttl_horizon()
    assert ensure_utc(dataset.last_ttl_renewed_at) == now
    assert dataset.ttl_renewal_tx_hash == MOCK_TX_HASH
    assert dataset.ttl_renewal_attempts == 1
    assert dataset.ttl_renewal_error is None


@pytest.mark.asyncio
async def test_a_failing_record_does_not_stop_the_others():
    now = datetime.now(UTC)
    broken = await _add_dataset(expires_in=timedelta(days=1), now=now)
    healthy = await _add_dataset(expires_in=timedelta(days=2), now=now)
    broken_hash = (await _get_dataset(broken)).dataset_hash

    def _fails_for_one_record(key: str, extend_to: int) -> dict:
        if key == broken_hash:
            raise RuntimeError("RPC unreachable")
        return {"tx_hash": MOCK_TX_HASH, "ledger": 12}

    with patch.object(ttl_renewal, "renew_record_ttl_on_chain", side_effect=_fails_for_one_record):
        summary = await _renew_records(now=now)

    assert summary.considered == 2
    assert summary.renewed == 1
    assert summary.failed == 1
    assert (await _get_dataset(broken)).ttl_renewal_error == "RPC unreachable"
    assert (await _get_dataset(healthy)).ttl_renewal_tx_hash == MOCK_TX_HASH


# ── Renewal runs: both kinds together ─────────────────────────────


@pytest.mark.asyncio
async def test_full_run_renews_roots_and_records_in_one_pass():
    now = datetime.now(UTC)
    await _add_batch(expires_in=timedelta(days=1), now=now)
    await _add_dataset(expires_in=timedelta(days=1), now=now)

    with (
        patch.object(
            ttl_renewal,
            "renew_root_ttl_on_chain",
            return_value={"tx_hash": MOCK_TX_HASH, "ledger": 1},
        ),
        patch.object(
            ttl_renewal,
            "renew_record_ttl_on_chain",
            return_value={"tx_hash": MOCK_TX_HASH, "ledger": 2},
        ),
    ):
        run_result = await _renew_all(now=now)

    assert run_result.considered == 2
    assert run_result.renewed == 2
    assert run_result.failed == 0
    assert run_result.roots.renewed == 1
    assert run_result.records.renewed == 1


@pytest.mark.asyncio
async def test_roots_are_renewed_before_records_when_the_budget_is_tight():
    """One root covers a whole batch, so it should win a scarce fee budget."""
    now = datetime.now(UTC)
    await _add_batch(expires_in=timedelta(days=1), now=now)
    root_two = await _add_batch(expires_in=timedelta(days=2), now=now)
    await _add_dataset(expires_in=timedelta(days=1), now=now)

    with (
        patch.object(
            ttl_renewal,
            "renew_root_ttl_on_chain",
            return_value={"tx_hash": MOCK_TX_HASH, "ledger": 1},
        ) as renew_roots,
        patch.object(
            ttl_renewal,
            "renew_record_ttl_on_chain",
            return_value={"tx_hash": MOCK_TX_HASH, "ledger": 2},
        ) as renew_records,
    ):
        run_result = await _renew_all(now=now, limit=2)

    # Budget of two goes entirely to the roots; the record waits for a later run.
    assert run_result.roots.considered == 2
    assert renew_roots.call_count == 2
    assert renew_records.call_count == 0
    assert run_result.considered == 2
    assert (await _get_batch(root_two)).ttl_renewal_tx_hash == MOCK_TX_HASH


@pytest.mark.asyncio
async def test_a_run_with_nothing_due_calls_nothing():
    now = datetime.now(UTC)
    await _add_batch(expires_in=timedelta(days=120), now=now)
    await _add_dataset(expires_in=timedelta(days=120), now=now)

    with (
        patch.object(ttl_renewal, "renew_root_ttl_on_chain") as renew_roots,
        patch.object(ttl_renewal, "renew_record_ttl_on_chain") as renew_records,
    ):
        run_result = await _renew_all(now=now)

    assert renew_roots.call_count == 0
    assert renew_records.call_count == 0
    assert run_result.considered == 0
    assert run_result.as_dict()["failed"] == 0


# ── Status reporting ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_counts_roots_by_urgency():
    now = datetime.now(UTC)
    await _add_batch(expires_in=timedelta(days=1), now=now)
    await _add_batch(expires_in=timedelta(days=100), now=now)
    await _add_batch(expires_in=timedelta(days=-1), now=now)
    await _add_batch(expires_in=None, now=now)
    await _add_batch(status="pending", expires_in=timedelta(days=1), now=now)

    roots = (await _status(now=now))["roots"]

    # Pending roots are not anchored, so they are excluded from every count.
    assert roots["anchored"] == 4
    assert roots["without_recorded_expiry"] == 1
    assert roots["due_for_renewal"] == 2
    assert roots["past_recorded_expiry"] == 1


@pytest.mark.asyncio
async def test_status_counts_records_and_ignores_batched_datasets():
    now = datetime.now(UTC)
    batch_id = await _add_batch(expires_in=timedelta(days=1), now=now)
    await _add_dataset(expires_in=timedelta(days=2), now=now)
    await _add_dataset(expires_in=timedelta(days=2), batch_id=batch_id, now=now)
    await _add_dataset(expires_in=timedelta(days=-1), now=now)

    records = (await _status(now=now))["records"]

    # Only the two standalone datasets count; the batched one is the root's job.
    assert records["anchored"] == 2
    assert records["due_for_renewal"] == 2
    assert records["past_recorded_expiry"] == 1


@pytest.mark.asyncio
async def test_status_surfaces_entries_that_keep_failing():
    now = datetime.now(UTC)
    await _add_batch(expires_in=timedelta(days=1), ttl_renewal_error="boom", now=now)
    await _add_dataset(expires_in=timedelta(days=1), ttl_renewal_error="boom", now=now)

    status = await _status(now=now)

    assert status["roots"]["with_renewal_error"] == 1
    assert status["records"]["with_renewal_error"] == 1


@pytest.mark.asyncio
async def test_status_reports_the_next_deadline_and_the_last_renewal():
    now = datetime.now(UTC)
    renewed_at = now - timedelta(days=1)
    await _add_batch(expires_in=timedelta(days=40), now=now)
    await _add_batch(expires_in=timedelta(days=5), last_ttl_renewed_at=renewed_at, now=now)
    await _add_dataset(expires_in=timedelta(days=3), now=now)

    status = await _status(now=now)

    assert status["roots"]["next_expiry_at"] == (now + timedelta(days=5)).isoformat()
    assert status["roots"]["last_renewed_at"] == renewed_at.isoformat()
    assert status["records"]["next_expiry_at"] == (now + timedelta(days=3)).isoformat()
    assert status["records"]["last_renewed_at"] is None


@pytest.mark.asyncio
async def test_status_is_empty_but_valid_with_no_anchored_entries():
    status = await _status()

    assert status["roots"]["anchored"] == 0
    assert status["records"]["anchored"] == 0
    assert status["roots"]["next_expiry_at"] is None
    assert status["records"]["next_expiry_at"] is None


@pytest.mark.asyncio
async def test_status_advertises_the_configured_horizon(monkeypatch):
    monkeypatch.setattr(settings, "ttl_renewal_window_days", 45)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "S" + "A" * 55)
    monkeypatch.setattr(settings, "ttl_renewal_enabled", True)

    status = await _status()

    assert status["renewal_window_days"] == 45
    assert status["entry_lifetime_days"] == 180.0
    assert status["signer_configured"] is True
    assert status["enabled"] is True


# ── Job entrypoint ────────────────────────────────────────────────


def _arm_job(monkeypatch) -> None:
    """Configure the job to run and point it at the test database."""
    monkeypatch.setattr(settings, "ttl_renewal_enabled", True)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "S" + "A" * 55)
    monkeypatch.setattr(renewal_job, "AsyncSessionLocal", TestSessionLocal)


def test_main_defaults_to_a_real_pass(monkeypatch):
    """The console script's entry point forwards its parsed flags into `run`."""
    run = AsyncMock(return_value=renewal_job.EXIT_OK)
    monkeypatch.setattr(renewal_job, "run", run)

    assert renewal_job.main([]) == renewal_job.EXIT_OK

    run.assert_awaited_once_with(dry_run=False, limit=None)


def test_main_forwards_dry_run_and_limit(monkeypatch):
    """`--dry-run` and `--limit` reach the pass unchanged."""
    run = AsyncMock(return_value=renewal_job.EXIT_OK)
    monkeypatch.setattr(renewal_job, "run", run)

    assert renewal_job.main(["--dry-run", "--limit", "5"]) == renewal_job.EXIT_OK

    run.assert_awaited_once_with(dry_run=True, limit=5)


def test_main_reports_a_misconfigured_job(monkeypatch):
    """A scheduler alerting on exit code 2 needs `main` itself to propagate it."""
    monkeypatch.setattr(settings, "ttl_renewal_enabled", False)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "")

    assert renewal_job.main([]) == renewal_job.EXIT_NOT_CONFIGURED


def test_job_refuses_to_run_while_switched_off(monkeypatch):
    """Renewal spends fees, so a misconfigured job must fail loudly, not quietly."""
    monkeypatch.setattr(settings, "ttl_renewal_enabled", False)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "S" + "A" * 55)

    assert asyncio.run(renewal_job.run()) == renewal_job.EXIT_NOT_CONFIGURED


def test_job_refuses_to_run_without_a_signing_account(monkeypatch):
    monkeypatch.setattr(settings, "ttl_renewal_enabled", True)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "")

    assert asyncio.run(renewal_job.run()) == renewal_job.EXIT_NOT_CONFIGURED


@pytest.mark.asyncio
async def test_job_renews_both_kinds_and_exits_cleanly(monkeypatch):
    _arm_job(monkeypatch)
    batch_id = await _add_batch(expires_in=timedelta(days=1))
    dataset_id = await _add_dataset(expires_in=timedelta(days=1))

    with (
        patch.object(
            ttl_renewal,
            "renew_root_ttl_on_chain",
            return_value={"tx_hash": MOCK_TX_HASH, "ledger": 5},
        ),
        patch.object(
            ttl_renewal,
            "renew_record_ttl_on_chain",
            return_value={"tx_hash": MOCK_TX_HASH, "ledger": 6},
        ),
    ):
        code = await renewal_job.run()

    assert code == renewal_job.EXIT_OK
    assert (await _get_batch(batch_id)).ttl_renewal_tx_hash == MOCK_TX_HASH
    assert (await _get_dataset(dataset_id)).ttl_renewal_tx_hash == MOCK_TX_HASH


@pytest.mark.asyncio
async def test_job_exits_non_zero_when_a_renewal_fails(monkeypatch):
    """A scheduler can only alert on a failing renewal if the process says so."""
    _arm_job(monkeypatch)
    await _add_batch(expires_in=timedelta(days=1))

    with patch.object(
        ttl_renewal, "renew_root_ttl_on_chain", side_effect=RuntimeError("RPC unreachable")
    ):
        code = await renewal_job.run()

    assert code == renewal_job.EXIT_RENEWAL_FAILED


@pytest.mark.asyncio
async def test_job_dry_run_touches_nothing(monkeypatch):
    _arm_job(monkeypatch)
    batch_id = await _add_batch(expires_in=timedelta(days=1))
    dataset_id = await _add_dataset(expires_in=timedelta(days=1))

    with (
        patch.object(ttl_renewal, "renew_root_ttl_on_chain") as renew_roots,
        patch.object(ttl_renewal, "renew_record_ttl_on_chain") as renew_records,
    ):
        code = await renewal_job.run(dry_run=True)

    assert code == renewal_job.EXIT_OK
    assert renew_roots.call_count == 0
    assert renew_records.call_count == 0
    assert (await _get_batch(batch_id)).ttl_renewal_attempts == 0
    assert (await _get_dataset(dataset_id)).ttl_renewal_attempts == 0


# ── On-chain renewal transactions ─────────────────────────────────


def _fake_contract_id() -> str:
    return StrKey.encode_contract(bytes(32))


def _stub_transaction_layer(monkeypatch, captured: dict) -> None:
    """Stub the build/submit layer so renewal can be exercised without a network."""

    async def fake_build(source, function_name, args, log_context=""):
        captured["source"] = source
        captured["function"] = function_name
        captured["args"] = args
        envelope = (
            TransactionBuilder(
                Account(source, 1), settings.soroban_network_passphrase, base_fee=100
            )
            .append_invoke_contract_function_op(
                contract_id=settings.contract_id,
                function_name=function_name,
                parameters=args,
            )
            .set_timeout(300)
            .build()
        )
        return envelope.to_xdr()

    async def fake_submit(signed_xdr):
        captured["signed_xdr"] = signed_xdr
        return {"tx_hash": MOCK_TX_HASH, "ledger": 1234}

    monkeypatch.setattr(soroban, "_build_and_prepare_unsigned", fake_build)
    monkeypatch.setattr(soroban, "submit_transaction", fake_submit)


@pytest.mark.asyncio
async def test_root_renewal_builds_signs_and_submits_for_the_payer(monkeypatch):
    """The renewal call must target the right function, be signed, and be paid by us.

    This is the seam the whole feature rests on: if the argument order were
    wrong, or the envelope were submitted unsigned, every unit test above would
    still pass while production renewal failed on-chain.
    """
    signer = Keypair.random()
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", signer.secret)
    monkeypatch.setattr(settings, "contract_id", _fake_contract_id())

    captured: dict = {}
    _stub_transaction_layer(monkeypatch, captured)

    root = "ab" * 32
    result = await soroban.renew_root_ttl_on_chain(root, CONTRACT_TTL_EXTEND_TO)

    assert result == {"tx_hash": MOCK_TX_HASH, "ledger": 1234}
    assert captured["function"] == "extend_root_ttl"
    # The operational account is the source, so it pays the fee rather than the
    # researcher who anchored the batch.
    assert captured["source"] == signer.public_key
    assert scval.to_native(captured["args"][0]) == bytes.fromhex(root)
    assert scval.to_native(captured["args"][1]) == CONTRACT_TTL_EXTEND_TO

    submitted = TransactionEnvelope.from_xdr(
        captured["signed_xdr"], settings.soroban_network_passphrase
    )
    assert len(submitted.signatures) == 1


@pytest.mark.asyncio
async def test_record_renewal_targets_extend_ttl(monkeypatch):
    """Records are renewed with `extend_ttl`, not the batch-root entry point."""
    signer = Keypair.random()
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", signer.secret)
    monkeypatch.setattr(settings, "contract_id", _fake_contract_id())

    captured: dict = {}
    _stub_transaction_layer(monkeypatch, captured)

    dataset_hash = "cd" * 32
    result = await soroban.renew_record_ttl_on_chain(dataset_hash, CONTRACT_TTL_EXTEND_TO)

    assert result == {"tx_hash": MOCK_TX_HASH, "ledger": 1234}
    assert captured["function"] == "extend_ttl"
    assert captured["source"] == signer.public_key
    assert scval.to_native(captured["args"][0]) == bytes.fromhex(dataset_hash)
    assert scval.to_native(captured["args"][1]) == CONTRACT_TTL_EXTEND_TO

    submitted = TransactionEnvelope.from_xdr(
        captured["signed_xdr"], settings.soroban_network_passphrase
    )
    assert len(submitted.signatures) == 1


@pytest.mark.asyncio
async def test_renewal_refuses_without_a_signing_account(monkeypatch):
    """No operational key means no renewal — never an unsigned or self-paid call."""
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "")
    monkeypatch.setattr(settings, "contract_id", _fake_contract_id())

    with pytest.raises(ValueError, match="TTL_RENEWAL_SIGNER_SECRET"):
        await soroban.renew_root_ttl_on_chain("ab" * 32, CONTRACT_TTL_EXTEND_TO)


@pytest.mark.asyncio
async def test_renewal_refuses_without_a_contract(monkeypatch):
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", Keypair.random().secret)
    monkeypatch.setattr(settings, "contract_id", "")

    with pytest.raises(ValueError, match="CONTRACT_ID"):
        await soroban.renew_record_ttl_on_chain("ab" * 32, CONTRACT_TTL_EXTEND_TO)
