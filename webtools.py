"""
webtools.py — работа с целевым сайтом PC Action Imitator.

Все записываемые и воспроизводимые действия выполняются на целевом сайте:
  https://portal.dev.symphony.itfb.tech/document-and-storage/list/all

Модуль открывает нужный адрес в браузере по умолчанию перед стартом
записи/воспроизведения (само ожидание загрузки делает UI/плеер через
отменяемый отсчёт, чтобы ESC продолжал работать).
"""
from __future__ import annotations

import webbrowser

# Сайт, на котором выполняются все действия (адрес по умолчанию)
DEFAULT_TARGET_URL = "https://portal.dev.symphony.itfb.tech/document-and-storage/list/all"


def normalize_url(url: str) -> str:
    """Привести адрес к полноценному URL.

    * пробелы по краям убираются;
    * если схема не указана — добавляется "https://";
    * пустое значение остаётся пустым.
    """
    url = str(url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    return url


def open_url(url: str) -> bool:
    """Открыть URL в браузере по умолчанию.

    Возвращает True, если адрес ушёл в браузер. False — пустой адрес
    или браузер не удалось запустить (приложение при этом не падает).
    """
    target = normalize_url(url)
    if not target:
        return False
    try:
        return bool(webbrowser.open(target, new=0, autoraise=True))
    except Exception as exc:
        print(f"[webtools] Не удалось открыть {target}: {exc}")
        return False
