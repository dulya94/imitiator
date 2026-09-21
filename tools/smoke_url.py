# tools/smoke_url.py — проверка привязки всех действий к целевому сайту.
# Запуск: python -X utf8 tools/smoke_url.py
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

import webtools
import storage
import models


# 1. normalize_url: схема добавляется, пробелы убираются, пусто остаётся пустым
assert webtools.normalize_url("portal.dev.symphony.itfb.tech") == \
    "https://portal.dev.symphony.itfb.tech"
assert webtools.normalize_url(" https://portal.dev.symphony.itfb.tech/ ") == \
    "https://portal.dev.symphony.itfb.tech/"
assert webtools.normalize_url("") == ""
assert webtools.normalize_url(None) == ""

# 2. Предустановленные стенды (4 шт.) и адрес по умолчанию = первый стенд
assert webtools.PRESET_STANDS == [
    "https://portal.dev.symphony.itfb.tech/",
    "https://portal.test.symphony.itfb.tech/",
    "https://portal.demo.symphony.itfb.tech/",
    "https://portal.dev.symphony.moek.itfb.tech/",
], "список предустановленных стендов неверен"
assert webtools.DEFAULT_TARGET_URL == webtools.PRESET_STANDS[0]
# preset_stands() возвращает копию, а не саму константу
_copy = webtools.preset_stands()
_copy.append("x")
assert "x" not in webtools.PRESET_STANDS

# 3. Поле url сценария: полный цикл через JSON
sc = models.Scenario(name="t", url="https://portal.dev.symphony.itfb.tech/")
sc2 = models.Scenario.from_dict(sc.to_dict())
assert sc2.url == sc.url

# 4. Обратная совместимость: старый JSON без поля url
sc3 = models.Scenario.from_dict({"name": "old"})
assert sc3.url == ""

# 5. Конфиг: стенд, список стендов, ожидание загрузки, режим выбора стенда
cfg = storage.load_config()
assert isinstance(cfg.get("target_url", ""), str) and cfg["target_url"]
assert isinstance(cfg.get("stands", []), list)
assert float(cfg.get("page_load_wait", 0)) >= 0
assert cfg.get("use_scenario_url") in (True, False)
assert storage.DEFAULT_CONFIG["use_scenario_url"] is False

# 6. open_url на пустом значении не открывает браузер и возвращает False
assert webtools.open_url("") is False

# 7. Интеграция с UI. ВАЖНО: тест ничего не пишет в пользовательский config.json.
import main

storage.save_config = lambda cfg: None  # нейтрализуем запись настроек

app = main.App()
# детерминированное состояние контролов (не зависим от личного config.json)
app.config_data = {
    "loop": False, "delay": 0.0,
    "target_url": webtools.DEFAULT_TARGET_URL,
    "stands": [], "use_scenario_url": False,
    "page_load_wait": 5.0, "adapt_resolution": True, "schedules": {},
}
app._controls_from_config()

# выпадающий список содержит все 4 предустановленных стенда
assert isinstance(app.cmb_site["values"], tuple) and app.cmb_site["values"]
for preset in webtools.PRESET_STANDS:
    assert preset in app.cmb_site["values"], f"нет стенда {preset} в списке"
assert app._stand_values()[:4] == webtools.PRESET_STANDS
assert app._target_site() == webtools.DEFAULT_TARGET_URL

# 8. ИСПРАВЛЕНИЕ: кнопка ▶ открывает стенд, ВЫБРАННЫЙ в списке (его можно менять)
app.var_sc_url.set(False)
app.cmb_site.set("https://portal.test.symphony.itfb.tech/")
assert app._target_site() == "https://portal.test.symphony.itfb.tech/"
# сценарий без своего стенда -> выбранный в списке
assert app._playback_url(models.Scenario(name="x")) == \
    "https://portal.test.symphony.itfb.tech/"
# даже если у сценария свой стенд (🔗), при выключенной галочке берём выбранный
assert app._playback_url(
    models.Scenario(name="y", url="https://portal.demo.symphony.itfb.tech/")) == \
    "https://portal.test.symphony.itfb.tech/"
# меняем выбор в списке -> меняется стенд запуска
app.cmb_site.set("https://portal.demo.symphony.itfb.tech/")
assert app._playback_url(models.Scenario(name="z")) == \
    "https://portal.demo.symphony.itfb.tech/"
assert app._playback_url(
    models.Scenario(name="w", url="https://portal.dev.symphony.moek.itfb.tech/")) == \
    "https://portal.demo.symphony.itfb.tech/"

# 9. Галочка «брать стенд из сценария» включает приоритет 🔗 (если стенд задан)
app.var_sc_url.set(True)
assert app._playback_url(
    models.Scenario(name="w", url="https://portal.dev.symphony.moek.itfb.tech/")) == \
    "https://portal.dev.symphony.moek.itfb.tech/"
# своего стенда нет -> всё равно берём выбранный в списке
assert app._playback_url(models.Scenario(name="no-url")) == \
    "https://portal.demo.symphony.itfb.tech/"
app.var_sc_url.set(False)

# 10. Свои стенды запоминаются; предустановленные в свои не попадают
app._remember_stand("portal.dev.symphony.itfb.tech/dev")
assert "https://portal.dev.symphony.itfb.tech/dev" in app._stands_list()
before = len(app._stands_list())
app._remember_stand("https://portal.dev.symphony.itfb.tech/dev")
assert len(app._stands_list()) == before  # дубликат не добавился
for preset in webtools.PRESET_STANDS:
    app._remember_stand(preset)
    assert preset not in app._stands_list(), "предустановленный стенд попал в список своих"

# 11. Смена стенда в списке (_on_stand_changed) делает его текущим и сохраняет
app.cmb_site.set("https://portal.dev.symphony.moek.itfb.tech/")
app._on_stand_changed()
assert app._target_site() == "https://portal.dev.symphony.moek.itfb.tech/"
assert app.config_data["target_url"] == "https://portal.dev.symphony.moek.itfb.tech/"

# 12. Кнопка «＋ Стенд» (_add_stand): диалоги перехвачены, браузер не открываем
from tkinter import simpledialog as _sd
from tkinter import messagebox as _mb
_orig_ask = _sd.askstring
_orig_yesno = _mb.askyesno
_orig_error = _mb.showerror
_mb.showerror = lambda *a, **k: None          # не блокируемся на сообщении об ошибке
_sd.askstring = lambda *a, **k: "portal-dev2.symphony.itfb.tech/login"
_mb.askyesno = lambda *a, **k: False          # не открывать браузер
try:
    app._add_stand()
finally:
    _sd.askstring = _orig_ask
    _mb.askyesno = _orig_yesno
new_url = "https://portal-dev2.symphony.itfb.tech/login"
assert new_url in app._stands_list(), "стенд не добавлен"
assert app.cmb_site.get() == new_url, "стенд не стал текущим"
assert app._target_site() == new_url
# добавленный стенд появился и в выпадающем списке (после предустановленных)
assert new_url in app.cmb_site["values"]
# отмена диалога ничего не меняет
_sd.askstring = lambda *a, **k: None
try:
    app._add_stand()
finally:
    _sd.askstring = _orig_ask
assert app.cmb_site.get() == new_url
# пустая ссылка отвергается
_sd.askstring = lambda *a, **k: "   "
try:
    app._add_stand()
finally:
    _sd.askstring = _orig_ask
    _mb.showerror = _orig_error
assert app.cmb_site.get() == new_url

app.after(1200, app.destroy)
app.mainloop()

print("URL_SMOKE_OK")
