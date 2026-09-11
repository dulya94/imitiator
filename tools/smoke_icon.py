# tools/smoke_icon.py — краткая проверка: окно создаётся, иконка ставится, ошибок нет.
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

import main  # noqa: E402

app = main.App()
# Проверяем, что иконка жива (iconphoto не упал)
assert getattr(app, "_icon_photo", None) is not None, "iconphoto не установился"
print("ICON_OK:", app._icon_photo.width(), "x", app._icon_photo.height())
app.after(1200, app.destroy)
app.mainloop()
print("SMOKE_OK")
