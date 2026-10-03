"""Generate brand images (icon/logo, light/dark, @2x).

Run: python scripts/make_brand.py  (requires Pillow)
The artwork is a generic amplifier volume knob, not the Rotel trademark.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "custom_components" / "rotel_amp" / "brand"
ACCENT = (200, 30, 45, 255)


def knob(size: int, dark: bool) -> Image.Image:
    """Draw a volume knob with a scale."""
    s = size * 4  # supersample
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    ring = (230, 230, 230, 255) if dark else (40, 40, 44, 255)
    face = (60, 60, 66, 255) if dark else (28, 28, 32, 255)
    # scale ticks from -135 to +135 deg
    for i in range(11):
        a = math.radians(-225 + i * 27)
        r1, r2 = s * 0.40, s * 0.48
        col = ACCENT if i >= 8 else ring
        d.line(
            [(c + r1 * math.cos(a), c + r1 * math.sin(a)),
             (c + r2 * math.cos(a), c + r2 * math.sin(a))],
            fill=col, width=int(s * 0.035),
        )
    r = s * 0.33
    d.ellipse([c - r, c - r, c + r, c + r], fill=face, outline=ring, width=int(s * 0.03))
    a = math.radians(-60)
    d.line(
        [(c + r * 0.25 * math.cos(a), c + r * 0.25 * math.sin(a)),
         (c + r * 0.8 * math.cos(a), c + r * 0.8 * math.sin(a))],
        fill=ACCENT, width=int(s * 0.05),
    )
    return img.resize((size, size), Image.LANCZOS)


def logo(height: int, dark: bool) -> Image.Image:
    """Knob + wordmark."""
    text = "Rotel Amp"
    color = (235, 235, 235, 255) if dark else (30, 30, 34, 255)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(height * 0.55))
    except OSError:
        font = ImageFont.load_default(int(height * 0.55))
    tw = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(text, font=font)
    w = int(height + height * 0.25 + tw + height * 0.1)
    img = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    img.alpha_composite(knob(height, dark), (0, 0))
    d = ImageDraw.Draw(img)
    d.text((height * 1.2, height / 2), text, font=font, fill=color, anchor="lm")
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for dark, prefix in ((False, ""), (True, "dark_")):
        knob(256, dark).save(OUT / f"{prefix}icon.png", optimize=True)
        knob(512, dark).save(OUT / f"{prefix}icon@2x.png", optimize=True)
        logo(128, dark).save(OUT / f"{prefix}logo.png", optimize=True)
        logo(256, dark).save(OUT / f"{prefix}logo@2x.png", optimize=True)
    print("written to", OUT)


if __name__ == "__main__":
    main()
