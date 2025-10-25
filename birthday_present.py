# скрипт безопасный, проверял на себе
# pip install pillow


import base64
import hashlib
import io
import math
import os
import random
import zlib
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

def _k(n: int) -> bytes:
    h = hashlib
    _p = ''.join(map(chr, [
        0x50, 0x79, 0x74, 0x68, 0x6F, 0x6E,  # 'Python'
        0x33, 0x2E, 0x31, 0x30,              # '3.10'
        0x2D, 0x53, 0x65, 0x63, 0x72, 0x65, 0x74  # '-Secret'
    ]))
    _s = h.blake2b(
        "Соль? Да какая тут соль".encode("utf-8") + b"\xf0\x9f\x8d\x9a",
        digest_size=16, person=b"qr-obf"
    ).digest()
    return h.pbkdf2_hmac("sha256", _p.encode("utf-8"), _s, 200_000, dklen=n)

def _reveal_msg() -> str:
    _blob_b64 = (
        "zzwTuglfXH2YcJQpvmg3c1RIEonZTnyiUnMBZIgpogzE9/akasjuwqrqmDN2UmfO"
        "aNdBCVRP7W2Ey3lN4ujFxl1JaLuK50TbjArx/IKPQPn6pG4="
    )
    _ct = base64.b64decode(_blob_b64)
    _ks = _k(len(_ct))
    _b85 = bytes(c ^ k for c, k in zip(_ct, _ks))
    _packed = base64.b85decode(_b85)
    return zlib.decompress(_packed).decode("utf-8")

# ---------- Вспомогательные графические утилиты ----------
def _rand_seed(msg: str) -> int:
    a = int.from_bytes(hashlib.blake2b(msg.encode("utf-8"), digest_size=8).digest(), "big")
    b = int.from_bytes(os.urandom(8), "big")
    return a ^ b

def _choose_canvas() -> Tuple[int, int]:
    return random.choice([(1280, 720), (1600, 900), (1080, 1080), (1350, 900), (1920, 1080)])

def _rand_color():
    return tuple(random.randint(24, 232) for _ in range(3)) + (255,)

def _muted_color():
    # Чуть приглушённая палитра
    h = random.random()
    s = random.uniform(0.25, 0.55)
    v = random.uniform(0.35, 0.85)
    return _hsv_to_rgba(h, s, v, 255)

def _hsv_to_rgba(h, s, v, a=255):
    i = int(h * 6)
    f = h * 6 - i
    p = int(255 * v * (1 - s))
    q = int(255 * v * (1 - f * s))
    t = int(255 * v * (1 - (1 - f) * s))
    v = int(255 * v)
    i %= 6
    if i == 0: r, g, b = v, t, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t, p, v
    else: r, g, b = v, p, q
    return (r, g, b, a)

def _find_font(size_hint: int) -> ImageFont.FreeTypeFont:
    # Пытаемся найти системный шрифт, иначе fallback на встроенный.
    candidates = [
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial.ttf",
        # Windows
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size_hint)
        except Exception:
            pass
    # Fallback: увеличим bitmap-шрифт за счёт рендеринга на маску и масштабирования (ниже в коде).
    return None

def _fit_text(draw: ImageDraw.ImageDraw, text: str, font_paths_font, w: int, h: int) -> Tuple[ImageFont.ImageFont, str, bool]:
    # Подбираем размер шрифта и переносы строк так, чтобы поместилось ~в 85–90% области.
    max_w = int(w * random.uniform(0.78, 0.9))
    max_h = int(h * random.uniform(0.48, 0.65))
    # Бинарный поиск размера
    lo, hi = 16, int(h * 0.16)
    use_fallback_bitmap = False
    best_font = None
    best_wrapped = text
    while lo <= hi:
        mid = (lo + hi) // 2
        font = _find_font(mid) if font_paths_font is None else font_paths_font
        if font is None:
            # Нет TTF — используем bitmap по умолчанию, но с последующим масштабированием.
            font = ImageFont.load_default()
            use_fallback_bitmap = True
        wrapped = _wrap_by_width(draw, text, font, max_w)
        tw, th = _measure_block(draw, wrapped, font)
        if tw <= max_w and th <= max_h:
            best_font, best_wrapped = font, wrapped
            lo = mid + 1
        else:
            hi = mid - 1
    if best_font is None:
        best_font = ImageFont.load_default()
        use_fallback_bitmap = True
        best_wrapped = _wrap_by_width(draw, text, best_font, max_w)
    return best_font, best_wrapped, use_fallback_bitmap

def _wrap_by_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    words = text.split(" ")
    lines = []
    cur = []
    for w in words:
        test = (" ".join(cur + [w])).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
                cur = [w]
            else:
                # слово само по себе слишком длинное — грубый перенос
                lines.append(w)
                cur = []
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines)

def _measure_block(draw: ImageDraw.ImageDraw, wrapped: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    lines = wrapped.split("\n")
    widths = [int(draw.textlength(line, font=font)) for line in lines]
    line_h = font.getbbox("Hg")[3] - font.getbbox("Hg")[1]
    return (max(widths) if widths else 0, int(line_h * len(lines) * 1.15))

# ---------- Генерация изображения ----------
def _make_background(size: Tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, _muted_color())
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")

    # Случайные полупрозрачные фигуры
    for _ in range(random.randint(12, 26)):
        c = _muted_color()[:-1] + (random.randint(28, 96),)
        x0 = random.randint(-w//6, int(w*0.9))
        y0 = random.randint(-h//6, int(h*0.9))
        x1 = x0 + random.randint(w//6, int(w*0.9))
        y1 = y0 + random.randint(h//6, int(h*0.9))
        shape = random.choice(["ellipse", "rectangle", "chord", "pieslice"])
        if shape == "ellipse":
            d.ellipse([x0, y0, x1, y1], fill=c)
        elif shape == "rectangle":
            d.rectangle([x0, y0, x1, y1], fill=c)
        elif shape == "chord":
            d.chord([x0, y0, x1, y1], start=random.randint(0, 360), end=random.randint(0, 360), fill=c)
        else:
            d.pieslice([x0, y0, x1, y1], start=random.randint(0, 360), end=random.randint(0, 360), fill=c)

    img = Image.alpha_composite(img, overlay).filter(ImageFilter.GaussianBlur(radius=random.uniform(3.0, 9.0)))

    # Лёгкий виньетт
    vignette = Image.new("L", size, 0)
    vd = ImageDraw.Draw(vignette)
    for r in range(0, int(max(w, h) * 0.9), 8):
        alpha = int(255 * (r / max(w, h)) ** 2 * 0.25)
        vd.ellipse([w//2 - r, h//2 - r, w//2 + r, h//2 + r], outline=alpha, width=8)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=20))
    dark = Image.new("RGBA", size, (0, 0, 0, 0))
    dark.putalpha(vignette)
    img = Image.alpha_composite(img, dark)
    return img

def _draw_text(img: Image.Image, text: str) -> Image.Image:
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    # Подбор шрифта/переносов
    font, wrapped, bitmap_fallback = _fit_text(draw, text, None, w, h)

    # Позиционирование
    tw, th = _measure_block(draw, wrapped, font)
    x = (w - tw) // 2
    y = (h - th) // 2 + random.randint(-h//12, h//12)

    # Цвет текста и обводки под контраст
    base = _muted_color()[:-1]
    inv = (255 - base[0], 255 - base[1], 255 - base[2])
    txt_color = random.choice([base, inv, (240, 240, 240), (20, 20, 20)])
    outline = (0, 0, 0, 255) if sum(txt_color) > 382 else (255, 255, 255, 255)

    # Тень/обводка
    offsets = [(dx, dy) for dx in (-2, -1, 1, 2) for dy in (-2, -1, 1, 2)]
    for dx, dy in offsets:
        draw.multiline_text((x+dx, y+dy), wrapped, font=font, fill=outline, align="center", spacing=8)

    # Сам текст
    if bitmap_fallback:
        # Если нет TTF — рисуем на маску и масштабируем слегка для "крупного" вида
        tmp = Image.new("L", (tw, th), 0)
        td = ImageDraw.Draw(tmp)
        td.multiline_text((0, 0), wrapped, font=font, fill=255, align="center", spacing=8)
        scale = random.uniform(1.6, 2.2)
        tmp = tmp.resize((int(tw*scale), int(th*scale)), Image.BICUBIC)
        colored = Image.new("RGBA", tmp.size, (*txt_color, 255))
        colored.putalpha(tmp)
        img.alpha_composite(colored, (int(x - (tmp.size[0]-tw)/2), int(y - (tmp.size[1]-th)/2)))
    else:
        draw.multiline_text((x, y), wrapped, font=font, fill=txt_color+(255,), align="center", spacing=8)

    # Лёгкое свечение
    glow = img.filter(ImageFilter.GaussianBlur(radius=2.0))
    img = Image.blend(glow, img, 0.65)
    return img

def make_image(outfile: str = "note.png") -> None:
    msg = _reveal_msg()
    random.seed(_rand_seed(msg))
    size = _choose_canvas()
    img = _make_background(size)
    img = _draw_text(img, msg)
    # Чуть шуму для «плёночности»
    noise = Image.effect_noise(size, random.uniform(6.0, 16.0)).convert("L")
    noise = noise.point(lambda p: int(p * random.uniform(0.08, 0.14)))
    grain = Image.merge("RGBA", (noise, noise, noise, noise.point(lambda p: int(p*0.7))))
    img = Image.alpha_composite(img, grain).filter(ImageFilter.UnsharpMask(radius=1.4, percent=140, threshold=3))
    img.convert("RGB").save(outfile, "PNG")
    print(f"Изображение сохранено: {outfile}")

if __name__ == "__main__":
    make_image()
