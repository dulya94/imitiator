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

# 2. Константа сайта по умолчанию
assert webtools.DEFAULT_TARGET_URL == "https://portal.dev.symphony.itfb.tech/document-and-storage/list/all"

# 3. Поле url сценария: полный цикл через JSON
sc = models.Scenario(name="t", url="https://portal.dev.symphony.itfb.tech/")
sc2 = models.Scenario.from_dict(sc.to_dict())
assert sc2.url == sc.url

# 4. Обратная совместимость: старый JSON без поля url
sc3 = models.Scenario.from_dict({"name": "old"})
assert sc3.url == ""

# 5. Конфиг содержит стенд, список стендов и ожидание загрузки
cfg = storage.load_config()
assert str(cfg.get("target_url", "")).startswith("https://portal.dev.symphony.itfb.tech")
assert isinstance(cfg.get("stands", []), list)
assert float(cfg.get("page_load_wait", 0)) >= 0

# 6. open_url на пустом значении не открывает браузер и возвращает False
assert webtools.open_url("") is False

# 7. Интеграция с UI: окно создаётся, комбобокс стендов заполнен, _scenario_url
#    отдаёт стенд по умолчанию для сценария без своего URL (браузер не открываем)
import main

app = main.App()
assert app.cmb_site.get().startswith("https://portal.dev")
assert isinstance(app.cmb_site["values"], tuple) and app.cmb_site["values"]
assert app._scenario_url(models.Scenario(name="x")) == webtools.DEFAULT_TARGET_URL
assert app._scenario_url(models.Scenario(name="y", url="portal.dev.symphony.itfb.tech/login")) == \
    "https://portal.dev.symphony.itfb.tech/login"
assert app._target_site() == webtools.DEFAULT_TARGET_URL

# 8. Список стендов: запоминание и дедупликация
app._remember_stand("portal.dev.symphony.itfb.tech/dev")
assert "https://portal.dev.symphony.itfb.tech/dev" in app._stands_list()
before = len(app._stands_list())
app._remember_stand("https://portal.dev.symphony.itfb.tech/dev")
assert len(app._stands_list()) == before  # дубликат не добавился
app.after(1200, app.destroy)
app.mainloop()

print("URL_SMOKE_OK")
