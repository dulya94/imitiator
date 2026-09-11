# -*- coding: utf-8 -*-
"""
tools/smoke_screen.py — проверка учёта разрешения экрана.

Запуск:  python -X utf8 tools\\smoke_screen.py
Ожидаемый вывод: SCREEN_SMOKE_OK
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name}{(' — ' + detail) if detail else ''}")
    if not cond:
        FAILURES.append(name)


def main() -> None:
    import screeninfo
    from models import Event, Scenario
    from player import ActionPlayer
    import storage

    # --- 1. Определение разрешения ---
    w, h = screeninfo.primary_resolution()
    check("primary_resolution>0", w > 100 and h > 100, f"{w}x{h}")
    vx, vy, vw, vh = screeninfo.virtual_bounds()
    check("virtual_bounds", vw >= w and vh >= h, f"{vx},{vy} {vw}x{vh}")

    # --- 2. Пересчёт координат ---
    nx, ny = screeninfo.scale_point(960, 540, (1920, 1080), (1280, 720))
    check("scale_point 1920->1280", (nx, ny) == (640, 360), f"({nx},{ny})")
    nx2, ny2 = screeninfo.scale_point(640, 360, (1280, 720), (1920, 1080))
    check("scale_point 1280->1920", (nx2, ny2) == (960, 540), f"({nx2},{ny2})")
    same_x, same_y = screeninfo.scale_point(500, 300, (0, 0), (1920, 1080))
    check("scale_point bad src", (same_x, same_y) == (500, 300))
    cx, cy = screeninfo.clamp_to_primary(-50, 999999)
    check("clamp_to_primary", cx == 0 and 0 <= cy < h, f"({cx},{cy})")
    bx, by = screeninfo.scale_point(100, 200, (1920, 1080), (2560, 1440))
    back_x, back_y = screeninfo.scale_point(bx, by, (2560, 1440), (1920, 1080))
    check("scale round-trip ~", abs(back_x - 100) <= 2 and abs(back_y - 200) <= 2,
          f"({back_x},{back_y})")

    # --- 3. Модель: поля screen_w/screen_h ---
    sc = Scenario(name="t", screen_w=1920, screen_h=1080)
    d = sc.to_dict()
    check("to_dict screen", d.get("screen_w") == 1920 and d.get("screen_h") == 1080)
    sc2 = Scenario.from_dict(json.loads(json.dumps(d)))
    check("from_dict screen round-trip", sc2.screen_size == (1920, 1080))
    old = {"name": "legacy", "events": [], "duration": 1.0}
    sc3 = Scenario.from_dict(old)
    check("old JSON без screen", sc3.screen_size == (0, 0))
    check("screen_note пуст для legacy", sc3.screen_note == "")
    check("screen_note заполнен", sc.screen_note == "1920×1080", sc.screen_note)
    garbage = {"name": "g", "screen_w": "abc", "screen_h": None}
    check("мусор в screen_w", Scenario.from_dict(garbage).screen_size == (0, 0))

    # --- 4. Плеер: масштабирование ---
    sc_sim = Scenario(name="sim", screen_w=w * 2, screen_h=h * 2)
    sc_sim.events = [Event(type="move", t=0.05, x=500, y=400)]
    p = ActionPlayer(sc_sim, fit_screen=True)
    mx, my = p._map_xy(500, 400)
    check("map_xy при другом разрешении", (mx, my) == (250, 200), f"({mx},{my})")
    check("resolution_note не пуст", "→" in p.resolution_note, p.resolution_note)
    p2 = ActionPlayer(sc_sim, fit_screen=False)
    check("fit_screen=False identity", p2._map_xy(500, 400) == (500, 400))
    sc_none = Scenario(name="none")  # без записи разрешения
    sc_none.events = [Event(type="move", t=0.05, x=123, y=321)]
    p3 = ActionPlayer(sc_none, fit_screen=True)
    check("без записи разрешения identity", p3._map_xy(123, 321) == (123, 321))
    sc_same = Scenario(name="same", screen_w=w, screen_h=h)
    sc_same.events = [Event(type="move", t=0.05, x=10, y=20)]
    p4 = ActionPlayer(sc_same)
    check("то же разрешение identity", p4._map_xy(10, 20) == (10, 20))
    sc_out = Scenario(name="out", screen_w=w * 2, screen_h=h * 2)  # масштабирование активно
    sc_out.events = [Event(type="click", t=0.05, x=999999, y=-100, button="left", pressed=True)]
    p5 = ActionPlayer(sc_out)
    ox, oy = p5._map_xy(999999, -100)
    check("клик вне экрана отсечён", 0 <= ox < w and oy == 0, f"({ox},{oy})")

    # --- 5. Конфиг по умолчанию ---
    check("config default adapt_resolution", storage.DEFAULT_CONFIG.get("adapt_resolution") is True)

    # --- 6. Рекордер заполняет разрешение (симуляция без реального захвата) ---
    from recorder import ActionRecorder
    rec = ActionRecorder()
    rec._events = [Event(type="key", t=0.1, key="k:esc", action="press")]
    rec._recording = True
    rec._start_time = 0.0
    rec._mouse_listener = None
    rec._key_listener = None
    sim = rec.stop()
    check("recorder пишет разрешение", sim.screen_size == (w, h), f"{sim.screen_size}")

    # --- 7. UI: чекбокс подгонки и передача в плеер ---
    import main as main_mod
    app = main_mod.App()
    app.withdraw()
    app.update_idletasks()
    check("UI var_fit существует", hasattr(app, "var_fit"))
    default_fit = bool(app.config_data.get("adapt_resolution", True))
    check("UI var_fit из конфига", bool(app.var_fit.get()) == default_fit)
    probe = ActionPlayer(sc_sim, fit_screen=bool(app.var_fit.get()))
    check("UI fit_screen передаётся", probe.fit_screen == default_fit)
    app.destroy()

    # --- 8. Round-trip сценария с разрешением через файл ---
    tmp_json = Path(tempfile.mkdtemp()) / "rt.json"
    tmp_json.write_text(json.dumps(sc.to_dict(), ensure_ascii=False), encoding="utf-8")
    rt = Scenario.from_dict(json.loads(tmp_json.read_text(encoding="utf-8")))
    check("JSON round-trip с экраном", rt.screen_size == (1920, 1080) and rt.screen_note)

    print()
    if FAILURES:
        print(f"SCREEN_SMOKE_FAIL: {len(FAILURES)} проверок: {', '.join(FAILURES)}")
        sys.exit(1)
    print("SCREEN_SMOKE_OK")


if __name__ == "__main__":
    main()
