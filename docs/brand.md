# GeoGuard Ledger — Brand Assets

The project mark, the palette it draws from, and how to regenerate it. Every
asset here is produced by `scripts/generate_logo.py`, so the numbers in that
script are the source of truth: change them, re-run it, and commit the result.

## 1. The mark

A white shield with a padlock punched out of it, on a violet disc.

The padlock is the same idea as the glyph in the README's wordmark badge — a
ledger entry nobody can alter — and punching it *through* the shield, rather
than drawing it on top, is what makes the shield read as intact rather than
decorated. The hole shows the disc's gradient, so the mark is built from flat
areas with no outlines — nothing to blur into mush at favicon size.

The disc is deliberately full-bleed: it touches all four edges of the canvas, so
GitHub's circular avatar crop lands exactly on its rim and never reveals a
transparent corner. That is also why there is no separate "circular" variant —
one square asset works for the avatar, the browser tab, and the README header —
the iOS home-screen icon is the one exception, and it differs only in how the
background is drawn (§3).

## 2. Palette

| Role | Colour | Notes |
|---|---|---|
| Disc gradient, top-left | `#7C3AED` | The brand violet already used by the README badge and the "active development" badge |
| Disc gradient, bottom-right | `#4C1D95` | Deep end of the same violet ramp, roughly the family of the frontend's `stellar` tokens (`#3E1BDB`, dark `#2B1399`) |
| Shield | `#FFFFFF` | Neutral on both light and dark page backgrounds |
| Keyhole | `#10B981` | Emerald-500. The README architecture diagram marks the AI layer with the darker `#059669` from the same ramp |

The gradient runs corner to corner across the 1024×1024 canvas, so the punched
padlock and the keyhole sit against its mid-violet, where the white shield
around them gives them the most contrast.

## 3. Files

| Path | Size | Used by |
|---|---|---|
| `assets/logo.svg` | vector, 1024 viewBox | README header; anywhere a crisp scalable copy is needed |
| `assets/logo-1024.png` | 1024×1024 | Highest-resolution raster (social previews, print) |
| `assets/logo-512.png` | 512×512 | The one to upload where an avatar is scaled up from a source image |
| `assets/logo-256.png` | 256×256 | Smaller avatar slots |
| `assets/logo-128.png` | 128×128 | Inline or list contexts |
| `frontend/public/favicon.svg` | vector | Browser tab. Vite serves `public/` at `/`, and `index.html` links `/favicon.svg` |
| `frontend/public/favicon-32.png` | 32×32 | PNG fallback for the browsers and scrapers that ignore SVG icons |
| `frontend/public/apple-touch-icon.png` | 180×180 | iOS and iPadOS home-screen icon. Opaque and square-backed — see below |
| `frontend/public/og-image.png` | 1200×630 | Link previews on Slack, Discord, Twitter/X, Facebook, LinkedIn |

`assets/logo.svg` and `frontend/public/favicon.svg` are the same markup, written
to two paths because the frontend's static directory is the only place Vite will
serve it from. Both are regenerated together, so they cannot drift apart.

`apple-touch-icon.png` is the one asset that is not a scaled copy of the mark.
iOS masks an apple-touch-icon to a rounded square and paints any transparent
pixel black, so the full-bleed disc would land on the home screen as a black
tile with a violet circle inside it. That variant is rendered with the gradient
filling the whole square instead (`square_background=True` on `render()`), which
makes the disc's rim disappear into the background and leaves the shield reading
on its own. Everything else about the drawing is identical, so it still cannot
drift from the mark.

`og-image.png` uses that same opaque treatment, for a related reason: a link
preview has no transparency to fall back on, so the card is the gradient edge to
edge, with the shield above the project name and the pair centred on it.

The wordmark is hand-built rather than typeset. A font engine is a real
dependency to take on for a single string, so `_glyphs()` draws the eight
letters "GEOGUARD LEDGER" needs as geometry — circular rings for the bowls,
rectangles for the stems, one polygon for the `A` — sized in a 100-unit cap
height, the same way the mark's shackle is built from arcs. `wordmark_polygons()`
lays them out with fixed tracking, and it raises rather than guessing when asked
for a letter it does not have: extending the text means drawing the missing
letter first.

The card is wired up in `frontend/index.html` along with the icons, as the Open
Graph and Twitter tags (`og:title`, `og:image`, `twitter:card`, and the rest).
Those image URLs are relative to the site root, which every renderer except
Facebook and Twitter resolves. Twitter and Facebook ask for absolute URLs, so
once the app is deployed behind a real domain, `og:image` and `twitter:image`
are the two values to make absolute.

## 4. Regenerating

```bash
# From the repository root. Rewrites every file in the table above.
python3 scripts/generate_logo.py

# Look at the mark as ASCII art before writing anything.
python3 scripts/generate_logo.py --preview

# Confirm the committed assets still match the script. This is what CI runs.
python3 scripts/generate_logo.py --check
```

| Flag | Default | Effect |
|---|---|---|
| `--sizes` | `1024,512,256,128` | Comma-separated PNG sizes to emit alongside the SVGs |
| `--supersample` | `2` | Subsamples per axis in the master render; raise it for smoother edges |
| `--preview` | off | Print the mark as ASCII art and exit without writing files |
| `--check` | off | Compare the committed assets against freshly generated output, write nothing, and exit non-zero on any difference |

`--supersample` applies to every output, including the social card, which is
rendered at its full 1200×630 rather than filtered down from the master render.
Raise it if the shield's curves on the card look soft at 100%.

There is no SVG rasteriser in this toolchain — no `rsvg-convert`, Inkscape, or
cairo — and pulling one in for a handful of static files would not have earned
its keep, so the script renders the PNGs itself. Shapes are flattened to
polygons, scanned row by row, and supersampled; the largest size is rendered
once and box-filtered down, so every PNG shares the same antialiasing (a size
that does not divide the master evenly is rendered on its own instead). It uses
only the standard library, which is what lets the CI job above run without
installing anything.

## 5. What CI enforces

The `brand-assets` job runs `python3 scripts/generate_logo.py --check`, so a
change to the geometry that is not followed by a re-run fails the build rather
than silently leaving the README and the favicon showing a mark the code no
longer describes:

```text
Committed logo assets are stale — run scripts/generate_logo.py and commit:
  assets/logo-512.png (differs)
```

Fixing it means running the generator and committing the result. The check
reports a file as `missing`, `differs`, or `unreadable`, so a deleted or
truncated asset is caught by the same job.

One detail worth knowing if you extend the check: it compares *decoded pixels*,
not the files' bytes. Deflate output is not identical across zlib versions, so a
byte comparison would fail on a runner whose Python links a different zlib than
the one that produced the committed files — a false alarm that has nothing to do
with the mark.

## 6. Changing the mark

Everything is defined in the 1024×1024 coordinate space of the SVG's viewBox, at
the top of `scripts/generate_logo.py`:

- **Constants** — `GRADIENT_TOP`/`GRADIENT_BOTTOM`, `DISC_CENTER`/`DISC_RADIUS`,
  `BODY_*` (the padlock body), `SHACKLE_*` (its arch), `KEYHOLE_*`, and
  `CURVE_STEPS` (the flattening budget for curved edges).
- **Path builders** — `shield_path()`, `shackle_path()`,
  `rounded_rect_polygon()`, and `keyhole_stem_polygon()`. These build the SVG
  `d` strings and the polygons the rasteriser scans from the same numbers, so a
  shape never has to be described twice.
- **Card layout** — `OG_*`: the canvas size, where the mark sits and how big it
  is, and the wordmark's text, cap height, and centre line. The mark and the
  wordmark have to stay clear of each other; they are composited as if the
  wordmark were on top, so overlapping them would punch a hole in the shield
  rather than layer cleanly.
- **Letterforms** — `_glyphs()` holds each letter's advance width and shapes,
  with `GLYPH_CAP`, `GLYPH_STROKE`, and `GLYPH_TRACKING` setting the metrics.

Two properties are worth preserving:

- **The disc stays full-bleed.** Shrinking it, or rounding the square's corners,
  puts transparent pixels under GitHub's circular crop.
- **The mark still reads at 32px.** Run `--preview` after any change: the shield
  should stay the dominant shape and the padlock should still be obvious as a
  padlock. Fine detail — the keyhole in particular — is invisible at favicon
  size by design and carries the brand colour rather than any meaning.

Since the generator is the only thing that writes these files, a geometry change
is never complete until `python3 scripts/generate_logo.py` has been run and its
output committed; the CI job exists to make that hard to forget.
