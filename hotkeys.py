"""
hotkeys.py — глобальные горячие клавиши (работают даже без фокуса окна).

  F9  — старт записи
  F10 — стоп записи
  ESC — стоп воспроизведения

suppress_check — колбэк, который возвращает True, когда хоткеи нужно
игнорировать (например, пока плеер сам воспроизводит нажатие ESC).
"""
from __future__ import annotations

from typing import Callable, Optional

from pynput import keyboard


class HotkeyManager:
    """Слушает глобальные нажатия и вызывает колбэки."""

    def __init__(
        self,
        on_f9: Callable[[], None],
        on_f10: Callable[[], None],
        on_esc: Callable[[], None],
        suppress_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._on_f9 = on_f9
        self._on_f10 = on_f10
        self._on_esc = on_esc
        self._suppress_check = suppress_check or (lambda: False)
        self._listener: Optional[keyboard.Listener] = None

    def start(self) -> None:
        if self._listener is None:
            try:
                self._listener = keyboard.Listener(on_press=self._on_press)
                self._listener.start()
            except OSError as exc:
                print(f"[hotkeys] Не удалось запустить слушатель клавиатуры: {exc}")

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _on_press(self, key) -> None:
        try:
            # Пока плеер воспроизводит клавиши, ESC/F-клавиши игнорируем,
            # чтобы синтетический ввод не управлял самим плеером.
            if self._suppress_check():
                return
            if key == keyboard.Key.f9:
                self._on_f9()
            elif key == keyboard.Key.f10:
                self._on_f10()
            elif key == keyboard.Key.esc:
                self._on_esc()
        except Exception as exc:
            print(f"[hotkeys] Ошибка обработки клавиши: {exc}")
