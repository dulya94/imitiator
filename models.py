"""
models.py — модели данных PC Action Imitator.

Event  — одно действие пользователя (мышь/клавиатура) с меткой времени.
Scenario — упорядоченный список событий + метаданные (имя, дата, длительность,
целевая страница url, на которой записаны действия).
Содержит сериализацию объектов клавиш pynput в строки JSON и обратно.
"""
from __future__ import annotations

import datetime
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from pynput import keyboard

# Версия схемы JSON — на случай будущих изменений формата хранения
SCHEMA_VERSION = 1

# Типы событий
EVENT_MOVE = "move"      # движение мыши
EVENT_CLICK = "click"    # нажатие/отпускание кнопки мыши
EVENT_SCROLL = "scroll"  # прокрутка колеса мыши
EVENT_KEY = "key"        # нажатие/отпускание клавиши


@dataclass
class Event:
    """Одно записанное действие со временем t (секунды от начала записи)."""

    type: str                       # один из EVENT_*
    t: float                        # время события от начала записи
    # --- мышь ---
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None    # "left" | "right" | "middle"
    pressed: Optional[bool] = None  # True — нажатие, False — отпускание
    dx: Optional[int] = None        # прокрутка по горизонтали
    dy: Optional[int] = None        # прокрутка по вертикали
    # --- клавиатура ---
    key: Optional[str] = None       # сериализованная клавиша (key_to_str)
    action: Optional[str] = None    # "press" | "release"

    def to_dict(self) -> dict:
        """Словарь для JSON без None-полей (компактный файл)."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(d: dict) -> "Event":
        """Восстановление события из словаря JSON с защитой от мусора."""
        return Event(
            type=str(d.get("type", "")),
            t=float(d.get("t", 0.0)),
            x=d.get("x"),
            y=d.get("y"),
            button=d.get("button"),
            pressed=d.get("pressed"),
            dx=d.get("dx"),
            dy=d.get("dy"),
            key=d.get("key"),
            action=d.get("action"),
        )


# --------------------------------------------------------------------------
# Сериализация клавиш pynput.
# Форматы: "k:<name>" — спец. клавиша (Key.esc -> "k:esc"),
#          "c:<char>" — обычный символ, "v:<vk>" — запасной вариант по vk-коду.
# --------------------------------------------------------------------------
def key_to_str(key) -> str:
    """Преобразовать объект клавиши pynput в строку для JSON."""
    if isinstance(key, keyboard.Key):
        return "k:" + key.name
    char = getattr(key, "char", None)
    if char:
        return "c:" + char
    vk = getattr(key, "vk", None)
    if vk is not None:
        return "v:" + str(vk)
    return "k:unknown"


def str_to_key(s: str):
    """Восстановить объект клавиши pynput из строки JSON."""
    tag, _, value = s.partition(":")
    try:
        if tag == "k":
            return keyboard.Key[value]
        if tag == "c":
            return keyboard.KeyCode.from_char(value)
        return keyboard.KeyCode.from_vk(int(value))
    except (KeyError, ValueError):
        # Неизвестная клавиша — вернём ESC, чтобы воспроизведение не упало
        return keyboard.Key.esc


@dataclass
class Scenario:
    """Сценарий = имя + список событий + метаданные."""

    name: str
    events: List[Event] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    duration: float = 0.0  # длительность записи в секундах
    url: str = ""          # страница, на которой выполняются действия ("" = сайт по умолчанию)
    screen_w: int = 0      # ширина экрана при записи (0 = не записано, пересчёт невозможен)
    screen_h: int = 0      # высота экрана при записи

    # ----------------------------- сериализация -----------------------------
    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA_VERSION,
            "name": self.name,
            "created_at": self.created_at,
            "duration": self.duration,
            "url": self.url,
            "screen_w": self.screen_w,
            "screen_h": self.screen_h,
            "events": [e.to_dict() for e in self.events],
        }

    @staticmethod
    def from_dict(d: dict) -> "Scenario":
        if not isinstance(d, dict) or "name" not in d:
            raise ValueError("Некорректный формат сценария")
        events_raw = d.get("events") or []
        events = [Event.from_dict(e) for e in events_raw if isinstance(e, dict)]

        def _int_or_zero(value) -> int:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                return 0

        return Scenario(
            name=str(d["name"]),
            events=events,
            created_at=float(d.get("created_at", time.time())),
            duration=float(d.get("duration", 0.0)),
            url=str(d.get("url", "") or ""),
            screen_w=_int_or_zero(d.get("screen_w", 0)),
            screen_h=_int_or_zero(d.get("screen_h", 0)),
        )

    @property
    def screen_size(self) -> tuple[int, int]:
        """Разрешение экрана при записи как кортеж (0, 0), если не записано."""
        return self.screen_w, self.screen_h

    @property
    def screen_note(self) -> str:
        """Разрешение записи для отображения в UI ('' — не записано)."""
        return f"{self.screen_w}×{self.screen_h}" if self.screen_w and self.screen_h else ""

    # ------------------------- отображение в UI -----------------------------
    @property
    def duration_str(self) -> str:
        """Длительность в формате ЧЧ:ММ:СС или ММ:СС."""
        total = int(round(self.duration))
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    @property
    def created_str(self) -> str:
        """Дата создания в человекочитаемом виде."""
        return datetime.datetime.fromtimestamp(self.created_at).strftime("%d.%m.%Y %H:%M")

    @property
    def events_count(self) -> int:
        return len(self.events)
