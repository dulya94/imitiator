"""
screeninfo.py — учёт параметров экрана (разрешение, DPI, мониторы).

Проблема: сценарий записывается в абсолютных пикселях того разрешения, при котором
шла запись. Если воспроизведение выполняется при другом разрешении (сменился монитор,
изменились настройки экрана Windows, другой ПК), клики «съезжают». Этот модуль даёт
текущее разрешение и функцию пропорционального пересчёта координат.

DPI-awareность: координаты pynput — физические пиксели. Если процесс не DPI-aware,
GetSystemMetrics вернёт «виртуализированные» числа и при масштабе Windows 125–150%
они не совпадут с координатами мыши. Поэтому процесс делаем DPI-aware при импорте.
"""
from __future__ import annotations

import ctypes

# GetSystemMetrics: индексы системных метрик Windows
_SM_CXSCREEN = 0   # ширина основного монитора
_SM_CYSCREEN = 1   # высота основного монитора
_SM_XVIRTUAL = 76  # X левого края виртуального рабочего стола
_SM_YVIRTUAL = 77  # Y верхнего края виртуального рабочего стола
_SM_CXVIRTUAL = 78 # ширина виртуального рабочего стола (все мониторы)
_SM_CYVIRTUAL = 79 # высота виртуального рабочего стола


def _ensure_dpi_aware() -> None:
    """Сделать процесс DPI-aware (best-effort, любые ошибки игнорируем)."""
    try:
        user32 = ctypes.windll.user32
        # Windows 10 1703+: Per-Monitor V2
        try:
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except (AttributeError, OSError):
            pass
        # Windows 8.1+: shcore
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except (AttributeError, OSError):
            pass
        # Windows Vista+: системный DPI-aware
        user32.SetProcessDPIAware()
    except Exception:
        pass


_ensure_dpi_aware()


def _metric(index: int, default: int = 0) -> int:
    """Одна системная метрика с защитой от ошибок."""
    try:
        value = ctypes.windll.user32.GetSystemMetrics(index)
        return int(value) if value else default
    except Exception:
        return default


def primary_resolution() -> tuple[int, int]:
    """Разрешение основного монитора в физических пикселях (ширина, высота)."""
    return _metric(_SM_CXSCREEN), _metric(_SM_CYSCREEN)


def virtual_bounds() -> tuple[int, int, int, int]:
    """Границы виртуального рабочего стола (x, y, w, h) — все мониторы вместе."""
    return (
        _metric(_SM_XVIRTUAL),
        _metric(_SM_YVIRTUAL),
        _metric(_SM_CXVIRTUAL),
        _metric(_SM_CYVIRTUAL),
    )


# Псевдоним: «текущее разрешение» = основной монитор
current_resolution = primary_resolution


def scale_point(
    x: int, y: int,
    src_size: tuple[int, int],
    dst_size: tuple[int, int],
) -> tuple[int, int]:
    """Пропорционально пересчитать точку из разрешения src в разрешение dst.

    Если любой из размеров некорректен (0 или отрицательный), точка возвращается
    без изменений — так старые сценарии без записи разрешения работают как раньше.
    """
    sw, sh = src_size
    dw, dh = dst_size
    if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
        return int(x), int(y)
    nx = int(round(x * dw / sw))
    ny = int(round(y * dh / sh))
    return nx, ny


def clamp_to_primary(x: int, y: int) -> tuple[int, int]:
    """Отсечь координаты границами основного монитора (0 .. w-1 / 0 .. h-1)."""
    w, h = primary_resolution()
    if w <= 0 or h <= 0:
        return x, y
    return max(0, min(int(x), w - 1)), max(0, min(int(y), h - 1))
