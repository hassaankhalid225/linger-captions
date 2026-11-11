"""Generate assets/icon.ico (gradient rounded square with "CC") — used by the PyInstaller build."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "icon.ico"
A, B = (0x7C, 0xD2, 0xFF), (0xA9, 0x9B, 0xFF)


def render(size: int = 256) -> Image.Image:
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = tuple(int(A[i] + (B[i] - A[i]) * t) for i in range(3)) + (255,)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.3), fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(size * 0.42))
    except OSError:
        font = ImageFont.load_default()
    draw.text((size / 2, size / 2), "CC", font=font, fill=(11, 11, 18, 255), anchor="mm")
    return img


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    render().save(OUT, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"wrote {OUT}")
