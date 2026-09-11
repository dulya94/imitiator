"""
player.py — воспроизведение записанных сценариев.

Особенности:
  * воспроизведение в отдельном потоке (UI не блокируется);
  * точные тайминги: события выполняются по своим меткам времени,
    ожидание реализовано через time.perf_counter() с шагом ~20 мс;
  * плавное движение мыши: длинные перемещения интерполируются в реальном
    времени между записанными точками;
  * остановка в любой момент (ESC / кнопка) через threading.Event;
  * флаг synthetic — на время синтетического нажатия клавиш, чтобы
    глобальный хоткей ESC (failsafe) не реагировал на "сам себя".
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from pynput import keyboard, mouse

from models import (
    EVENT_CLICK,
    EVENT_KEY,
    EVENT_MOVE,
    EVENT_SCROLL,
    Scenario,
    str_to_key,
)
import screeninfo

# Шаг "сонного" цикла ожидания
TICK = 0.02
# Задержка между press и release клавиши/кнопки мыши
CLICK_PAUSE = 0.01
# Если до клика/движения далеко по времени — мышь ведём плавно
SMOOTH_MIN_GAP = 0.25


class ActionPlayer:
    """Проигрыватель одного сценария (один экземпляр = одно воспроизведение)."""

    def __init__(
        self,
        scenario: Scenario,
        loop: bool = False,
        delay: float = 0.0,
        fit_screen: bool = True,
        on_status: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        self.scenario = scenario
        self.loop = loop
        self.delay = max(0.0, float(delay))
        self.on_status = on_status
        self.on_finished = on_finished

        self._mouse = mouse.Controller()
        self._kb = keyboard.Controller()
        self._stop_event = threading.Event()
        self._synthetic = threading.Event()  # активен при синтетическом вводе
        self._thread: Optional[threading.Thread] = None
        self._t0 = 0.0

        # ---- учёт разрешения экрана -------------------------------------
        # Координаты сценария записаны при разрешении scenario.screen_size.
        # Если текущее разрешение другое (другой монитор/настройки Windows),
        # пересчитываем координаты пропорционально и отсекаем их границами
        # экрана. fit_screen=False или отсутствие записи разрешения (0,0)
        # отключает пересчёт — события идут в исходных пикселях.
        self.fit_screen = bool(fit_screen)
        rec_w, rec_h = getattr(scenario, "screen_size", (0, 0))
        cur_w, cur_h = screeninfo.primary_resolution()
        if self.fit_screen and rec_w > 0 and rec_h > 0 and (rec_w, rec_h) != (cur_w, cur_h):
            self._fx = cur_w / rec_w
            self._fy = cur_h / rec_h
        else:
            self._fx = 1.0
            self._fy = 1.0
        self._res_note = (
            f"{rec_w}×{rec_h} → {cur_w}×{cur_h}"
            if (self._fx, self._fy) != (1.0, 1.0) else ""
        )

    # --------------------- пересчёт координат -------------------------------
    @property
    def resolution_note(self) -> str:
        """Описание пересчёта разрешения ('1920×1080 → 2560×1440' или '')."""
        return self._res_note

    def _map_xy(self, x: Optional[int], y: Optional[int]) -> tuple[Optional[int], Optional[int]]:
        """Пересчитать координату события под текущее разрешение экрана."""
        if x is None or y is None or (self._fx, self._fy) == (1.0, 1.0):
            return x, y
        nx = int(round(x * self._fx))
        ny = int(round(y * self._fy))
        nx, ny = screeninfo.clamp_to_primary(nx, ny)
        return nx, ny

    # ------------------------------ публичное API ---------------------------
    @property
    def playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def synthetic_active(self) -> bool:
        """True, пока плеер сам нажимает клавиши (для фильтрации хоткеев)."""
        return self._synthetic.is_set()

    def start(self) -> None:
        """Запустить воспроизведение в фоновом потоке."""
        if self.playing:
            raise RuntimeError("Воспроизведение уже выполняется")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="ActionPlayer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Остановить воспроизведение (безопасно вызывать из любого потока)."""
        self._stop_event.set()

    # ------------------------------ внутреннее ------------------------------
    def _notify_status(self, text: str) -> None:
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

    def _run(self) -> None:
        try:
            # Стартовая задержка — с возможностью отмены (ESC работает и тут)
            if self.delay > 0:
                self._notify_status(
                    f"Старт через {int(self.delay)} сек (ESC — отмена)..."
                )
                if not self._sleep(self.delay):
                    return
            iterations = 0
            while not self._stop_event.is_set():
                if not self._play_once():
                    break
                iterations += 1
                if not self.loop:
                    break
                self._notify_status(
                    f"Воспроизведение: {self.scenario.name} (проход {iterations + 1})"
                )
        finally:
            finished = not self._stop_event.is_set()
            self._notify_status("Готово" if finished else "Остановлено пользователем")
            if self.on_finished:
                try:
                    self.on_finished()
                except Exception:
                    pass

    def _sleep(self, seconds: float) -> bool:
        """Спать seconds с проверкой stop_event. False — воспроизведение отменено."""
        deadline = time.perf_counter() + seconds
        while not self._stop_event.is_set():
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return True
            time.sleep(min(remaining, TICK))
        return False


    def _play_once(self) -> bool:
        """Один проход по всем событиям сценария. False — отмена/ошибка."""
        events = self.scenario.events
        if not events:
            self._notify_status("Сценарий пуст — нечего воспроизводить")
            return False
        self._t0 = time.perf_counter()
        prev_t = 0.0
        prev_pos: Optional[tuple] = None
        for ev in events:
            if self._stop_event.is_set():
                return False
            # Координаты события под текущее разрешение экрана
            ex, ey = self._map_xy(ev.x, ev.y)
            # Плавное ведение мыши к клику, если до него далеко по времени
            if ev.type == EVENT_CLICK and prev_pos and ex is not None:
                gap = ev.t - prev_t
                if gap > SMOOTH_MIN_GAP:
                    self._smooth_to(ex, ey, ev.t, prev_pos)
                    prev_t = ev.t
                    if self._stop_event.is_set():
                        return False
                    continue
            if not self._wait_until(ev.t):
                return False
            # Длинный прыжок move-события тоже проходим плавно
            if ev.type == EVENT_MOVE and prev_pos and ex is not None:
                dist = max(abs(ex - prev_pos[0]), abs(ey - prev_pos[1]))
                gap = ev.t - prev_t
                if dist > 250 and gap > SMOOTH_MIN_GAP:
                    self._smooth_to(ex, ey, ev.t, prev_pos)
                    prev_t, prev_pos = ev.t, (ex, ey)
                    continue
            self._execute(ev, ex, ey)
            if ex is not None and ey is not None:
                prev_pos = (ex, ey)
            prev_t = ev.t
        # Небольшая пауза в конце прохода (даём "дожать" последнюю клавишу)
        return self._sleep(0.1)

    def _wait_until(self, target: float) -> bool:
        """Ждать до момента t0 + target с шагом TICK. False — отмена."""
        deadline = self._t0 + max(target, 0.0)
        while not self._stop_event.is_set():
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return True
            time.sleep(min(remaining, TICK))
        return False

    def _smooth_to(self, x: int, y: int, target_t: float, start_pos: tuple) -> None:
        """Плавно вести курсор к (x, y) до наступления времени target_t."""
        deadline = self._t0 + max(target_t, 0.0)
        sx, sy = start_pos
        total = max(deadline - time.perf_counter(), 0.0)
        if total <= 0:
            self._mouse.position = (x, y)
            return
        while not self._stop_event.is_set():
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            progress = 1.0 - remaining / total
            nx = int(round(sx + (x - sx) * progress))
            ny = int(round(sy + (y - sy) * progress))
            try:
                self._mouse.position = (nx, ny)
            except Exception:
                pass
            time.sleep(min(TICK, remaining))
        if not self._stop_event.is_set():
            self._mouse.position = (x, y)

    def _execute(self, ev, ex: Optional[int] = None, ey: Optional[int] = None) -> None:
        """Выполнить одно событие. (ex, ey) — уже пересчитанные координаты."""
        try:
            if ev.type == EVENT_MOVE:
                if ex is not None and ey is not None:
                    self._mouse.position = (ex, ey)
            elif ev.type == EVENT_CLICK:
                if ex is not None and ey is not None:
                    self._mouse.position = (ex, ey)
                time.sleep(CLICK_PAUSE)
                button = getattr(mouse.Button, ev.button or "left", mouse.Button.left)
                if ev.pressed:
                    self._mouse.press(button)
                else:
                    self._mouse.release(button)
            elif ev.type == EVENT_SCROLL:
                self._mouse.scroll(int(ev.dx or 0), int(ev.dy or 0))
            elif ev.type == EVENT_KEY:
                key = str_to_key(ev.key or "")
                # synthetic поднимаем на время нажатия, чтобы глобальный
                # хоткей ESC игнорировал ввод самого плеера (иначе ESC из
                # записи остановил бы само воспроизведение)
                self._synthetic.set()
                try:
                    if ev.action == "press":
                        self._kb.press(key)
                    else:
                        self._kb.release(key)
                    time.sleep(CLICK_PAUSE)
                finally:
                    self._synthetic.clear()
        except Exception as exc:
            # Ошибка одного события не должна ронять всё воспроизведение
            print(f"[player] Ошибка события {ev}: {exc}")

