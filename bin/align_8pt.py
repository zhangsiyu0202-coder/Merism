#!/usr/bin/env python3
"""Bulk-align the frontend to a strict 4pt grid.

Rules
-----
1. Every Tailwind ``*.5`` spacing class → nearest 4pt multiple:
       0.5 (2)  → 1  (4)
       1.5 (6)  → 2  (8)
       2.5 (10) → 2  (8)
       3.5 (14) → 4  (16)

2. Arbitrary text-[10px] / text-[11px] → text-merism-caption (12px).
   Arbitrary text-[14px] → text-merism-body-sm.
   Arbitrary text-[15px] → text-merism-body (16px).
   Arbitrary text-[17|19|21px] → warn (manual).

3. Off-grid heights / widths ``h-9`` (36) / ``h-11`` (44) kept —
   36 and 44 are multiples of 4, so they're on the 4pt grid.

Run from repo root::

    python bin/align_8pt.py frontend/src

Idempotent — safe to re-run.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Class families that take spacing values.
SPACING_FAMILIES = (
    "gap",
    "p", "px", "py", "pt", "pb", "pl", "pr",
    "m", "mx", "my", "mt", "mb", "ml", "mr",
    "space-x", "space-y",
    "h", "w",
    "top", "bottom", "left", "right", "inset",
    "inset-x", "inset-y",
    "translate-x", "translate-y",
    "size",
)

# Map *.5 → integer replacement (rounded to nearest 4pt multiple).
DOT_FIVE_MAP = {
    "0.5": "1",
    "1.5": "2",
    "2.5": "2",
    "3.5": "4",
    # 4.5 / 5.5 / 6.5 etc are rare but stay on 4pt (4.5×4 = 18, off).
    # Round down to even.
    "4.5": "4",
    "5.5": "6",
    "6.5": "6",
    "7.5": "8",
    "8.5": "8",
}


def fix_dot_five(text: str) -> tuple[str, int]:
    """Replace every ``<family>-N.5`` with the nearest 4pt multiple."""
    count = 0
    for family in SPACING_FAMILIES:
        for old_val, new_val in DOT_FIVE_MAP.items():
            pattern = re.compile(
                rf"\b{re.escape(family)}-{re.escape(old_val)}\b"
            )
            text, n = pattern.subn(f"{family}-{new_val}", text)
            count += n
    return text, count


# Text-size collapses.
TEXT_SIZE_MAP = {
    "text-[10px]": "text-merism-caption",
    "text-[11px]": "text-merism-caption",
    "text-[14px]": "text-merism-body-sm",
    "text-[15px]": "text-merism-body",
    "text-[17px]": "text-merism-subtitle",   # 17 → 18
    "text-[19px]": "text-merism-title",      # 19 → 20
    "text-[21px]": "text-merism-title",
    "text-[22px]": "text-merism-h2",
    "text-[23px]": "text-merism-h2",
}


def fix_text_sizes(text: str) -> tuple[str, int]:
    count = 0
    for old, new in TEXT_SIZE_MAP.items():
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            count += n
    return text, count


def process_file(path: Path) -> tuple[int, int]:
    original = path.read_text()
    updated, sp = fix_dot_five(original)
    updated, ts = fix_text_sizes(updated)
    if updated != original:
        path.write_text(updated)
    return sp, ts


def main(root: str) -> None:
    root_path = Path(root)
    if not root_path.exists():
        print(f"no such dir: {root}", file=sys.stderr)
        sys.exit(1)

    total_sp = total_ts = total_files = 0
    for p in root_path.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in {".tsx", ".ts", ".css"}:
            continue
        if "node_modules" in p.parts or "dist" in p.parts:
            continue
        sp, ts = process_file(p)
        if sp or ts:
            print(f"  {p.relative_to(root_path.parent)}: spacing={sp} text={ts}")
            total_files += 1
            total_sp += sp
            total_ts += ts

    print()
    print(f"{total_files} file(s) migrated · {total_sp} spacing fixes · {total_ts} text-size fixes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "frontend/src")
