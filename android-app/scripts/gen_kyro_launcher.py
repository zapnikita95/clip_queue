"""Generate Kyro launcher icons (text in black square)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "res"

SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

FONT_CANDIDATES = [
    str(Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "res" / "font" / "outfit_medium.ttf"),
    str(Path(__file__).resolve().parents[2] / "web" / "fonts" / "Outfit-Medium.ttf"),
    r"C:\Windows\Fonts\segoeui.ttf",
]


def pick_font() -> str | None:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: str | None, size: int, max_w: float, max_h: float):
    font_size = int(size * 0.28)
    while font_size > 8:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if tw <= max_w and th <= max_h:
            return font, bbox
        font_size -= 1
    font = ImageFont.truetype(font_path, 8) if font_path else ImageFont.load_default()
    return font, draw.textbbox((0, 0), text, font=font)


def make_icon(size: int, *, rounded: bool = True, pad_ratio: float = 0.18) -> Image.Image:
    img = Image.new("RGBA", (size, size), (10, 10, 12, 255))
    draw = ImageDraw.Draw(img)
    font_path = pick_font()
    text = "Kyro"

    if rounded:
        inset = max(1, size // 64)
        r = int(size * 0.22)
        border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        bd = ImageDraw.Draw(border)
        bd.rounded_rectangle(
            [inset, inset, size - 1 - inset, size - 1 - inset],
            radius=r,
            outline=(255, 255, 255, 36),
            width=max(1, size // 54),
        )
        img = Image.alpha_composite(img, border)
        draw = ImageDraw.Draw(img)

    font, bbox = fit_font(draw, text, font_path, size, size * (1 - 2 * pad_ratio), size * 0.42)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((x, y), text, font=font, fill=(255, 255, 255, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(1, size // 28)))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)
    draw.text((x, y), text, font=font, fill=(243, 243, 245, 255))
    return img


def main() -> None:
    font_path = pick_font()
    print("font", font_path)
    for folder, size in SIZES.items():
        d = ROOT / folder
        d.mkdir(parents=True, exist_ok=True)
        icon = make_icon(size)
        icon.save(d / "ic_launcher.png", optimize=True)
        icon.save(d / "ic_launcher_round.png", optimize=True)
        print("wrote", folder, size)

    fg_size = 432
    fg = Image.new("RGBA", (fg_size, fg_size), (10, 10, 12, 255))
    draw = ImageDraw.Draw(fg)
    text = "Kyro"
    font, bbox = fit_font(draw, text, font_path, fg_size, fg_size * 0.52, fg_size * 0.36)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (fg_size - tw) / 2 - bbox[0]
    y = (fg_size - th) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=(243, 243, 245, 255))
    (ROOT / "drawable").mkdir(parents=True, exist_ok=True)
    fg.save(ROOT / "drawable" / "ic_launcher_foreground.png", optimize=True)
    Image.new("RGBA", (fg_size, fg_size), (10, 10, 12, 255)).save(
        ROOT / "drawable" / "ic_launcher_background.png", optimize=True
    )
    print("adaptive layers ok")


if __name__ == "__main__":
    main()
