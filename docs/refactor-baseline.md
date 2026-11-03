# Refactor Baseline — 2026-11-03

Snapshot of the test suite and code size before the refactor begins. All values
below are copied from command output on this date; rerun the commands to
refresh them.

## Tests

| Suite | Command | Result |
|---|---|---|
| Backend | `cd backend && uv run pytest -q` | 402 passed, 0 failed |
| Frontend | `cd frontend && npm test -- --run` | 329 passed across 34 test files, 0 failed |

## Backend coverage

Command: `cd backend && uv run pytest --cov=app -q`

```
TOTAL                          1305     11    99%
```

**99%** statement coverage (1305 statements, 11 missed).

## Line counts

Command: `git ls-files backend/app frontend/src | xargs wc -l`

| Scope | Lines |
|---|---:|
| `backend/app` | 4,158 |
| `frontend/src` | 4,244 |
| **Total** | **8,402** |

## Largest files

Command: `git ls-files backend/app frontend/src | xargs wc -l | sort -rn | head -30`

| Lines | File |
|---:|---|
| 631 | `backend/app/services/soroban.py` |
| 538 | `frontend/src/components/BatchAnchorFlow.tsx` |
| 513 | `backend/app/services/ttl_renewal.py` |
| 386 | `frontend/src/components/SingleAnchorFlow.tsx` |
| 358 | `backend/app/api/v1/datasets.py` |
| 305 | `backend/app/api/v1/batches.py` |
| 291 | `backend/app/services/parser.py` |
| 277 | `backend/app/services/anomaly.py` |
| 232 | `frontend/src/components/CsvDropzone.tsx` |
| 228 | `backend/app/services/validation.py` |
| 206 | `backend/app/config.py` |
| 198 | `frontend/src/pages/DatasetDetailPage.tsx` |
| 179 | `frontend/src/utils/csv.ts` |
| 167 | `backend/app/models/dataset.py` |
| 165 | `frontend/src/pages/VerifyPage.tsx` |

## Type check

Command: `cd frontend && npx tsc --noEmit` — passes with no diagnostics.
