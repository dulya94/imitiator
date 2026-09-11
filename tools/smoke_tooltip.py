# -*- coding: utf-8 -*-
"""
tools/smoke_tooltip.py — проверка всплывающих подсказок с горячими клавишами.

Запуск:  python -X utf8 tools\\smoke_tooltip.py
Ожидаемый вывод: TOOLTIP_SMOKE_OK
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name}{(' — ' + detail) if detail else ''}")
    if not cond:
        FAILURES.append(name)


def main() -> None:
    import tkinter as tk
    from tooltip import ToolTip

    root = tk.Tk()
    root.withdraw()

    # --- 1. Базовая механика ToolTip ---
    btn = tk.Button(root, text="B")
    btn.pack()
    root.update_idletasks()
    tip = ToolTip(btn, "F9 — старт", delay_ms=10)
    check("tooltip создаётся", tip is not None)
    check("привязки Enter/Leave/клик установлены",
          all(btn.bind(ev) for ev in ("<Enter>", "<Leave>", "<ButtonPress>", "<Destroy>")))
    # В этом окружении Tk не диспетчеризует синтетические <Enter>/<Leave>
    # (окно скрыто), поэтому показ/скрытие проверяем прямыми вызовами —
    # с реальной мышью события приходят автоматически.
    tip._show()
    root.update()
    check("тултип показывается", tip._tip is not None)
    if tip._tip is not None:
        kids = tip._tip.winfo_children()
        labels = [w for w in kids[0].winfo_children()] if kids else []
        text = labels[0].cget("text") if labels else ""
        check("текст подсказки верный", "F9" in text, text.replace("\n", " | "))
    tip._hide()
    root.update()
    check("тултип скрывается", tip._tip is None)
    # повторный show/hide не ломается
    tip._show(); root.update()
    ok_twice = tip._tip is not None
    tip._hide(); root.update()
    check("повторный цикл show/hide", ok_twice and tip._tip is None)
    tip.set_text("новый текст")
    check("set_text меняет текст", tip.text == "новый текст")

    # --- 2. Интеграция с приложением ---
    import main as main_mod
    app = main_mod.App()
    app.withdraw()
    app.update_idletasks()
    check("tip_add существует", hasattr(app, "tip_add"))
    check("подсказка кнопки '+' с F9/F10",
          "F9" in app.tip_add.text and "F10" in app.tip_add.text,
          app.tip_add.text.replace("\n", " | "))
    check("кнопка '🌐 Открыть' найдена", hasattr(app, "btn_open_site"))
    check("кнопка 'Применить к выбранному' найдена", hasattr(app, "btn_apply_schedule"))
    check("подсказка строки сценария с ESC",
          "ESC" in main_mod.TIP_PLAY and "ESC" in main_mod.TIP_STOP)
    # смена подсказки в режиме записи и обратно
    app.tip_add.set_text(main_mod.TIP_ADD_RECORDING)
    check("подсказка режима записи", "F10" in app.tip_add.text)
    app.tip_add.set_text(main_mod.TIP_ADD_IDLE)
    check("подсказка обратно F9", "F9" in app.tip_add.text)

    app.destroy()
    root.destroy()

    print()
    if FAILURES:
        print(f"TOOLTIP_SMOKE_FAIL: {len(FAILURES)} проверок: {', '.join(FAILURES)}")
        sys.exit(1)
    print("TOOLTIP_SMOKE_OK")


if __name__ == "__main__":
    main()
