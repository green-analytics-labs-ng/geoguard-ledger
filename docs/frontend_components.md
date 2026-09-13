# GeoGuard Ledger — Frontend Component Guide

Conventions for `frontend/src`, plus the accessibility rules new components are
expected to follow. The accessibility section lists what is already handled and
what is still open, so the open items do not get mistaken for finished work.

## 1. Directory layout

| Path | Holds |
|---|---|
| `src/components/` | Presentational components and multi-step flows, re-exported from `src/components/index.ts` |
| `src/pages/` | Route-level views, re-exported from `src/pages/index.ts`, lazy-loaded in `src/routes.tsx` |
| `src/hooks/` | Data and wallet hooks (`useDatasets`, `useVerify`, `useWallet`) |
| `src/api/` | Typed HTTP client, one module per backend resource |
| `src/utils/` | Pure functions (`csv`, `xml`, `merkle`, `stellar`) with no React dependency |
| `src/context/` | Cross-cutting state (`WalletContext`) |
| `src/types/` | Shared type declarations |
| `tests/` | Mirrors the source tree: `tests/components/`, `tests/pages/`, `tests/utils/`, `tests/app/` |

## 2. Component conventions

- **Default export is the component.** Named exports are for sub-parts that are
  useful on their own — `MerkleProof` also exports `ProofPath` and
  `InclusionVerdictBadge`.
- **Props live in a local `interface Props`** declared directly above the
  component. Export it only when another module genuinely needs it.
- **Optional props carry their default in the signature**, e.g.
  `showLabel = true`, `size = "sm"`, `showVerdict = true`, so call sites stay
  terse and the default is visible where it is defined.
- **Push logic out of the render path.** Anything that can be a pure function
  belongs in `src/utils` and is tested without rendering — for example the
  `inclusionVerdict` / `isInclusionVerified` helpers behind `MerkleProof`.
- **Register new modules in the barrel files**: components in
  `src/components/index.ts`, pages in `src/pages/index.ts`.
- **Pages are lazy.** `src/routes.tsx` wraps each page in `React.lazy`, and
  `src/App.tsx` renders them inside a `Suspense` boundary that sits *inside*
  `ErrorBoundary`, so a chunk that fails to download shows the recoverable
  fallback instead of a blank screen.

## 3. Styling

- **Tailwind utilities inline.** Reusable primitives live in `src/index.css`
  under `@layer components`: `.btn-primary`, `.btn-secondary`, `.card`,
  `.input-field`.
- **Use the theme tokens, not raw hex.** The brand colour is `stellar`
  (`#3E1BDB`) with `stellar-light` / `stellar-dark`; prefer `text-stellar` and
  friends so a rebrand is a one-file change.
- **Fonts:** Inter for UI text, JetBrains Mono for anything hash-shaped — use
  `font-mono` plus `break-all` for hashes, keys, and XDR so they wrap instead of
  overflowing their container.

## 4. Code style

- **Prettier** (`.prettierrc.json`): 100-column width, double quotes,
  semicolons, trailing commas. Run `npm run format` to write and
  `npm run format:check` to verify; the check runs in CI.
- **ESLint** runs with `--max-warnings 0`, so a new warning fails the build.
- **TypeScript is `strict`**, with `noUnusedLocals` and `noUnusedParameters` on.
- **Route rendering is asynchronous.** Because pages are lazy, tests asserting
  on a page must use `findBy*` rather than `getBy*`.

## 5. Testing

Tests use Vitest and React Testing Library, and every component under
`src/components` has a matching file in `tests/components`. Beyond the happy
path, cover the failure states — empty input, parse errors, unverified proofs,
and unavailable wallets all have tests today. `tests/app/routes.test.tsx` pins
the route table so a path cannot be added, removed, or duplicated silently.

## 6. Accessibility notes

### Already in place

- `ErrorBoundary` renders its fallback with `role="alert"`.
- The lazy-route loading fallback uses `role="status"` with `aria-live="polite"`.
- `MerkleProof` uses a heading for its title, an ordered list for the sibling
  path, and `<code>` for hashes, so the structure is exposed to assistive tech.
- `InclusionVerdictBadge` pairs its colour with a text label ("Verified
  on-chain", "Verified locally", "Not verified") and a checkmark icon, rather
  than signalling state by colour alone.
- The `CsvDropzone` preview is a semantic `<table>` with `<th>` header cells.
- The shared `.btn-primary` and `.input-field` classes include visible
  `focus:ring-*` states.

### Open gaps

| Component | Issue | Fix |
|---|---|---|
| `CsvDropzone` | The drop target is a `<div>` with `onClick` only — no `role`, `tabIndex`, or key handler — so keyboard users cannot open the file picker. The `<input type="file">` is `hidden` and unlabelled. | Use a `<button>`/`<label htmlFor>` wrapper, or add `role="button"`, `tabIndex={0}`, a key handler, and an accessible name for the input. |
| `CsvDropzone` | Parse errors render in a plain `<div>` with no `role="alert"` or `aria-live`, so they are not announced. | Add `role="alert"` to the error block. |
| `CsvDropzone` | The drag state swaps the instruction text in place with no announcement. | Announce drag enter/leave through a polite live region. |
| `CsvDropzone` | "Showing first 5 of N rows" is not associated with the table. | Tie it to the table with a `<caption>` or `aria-describedby`. |
| `AnomalyBadge` | With `showLabel={false}` the risk level is conveyed by colour and the percentage alone; the full description lives only in a `title` attribute, which is not reliably announced. | Render the risk level as visually hidden text (`sr-only`) so it is always available. |

### Rules for new components

1. Prefer semantic HTML; reach for ARIA only to fill a real gap.
2. Never encode meaning in colour alone — pair it with text.
3. Every interactive element must be keyboard reachable and show a visible focus
   indicator.
4. Announce asynchronous state changes — loading, errors, drag state — with
   `role="status"`, `role="alert"`, or an `aria-live` region.
5. Give every form control an accessible name via `<label>`, `aria-label`, or
   `aria-labelledby`.
