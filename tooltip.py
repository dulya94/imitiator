"""
tooltip.py — всплывающие подсказки для виджетов Tkinter.

Использование:
    from tooltip import ToolTip
    ToolTip(button, "F9 — быстрый старт записи")

Подсказка появляется при наведении курсора (с небольшой задержкой),
следует за виджетом и исчезает при уходе курсора / клике / закрытии окна.
"""
from __future__ import annotations

import tkinter as tk

# Оформление подсказки
TOOLTIP_BG = "#2d2d30"      # тёмно-серый, как в VS Code
TOOLTIP_FG = "#f1f1f1"
TOOLTIP_BORDER = "#4f8ef7"  # фирменный синий кант
TOOLTIP_DELAY_MS = 500      # задержка перед появлением


class ToolTip:
    """Тултип, привязанный к виджету (кнопке, полю, метке)."""

    def __init__(
        self,
        widget: tk.Misc,
        text: str,
        delay_ms: int = TOOLTIP_DELAY_MS,
        wraplength: int = 340,
    ) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = max(0, int(delay_ms))
        self.wraplength = wraplength
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        # Наведение / уход / клик / уничтожение виджета
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    # ----------------------------- внутреннее ------------------------------
    def _schedule(self, _event=None) -> None:
        """Запланировать показ подсказки через delay_ms."""
        self._cancel_pending()
        if self.delay_ms:
            self._after_id = self.widget.after(self.delay_ms, self._show)
        else:
            self._show()

    def _cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._tip is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx()
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return  # виджет уже скрыт
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)  # окно без рамки и заголовка
        try:
            tip.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(
            tip, bg=TOOLTIP_BORDER, bd=0,
            highlightthickness=1, highlightbackground=TOOLTIP_BORDER)
        label = tk.Label(
            frame, text=self.text, justify="left", wraplength=self.wraplength,
            bg=TOOLTIP_BG, fg=TOOLTIP_FG, bd=0,
            font=("Segoe UI", 9), padx=8, pady=6)
        label.pack(padx=1, pady=1)
        frame.pack()
        tip.wm_geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide(self, _event=None) -> None:
        self._cancel_pending()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def set_text(self, text: str) -> None:
        """Изменить текст подсказки на лету (например, при смене режима кнопки)."""
        self.text = text
        self._hide()
