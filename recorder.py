"""
recorder.py — запись действий пользователя (мышь + клавиатура).

Использует pynput.mouse.Listener и pynput.keyboard.Listener.
Каждое событие получает метку времени time.time() относительно старта записи.
Служебные клавиши F9/F10 (управление записью) в сценарий не попадают.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from pynput import keyboard, mouse

from models import (
    EVENT_CLICK,
    EVENT_KEY,
    EVENT_MOVE,
    EVENT_SCROLL,
    Event,
    Scenario,
    key_to_str,
)

# Фильтрация "дребезга" движений мыши: не чаще и не ближе указанных порогов
MOVE_MIN_INTERVAL = 0.01  # сек между записанными движениями
MOVE_MIN_DISTANCE = 2     # пиксели


class ActionRecorder:
    """Записывает действия пользователя и формирует Scenario."""

    def __init__(self) -> None:
        self._events: List[Event] = []
        self._lock = threading.Lock()
        self._mouse_listener: Optional[mouse.Listener] = None
        self._key_listener: Optional[keyboard.Listener] = None
        self._start_time: float = 0.0
        self._recording = False
        self._last_move_time = 0.0
        self._last_pos = (-1, -1)
        # Служебные клавиши, которые не записываем (глобальное управление)
        self._ignored = {keyboard.Key.f9, keyboard.Key.f10}

    # ------------------------------ публичное API ---------------------------
    @property
    def recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        """Начать запись. Бросает RuntimeError, если запись уже идёт."""
        if self._recording:
            raise RuntimeError("Запись уже выполняется")
        self._events = []
        self._start_time = time.time()
        self._last_move_time = 0.0
        self._last_pos = (-1, -1)
        self._recording = True
        try:
            self._mouse_listener = mouse.Listener(
                on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll
            )
            self._key_listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release
            )
            self._mouse_listener.start()
            self._key_listener.start()
        except OSError as exc:
            self._recording = False
            raise RuntimeError(
                f"Не удалось перехватить ввод (попробуйте запустить от администратора): {exc}"
            ) from exc

    def stop(self) -> Scenario:
        """Остановить запись и вернуть готовый Scenario."""
        if not self._recording:
            raise RuntimeError("Запись не выполняется")
        self._recording = False
        for listener in (self._mouse_listener, self._key_listener):
            try:
                if listener:
                    listener.stop()
            except Exception:
                pass
        self._mouse_listener = None
        self._key_listener = None
        with self._lock:
            events = list(self._events)
        duration = events[-1].t if events else 0.0
        scenario = Scenario(name="", events=events, duration=duration)
        # Разрешение экрана на момент записи — для пересчёта координат
        # при воспроизведении на другом разрешении (см. player.py).
        try:
            import screeninfo
            scenario.screen_w, scenario.screen_h = screeninfo.primary_resolution()
        except Exception:
            pass  # останется (0, 0) — плеер воспроизведёт координаты как есть
        return scenario

    # ------------------------------ колбэки pynput --------------------------
    def _now(self) -> float:
        return time.time() - self._start_time

    def _add(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)

    def _on_move(self, x: int, y: int) -> None:
        if not self._recording:
            return
        now = self._now()
        dist = max(abs(x - self._last_pos[0]), abs(y - self._last_pos[1]))
        if now - self._last_move_time < MOVE_MIN_INTERVAL and dist < MOVE_MIN_DISTANCE:
            return
        self._last_move_time = now
        self._last_pos = (x, y)
        self._add(Event(type=EVENT_MOVE, t=now, x=int(x), y=int(y)))

    def _on_click(self, x: int, y: int, button, pressed: bool) -> None:
        if not self._recording:
            return
        self._last_pos = (x, y)
        self._add(
            Event(
                type=EVENT_CLICK,
                t=self._now(),
                x=int(x),
                y=int(y),
                button=button.name.replace("Button.", ""),  # "left" / "right" / "middle"
                pressed=bool(pressed),
            )
        )

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self._recording:
            return
        self._add(
            Event(type=EVENT_SCROLL, t=self._now(), x=int(x), y=int(y), dx=int(dx), dy=int(dy))
        )

    def _on_press(self, key) -> None:
        if not self._recording or key in self._ignored:
            return
        self._add(
            Event(type=EVENT_KEY, t=self._now(), key=key_to_str(key), action="press")
        )

    def _on_release(self, key) -> None:
        if not self._recording or key in self._ignored:
            return
        self._add(
            Event(type=EVENT_KEY, t=self._now(), key=key_to_str(key), action="release")
        )
