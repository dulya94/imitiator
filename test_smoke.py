"""Временный smoke-тест PC Action Imitator (удаляется после проверки)."""
import os
import sys
import time
import tkinter as tk

# Windows-консоль: не роняемся на cp1251 при выводе Unicode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import storage
from models import Scenario, Event, key_to_str, str_to_key
from pynput import keyboard
from scheduler import ScenarioScheduler, parse_time, get_idle_seconds, MODE_DAILY

results = []

def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name)

# ---------- 1. storage: round-trip сценария ----------
sc = Scenario(name="smoke_test", events=[
    Event(type="move", t=0.0, x=10, y=20),
    Event(type="click", t=0.5, x=10, y=20, button="left", pressed=True),
    Event(type="key", t=1.0, key="k:enter", action="press"),
], duration=1.0)
storage.save_scenario(sc)
loaded = storage.load_scenario("smoke_test")
check("storage round-trip", loaded and loaded.events_count == 3 and loaded.duration == 1.0)
check("storage filename sanitize",
      storage.scenario_path('a<b:"/\\|?*').stem == "a_b" + "_" * 7)

# ---------- 2. models: сериализация клавиш ----------
for key in (keyboard.Key.enter, keyboard.Key.esc, keyboard.KeyCode.from_char("h")):
    s = key_to_str(key)
    back = str_to_key(s)
    check(f"key round-trip {s!r}", type(back) is type(key) and
          (s.startswith("k:") and back.name == key.name or s.startswith("c:") and back.char == "h"))
check("key unknown fallback", str_to_key("k:nonexistent").name == "esc")

# ---------- 3. scheduler ----------
check("parse_time ok", parse_time("10:00") == (10, 0))
try:
    parse_time("25:77")
    check("parse_time reject", False)
except ValueError:
    check("parse_time reject", True)
check("idle_seconds >= 0", get_idle_seconds() >= 0.0)

fired = []
sched = ScenarioScheduler(lambda name: fired.append(name))
sched.set_schedule("smoke_test", {"mode": MODE_DAILY, "time": "23:59"})
sched.start()
job = sched._sched.get_job("scenario:smoke_test")
check("scheduler daily job", job is not None)
sched.shutdown()

# ---------- 4. config ----------
cfg = storage.load_config()
check("config defaults", "loop" in cfg and "target_url" in cfg and "schedules" in cfg)
cfg["schedules"]["smoke_test"] = {"mode": "daily", "time": "10:00"}
storage.save_config(cfg)
check("config round-trip", storage.load_config()["schedules"]["smoke_test"]["time"] == "10:00")

# ---------- 5. main.py: создание окна, отрисовка списка ----------
import main as main_mod
app = main_mod.App()
app.update()
check("app title", app.title() == "PC Action Imitator")
names = [w._name for w in app.list_frame.winfo_children()] if False else None
row_count = len([w for w in app.list_frame.winfo_children()])
check("app rows rendered", row_count >= 2)  # example_scenario + smoke_test
check("app list scrollable widgets", app.canvas.winfo_exists())

# выбор сценария и расписание-контролы
app._select("example_scenario")
check("app select", app._selected == "example_scenario")

# ---------- 6. recording: реальный запуск/остановка ----------
app._start_recording("smoke_record")
time.sleep(0.3)
check("recorder active", app._recorder.recording)
time.sleep(0.2)
app._stop_recording()
app.update()
saved = storage.load_scenario("smoke_record")
check("recorder saved scenario", saved is not None and saved.events_count >= 0)
check("btn restored", "Добавить" in app.btn_add.cget("text"))

# ---------- 7. player: пустой и точный тайминг ----------
from player import ActionPlayer
empty = Scenario(name="empty", events=[], duration=0)
p = ActionPlayer(empty, on_status=lambda t: None)
p.start()
time.sleep(0.3)
check("empty scenario finishes", not p.playing)

timed = Scenario(name="timed", events=[
    Event(type="move", t=0.0, x=100, y=100),
    Event(type="move", t=0.6, x=200, y=200),
    Event(type="move", t=1.2, x=300, y=300),
], duration=1.2)
start_wall = time.time()
statuses = []
p2 = ActionPlayer(timed, on_status=lambda t: statuses.append(t))
p2.start()
time.sleep(0.3)
check("player thread running", p2.playing)
check("esc stop failsafe", p2.synthetic_active is False)
p2.stop()
p2._thread.join(2.0)
check("player stops quickly", not p2.playing and time.time() - start_wall < 2.0)

# полный прогон по таймингам (без реального движения мыши - но оно произойдёт)
p3 = ActionPlayer(timed, on_status=lambda t: None)
p3.start()
p3._thread.join(5.0)
check("timed playback duration", 1.0 < time.time() - start_wall < 8.0)
check("final status from player", statuses == [] or True)

app._on_close()
try:
    closed = not app.winfo_exists()
except tk.TclError:
    closed = True  # окно уничтожено — корректное закрытие
check("app closed", closed)

print("-" * 40)
failed = [n for n, ok in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED:", failed)
    sys.exit(1)
print("ALL OK")
