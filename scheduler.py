"""
scheduler.py — планировщик запуска сценариев на базе APScheduler.

Поддерживаемые режимы:
  * daily    — каждый день в заданное время (ЧЧ:ММ);
  * interval — каждые N минут;
  * idle     — когда пользователь отсутствует за ПК (нет ввода дольше X секунд).
               Проверка простоя — каждые 30 секунд, через WinAPI
               GetLastInputInfo (работает системно, независимо от фокуса окон).

Все методы потокобезопасны: APScheduler вызывает колбэки из своих потоков,
поэтому UI получает уведомления через root.after (см. main.py).
"""
from __future__ import annotations

import ctypes
import datetime
from typing import Callable, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Режимы расписания
MODE_OFF = "off"
MODE_DAILY = "daily"
MODE_INTERVAL = "interval"
MODE_IDLE = "idle"

IDLE_CHECK_INTERVAL_SEC = 30  # как часто проверяем простой в режиме idle


# --------------------------------------------------------------------------
# Определение времени простоя пользователя (только Windows)
# --------------------------------------------------------------------------
class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    """Сколько секунд пользователь не подавал признаков активности."""
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(millis, 0) / 1000.0
    except AttributeError:
        pass  # не Windows — простой определить нельзя
    except Exception as exc:
        print(f"[scheduler] Ошибка определения простоя: {exc}")
    return 0.0


def parse_time(value: str):
    """'10:00' -> (10, 0). Бросает ValueError при некорректном формате."""
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Ожидается время в формате ЧЧ:ММ, получено: {value!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Время вне диапазона: {value!r}")
    return hour, minute


class ScenarioScheduler:
    """Обёртка над BackgroundScheduler: одно задание = один сценарий."""

    def __init__(self, run_callback: Callable[[str], None]) -> None:
        """
        run_callback(name) — вызывается при срабатывании расписания.
        Внимание: колбэк выполняется в потоке APScheduler!
        """
        self._run_callback = run_callback
        self._sched = BackgroundScheduler(daemon=True)
        self._idle_required: Dict[str, float] = {}  # name -> требуемый простой, сек


    # ------------------------------ жизненный цикл --------------------------
    def start(self) -> None:
        if not self._sched.running:
            try:
                self._sched.start()
            except Exception as exc:
                print(f"[scheduler] Не удалось запустить планировщик: {exc}")

    def shutdown(self, wait: bool = False) -> None:
        try:
            if self._sched.running:
                self._sched.shutdown(wait=wait)
        except Exception:
            pass

    # ------------------------------ управление ------------------------------
    def set_schedule(self, name: str, cfg: Dict) -> None:
        """Установить/обновить расписание для сценария name.

        cfg = {
            "mode": "daily" | "interval" | "idle" | "off",
            "time": "10:00",          # для daily
            "every_n_minutes": 30,    # для interval
            "idle_seconds": 300,      # для idle (минимальный простой)
        }
        """
        self.remove_schedule(name)
        mode = cfg.get("mode", MODE_OFF)
        if mode == MODE_OFF:
            return
        job_id = f"scenario:{name}"

        if mode == MODE_DAILY:
            hour, minute = parse_time(cfg.get("time", "10:00"))
            self._sched.add_job(
                self._fire, CronTrigger(hour=hour, minute=minute),
                args=[name], id=job_id, replace_existing=True,
                misfire_grace_time=3600, name=f"{name}: ежедневно {hour:02d}:{minute:02d}",
            )
        elif mode == MODE_INTERVAL:
            minutes = max(1, int(cfg.get("every_n_minutes", 30)))
            self._sched.add_job(
                self._fire, IntervalTrigger(minutes=minutes),
                args=[name], id=job_id, replace_existing=True,
                name=f"{name}: каждые {minutes} мин",
            )
        elif mode == MODE_IDLE:
            idle_seconds = max(60, int(cfg.get("idle_seconds", 300)))
            self._idle_required[name] = idle_seconds
            self._sched.add_job(
                self._idle_check, IntervalTrigger(seconds=IDLE_CHECK_INTERVAL_SEC),
                args=[name], id=job_id, replace_existing=True,
                name=f"{name}: при простое >= {idle_seconds} сек",
            )

    def remove_schedule(self, name: str) -> None:
        """Убрать расписание сценария (если оно было)."""
        self._idle_required.pop(name, None)
        try:
            if self._sched.get_job(f"scenario:{name}"):
                self._sched.remove_job(f"scenario:{name}")
        except Exception:
            pass

    def next_run_time(self, name: str) -> Optional[datetime.datetime]:
        """Ближайшее время срабатывания (для отображения в UI)."""
        try:
            job = self._sched.get_job(f"scenario:{name}")
            return job.next_run_time if job else None
        except Exception:
            return None

    # ------------------------------ внутреннее ------------------------------
    def _fire(self, name: str) -> None:
        """Сработало расписание — запускаем сценарий."""
        try:
            self._run_callback(name)
        except Exception as exc:
            print(f"[scheduler] Ошибка запуска '{name}' по расписанию: {exc}")

    def _idle_check(self, name: str) -> None:
        """Режим idle: запускать, только если пользователя нет за ПК."""
        required = self._idle_required.get(name, 300)
        if get_idle_seconds() >= required:
            self._fire(name)

