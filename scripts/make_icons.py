#!/usr/bin/env python3
"""Generate simple PNG icons for the PWA manifest using PIL."""
from pathlib import Path
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pillow"])
    from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent.parent / "web" / "public"

RED = (165, 12, 38)        # #a50c26 — Banská Bystrica heraldic red
WHITE = (255, 255, 255)


def _load_bold_font(size: int):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make(size: int):
    """Solid red square with bold white 'MHD' text."""
    img = Image.new("RGBA", (size, size), RED)
    draw = ImageDraw.Draw(img)
    text = "MHD"
    # Pick the largest font size that fits within ~80% of the icon width
    target_width = size * 0.78
    font_size = int(size * 0.5)
    font = _load_bold_font(font_size)
    while font_size > 8:
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= target_width:
            break
        font_size -= 2
        font = _load_bold_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - size * 0.03),
        text,
        fill=WHITE,
        font=font,
    )
    img.save(OUT / f"icon-{size}.png", "PNG")
    print(f"Wrote {OUT / f'icon-{size}.png'}")


make(192)
make(512)
