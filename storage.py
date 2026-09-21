"""
storage.py — сохранение/загрузка сценариев и настроек.

Сценарии:  <папка проекта>/scenarios/<имя>.json
Настройки: <папка проекта>/config.json

Все операции защищены обработкой ошибок и потокобезопасны (планировщик,
рекордер и UI могут обращаться к хранилищу из разных потоков).
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional

from models import Scenario
import webtools

# Базовые пути
BASE_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = BASE_DIR / "scenarios"
CONFIG_PATH = BASE_DIR / "config.json"

# Настройки по умолчанию
DEFAULT_CONFIG: Dict = {
    "loop": False,        # повторять сценарий в цикле
    "delay": 0,           # задержка перед стартом, сек
    # Стенд, на котором выполняются все действия (запись/воспроизведение)
    "target_url": webtools.DEFAULT_TARGET_URL,
    # Список сохранённых стендов для быстрого переключения
    "stands": [],
    # False — при запуске брать стенд, выбранный в списке (по умолчанию);
    # True  — брать стенд, сохранённый в сценарии (кнопка 🔗), если он задан
    "use_scenario_url": False,
    "page_load_wait": 5,  # ожидание загрузки страницы перед стартом, сек
    # Подгонять координаты кликов под текущее разрешение экрана
    "adapt_resolution": True,
    "schedules": {},      # расписание по именам сценариев
}

_CONFIG_LOCK = threading.Lock()


def ensure_dirs() -> None:
    """Создать каталог сценариев, если его нет."""
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Убрать из имени файла запрещённые в Windows символы."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().strip(".")
    return cleaned or "scenario"


def scenario_path(name: str) -> Path:
    """Путь к JSON-файлу сценария по его имени."""
    return SCENARIOS_DIR / (sanitize_filename(name) + ".json")


# --------------------------------------------------------------------------
# Сценарии
# --------------------------------------------------------------------------
def list_scenarios() -> List[Scenario]:
    """Все сценарии из папки scenarios/, отсортированные по дате (новые сверху).

    Повреждённые файлы пропускаются, чтобы один битый JSON не ломал список.
    """
    ensure_dirs()
    scenarios: List[Scenario] = []
    for path in SCENARIOS_DIR.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                scenarios.append(Scenario.from_dict(json.load(f)))
        except (json.JSONDecodeError, ValueError, OSError, KeyError) as exc:
            print(f"[storage] Пропущен повреждённый сценарий {path.name}: {exc}")
    scenarios.sort(key=lambda s: s.created_at, reverse=True)
    return scenarios


def load_scenario(name: str) -> Optional[Scenario]:
    """Загрузить один сценарий по имени. None — если файла нет или он битый."""
    path = scenario_path(name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return Scenario.from_dict(json.load(f))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"[storage] Ошибка загрузки '{name}': {exc}")
        return None


def save_scenario(scenario: Scenario) -> Path:
    """Сохранить сценарий (атомарно: сначала во временный файл, затем replace)."""
    ensure_dirs()
    path = scenario_path(scenario.name)
    tmp = path.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(scenario.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)  # атомарная замена на Windows
    except OSError as exc:
        raise RuntimeError(f"Не удалось сохранить сценарий '{scenario.name}': {exc}") from exc
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return path


def delete_scenario(name: str) -> None:
    """Удалить файл сценария (отсутствие файла ошибкой не считается)."""
    try:
        scenario_path(name).unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Не удалось удалить сценарий '{name}': {exc}") from exc


def rename_scenario(old_name: str, new_name: str) -> None:
    """Переименовать сценарий: перезаписать содержимое под новым именем."""
    scenario = load_scenario(old_name)
    if scenario is None:
        raise RuntimeError(f"Сценарий '{old_name}' не найден")
    delete_scenario(old_name)
    scenario.name = new_name
    save_scenario(scenario)


def scenario_exists(name: str) -> bool:
    return scenario_path(name).exists()


# --------------------------------------------------------------------------
# Конфигурация
# --------------------------------------------------------------------------
def load_config() -> Dict:
    """Загрузить config.json (или вернуть настройки по умолчанию)."""
    with _CONFIG_LOCK:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise ValueError("config.json должен быть объектом")
        except FileNotFoundError:
            cfg = {}
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            print(f"[storage] config.json повреждён ({exc}), используются значения по умолчанию")
            cfg = {}
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in cfg.items() if k != "schedules"})
    merged["schedules"] = dict(cfg.get("schedules") or {})
    return merged


def save_config(cfg: Dict) -> None:
    """Сохранить config.json (атомарно, потокобезопасно)."""
    with _CONFIG_LOCK:
        try:
            tmp = CONFIG_PATH.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, CONFIG_PATH)
        except OSError as exc:
            print(f"[storage] Не удалось сохранить config.json: {exc}")
        finally:
            tmp = CONFIG_PATH.with_suffix(".json.tmp")
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
