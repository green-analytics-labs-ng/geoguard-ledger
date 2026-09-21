# Accessibility notes

What was found, what was fixed, and what is still open. The frontend review that
prompted this work counted six `aria`/`role` attributes across all of `src`, no
`htmlFor` anywhere, and two `<label>` elements — for five forms and a data
preview table.

## How it is enforced now

- **`eslint-plugin-jsx-a11y`** (`plugin:jsx-a11y/recommended` in
  `frontend/.eslintrc.cjs`) fails the build on an unlabelled control, a click
  handler on a non-interactive element, or a missing alt text. Lint runs in CI,
  so these are caught while the component is written rather than in an audit.
- **`tests/a11y/pages.test.tsx`** renders every route through the real `App` —
  shell, navigation and page — and asserts `axe` finds no violations. `axe` is
  registered as a matcher in `tests/setup.ts`, which `vite.config.ts` loads for
  every suite.

## Fixed

| Finding | Fix |
| --- | --- |
| Five pages each drew their own nav, so the header changed shape as you navigated | One `AppLayout` owns the header; `NavLink` marks the current section with `aria-current="page"` |
| No way past the nav for keyboard users | Skip-to-content link, first in the tab order, hidden until focused; `<main>` is `tabIndex={-1}` so focus actually lands there |
| The file picker in `CsvDropzone` was a `<div>` with an `onClick` — no role, no tab stop, no key handler | A real `<button>` opens the picker, so it is reachable and activates on Enter and Space |
| Dropzone errors appeared as a plain `<div>` after the user acted | `role="alert"`, plus `aria-describedby` linking the control to the message |
| Upload and anchor progress swapped silently | `role="status" aria-live="polite"` on the route-loading fallback and progress regions |
| Real errors were unannounced | `ErrorBanner` and `ErrorBoundary` both use `role="alert"` |
| `VerifyPage` labels were not associated with their inputs | `htmlFor`/`id` on both the hash and the file input |
| The anomaly level was carried by colour alone | `AnomalyBadge` renders the level as text (`Normal`, `Suspect`, `Anomalous`) next to the percentage |

## Open

- **Colour contrast is not machine-checked.** `axe`'s `color-contrast` rule
  needs a layout engine, and the suite runs in jsdom, so the rule is disabled in
  `tests/a11y/pages.test.tsx` rather than left on to pass vacuously. Contrast
  rests on the palette in `docs/brand.md` and on review.
- **No screen-reader pass.** The automated checks cover names, roles and
  relationships, not whether the order makes sense when read aloud. The
  anchor flows in particular announce step changes by swapping the whole
  subtree; a manual pass would say whether that is enough.
- **Focus management on step change is unverified.** Moving from one step of the
  upload flow to the next replaces the content without moving focus, so a
  keyboard user stays where the control they activated used to be.
