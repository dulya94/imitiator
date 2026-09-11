"""
run_app.pyw — запуск PC Action Imitator без консольного окна.

Файл имеет расширение .pyw, поэтому Windows запускает его через pythonw.exe
(консоль не появляется). Ярлык на рабочем столе указывает на этот файл.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    os.chdir(BASE_DIR)
    sys.path.insert(0, str(BASE_DIR))
    runpy.run_path(str(BASE_DIR / "main.py"), run_name="__main__")
