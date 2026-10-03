"""Generate brand images (icon/logo, light/dark, @2x).

Run: python scripts/make_brand.py  (requires Pillow + numpy)
The artwork is a generic amplifier volume knob, not the Rotel trademark.
All images are fully opaque so they are readable on light and dark themes.
"""
from __future__ import annotations

import math
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "custom_components" / "rotel_amp" / "brand"
OUT_ROOT = ROOT / "brand"
SS = 4  # supersampling factor

ACCENT = (226, 35, 52)
BG_TOP = np.array([46, 48, 54])
BG_BOTTOM = np.array([18, 19, 22])


def _grid(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return x, y


def background(w: int, h: int) -> Image.Image:
    """Opaque vertical gradient with a soft top light."""
    x, y = _grid(w, h)
    t = (y / max(h - 1, 1))[..., None]
    rgb = BG_TOP * (1 - t) + BG_BOTTOM * t
    glow = np.exp(-(((x - w / 2) / (w * 0.6)) ** 2 + ((y - h * 0.15) / (h * 0.5)) ** 2))
    rgb = rgb + glow[..., None] * 14
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


def _knob_layer(d: int) -> Image.Image:
    """Metallic knob (RGBA, d x d)."""
    x, y = _grid(d, d)
    c = d / 2
    dx, dy = (x - c) / c, (y - c) / c
    r = np.sqrt(dx**2 + dy**2)
    ang = np.arctan2(dy, dx)

    light = np.clip(0.55 - 0.35 * (dx + dy) / 1.4, 0, 1)
    body = 40 + 90 * light  # smooth cap (fine rings cause moire when downscaled)
    body = body + 10 * np.exp(-((dx + 0.35) ** 2 + (dy + 0.35) ** 2) / 0.08)  # highlight
    band = (r > 0.80) & (r <= 1.0)
    knurl = 0.5 + 0.5 * np.sin(ang * 60)
    body = np.where(band, 30 + 70 * light * (0.6 + 0.4 * knurl), body)
    body = np.where(np.abs(r - 0.80) < 0.012, 18, body)  # groove
    rgb = np.stack([body, body, body * 1.04], axis=-1)

    alpha = np.clip((1.0 - r) * c, 0, 1) * 255
    rgba = np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")

    dr = ImageDraw.Draw(img)
    a = math.radians(-50)
    p1 = (c + c * 0.30 * math.cos(a), c + c * 0.30 * math.sin(a))
    p2 = (c + c * 0.72 * math.cos(a), c + c * 0.72 * math.sin(a))
    dr.line([p1, p2], fill=ACCENT + (255,), width=int(d * 0.06))
    for p in (p1, p2):
        rr = d * 0.03
        dr.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=ACCENT + (255,))
    return img


def knob_scene(size: int) -> Image.Image:
    """Knob with LED scale on an opaque square background."""
    s = size * SS
    img = background(s, s).convert("RGBA")
    _draw_knob(img, s, 0)
    return img.convert("RGB").resize((size, size), Image.LANCZOS)


def _draw_knob(img: Image.Image, s: int, x0: int) -> None:
    """Draw LED scale + knob into an s x s square of img at (x0, 0)."""
    sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    _draw_knob_layers(sq, s)
    img.alpha_composite(sq, (x0, 0))


def _draw_knob_layers(img: Image.Image, s: int) -> None:
    c = s / 2

    scale = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ds = ImageDraw.Draw(scale)
    n, lit = 21, 15
    for i in range(n):
        a = math.radians(135 + i * 270 / (n - 1))
        r1, r2 = s * 0.40, s * 0.465
        if i < lit:
            col = ACCENT if i >= lit - 4 else (235, 235, 240)
        else:
            col = (80, 82, 90)
        ds.line(
            [(c + r1 * math.cos(a), c + r1 * math.sin(a)),
             (c + r2 * math.cos(a), c + r2 * math.sin(a))],
            fill=col + (255,), width=int(s * 0.022),
        )
    img.alpha_composite(scale.filter(ImageFilter.GaussianBlur(s * 0.012)))
    img.alpha_composite(scale)

    d = int(s * 0.64)
    off = (s - d) // 2
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        [off, off + s * 0.025, off + d, off + d + s * 0.025], fill=(0, 0, 0, 170)
    )
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s * 0.025)))
    img.alpha_composite(_knob_layer(d), (off, off))


def _font(px: int) -> ImageFont.ImageFont:
    for path, idx in (
        ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
        ("/System/Library/Fonts/Helvetica.ttc", 1),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ):
        try:
            return ImageFont.truetype(path, px, index=idx)
        except OSError:
            continue
    return ImageFont.load_default(px)


def logo(height: int) -> Image.Image:
    """Knob + wordmark on an opaque background."""
    s = height * SS
    font = _font(int(s * 0.42))
    text = "Rotel Amp"
    tw = ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=font)
    pad = int(s * 0.10)
    w = int(s + pad + tw + s * 0.3)
    img = background(w, s).convert("RGBA")
    _draw_knob(img, s, 0)
    img = img.convert("RGB")
    ImageDraw.Draw(img).text(
        (s + pad, s / 2), text, font=font, fill=(240, 240, 244), anchor="lm"
    )
    return img.resize((w // SS, height), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    files = {
        "icon.png": knob_scene(256),
        "icon@2x.png": knob_scene(512),
        "logo.png": logo(128),
        "logo@2x.png": logo(256),
    }
    for name, img in files.items():
        for prefix in ("", "dark_"):
            img.save(OUT / f"{prefix}{name}", optimize=True)
    for f in OUT.glob("*.png"):
        shutil.copy2(f, OUT_ROOT / f.name)
    print("written to", OUT, "and", OUT_ROOT)


if __name__ == "__main__":
    main()
