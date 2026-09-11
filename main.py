"""
main.py — точка входа и графический интерфейс PC Action Imitator (Tkinter).

Все действия (запись и воспроизведение) выполняются на целевом сайте:
  https://portal.dev.symphony.itfb.tech/document-and-storage/list/all
Перед записью и воспроизведением сайт открывается в браузере по умолчанию;
далее следует ожидание загрузки страницы (отменяемое: ESC / кнопка сверху).
Сайт задаётся в поле «Сайт действий» в настройках запуска.

Горячие клавиши (глобальные, работают без фокуса окна):
  F9  — старт записи нового сценария
  F10 — стоп записи
  ESC — стоп воспроизведения
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, Optional

import storage
import webtools
from hotkeys import HotkeyManager
from models import Scenario
from player import ActionPlayer
from recorder import ActionRecorder
from tooltip import ToolTip
from scheduler import (
    MODE_DAILY,
    MODE_IDLE,
    MODE_INTERVAL,
    MODE_OFF,
    ScenarioScheduler,
    parse_time,
)

APP_TITLE = "PC Action Imitator"
ICON_PATH = storage.BASE_DIR / "assets" / "app_icon.png"

# Тексты подсказок с горячими клавишами
TIP_ADD_IDLE = ("F9 — быстрый старт записи (без диалогов)\n"
                "F10 — стоп записи")
TIP_ADD_RECORDING = "Сейчас идёт запись\nF10 или эта кнопка — стоп записи"
TIP_PLAY = "Запустить сценарий\nESC — остановить воспроизведение"
TIP_STOP = "Остановить воспроизведение\n(горячая клавиша ESC)"
TIP_RENAME = "Переименовать сценарий"
TIP_DELETE = "Удалить сценарий (без возврата)"


def setup_window_icon(window: tk.Tk) -> None:
    """Иконка окна из assets/app_icon.png (игнорируем, если файла нет)."""
    try:
        photo = tk.PhotoImage(file=str(ICON_PATH))
        window.iconphoto(True, photo)
        # Ссылку надо держать живой, иначе Tkinter удалит изображение
        window._icon_photo = photo
    except (tk.TclError, OSError):
        pass

# Подписи режимов расписания в комбобоксе -> коды режима
SCHEDULE_LABELS: Dict[str, str] = {
    "Нет": MODE_OFF,
    "Каждый день в...": MODE_DAILY,
    "Каждые N минут": MODE_INTERVAL,
    "Когда ПК без действий": MODE_IDLE,
}

COLOR_ACCENT = "#4f8ef7"
COLOR_DANGER = "#e5484d"
COLOR_SELECTED = "#eef4ff"


def fmt_elapsed(seconds: float) -> str:
    """Секунды -> 'ММ:СС' / 'ЧЧ:ММ:СС'."""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class App(tk.Tk):
    """Главное окно приложения."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("800x580")
        self.minsize(680, 500)
        setup_window_icon(self)

        # ---------------- состояние ----------------
        self.config_data: Dict = storage.load_config()
        self._recorder = ActionRecorder()
        self._player: Optional[ActionPlayer] = None
        self._selected: Optional[str] = None       # выбранный сценарий
        self._recording_name: Optional[str] = None
        self._record_started_at: Optional[float] = None
        self._recording_url: str = ""              # сайт, на котором идёт запись
        self._row_frames: Dict[str, tk.Frame] = {}
        # Отложенный старт записи: браузер открывается, ждём загрузку сайта
        self._pending_record: Optional[str] = None     # id задачи after()
        self._pending_deadline: Optional[float] = None
        self._pending_name: Optional[str] = None

        # ---------------- подсистемы ----------------
        self._scheduler = ScenarioScheduler(self._on_scheduled_run)
        self._hotkeys = HotkeyManager(
            on_f9=self._hotkey_start_record,
            on_f10=self._hotkey_stop_record,
            on_esc=self._hotkey_stop_playback,
            # Пока плеер сам нажимает клавиши, хоткеи игнорируем,
            # чтобы записанный ESC не останавливал воспроизведение.
            suppress_check=lambda: bool(self._player and self._player.synthetic_active),
        )

        self._build_ui()
        self._controls_from_config()
        self._refresh_list()

        self._scheduler.start()
        self._hotkeys.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(500, self._tick)  # периодическое обновление статуса


    # ======================================================================
    #  ПОСТРОЕНИЕ ИНТЕРФЕЙСА
    # ======================================================================
    def _build_ui(self) -> None:
        try:  # нативный вид на Windows
            ttk.Style(self).theme_use("vista")
        except tk.TclError:
            pass
        # Стиль «клавиши» для панели горячих клавиш (моноширинный, как keycap)
        ttk.Style(self).configure(
            "Keycap.TLabel", font=("Consolas", 10, "bold"), padding=(7, 2))

        # ---------- шапка ----------
        header = ttk.Frame(self, padding=(14, 12))
        header.pack(fill="x")
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 16, "bold")).pack(side="left")
        self.btn_add = tk.Button(
            header, text="＋  Добавить имитацию работы",
            font=("Segoe UI", 11, "bold"), bg=COLOR_ACCENT, fg="white",
            activebackground="#3b7ae0", activeforeground="white",
            relief="flat", padx=14, pady=6, cursor="hand2",
            command=self._on_add_clicked,
        )
        self.btn_add.pack(side="right")
        # Подсказка на главной кнопке (текст меняется в режимах)
        self.tip_add = ToolTip(self.btn_add, TIP_ADD_IDLE)

        # ---------- список сценариев (прокручиваемый) ----------
        list_wrap = ttk.Frame(self, padding=(14, 0))
        list_wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(list_wrap, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_wrap, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg=self["bg"])
        self.list_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self._canvas_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._canvas_window, width=e.width),
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ---------- нижняя панель настроек ----------
        footer = ttk.LabelFrame(self, text=" Настройки запуска ", padding=(12, 8))
        footer.pack(fill="x", padx=14, pady=(8, 4))

        self.var_loop = tk.BooleanVar(value=False)
        ttk.Checkbutton(footer, text="Повторять в цикле", variable=self.var_loop).grid(
            row=0, column=0, sticky="w")

        ttk.Label(footer, text="Задержка перед стартом (сек):").grid(
            row=0, column=1, sticky="e", padx=(20, 4))
        self.spin_delay = ttk.Spinbox(footer, from_=0, to=86400, width=7)
        self.spin_delay.grid(row=0, column=2, sticky="w")

        # Подгонка координат под текущее разрешение экрана (см. screeninfo.py)
        self.var_fit = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            footer, text="Подгонять координаты под разрешение экрана",
            variable=self.var_fit).grid(row=0, column=3, sticky="w", padx=(24, 0))

        # ---------- строка 2: целевой сайт, на котором выполняются действия ----------
        ttk.Label(footer, text="Сайт действий:").grid(
            row=2, column=0, sticky="w", pady=(8, 0))
        self.ent_site = ttk.Entry(footer)
        self.ent_site.grid(row=2, column=1, columnspan=4, sticky="we",
                           pady=(8, 0), padx=(0, 6))
        self.btn_open_site = ttk.Button(
            footer, text="🌐 Открыть", width=10, command=self._open_site_now)
        self.btn_open_site.grid(row=2, column=5, sticky="w", pady=(8, 0))
        ToolTip(self.btn_open_site, "Открыть «Сайт действий» в браузере по умолчанию")
        ttk.Label(footer, text="Ожидание загрузки (сек):").grid(
            row=2, column=6, sticky="e", pady=(8, 0), padx=(20, 4))
        self.ent_page_wait = ttk.Spinbox(footer, from_=0, to=600, width=5)
        self.ent_page_wait.grid(row=2, column=7, sticky="w", pady=(8, 0))

        ttk.Label(footer, text="Расписание:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.cmb_schedule = ttk.Combobox(
            footer, values=list(SCHEDULE_LABELS), state="readonly", width=20)
        self.cmb_schedule.current(0)
        self.cmb_schedule.grid(row=1, column=1, columnspan=2, sticky="w", pady=(8, 0), padx=(0, 6))
        self.cmb_schedule.bind("<<ComboboxSelected>>", lambda e: self._on_schedule_mode_changed())

        # Поля параметров расписания (видимость зависит от режима)
        self.lbl_time = ttk.Label(footer, text="в")
        self.ent_time = ttk.Entry(footer, width=7)
        self.ent_time.insert(0, "10:00")
        self.lbl_minutes = ttk.Label(footer, text="N мин =")
        self.ent_minutes = ttk.Entry(footer, width=6)
        self.ent_minutes.insert(0, "30")
        self.lbl_idle = ttk.Label(footer, text="простой, сек =")
        self.ent_idle = ttk.Entry(footer, width=7)
        self.ent_idle.insert(0, "300")

        self.btn_apply_schedule = ttk.Button(
            footer, text="Применить к выбранному", command=self._apply_schedule)
        self.btn_apply_schedule.grid(row=1, column=6, sticky="e", pady=(8, 0), padx=(10, 0))
        ToolTip(self.btn_apply_schedule,
                "Сохранить расписание для выбранного сценария\n"
                "(клик по строке в списке = выбор)")
        footer.columnconfigure(1, weight=1)  # поле сайта растягивается

        # ---------- панель горячих клавиш (постоянная справка) ----------
        hotkeys_frame = ttk.LabelFrame(self, text=" ⌨ Горячие клавиши ", padding=(12, 6))
        hotkeys_frame.pack(fill="x", padx=14, pady=(6, 4))

        def _keycap(parent: ttk.LabelFrame, key: str, desc: str, col: int) -> None:
            """Мини-«клавиша» + описание в один столбец панели."""
            cell = ttk.Frame(parent)
            cell.grid(row=0, column=col, sticky="nsew", padx=(0, 18))
            cap = ttk.Label(cell, text=key, style="Keycap.TLabel", padding=(6, 2))
            cap.pack(anchor="w")
            ttk.Label(cell, text=desc, foreground="#9aa7b8").pack(anchor="w")

        _keycap(hotkeys_frame, "F9",  "Запустить запись действий", 0)
        _keycap(hotkeys_frame, "F10", "Остановить запись", 1)
        _keycap(hotkeys_frame, "Esc", "Остановить воспроизведение", 2)
        for c in range(3):
            hotkeys_frame.columnconfigure(c, weight=1)

        # ---------- строка статуса ----------
        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status_var, anchor="w",
                  padding=(14, 6), relief="sunken").pack(fill="x", side="bottom")

    def _on_mousewheel(self, event) -> None:
        """Прокрутка списка колесом мыши."""
        step = int(-event.delta / 120)
        if step == 0:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)


    # ======================================================================
    #  СПИСОК СЦЕНАРИЕВ
    # ======================================================================
    def _refresh_list(self) -> None:
        """Перерисовать список сценариев из /scenarios/."""
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._row_frames.clear()
        scenarios = storage.list_scenarios()
        if not scenarios:
            ttk.Label(
                self.list_frame,
                text="Сценариев пока нет.\n\n"
                     "Нажмите «＋ Добавить имитацию работы» (или F9),\n"
                     "чтобы записать первый сценарий.",
                padding=40, justify="center", foreground="#888",
            ).pack()
            return
        for sc in scenarios:
            self._build_row(sc)

    def _build_row(self, sc: Scenario) -> None:
        """Строка сценария: имя, длительность, дата и кнопки ▶ ⏹ ✏ 🗑."""
        is_selected = self._selected == sc.name
        bg = COLOR_SELECTED if is_selected else "white"
        row = tk.Frame(
            self.list_frame, bg=bg, padx=8, pady=4,
            highlightthickness=1,
            highlightbackground=COLOR_ACCENT if is_selected else "#dcdcdc",
        )
        row.pack(fill="x", pady=3, padx=2)
        self._row_frames[sc.name] = row

        icon = tk.Label(row, text="📄", font=("Segoe UI Emoji", 12), bg=bg, cursor="hand2")
        icon.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 6))

        # подпись с расписанием, целевой страницей и разрешением записи
        schedule_note = ""
        sch = self.config_data.get("schedules", {}).get(sc.name)
        if sch and sch.get("mode", "off") != "off":
            schedule_note = f"  •  ⏰ {self._schedule_note(sch)}"
        url_note = f"  •  🌐 {sc.url}" if getattr(sc, "url", "") else ""
        screen_note = getattr(sc, "screen_note", "")
        res_note = f"  •  🖥 {screen_note}" if screen_note else ""

        name_lbl = tk.Label(row, text=sc.name, font=("Segoe UI", 10, "bold"),
                            bg=bg, anchor="w", cursor="hand2")
        name_lbl.grid(row=0, column=1, sticky="w")
        info_lbl = tk.Label(
            row, font=("Segoe UI", 8), fg="#666", bg=bg, anchor="w",
            text=f"{sc.duration_str}  •  {sc.created_str}  •  "
                 f"{sc.events_count} действий{schedule_note}{url_note}{res_note}")
        info_lbl.grid(row=1, column=1, sticky="w")

        for w in (icon, name_lbl, info_lbl):
            w.bind("<Button-1>", lambda e, n=sc.name: self._select(n))

        buttons = (
            ("▶", COLOR_ACCENT, lambda n=sc.name: self._start_playback(n), TIP_PLAY),
            ("⏹", COLOR_DANGER, self._stop_playback_if_any, TIP_STOP),
            ("✏", "#8a8a8a", lambda n=sc.name: self._rename(n), TIP_RENAME),
            ("🗑", COLOR_DANGER, lambda n=sc.name: self._delete(n), TIP_DELETE),
        )
        # Кнопки ▶ ⏹ ✏ 🗑 в фиксированных колонках справа
        for col, (text, color, cmd, _tip) in enumerate(buttons, start=2):
            btn = tk.Button(
                row, text=text, command=cmd, width=3, relief="flat",
                bg=bg, fg=color, font=("Segoe UI", 11), cursor="hand2")
            btn.grid(row=0, column=col, rowspan=2, sticky="nse", padx=2)
            ToolTip(btn, _tip)  # подсказка при наведении
        row.columnconfigure(1, weight=1)  # имя растягивается

    def _schedule_note(self, sch: dict) -> str:
        """Короткое описание расписания для подписи строки."""
        mode = sch.get("mode")
        if mode == MODE_DAILY:
            return f"каждый день в {sch.get('time', '10:00')}"
        if mode == MODE_INTERVAL:
            return f"каждые {sch.get('every_n_minutes', 30)} мин"
        if mode == MODE_IDLE:
            return f"при простое ≥ {sch.get('idle_seconds', 300)} сек"
        return ""


    # ======================================================================
    #  ЗАПИСЬ ДЕЙСТВИЙ
    # ======================================================================
    def _on_add_clicked(self) -> None:
        """Кнопка «＋» — спросить имя, открыть сайт и начать запись.

        Во время записи — стоп. Во время ожидания загрузки сайта — отмена.
        """
        if self._recorder.recording:
            self._stop_recording()
            return
        if self._pending_record is not None:
            self._cancel_pending_record("Запись отменена до загрузки сайта")
            return
        name = simpledialog.askstring(
            "Новый сценарий", "Введите имя сценария:", parent=self)
        if not name or not name.strip():
            self._set_status("Готово")
            return
        name = name.strip()
        url = simpledialog.askstring(
            "Новый сценарий",
            "URL страницы, на которой записывать действия\n(пусто — сайт по умолчанию):",
            initialvalue=self._target_site(), parent=self)
        if url is None:
            self._set_status("Готово")
            return
        # Если такое имя уже занято — добавляем суффикс (2), (3), ...
        base, i = name, 2
        while storage.scenario_exists(name):
            name = f"{base} ({i})"
            i += 1
        self._open_site_then_record(name, webtools.normalize_url(url))

    def _open_site_then_record(self, name: str, url: str = "") -> None:
        """Открыть сайт в браузере и начать запись после загрузки страницы."""
        target = webtools.normalize_url(url) or self._target_site()
        webtools.open_url(target)
        wait = self._page_wait()
        self._pending_name = name
        self._pending_deadline = time.time() + wait
        self.btn_add.configure(text="⏹  Отменить запуск", bg=COLOR_DANGER)
        self._set_status(
            f"🌐 Открываю {target} — запись «{name}» начнётся "
            f"через {int(wait)} сек (кнопка сверху / ESC — отмена)")
        self._pending_record = self.after(
            int(wait * 1000), lambda: self._begin_pending_record(name))

    def _begin_pending_record(self, name: str) -> None:
        """Ожидание завершилось — старт записи на загруженном сайте."""
        url = webtools.normalize_url(self.ent_site.get())
        self._pending_record = None
        self._pending_deadline = None
        self._pending_name = None
        self._start_recording(name, url)

    def _cancel_pending_record(self, message: str) -> None:
        """Отменить запланированную запись (пользователь или закрытие окна)."""
        if self._pending_record is not None:
            try:
                self.after_cancel(self._pending_record)
            except Exception:
                pass
        self._pending_record = None
        self._pending_deadline = None
        self._pending_name = None
        self.btn_add.configure(text="＋  Добавить имитацию работы", bg=COLOR_ACCENT)
        self.tip_add.set_text(TIP_ADD_IDLE)
        self._set_status(message)

    def _start_recording(self, name: str, url: str = "") -> None:
        """Начать запись сценария (сайт уже открыт, ожидание загрузки пройдено)."""
        self._recording_url = webtools.normalize_url(url)
        try:
            self._recorder.start()
        except RuntimeError as exc:
            messagebox.showerror("Запись", str(exc), parent=self)
            self._set_status("Готово")
            return
        self._recording_name = name
        self._record_started_at = time.time()
        self.btn_add.configure(text="⏹  Остановить запись", bg=COLOR_DANGER)
        self.tip_add.set_text(TIP_ADD_RECORDING)  # подсказка меняется в режиме записи
        site_note = f" на {self._recording_url}" if self._recording_url else ""
        self._set_status(
            f"● ЗАПИСЬ: «{name}»{site_note} (F10 или кнопка сверху — стоп). Действуйте!")

    def _stop_recording(self) -> None:
        """Остановить запись и сохранить сценарий в /scenarios/<имя>.json."""
        if not self._recorder.recording:
            return
        try:
            scenario = self._recorder.stop()
        except RuntimeError as exc:
            messagebox.showerror("Запись", str(exc), parent=self)
            return
        name = self._recording_name or "Сценарий"
        scenario.name = name
        scenario.url = self._recording_url  # страница, где выполнялись действия
        # Длительность: по последнему событию, либо по фактическому времени записи
        if scenario.duration <= 0 and self._record_started_at:
            scenario.duration = time.time() - self._record_started_at
        scenario.created_at = time.time()
        try:
            storage.save_scenario(scenario)
        except RuntimeError as exc:
            messagebox.showerror("Сохранение", str(exc), parent=self)
            self._set_status("Готово")
        else:
            self._set_status(
                f"✔ Сценарий «{name}» сохранён ({scenario.duration_str}, "
                f"{scenario.events_count} действий)")
        self._recording_name = None
        self._record_started_at = None
        self._recording_url = ""
        self.btn_add.configure(text="＋  Добавить имитацию работы", bg=COLOR_ACCENT)
        self.tip_add.set_text(TIP_ADD_IDLE)  # подсказка возвращается к F9/F10
        self._refresh_list()

    # ------------------- обработчики горячих клавиш -------------------
    def _hotkey_start_record(self) -> None:
        """F9: старт записи с автоматическим именем."""
        self.after(0, self._start_record_hotkey)

    def _start_record_hotkey(self) -> None:
        if self._recorder.recording or self._pending_record is not None:
            return
        if self._player and self._player.playing:
            self._set_status("Нельзя записывать во время воспроизведения (ESC — стоп)")
            return
        name = "Сценарий " + time.strftime("%Y-%m-%d %H-%M-%S")
        base, i = name, 2
        while storage.scenario_exists(name):
            name = f"{base} ({i})"
            i += 1
        # F9 записывает без диалогов — на сайте из настроек
        self._open_site_then_record(name, "")

    def _hotkey_stop_record(self) -> None:
        """F10: стоп записи."""
        self.after(0, self._stop_recording)

    def _hotkey_stop_playback(self) -> None:
        """ESC: стоп воспроизведения."""
        self.after(0, self._stop_playback_if_any)


    # ======================================================================
    #  ВОСПРОИЗВЕДЕНИЕ
    # ======================================================================
    def _get_delay(self) -> float:
        try:
            return max(0.0, float(self.spin_delay.get()))
        except ValueError:
            return 0.0

    def _save_controls(self) -> None:
        """Сохранить loop/delay/сайт/подгонку разрешения в config.json."""
        self.config_data["loop"] = bool(self.var_loop.get())
        self.config_data["delay"] = self._get_delay()
        self.config_data["target_url"] = self._target_site()
        self.config_data["page_load_wait"] = self._page_wait()
        self.config_data["adapt_resolution"] = bool(self.var_fit.get())
        storage.save_config(self.config_data)

    def _controls_from_config(self) -> None:
        """Заполнить контролы из config.json."""
        self.var_loop.set(bool(self.config_data.get("loop", False)))
        self.spin_delay.delete(0, "end")
        self.spin_delay.insert(0, str(self.config_data.get("delay", 0)))
        self.ent_site.delete(0, "end")
        self.ent_site.insert(0, str(self.config_data.get("target_url", webtools.DEFAULT_TARGET_URL)))
        self.ent_page_wait.delete(0, "end")
        self.ent_page_wait.insert(0, str(self.config_data.get("page_load_wait", 5)))
        self.var_fit.set(bool(self.config_data.get("adapt_resolution", True)))

    # ---------------------- целевой сайт действий ----------------------
    def _target_site(self) -> str:
        """Сайт из поля настроек (нормализованный; пусто — адрес по умолчанию)."""
        return webtools.normalize_url(self.ent_site.get()) or webtools.DEFAULT_TARGET_URL

    def _page_wait(self) -> float:
        """Ожидание загрузки страницы перед стартом записи/воспроизведения."""
        try:
            return max(0.0, float(self.ent_page_wait.get()))
        except (ValueError, TypeError):
            return 5.0

    def _scenario_url(self, scenario: Scenario) -> str:
        """URL для сценария: свой, иначе глобальный сайт из настроек."""
        return webtools.normalize_url(getattr(scenario, "url", "")) or self._target_site()

    def _open_site_now(self) -> None:
        """Кнопка «🌐 Открыть» — открыть сайт в браузере вручную."""
        self._save_controls()
        url = self._target_site()
        if webtools.open_url(url):
            self._set_status(f"🌐 Сайт открыт в браузере: {url}")
        else:
            self._set_status(f"⚠ Не удалось открыть сайт: {url}")

    def _start_playback(self, name: str, from_schedule: bool = False) -> None:
        """Запустить сценарий в фоновом потоке (UI не блокируется)."""
        if self._recorder.recording or self._pending_record is not None:
            self._set_status("Идёт или готовится запись (F10 — стоп, ESC — отмена)")
            return
        if self._player and self._player.playing:
            self._set_status("Воспроизведение уже выполняется (ESC — стоп)")
            return
        scenario = storage.load_scenario(name)
        if scenario is None:
            messagebox.showerror("Воспроизведение",
                                 f"Сценарий «{name}» не найден или повреждён.",
                                 parent=self)
            self._refresh_list()
            return
        loop = bool(self.var_loop.get())
        # Открываем целевой сайт и добавляем ожидание его загрузки к задержке
        url = self._scenario_url(scenario)
        user_delay = self._get_delay() if not from_schedule else 0.0
        delay = self._page_wait() + user_delay
        webtools.open_url(url)
        self._save_controls()
        # Колбэки из потока плеера передаём в поток Tk через after
        self._player = ActionPlayer(
            scenario,
            loop=loop,
            delay=delay,
            fit_screen=bool(self.var_fit.get()),  # пересчёт координат под экран
            on_status=lambda text: self.after(0, self._set_status, text),
            on_finished=lambda: self.after(0, self._on_play_finished),
        )
        self._player.start()
        prefix = "По расписанию запущено: " if from_schedule else "Воспроизведение: "
        res_note = self._player.resolution_note
        res_part = f"  🖥 {res_note}" if res_note else ""
        self._set_status(
            f"{prefix}«{name}» {scenario.duration_str}, цикл={loop}  🌐 {url}{res_part}  "
            f"старт через {int(delay)} сек (ESC — стоп)")

    def _stop_playback_if_any(self) -> None:
        """Остановить воспроизведение / отменить отложенную запись (ESC, кнопка ⏹)."""
        if self._player and self._player.playing:
            self._player.stop()
        elif self._pending_record is not None:
            self._cancel_pending_record("Запись отменена до загрузки сайта")
        elif not self._recorder.recording:
            self._set_status("Готово")

    def _on_play_finished(self) -> None:
        self._player = None
        # финальный текст статуса уже установлен плеером


    # ======================================================================
    #  ПЛАНИРОВЩИК
    # ======================================================================
    def _on_scheduled_run(self, name: str) -> None:
        """Колбэк APScheduler (чужой поток) -> передаём запуск в поток Tk."""
        self.after(0, lambda: self._start_playback(name, from_schedule=True))

    def _on_schedule_mode_changed(self) -> None:
        """Показать поле параметра, соответствующее выбранному режиму."""
        mode = SCHEDULE_LABELS.get(self.cmb_schedule.get(), MODE_OFF)
        widgets = {
            MODE_DAILY: (self.lbl_time, self.ent_time),
            MODE_INTERVAL: (self.lbl_minutes, self.ent_minutes),
            MODE_IDLE: (self.lbl_idle, self.ent_idle),
        }
        for m, pair in widgets.items():
            is_shown = bool(pair[0].grid_info())
            if m == mode and not is_shown:
                pair[0].grid(row=1, column=3, sticky="e", pady=(8, 0), padx=(8, 2))
                pair[1].grid(row=1, column=4, sticky="w", pady=(8, 0))
            elif m != mode and is_shown:
                pair[0].grid_remove()
                pair[1].grid_remove()

    def _load_schedule_controls(self, name: Optional[str]) -> None:
        """Заполнить расписание-контролы из config.json для сценария name."""
        self.cmb_schedule.set("Нет")
        for pair in ((self.lbl_time, self.ent_time),
                     (self.lbl_minutes, self.ent_minutes),
                     (self.lbl_idle, self.ent_idle)):
            pair[0].grid_remove()
            pair[1].grid_remove()
        if not name:
            return
        sch = self.config_data.get("schedules", {}).get(name) or {}
        mode = sch.get("mode", "off")
        label = next((l for l, m in SCHEDULE_LABELS.items() if m == mode), None)
        if not label:
            return
        self.cmb_schedule.set(label)
        if mode == MODE_DAILY:
            self.ent_time.delete(0, "end")
            self.ent_time.insert(0, str(sch.get("time", "10:00")))
        elif mode == MODE_INTERVAL:
            self.ent_minutes.delete(0, "end")
            self.ent_minutes.insert(0, str(sch.get("every_n_minutes", 30)))
        elif mode == MODE_IDLE:
            self.ent_idle.delete(0, "end")
            self.ent_idle.insert(0, str(sch.get("idle_seconds", 300)))
        self._on_schedule_mode_changed()

    def _apply_schedule(self) -> None:
        """Применить расписание к выбранному сценарию и сохранить в config.json."""
        if not self._selected:
            self._set_status("Выберите сценарий в списке (клик по строке)")
            return
        mode = SCHEDULE_LABELS.get(self.cmb_schedule.get(), MODE_OFF)
        cfg: Dict = {"mode": mode}
        try:
            if mode == MODE_DAILY:
                cfg["time"] = self.ent_time.get().strip()
                parse_time(cfg["time"])
            elif mode == MODE_INTERVAL:
                cfg["every_n_minutes"] = int(self.ent_minutes.get().strip())
            elif mode == MODE_IDLE:
                cfg["idle_seconds"] = int(self.ent_idle.get().strip())
        except ValueError as exc:
            messagebox.showerror("Расписание", str(exc), parent=self)
            return
        self.config_data.setdefault("schedules", {})[self._selected] = cfg
        storage.save_config(self.config_data)
        if mode == MODE_OFF:
            self._scheduler.remove_schedule(self._selected)
            self._set_status(f"Расписание «{self._selected}» отключено")
        else:
            try:
                self._scheduler.set_schedule(self._selected, cfg)
            except Exception as exc:
                messagebox.showerror("Расписание",
                                     f"Не удалось установить расписание: {exc}", parent=self)
                return
            nxt = self._scheduler.next_run_time(self._selected)
            when = f", ближайший запуск: {nxt:%H:%M}" if nxt else ""
            self._set_status(f"⏰ «{self._selected}»: {self._schedule_note(cfg)}{when}")
        self._refresh_list()


    # ======================================================================
    #  ПЕРЕИМЕНОВАНИЕ / УДАЛЕНИЕ / ВЫБОР
    # ======================================================================
    def _select(self, name: str) -> None:
        """Клик по строке списка — выбрать сценарий (подсветка + расписание)."""
        self._selected = name
        self._load_schedule_controls(name)
        self._refresh_list()

    def _rename(self, old_name: str) -> None:
        new_name = simpledialog.askstring(
            "Переименовать", "Новое имя сценария:",
            initialvalue=old_name, parent=self)
        if not new_name or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        try:
            storage.rename_scenario(old_name, new_name)
        except RuntimeError as exc:
            messagebox.showerror("Переименование", str(exc), parent=self)
            return
        # Расписание переносится за сценарием
        schedules = self.config_data.setdefault("schedules", {})
        if old_name in schedules:
            sch = schedules.pop(old_name)
            schedules[new_name] = sch
            storage.save_config(self.config_data)
            self._scheduler.remove_schedule(old_name)
            try:
                self._scheduler.set_schedule(new_name, sch)
            except Exception:
                pass
        if self._selected == old_name:
            self._selected = new_name
        self._refresh_list()
        self._set_status(f"✔ Переименовано: «{old_name}» -> «{new_name}»")

    def _delete(self, name: str) -> None:
        if not messagebox.askyesno("Удаление", f"Удалить сценарий «{name}»?", parent=self):
            return
        try:
            storage.delete_scenario(name)
        except RuntimeError as exc:
            messagebox.showerror("Удаление", str(exc), parent=self)
            return
        self._scheduler.remove_schedule(name)
        self.config_data.get("schedules", {}).pop(name, None)
        storage.save_config(self.config_data)
        if self._selected == name:
            self._selected = None
        self._refresh_list()
        self._set_status(f"🗑 Сценарий «{name}» удалён")

    # ======================================================================
    #  СЛУЖЕБНОЕ
    # ======================================================================
    def _tick(self) -> None:
        """Периодическое обновление статуса (таймер записи / ожидание сайта)."""
        if self._recorder.recording and self._record_started_at:
            elapsed = time.time() - self._record_started_at
            self._set_status(
                f"● ЗАПИСЬ: «{self._recording_name}»  {fmt_elapsed(elapsed)}  "
                f"(F10 — стоп)")
        elif self._pending_record is not None and self._pending_deadline:
            remaining = max(0, int(self._pending_deadline - time.time()))
            self._set_status(
                f"🌐 Загрузка сайта — запись «{self._pending_name}» "
                f"через {remaining} сек (кнопка сверху / ESC — отмена)")
        self.after(500, self._tick)

    def _on_close(self) -> None:
        """Корректное завершение: приложение не падает при закрытии окна
        во время записи или воспроизведения."""
        if self._pending_record is not None:  # отмена запланированной записи
            self._cancel_pending_record("Готово")
        try:  # сохранить настройки (сайт, задержка, цикл)
            self._save_controls()
        except Exception:
            pass
        try:
            self._hotkeys.stop()
        except Exception:
            pass
        if self._recorder.recording:
            try:
                self._recorder.stop()
            except Exception:
                pass
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
        try:
            self._scheduler.shutdown()
        except Exception:
            pass
        self.destroy()


def main() -> None:
    """Точка входа PC Action Imitator."""
    storage.ensure_dirs()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()






