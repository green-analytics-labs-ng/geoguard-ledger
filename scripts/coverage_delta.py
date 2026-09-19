#!/usr/bin/env python3
"""Render coverage reports and their change since the base branch as Markdown.

The backend and the frontend each write coverage in their own job, so a pull
request has two numbers in two job logs and no single place that says whether
either moved. This script reads both, compares them with the same reports from
the base branch, and writes the comment that `ci.yml` posts.

Reports are found by file name, not by path, because the artifact a job uploads
flattens its directory structure:

    coverage.xml             Cobertura,      written by pytest-cov
    coverage-summary.json    Istanbul,       written by the v8 vitest provider

A report missing from the head run is reported as missing; a report missing
from the base run simply has no delta. Neither is an error: a job that failed
before it wrote coverage must not turn into a second failure here.

Usage:
    python3 scripts/coverage_delta.py \
        --head head-coverage --base base-coverage \
        --base-label main --out coverage-comment.md

Exits 0 whenever it could read what was there.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

# Report file name -> (label, reader). Keyed by name so a report found anywhere
# under the search root — including inside an artifact directory — is picked up.
COBERTURA = "coverage.xml"
ISTANBUL = "coverage-summary.json"


def _read_cobertura(path: Path) -> tuple[float, float]:
    """Line and branch percentages from a Cobertura report's root attributes."""
    root = ET.parse(path).getroot()
    return (
        float(root.get("line-rate", "0")) * 100,
        float(root.get("branch-rate", "0")) * 100,
    )


def _read_istanbul(path: Path) -> tuple[float, float]:
    """Line and branch percentages from an Istanbul `coverage-summary.json`."""
    total = json.loads(path.read_text(encoding="utf-8"))["total"]
    return float(total["lines"]["pct"]), float(total["branches"]["pct"])


READERS: dict[str, tuple[str, Callable[[Path], tuple[float, float]]]] = {
    COBERTURA: ("Python (backend)", _read_cobertura),
    ISTANBUL: ("TypeScript (frontend)", _read_istanbul),
}


def collect(root: Path) -> dict[str, tuple[float, float]]:
    """Every recognised report under `root`, keyed by the file that held it."""
    found: dict[str, tuple[float, float]] = {}
    if not root.is_dir():
        return found
    for name, (_, reader) in READERS.items():
        # The head and base trees have the same shape, so the first match is the
        # only one that can be compared with the other side.
        for path in sorted(root.rglob(name)):
            found[name] = reader(path)
            break
    return found


def _format(pct: float | None) -> str:
    return "—" if pct is None else f"{pct:.1f}%"


def _format_delta(head: float | None, base: float | None) -> str:
    if head is None or base is None:
        return "n/a"
    delta = head - base
    # A tenth of a point is the resolution the table reports, so anything
    # smaller is noise rather than movement.
    if abs(delta) < 0.05:
        return "±0.0"
    return f"{delta:+.1f}"


def render(head: dict[str, tuple[float, float]], base: dict[str, tuple[float, float]], label: str) -> str:
    lines = [
        "### Coverage",
        "",
        f"| Suite | Lines | Branches | Δ lines vs `{label}` |",
        "| --- | --- | --- | --- |",
    ]

    for name, (title, _) in READERS.items():
        head_values = head.get(name)
        base_values = base.get(name)
        lines.append(
            "| {title} | {lines} | {branches} | {delta} |".format(
                title=title,
                lines=_format(head_values[0] if head_values else None),
                branches=_format(head_values[1] if head_values else None),
                delta=_format_delta(
                    head_values[0] if head_values else None,
                    base_values[0] if base_values else None,
                ),
            )
        )

    lines += [
        "",
        "<sub>Δ compares this pull request with the latest run on the base branch; "
        f"`n/a` means no report was available there. The backend suite also enforces "
        "a floor (`--cov-fail-under`) in CI.</sub>",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", type=Path, required=True, help="directory of this run's reports")
    parser.add_argument("--base", type=Path, help="directory of the base branch's reports")
    parser.add_argument("--base-label", default="base", help="display name of the base branch")
    parser.add_argument("--out", type=Path, help="write the Markdown here as well as printing it")
    args = parser.parse_args(argv)

    head = collect(args.head)
    base = collect(args.base) if args.base else {}

    if not head:
        print(f"No coverage reports found under {args.head}; nothing to comment.")
        return 0

    markdown = render(head, base, args.base_label)
    print(markdown)
    if args.out:
        args.out.write_text(markdown + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
