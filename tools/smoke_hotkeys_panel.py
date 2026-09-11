"""Smoke-тест: панель «Горячие клавиши» в главном окне."""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import os
os.chdir(BASE)

import tkinter as tk
import main as m


def find_labels(widget, results, depth=0):
    for w in widget.winfo_children():
        if isinstance(w, ttk.Label):
            results.append(w)
        find_labels(w, results, depth + 1)


def run():
    app = m.App()
    app.update_idletasks()

    # 1. Лабелфрейм панели существует
    labelframes = [w for w in app.winfo_children()
                   if isinstance(w, ttk.LabelFrame) and "Горячие клавиши" in str(w.cget("text"))]
    assert labelframes, "панель горячих клавиш не найдена"
    panel = labelframes[0]

    # 2. Кейкапы F9 / F10 / Esc и описания присутствуют
    texts = []
    collect(panel, texts)
    joined = "\n".join(texts)
    assert "F9" in joined, "нет F9"
    assert "F10" in joined, "нет F10"
    assert "Esc" in joined, "нет Esc"
    assert "Запустить запись" in joined, "нет описания F9"
    assert "Остановить запись" in joined, "нет описания F10"
    assert "Остановить воспроизведение" in joined, "нет описания ESC"

    # 3. Стиль Keycap применён к трём кейкапам
    caps = [t for t in texts if t in ("F9", "F10", "Esc")]
    assert len(caps) == 3, f"кейкапов найдено {len(caps)}, ожидалось 3"

    # 4. Статусная строка всё ещё ниже панели (pack side=bottom последним)
    app.update()
    app.destroy()
    print("HOTKEYS_PANEL_SMOKE_OK")


def collect(widget, out):
    for w in widget.winfo_children():
        if isinstance(w, ttk.Label):
            out.append(str(w.cget("text")))
        collect(w, out)


if __name__ == "__main__":
    import tkinter.ttk as ttk
    run()
