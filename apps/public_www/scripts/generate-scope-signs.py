#!/usr/bin/env python3
"""Draw the hero street-name plates from the wizard place names.

The homepage shows one plate per open place. Rendering them here keeps
the English and Chinese exact for every neighbourhood the search-area
variable can name, without a font on the visitor's machine. Run from
anywhere; output lands in public/images/scope-signs/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CHOICES = ROOT / "src" / "data" / "home_wizard_choices.json"
OUT = ROOT / "public" / "images" / "scope-signs"

SCALE = 4
EN_FONT = ImageFont.truetype(
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    26 * SCALE,
)
ZH_FONT = ImageFont.truetype(
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    30 * SCALE,
)
PAD_X = 16 * SCALE
PAD_Y = 9 * SCALE
GAP = 2 * SCALE
BORDER = 3 * SCALE
RADIUS = 4 * SCALE
ZH_TRACKING = 2 * SCALE
ZH_STROKE = 1


def tracked_width(font: ImageFont.FreeTypeFont, text: str, tracking: int) -> int:
    if text == "":
        return 0
    total = 0
    for index, char in enumerate(text):
        box = font.getbbox(char)
        width = box[2] - box[0]
        if width <= 0:
            message = f"Font has no glyph for {char!r} in {text!r}"
            raise SystemExit(message)
        total += width
        if index < len(text) - 1:
            total += tracking
    return total


def draw_tracked(
    draw: ImageDraw.ImageDraw,
    origin_x: float,
    origin_y: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    tracking: int,
) -> None:
    cursor = origin_x
    for char in text:
        box = font.getbbox(char)
        draw.text(
            (cursor - box[0], origin_y),
            char,
            font=font,
            fill="black",
            stroke_width=ZH_STROKE,
            stroke_fill="black",
        )
        cursor += (box[2] - box[0]) + tracking


def render_plate(english: str, chinese: str) -> Image.Image:
    en_box = EN_FONT.getbbox(english)
    zh_box = ZH_FONT.getbbox(chinese)
    en_w = en_box[2] - en_box[0]
    en_h = en_box[3] - en_box[1]
    zh_w = tracked_width(ZH_FONT, chinese, ZH_TRACKING)
    zh_h = zh_box[3] - zh_box[1]
    inner_w = max(en_w, zh_w)
    width = inner_w + PAD_X * 2 + BORDER * 2
    height = en_h + GAP + zh_h + PAD_Y * 2 + BORDER * 2
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = BORDER // 2
    draw.rounded_rectangle(
        [inset, inset, width - 1 - inset, height - 1 - inset],
        radius=RADIUS,
        fill="white",
        outline="black",
        width=BORDER,
    )
    en_x = (width - en_w) / 2 - en_box[0]
    en_y = BORDER + PAD_Y - en_box[1]
    draw.text((en_x, en_y), english, font=EN_FONT, fill="black")
    zh_x = (width - zh_w) / 2
    zh_y = BORDER + PAD_Y + en_h + GAP - zh_box[1]
    draw_tracked(draw, zh_x, zh_y, chinese, ZH_FONT, ZH_TRACKING)
    return image


def plates() -> list[tuple[str, str, str]]:
    data = json.loads(CHOICES.read_text(encoding="utf-8"))
    rows: list[tuple[str, str, str]] = []
    for region in data["regions"]:
        labels = region["labels"]
        rows.append((region["id"], labels["en"], labels["zh-HK"]))
    for place in data["neighbourhoods"]:
        labels = place["labels"]
        rows.append((place["id"], labels["en"], labels["zh-HK"]))
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written: set[str] = set()
    for plate_id, english, chinese in plates():
        if plate_id in written:
            raise SystemExit(f"Duplicate plate id {plate_id}")
        written.add(plate_id)
        image = render_plate(english, chinese)
        image.save(OUT / f"{plate_id}.webp", "WEBP", quality=85, method=6)
    print(f"Wrote {len(written)} plates to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
