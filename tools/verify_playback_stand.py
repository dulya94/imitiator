# tools/verify_playback_stand.py — сквозная проверка ИСПРАВЛЕНИЯ:
# кнопка ▶ (и запуск по расписанию) должны открывать стенд,
# выбранный пользователем в списке «Стенд действий».
# Браузер реально НЕ открывается — вызов webtools.open_url перехвачен.
# Запуск: python -X utf8 tools/verify_playback_stand.py
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

import webtools
import storage
import models

TMP_NAME = "tmp_verify_stand"

# Перехватываем открытие браузера: запоминаем адрес, ничего не запускаем
opened: list = []
webtools.open_url = lambda url: (opened.append(url), True)[1]
# Тест не должен менять пользовательский config.json
storage.save_config = lambda cfg: None

import main

app = main.App()
app.config_data = {
    "loop": False, "delay": 0.0,
    "target_url": webtools.DEFAULT_TARGET_URL,
    "stands": [], "use_scenario_url": False,
    "page_load_wait": 0.0, "adapt_resolution": False, "schedules": {},
}
app._controls_from_config()

# Готовим сценарий: пустой (завершается мгновенно), со своим стендом 🔗
sc = models.Scenario(name=TMP_NAME, events=[], duration=0.0,
                     url="https://portal.demo.symphony.itfb.tech/")
storage.save_scenario(sc)

results = []


def check(label: str, expect: str) -> None:
    got = opened[-1] if opened else None
    ok = got == expect
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + label + " -> " + str(got), flush=True)
    if not ok:
        print("     expected: " + expect, flush=True)


def run_and_wait(from_schedule: bool = False) -> None:
    """Нажать ▶ (или сымитировать расписание) и дождаться завершения плеера."""
    app._start_playback(TMP_NAME, from_schedule=from_schedule)
    deadline = time.time() + 10
    while time.time() < deadline:
        app.update()          # прокачиваем очередь Tk (колбэки плеера через after)
        if not (app._player and app._player.playing):
            break
        time.sleep(0.05)
    app.update()


# --- 1. Выбран стенд TEST -> ▶ открывает именно его (хотя у сценария свой DEMO) ---
app.var_sc_url.set(False)
app.cmb_site.set("https://portal.test.symphony.itfb.tech/")
opened.clear()
run_and_wait()
check("play->test (stand from list wins)",
      "https://portal.test.symphony.itfb.tech/")

# --- 2. Смена выбора на MOEK -> ▶ открывает MOEK (стенд можно менять) ---
app.cmb_site.set("https://portal.dev.symphony.moek.itfb.tech/")
opened.clear()
run_and_wait()
check("play->moek (stand changed)",
      "https://portal.dev.symphony.moek.itfb.tech/")

# --- 3. Выбор DEV -> ▶ открывает DEV ---
app.cmb_site.set("https://portal.dev.symphony.itfb.tech/")
opened.clear()
run_and_wait()
check("play->dev", "https://portal.dev.symphony.itfb.tech/")

# --- 4. Запуск ПО РАСПИСАНИЮ тоже берёт выбранный стенд ---
app.cmb_site.set("https://portal.demo.symphony.itfb.tech/")
opened.clear()
run_and_wait(from_schedule=True)
check("schedule->demo", "https://portal.demo.symphony.itfb.tech/")

# --- 5. Своя ссылка (не из списка) тоже работает ---
app.cmb_site.set("portal-custom.symphony.itfb.tech/login")
opened.clear()
run_and_wait()
check("play->custom url", "https://portal-custom.symphony.itfb.tech/login")

# --- 6. Галочка «брать стенд из сценария» -> приоритет у 🔗 ---
app.var_sc_url.set(True)
app.cmb_site.set("https://portal.test.symphony.itfb.tech/")
opened.clear()
run_and_wait()
check("play->scenario url (checkbox on)",
      "https://portal.demo.symphony.itfb.tech/")
app.var_sc_url.set(False)

# --- 7. Включённая галочка, но у сценария стенда нет -> выбранный из списка ---
sc.url = ""
storage.save_scenario(sc)
app.var_sc_url.set(True)
app.cmb_site.set("https://portal.dev.symphony.moek.itfb.tech/")
opened.clear()
run_and_wait()
check("play->list (checkbox on, no own url)",
      "https://portal.dev.symphony.moek.itfb.tech/")
app.var_sc_url.set(False)

# Уборка
try:
    storage.delete_scenario(TMP_NAME)
except Exception:
    pass

app.after(300, app.destroy)
app.mainloop()

passed = sum(1 for r in results if r)
print("-" * 40)
print(f"{passed}/{len(results)} checks passed")
if passed == len(results):
    print("PLAYBACK_STAND_OK")
else:
    sys.exit(1)
