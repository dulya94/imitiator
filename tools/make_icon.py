"""
tools/make_icon.py — генерация иконки приложения PC Action Imitator.

Создаёт:
  assets/app_icon.ico  — многослойный .ico для ярлыка Windows (256..16 px)
  assets/app_icon.png  — PNG 256px для иконки окна Tk (iconphoto)

Запуск:  python tools/make_icon.py
Зависимость: pillow
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZES = [256, 128, 64, 48, 32, 16]

# Цвета фирменного стиля приложения
BLUE_TOP = (79, 142, 247)     # #4f8ef7
BLUE_BOTTOM = (42, 98, 214)
GREEN = (34, 197, 94)         # бейдж «play»
WHITE = (255, 255, 255, 255)


def _vertical_gradient(size: int) -> Image.Image:
    """Вертикальный градиент от BLUE_TOP к BLUE_BOTTOM."""
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / max(size - 1, 1)
        color = tuple(
            int(BLUE_TOP[i] + (BLUE_BOTTOM[i] - BLUE_TOP[i]) * t) for i in range(3)
        ) + (255,)
        d.line([(0, y), (size, y)], fill=color)
    return grad


def _draw_mouse(d: ImageDraw.ImageDraw, size: int) -> None:
    """Стилизованная мышь: белый корпус с тёмно-синей разметкой кнопок."""
    x0, y0 = int(size * 0.28), int(size * 0.18)
    x1, y1 = int(size * 0.72), int(size * 0.74)
    cx = (x0 + x1) // 2
    line_w = max(2, size // 22)
    # корпус
    d.ellipse([x0, y0, x1, y1], fill=WHITE)
    # вертикальная линия между кнопками
    d.line([cx, y0, cx, int(size * 0.42)], fill=BLUE_BOTTOM, width=line_w)
    # горизонтальная линия кнопок
    d.line([x0, int(size * 0.42), x1, int(size * 0.42)], fill=BLUE_BOTTOM, width=line_w)
    # колесо прокрутки
    wheel_h = max(2, size // 14)
    d.rounded_rectangle(
        [cx - line_w, y0 + size // 30, cx + line_w, y0 + size // 30 + wheel_h],
        radius=line_w, fill=BLUE_BOTTOM,
    )


def _draw_play_badge(d: ImageDraw.ImageDraw, size: int) -> None:
    """Зелёный бейдж с белым треугольником «play» в правом нижнем углу."""
    r = int(size * 0.22)
    cx, cy = int(size * 0.73), int(size * 0.75)
    # белая окантовка для контраста
    w = max(2, size // 30)
    d.ellipse([cx - r - w, cy - r - w, cx + r + w, cy + r + w], fill=WHITE)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)
    t = int(size * 0.09)
    d.polygon([(cx - t, cy - t), (cx - t, cy + t), (cx + int(t * 1.3), cy)], fill=WHITE)


def build_icon(size: int) -> Image.Image:
    """Собрать иконку заданного размера: скруглённый квадрат + мышь + play."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    m = max(2, size // 32)
    # фон с градиентом и скруглением
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [m, m, size - m - 1, size - m - 1], radius=size // 5, fill=255
    )
    img.paste(_vertical_gradient(size), (0, 0), mask)
    d = ImageDraw.Draw(img)
    if size >= 32:
        _draw_mouse(d, size)
    if size >= 24:
        _draw_play_badge(d, size)
    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icons = [build_icon(s) for s in SIZES]
    ico_path = ASSETS / "app_icon.ico"
    png_path = ASSETS / "app_icon.png"
    # ICO со всеми размерами (Windows сам выберет нужный)
    icons[0].save(ico_path, format="ICO", sizes=[(s, s) for s in SIZES])
    icons[0].save(png_path, format="PNG")
    print(f"OK: {ico_path}")
    print(f"OK: {png_path}")


if __name__ == "__main__":
    main()
