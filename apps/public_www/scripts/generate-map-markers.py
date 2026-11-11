#!/usr/bin/env python3
"""Draw the search map pins from the category icons.

Google Maps markers take one image, so each category gets a pin with a
white backing (and a brand-yellow selected twin) that keeps the icon
legible over busy map tiles. A plain pin carries the count for places
with several activities. Run from anywhere; output lands in
public/images/markers/.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ROOT / "public" / "images" / "categories"
OUT = ROOT / "public" / "images" / "markers"

INK = "#2E1D12"
BACKINGS = {"": "#FFFFFF", "-selected": "#F5C51B"}
PIN_PATH = "M32 76 C32 76 8 50 8 30 A24 24 0 0 1 56 30 C56 50 32 76 32 76 Z"


def icon_body(svg: str) -> str:
    body = re.sub(r"^.*?<svg[^>]*>", "", svg, flags=re.DOTALL)
    body = re.sub(r"</svg>\s*$", "", body, flags=re.DOTALL)
    # The category art draws its own ground shadow; the pin has one already.
    return re.sub(r"<ellipse[^>]*opacity=\"0\.12\"[^>]*/>", "", body).strip()


def pin(fill: str, inner: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 80" fill="none">\n'
        '  <ellipse cx="32" cy="76" rx="10" ry="3" fill="#2E1D12" opacity="0.2"/>\n'
        f'  <path d="{PIN_PATH}" fill="{fill}" stroke="{INK}" stroke-width="2.5"/>\n'
        f"  {inner}\n"
        "</svg>\n"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for source in sorted(CATEGORIES.glob("*.svg")):
        body = icon_body(source.read_text(encoding="utf-8"))
        inner = f'<g transform="translate(0.8 -1.2) scale(0.65)">{body}</g>'
        for suffix, fill in BACKINGS.items():
            target = OUT / f"{source.stem}{suffix}.svg"
            target.write_text(pin(fill, inner), encoding="utf-8")
    for suffix, fill in BACKINGS.items():
        (OUT / f"group{suffix}.svg").write_text(pin(fill, ""), encoding="utf-8")


if __name__ == "__main__":
    main()
