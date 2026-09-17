#!/usr/bin/env python3
"""Generate the GeoGuard Ledger mark.

The mark is drawn once, in the same 1024x1024 coordinate space as the SVG:

  * a violet disc, the avatar background,
  * a white shield with a padlock punched out of it,
  * an emerald keyhole, the one green cue in an otherwise violet mark.

This script is the single source of truth, so the SVG and the PNGs can never
drift apart. It writes:

    assets/logo.svg                        scalable mark (README, docs, previews)
    assets/logo-{size}.png                 avatar uploads that reject SVG
    frontend/public/favicon.svg            served by Vite as the site icon
    frontend/public/favicon-32.png         PNG fallback for browsers ignoring SVG
    frontend/public/apple-touch-icon.png   opaque square variant, for iOS home screens
    frontend/public/og-image.png           social card for link previews (1200x630)

There is no SVG rasteriser in this toolchain (no rsvg-convert, inkscape, or
cairo), so the PNGs are rendered here: the shapes are flattened to polygons,
scanned row by row, and supersampled. Only the standard library is used.

Usage:
    # From the repository root:
    python3 scripts/generate_logo.py

    # Check the shape as ASCII art before writing anything:
    python3 scripts/generate_logo.py --preview

    # Verify the committed assets are still what this script produces (CI does
    # this, so editing the geometry without re-running the script fails):
    python3 scripts/generate_logo.py --check
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "assets"
FRONTEND_PUBLIC_DIR = REPO_ROOT / "frontend" / "public"

VIEWBOX = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

DEFAULT_SIZES = (1024, 512, 256, 128)
FAVICON_SIZE = 32
APPLE_TOUCH_SIZE = 180
PREVIEW_SIZE = 96

# The social card: the 1.91:1 shape Facebook and Twitter crop to without
# letterboxing. The shield sits above the project name, with the pair centred on
# the card: the shield spans 340px of the 630, the name another 48.
OG_WIDTH, OG_HEIGHT = 1200, 630
OG_MARK_HEIGHT = 726
OG_MARK_CENTRE_Y = 238.0
OG_WORDMARK = "GEOGUARD LEDGER"
OG_WORDMARK_HEIGHT = 48.0
OG_WORDMARK_CENTRE_Y = 500.0

# Brand violet, light to dark along the disc's diagonal (README badges use
# #7C3AED; the deep end matches the `stellar.dark` Token in the frontend theme).
GRADIENT_TOP = (0x7C, 0x3A, 0xED)
GRADIENT_BOTTOM = (0x4C, 0x1D, 0x95)
SHIELD_FILL = (0xFF, 0xFF, 0xFF)
KEYHOLE_FILL = (0x10, 0xB9, 0x81)

DISC_CENTER = 512.0
DISC_RADIUS = 512.0

# Tucked inside the shield: the padlock that gets punched out, then the keyhole
# painted back on top of the hole.
BODY_X, BODY_Y, BODY_W, BODY_H, BODY_R = 402.0, 500.0, 220.0, 150.0, 26.0
SHACKLE_OUTER_R, SHACKLE_INNER_R = 80.0, 44.0
SHACKLE_BASE_Y = 500.0
KEYHOLE_CENTER = (512.0, 545.0)
KEYHOLE_RADIUS = 25.0
KEYHOLE_STEM = ((499.0, 556.0), (525.0, 556.0), (512.0, 600.0))

# Curve flattening budget. A 32-segment polyline over the shield's bottom
# quarter deviates from the true quadratic by well under a tenth of a
# supersampled pixel, so the raster matches the SVG closely.
CURVE_STEPS = 32

# Layer codes, painted in this order: each one covers the one before it, and the
# wordmark goes on last of all.
DISC, SHIELD, LOCK, KEYHOLE, TEXT = 1, 2, 3, 4, 5


class PathBuilder:
    """Builds an SVG `d` string while flattening the same path to polygons.

    Only the commands this mark needs are implemented. `arc_to` is restricted
    to semicircles, which is all the padlock shackle uses: for a 180-degree arc
    the centre is the chord midpoint and the radius is half the chord, so the
    arc can be sampled without a general elliptical-arc implementation.
    """

    def __init__(self, steps: int = CURVE_STEPS) -> None:
        self._commands: list[str] = []
        self.points: list[tuple[float, float]] = []
        self._steps = steps
        self._x = 0.0
        self._y = 0.0

    def _number(self, value: float) -> str:
        return f"{value:g}"

    def move_to(self, x: float, y: float) -> None:
        self._commands.append(f"M{self._number(x)} {self._number(y)}")
        self._x, self._y = x, y
        self.points.append((x, y))

    def line_to(self, x: float, y: float) -> None:
        self._commands.append(f"L{self._number(x)} {self._number(y)}")
        self._x, self._y = x, y
        self.points.append((x, y))

    def quad_to(self, cx: float, cy: float, x: float, y: float) -> None:
        self._commands.append(
            f"Q{self._number(cx)} {self._number(cy)} {self._number(x)} {self._number(y)}"
        )
        x0, y0 = self._x, self._y
        for step in range(1, self._steps + 1):
            t = step / self._steps
            u = 1 - t
            self.points.append(
                (
                    u * u * x0 + 2 * u * t * cx + t * t * x,
                    u * u * y0 + 2 * u * t * cy + t * t * y,
                )
            )
        self._x, self._y = x, y

    def arc_to(self, radius: float, sweep: int, x: float, y: float) -> None:
        """Draw a semicircle to (x, y). `sweep=1` is clockwise, as in SVG."""
        self._commands.append(
            f"A{self._number(radius)} {self._number(radius)} 0 0 {sweep} "
            f"{self._number(x)} {self._number(y)}"
        )
        x0, y0 = self._x, self._y
        cx, cy = (x0 + x) / 2, (y0 + y) / 2
        start = math.atan2(y0 - cy, x0 - cx)
        # In SVG's y-down space, increasing angle reads as clockwise on screen.
        direction = 1 if sweep else -1
        for step in range(1, self._steps + 1):
            angle = start + direction * math.pi * step / self._steps
            self.points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        self._x, self._y = x, y

    def close(self) -> None:
        self._commands.append("Z")

    def d(self) -> str:
        return " ".join(self._commands)

    def polygon(self) -> list[tuple[float, float]]:
        return list(self.points)


def shield_path() -> PathBuilder:
    path = PathBuilder()
    path.move_to(308, 300)
    path.line_to(716, 300)
    path.quad_to(732, 300, 732, 316)
    path.line_to(732, 600)
    path.quad_to(732, 690, 512, 780)
    path.quad_to(292, 690, 292, 600)
    path.line_to(292, 316)
    path.quad_to(292, 300, 308, 300)
    path.close()
    return path


def shackle_path() -> PathBuilder:
    """The horseshoe above the lock body, as one filled shape.

    The legs run a couple of units past the body's top edge; the two are unioned
    when punched out, so the overlap is invisible.
    """
    path = PathBuilder()
    path.move_to(432, 502)
    path.line_to(432, SHACKLE_BASE_Y)
    path.arc_to(SHACKLE_OUTER_R, 1, 592, SHACKLE_BASE_Y)
    path.line_to(592, 502)
    path.line_to(556, 502)
    path.line_to(556, SHACKLE_BASE_Y)
    path.arc_to(SHACKLE_INNER_R, 0, 468, SHACKLE_BASE_Y)
    path.line_to(468, 502)
    path.close()
    return path


def keyhole_stem_polygon() -> list[tuple[float, float]]:
    return list(KEYHOLE_STEM)


def rounded_rect_polygon(steps: int = 8) -> list[tuple[float, float]]:
    """Sample the lock body, matching an SVG `<rect rx>`."""
    x0, y0 = BODY_X + BODY_R, BODY_Y + BODY_R
    x1, y1 = BODY_X + BODY_W - BODY_R, BODY_Y + BODY_H - BODY_R
    corners = (
        (x1, y0, -math.pi / 2, 0.0),
        (x1, y1, 0.0, math.pi / 2),
        (x0, y1, math.pi / 2, math.pi),
        (x0, y0, math.pi, 3 * math.pi / 2),
    )
    points: list[tuple[float, float]] = []
    for cx, cy, start, end in corners:
        for step in range(steps + 1):
            angle = start + (end - start) * step / steps
            points.append((cx + BODY_R * math.cos(angle), cy + BODY_R * math.sin(angle)))
    return points


# --- Wordmark lettering ---
#
# The social card's wordmark is hand-built rather than typeset: the generator
# has no font engine and no dependencies, so the eight letters "GEOGUARD
# LEDGER" needs are drawn here as geometry. Everything is measured in a cell
# that is GLYPH_CAP units tall — the cap height — with the origin at its
# top-left, and every curve is a circular arc so the shapes stay consistent
# with the mark's shackle.

GLYPH_CAP = 100.0
GLYPH_STROKE = 18.0
GLYPH_TRACKING = 24.0
SPACE_ADVANCE = 50.0


def _rect(x: float, y: float, width: float, height: float) -> list[tuple[float, float]]:
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]


def _ring(
    cx: float,
    cy: float,
    radius: float,
    start: float,
    end: float,
    steps: int = 48,
) -> list[tuple[float, float]]:
    """An annular sector, as one polygon: outer arc out, inner arc back.

    A full 360-degree sweep closes into a ring, and the two contours inside one
    polygon are exactly what the even-odd scanline fill reads as a hole.
    """
    inner = radius - GLYPH_STROKE
    points: list[tuple[float, float]] = []
    for step in range(steps + 1):
        angle = math.radians(start + (end - start) * step / steps)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    for step in range(steps, -1, -1):
        angle = math.radians(start + (end - start) * step / steps)
        points.append((cx + inner * math.cos(angle), cy + inner * math.sin(angle)))
    return points


def _glyphs() -> dict[str, tuple[float, list[list[tuple[float, float]]]]]:
    """Each letter as its advance width and the shapes that draw it.

    Bowls are half rings whose flat side meets the stem, so a circular arc gives
    the geometric look without needing elliptical support. Angles are degrees,
    clockwise from three o'clock, because y grows downwards.
    """
    stem = GLYPH_STROKE
    return {
        # A full ring, as wide as it is tall.
        "O": (100.0, [_ring(50, 50, 50, 0, 360, steps=64)]),
        # The same ring with a 30-degree gap above three o'clock, plus the bar.
        "G": (100.0, [_ring(50, 50, 50, 0, 330, steps=64), _rect(50, 41, 50, stem)]),
        # Two stems joined by the bottom half ring.
        "U": (
            100.0,
            [_rect(0, 0, stem, 50), _rect(82, 0, stem, 50), _ring(50, 50, 50, 0, 180)],
        ),
        # A silhouette with the counter cut out of it, plus the crossbar.
        "A": (
            100.0,
            [
                [(50, 0), (100, 100), (82, 100), (50, 36), (18, 100), (0, 100)],
                _rect(24, 66, 52, stem),
            ],
        ),
        # Stem, full-length top and bottom arms, and the shortened middle one.
        "E": (
            68.0,
            [
                _rect(0, 0, stem, 100),
                _rect(stem, 0, 50, stem),
                _rect(stem, 41, 34, stem),
                _rect(stem, 82, 50, stem),
            ],
        ),
        # Stem and foot.
        "L": (60.0, [_rect(0, 0, stem, 100), _rect(stem, 82, 42, stem)]),
        # Stem plus a bowl whose flat side is the stem's right edge.
        "D": (68.0, [_rect(0, 0, stem, 100), _ring(18, 50, 50, -90, 90)]),
        # Same bowl, stopped two thirds down, with the leg kicking out right.
        "R": (
            68.0,
            [
                _rect(0, 0, stem, 100),
                _ring(18, 32, 32, -90, 90),
                [(32, 50), (50, 50), (68, 100), (50, 100)],
            ],
        ),
        " ": (SPACE_ADVANCE, []),
    }


_GLYPHS = _glyphs()


def wordmark_polygons(
    text: str,
    cap_height: float,
    centre_x: float,
    top_y: float,
) -> list[list[tuple[float, float]]]:
    """Lay `text` out as polygons in output pixels, centred on `centre_x`."""
    text = text.upper()
    shapes: list[list[tuple[float, float]]] = []
    for character in set(text):
        if character not in _GLYPHS:
            letters = " ".join(sorted(set(_GLYPHS) - {" "}))
            raise ValueError(f"no letterform for {character!r} — the wordmark has {letters}")

    scale = cap_height / GLYPH_CAP
    advances = [_GLYPHS[character][0] for character in text]
    width = sum(advances) + GLYPH_TRACKING * (len(text) - 1)
    x = centre_x - width * scale / 2
    for character, advance in zip(text, advances, strict=True):
        for shape in _GLYPHS[character][1]:
            shapes.append([(x + px * scale, top_y + py * scale) for px, py in shape])
        x += (advance + GLYPH_TRACKING) * scale
    return shapes


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def svg_markup() -> str:
    """The mark as standalone SVG."""
    top = _hex(GRADIENT_TOP)
    bottom = _hex(GRADIENT_BOTTOM)
    keyhole = _hex(KEYHOLE_FILL)
    stem = " ".join(
        f"{command}{x:g} {y:g}"
        for command, (x, y) in zip("ML", KEYHOLE_STEM[:2], strict=True)
    )
    stem_tip = f"{KEYHOLE_STEM[2][0]:g} {KEYHOLE_STEM[2][1]:g}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEWBOX} {VIEWBOX}" \
width="{VIEWBOX}" height="{VIEWBOX}" role="img" aria-labelledby="logo-title logo-desc">
  <title id="logo-title">GeoGuard Ledger</title>
  <desc id="logo-desc">A white shield with a padlock cut out of it, over a violet disc.</desc>
  <defs>
    <linearGradient id="logo-disc" x1="0" y1="0" x2="{VIEWBOX}" y2="{VIEWBOX}" \
gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{top}"/>
      <stop offset="1" stop-color="{bottom}"/>
    </linearGradient>
    <mask id="logo-lockout" maskUnits="userSpaceOnUse" x="0" y="0" \
width="{VIEWBOX}" height="{VIEWBOX}">
      <rect width="{VIEWBOX}" height="{VIEWBOX}" fill="#fff"/>
      <g fill="#000">
        <rect x="{BODY_X:g}" y="{BODY_Y:g}" width="{BODY_W:g}" height="{BODY_H:g}" \
rx="{BODY_R:g}"/>
        <path d="{shackle_path().d()}"/>
      </g>
    </mask>
  </defs>
  <circle cx="{DISC_CENTER:g}" cy="{DISC_CENTER:g}" r="{DISC_RADIUS:g}" \
fill="url(#logo-disc)"/>
  <path d="{shield_path().d()}" fill="#fff" mask="url(#logo-lockout)"/>
  <circle cx="{KEYHOLE_CENTER[0]:g}" cy="{KEYHOLE_CENTER[1]:g}" r="{KEYHOLE_RADIUS:g}" \
fill="{keyhole}"/>
  <path d="{stem} L{stem_tip} Z" fill="{keyhole}"/>
</svg>
"""


def _polygon_spans(polygon: list[tuple[float, float]], y: float) -> list[tuple[float, float]]:
    """Where a horizontal scanline crosses a closed polygon (even-odd)."""
    crossings: list[float] = []
    count = len(polygon)
    for index in range(count):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % count]
        if y0 == y1:
            continue
        # Half-open rule, so a vertex on the scanline is counted once.
        if min(y0, y1) <= y < max(y0, y1):
            crossings.append(x0 + (y - y0) / (y1 - y0) * (x1 - x0))
    crossings.sort()
    return list(zip(crossings[0::2], crossings[1::2], strict=False))


def _circle_span(cx: float, cy: float, r: float, y: float) -> tuple[float, float] | None:
    inside = r * r - (y - cy) ** 2
    if inside <= 0:
        return None
    half = math.sqrt(inside)
    return (cx - half, cx + half)


def _merge(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Union of spans: the padlock is body ∪ shackle, not their symmetric difference."""
    merged: list[tuple[float, float]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _add_span(counter: list[float], start: float, end: float, supersample: int) -> None:
    """Spread a span's subsamples across the output pixels it covers."""
    first = int(start // supersample)
    last = int((end - 1e-6) // supersample)
    if first == last:
        counter[first] += end - start
        return
    counter[first] += (first + 1) * supersample - start
    for index in range(first + 1, last):
        counter[index] += supersample
    counter[last] += end - last * supersample


def render(
    width: int,
    height: int,
    supersample: int,
    *,
    square_background: bool = False,
    mark_height: int | None = None,
    mark_centre: tuple[float, float] | None = None,
    wordmark: str | None = None,
    wordmark_height: float = 0.0,
    wordmark_centre_y: float = 0.0,
) -> list[list[tuple[float, float, float, float]]]:
    """Rasterise the mark. Returns rows of (r, g, b, a) floats in 0..1.

    Coverage is accumulated per layer and composited analytically, which is the
    same result as painting the layers in order but lets the punch-out be
    expressed as "shield minus lock" instead of a fill rule.

    `square_background` fills the whole canvas with the disc's gradient instead
    of clipping it to a circle. That is what iOS wants: it masks an
    apple-touch-icon to a rounded square and paints transparent pixels black,
    so the disc would otherwise sit on a black tile. Filling with the same
    gradient makes the disc's rim disappear into the background, which is also
    how the social card is drawn.

    `mark_height` is the pixel height the mark's 1024-unit box is scaled to, and
    `mark_centre` is where that box sits on the canvas. The height defaults to
    the canvas's shorter side and the centre to the canvas centre, which is what
    makes the mark fill a square canvas edge to edge.

    `wordmark`, with `wordmark_height` and `wordmark_centre_y`, draws the project
    name in white across the middle of the canvas, centred horizontally. It is
    expected to sit clear of the mark; the two are drawn as if the wordmark were
    on top, so overlapping them would punch a hole rather than layer cleanly.
    """
    grid_width = width * supersample
    scale = (mark_height if mark_height is not None else min(width, height)) / VIEWBOX
    centre_x, centre_y = mark_centre if mark_centre is not None else (width / 2, height / 2)

    def place(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Map mark coordinates onto the canvas, in subsample units."""
        return [
            (
                ((x - DISC_CENTER) * scale + centre_x) * supersample,
                ((y - DISC_CENTER) * scale + centre_y) * supersample,
            )
            for x, y in points
        ]

    disc_centre = place([(DISC_CENTER, DISC_CENTER)])[0]
    disc_radius = DISC_RADIUS * scale * supersample
    shield = place(shield_path().polygon())
    body = place(rounded_rect_polygon())
    shackle = place(shackle_path().polygon())
    stem = place(keyhole_stem_polygon())
    keyhole_centre = place([KEYHOLE_CENTER])[0]
    keyhole_radius = KEYHOLE_RADIUS * scale * supersample

    text_shapes: list[list[tuple[float, float]]] = []
    if wordmark is not None:
        text_shapes = [
            [(x * supersample, y * supersample) for x, y in shape]
            for shape in wordmark_polygons(
                wordmark,
                wordmark_height,
                width / 2,
                wordmark_centre_y - wordmark_height / 2,
            )
        ]

    rows: list[list[tuple[float, float, float, float]]] = []
    for row_index in range(height):
        coverage = {code: [0.0] * width for code in (DISC, SHIELD, LOCK, KEYHOLE, TEXT)}
        for sub_row in range(row_index * supersample, (row_index + 1) * supersample):
            y = sub_row + 0.5
            disc_span: tuple[float, float] | None
            if square_background:
                disc_span = (0.0, float(grid_width))
            else:
                disc_span = _circle_span(*disc_centre, disc_radius, y)
            if disc_span is not None:
                _add_span(coverage[DISC], *disc_span, supersample)

            for span in _polygon_spans(shield, y):
                _add_span(coverage[SHIELD], *span, supersample)

            lock_spans: list[tuple[float, float]] = []
            for polygon in (body, shackle):
                lock_spans.extend(_polygon_spans(polygon, y))
            for span in _merge(lock_spans):
                _add_span(coverage[LOCK], *span, supersample)

            keyhole_spans = _polygon_spans(stem, y)
            keyhole_span = _circle_span(*keyhole_centre, keyhole_radius, y)
            if keyhole_span is not None:
                keyhole_spans.append(keyhole_span)
            for span in _merge(keyhole_spans):
                _add_span(coverage[KEYHOLE], *span, supersample)

            # Glyphs overlap deliberately (a stem into a bowl, and so on), so
            # the spans are unioned before they are counted.
            text_spans: list[tuple[float, float]] = []
            for shape in text_shapes:
                text_spans.extend(_polygon_spans(shape, y))
            for span in _merge(text_spans):
                _add_span(coverage[TEXT], *span, supersample)

        samples = supersample * supersample
        disc_row, shield_row = coverage[DISC], coverage[SHIELD]
        lock_row, keyhole_row = coverage[LOCK], coverage[KEYHOLE]
        text_row = coverage[TEXT]
        pixel_row: list[tuple[float, float, float, float]] = []
        for column in range(width):
            white = max(0.0, shield_row[column] + text_row[column] - lock_row[column])
            green = keyhole_row[column]
            gradient = (
                max(0.0, disc_row[column] - shield_row[column] - text_row[column])
                + max(0.0, lock_row[column] - keyhole_row[column])
            )
            colour = white + green + gradient
            if colour <= 0:
                pixel_row.append((0.0, 0.0, 0.0, 0.0))
                continue
            # The gradient is smooth, so one sample per pixel is enough.
            t = ((column + 0.5) + (row_index + 0.5)) / (width + height)
            gradient_rgb = tuple(
                top + (bottom - top) * t
                for top, bottom in zip(GRADIENT_TOP, GRADIENT_BOTTOM, strict=True)
            )
            blended = [
                (
                    SHIELD_FILL[channel] * white
                    + KEYHOLE_FILL[channel] * green
                    + gradient_rgb[channel] * gradient
                )
                / colour
                for channel in range(3)
            ]
            pixel_row.append(
                (
                    blended[0] / 255,
                    blended[1] / 255,
                    blended[2] / 255,
                    disc_row[column] / samples,
                )
            )
        rows.append(pixel_row)
    return rows


def downsample(
    image: list[list[tuple[float, float, float, float]]], factor: int
) -> list[list[tuple[float, float, float, float]]]:
    """Box-filter by an integer factor, weighting colour by alpha so the disc's
    edge does not fringe against transparent pixels."""
    height = len(image)
    width = len(image[0])
    samples = factor * factor
    reduced: list[list[tuple[float, float, float, float]]] = []
    for row_index in range(0, height, factor):
        row: list[tuple[float, float, float, float]] = []
        for column in range(0, width, factor):
            totals = [0.0, 0.0, 0.0, 0.0]
            for dy in range(factor):
                source = image[row_index + dy]
                for dx in range(factor):
                    r, g, b, a = source[column + dx]
                    totals[0] += r * a
                    totals[1] += g * a
                    totals[2] += b * a
                    totals[3] += a
            if totals[3] <= 0:
                row.append((0.0, 0.0, 0.0, 0.0))
            else:
                row.append(
                    (
                        totals[0] / totals[3],
                        totals[1] / totals[3],
                        totals[2] / totals[3],
                        totals[3] / samples,
                    )
                )
        reduced.append(row)
    return reduced


def scanlines(image: list[list[tuple[float, float, float, float]]]) -> bytes:
    """The bytes a PNG stores: one filter byte per row, then RGBA per pixel."""
    raw = bytearray()
    for row in image:
        raw.append(0)  # filter type 0 (None)
        for r, g, b, a in row:
            raw.extend((round(r * 255), round(g * 255), round(b * 255), round(a * 255)))
    return bytes(raw)


def write_png(path: Path, image: list[list[tuple[float, float, float, float]]]) -> None:
    width, height = len(image[0]), len(image)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunks = b"".join(
        (
            struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
            for name, data in (
                (b"IHDR", header),
                (b"IDAT", zlib.compress(scanlines(image), 9)),
                (b"IEND", b""),
            )
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_SIGNATURE + chunks)


def read_png(path: Path) -> tuple[int, int, bytes]:
    """Decode a PNG this script wrote, returning its stored byte stream.

    That stream is exactly what `scanlines` builds — a filter byte per row, then
    RGBA per pixel — so it can be compared directly with a freshly rendered
    image.

    The drift check compares this rather than the file's raw bytes on purpose:
    zlib's deflate output is not identical across versions, so a byte
    comparison would fail on a runner whose Python links a different zlib than
    the one that produced the committed files.
    """
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG")
    header = b""
    compressed = bytearray()
    position = len(PNG_SIGNATURE)
    while position < len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        name = data[position + 4 : position + 8]
        body = data[position + 8 : position + 8 + length]
        if name == b"IHDR":
            header = body
        elif name == b"IDAT":
            compressed += body
        position += 12 + length
    width, height, depth, colour = struct.unpack(">IIBB", header[:10])
    if (depth, colour) != (8, 6):
        raise ValueError(f"expected RGBA8, found depth={depth} colour type={colour}")
    raw = zlib.decompress(bytes(compressed))
    stride = 1 + 4 * width
    if len(raw) != stride * height:
        raise ValueError(f"expected {stride * height} bytes of pixels, found {len(raw)}")
    for row in range(height):
        row_start = row * stride
        if raw[row_start] != 0:
            raise ValueError(f"unexpected PNG filter {raw[row_start]} in row {row}")
    return width, height, raw


def preview(image: list[list[tuple[float, float, float, float]]]) -> str:
    """Render the mark as ASCII art, for eyeballing the shape in a terminal."""
    lines: list[str] = []
    for row_index in range(0, len(image), 2):
        line = []
        for r, g, b, a in image[row_index]:
            if a < 0.35:
                line.append(" ")
            elif g > max(r, b):
                line.append("o")  # keyhole
            elif min(r, g, b) > 0.72:
                line.append("#")  # white shield
            else:
                line.append(".")  # violet disc, and the punched-out padlock
        lines.append("".join(line))
    return "\n".join(lines)


def _scaled(
    master: list[list[tuple[float, float, float, float]]],
    master_size: int,
    size: int,
    supersample: int,
) -> list[list[tuple[float, float, float, float]]]:
    """Take `size` from the master where it divides evenly, else render afresh."""
    if size == master_size:
        return master
    if master_size % size == 0:
        return downsample(master, master_size // size)
    return render(size, size, supersample)


def _report_drift(
    svgs: dict[Path, str],
    images: dict[Path, list[list[tuple[float, float, float, float]]]],
) -> int:
    """Compare generated output against the committed files. Returns an exit code."""
    stale: list[tuple[Path, str]] = []
    for path, text in svgs.items():
        if not path.exists():
            stale.append((path, "missing"))
        elif path.read_text(encoding="utf-8") != text:
            stale.append((path, "differs"))
    for path, image in images.items():
        if not path.exists():
            stale.append((path, "missing"))
            continue
        try:
            width, height, pixels = read_png(path)
        except (ValueError, zlib.error) as error:
            stale.append((path, f"unreadable: {error}"))
            continue
        if (width, height) != (len(image[0]), len(image)) or pixels != scanlines(image):
            stale.append((path, "differs"))

    if not stale:
        print(f"{len(svgs) + len(images)} generated files are up to date")
        return 0
    print("Committed logo assets are stale — run scripts/generate_logo.py and commit:")
    for path, reason in stale:
        print(f"  {path.relative_to(REPO_ROOT)} ({reason})")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--supersample",
        type=int,
        default=2,
        help="subsamples per axis in the master render (default: 2)",
    )
    parser.add_argument(
        "--sizes",
        default=",".join(str(size) for size in DEFAULT_SIZES),
        help="comma-separated PNG sizes to emit (default: %(default)s)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="print the mark as ASCII art and exit without writing files",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed assets match this script without writing anything",
    )
    args = parser.parse_args()

    sizes = [int(size) for size in args.sizes.split(",")]
    # Render once at the largest size and box-filter down, so every PNG shares
    # the master's antialiasing instead of being scanned separately.
    master_size = max(*sizes, FAVICON_SIZE, VIEWBOX)

    if args.preview:
        print(preview(render(PREVIEW_SIZE, PREVIEW_SIZE, 2)))
        return

    svg = svg_markup()
    master = render(master_size, master_size, args.supersample)
    svgs = {ASSETS_DIR / "logo.svg": svg, FRONTEND_PUBLIC_DIR / "favicon.svg": svg}
    images = {
        ASSETS_DIR / f"logo-{size}.png": _scaled(master, master_size, size, args.supersample)
        for size in sizes
    }
    images[FRONTEND_PUBLIC_DIR / f"favicon-{FAVICON_SIZE}.png"] = downsample(
        master, master_size // FAVICON_SIZE
    )
    # The one variant that is not a plain scaled copy of the mark: iOS masks this
    # to a rounded square and paints transparent pixels black, so it is rendered
    # with an opaque square background. Going through a 2x render and filtering
    # down gives it the same effective subsampling as the PNGs above.
    images[FRONTEND_PUBLIC_DIR / "apple-touch-icon.png"] = downsample(
        render(
            APPLE_TOUCH_SIZE * 2,
            APPLE_TOUCH_SIZE * 2,
            args.supersample,
            square_background=True,
        ),
        2,
    )
    # The social card lives in the frontend's static directory rather than
    # assets/: it is referenced by /og-image.png, so the site has to serve it.
    images[FRONTEND_PUBLIC_DIR / "og-image.png"] = render(
        OG_WIDTH,
        OG_HEIGHT,
        args.supersample,
        square_background=True,
        mark_height=OG_MARK_HEIGHT,
        mark_centre=(OG_WIDTH / 2, OG_MARK_CENTRE_Y),
        wordmark=OG_WORDMARK,
        wordmark_height=OG_WORDMARK_HEIGHT,
        wordmark_centre_y=OG_WORDMARK_CENTRE_Y,
    )

    if args.check:
        sys.exit(_report_drift(svgs, images))

    for path, text in svgs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    for path, image in images.items():
        write_png(path, image)
        print(f"wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
