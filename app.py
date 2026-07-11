import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from tkinter import messagebox, ttk

from config import save_cube_roles
from hardware import WheelchairUmbrellaHardware
from tts import TtsSpeaker
from weather import KmaWeatherClient


class WheelchairUmbrellaApp:
    DIRECTIONS = {
        "Up": ("forward", "전진"),
        "Down": ("backward", "후진"),
        "Left": ("left", "좌회전"),
        "Right": ("right", "우회전"),
    }

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.hardware = WheelchairUmbrellaHardware(config)
        self.weather = KmaWeatherClient(
            config.kma_service_key,
            config.kma_nx,
            config.kma_ny,
            config.rain_pty_codes,
        )
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hardware")
        self.tts = None
        self.active_direction = None
        self.last_weather_rain = None
        self.umbrella_state = "unknown"
        self.connecting = False
        self.weather_running = False
        self.weather_after_id = None
        self.matrix_clear_after_id = None
        self.matrix_display_generation = 0
        self.closed = False

        self.connection_text = tk.StringVar(value="BLE 연결 대기")
        self.group_status = tk.StringVar(value="연결 안 됨")
        self.motion_status = tk.StringVar(value="정지")
        self.weather_status = tk.StringVar(value="조회 전")
        self.weather_detail = tk.StringVar(value="기상청 초단기실황")
        self.umbrella_text = tk.StringVar(value="상태 미확인")
        self.matrix_status = tk.StringVar(value="표시 대기")
        self.auto_weather = tk.BooleanVar(value=True)
        self.role_variables = {
            "left_wheel": tk.StringVar(value="Robot {}".format(config.left_wheel_cube)),
            "right_wheel": tk.StringVar(value="Robot {}".format(config.right_wheel_cube)),
            "umbrella": tk.StringVar(value="Robot {}".format(config.umbrella_cube)),
            "led_matrix": tk.StringVar(value="Robot {}".format(config.led_matrix_cube)),
        }

        self._configure_window()
        self._build_ui()
        self.tts = TtsSpeaker(lambda message: self._post(self.log, message, "error"))
        self._bind_controls()
        self.root.after(800, self.refresh_weather)

    def _configure_window(self):
        self.root.title("G-Cube Wheelchair & Weather Umbrella")
        self.root.geometry("1040x760")
        self.root.minsize(820, 700)
        self.root.configure(bg="#f2f4f1")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#ffffff", foreground="#202522", font=("Segoe UI", 12, "bold"))
        style.configure("Label.TLabel", background="#ffffff", foreground="#69706b", font=("Segoe UI", 9))
        style.configure("Value.TLabel", background="#ffffff", foreground="#252a27", font=("Segoe UI", 10, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=(13, 10))
        style.configure("Emergency.TButton", font=("Segoe UI", 11, "bold"), padding=(15, 12))

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#202522", height=66)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="G-CUBE MOBILITY CONTROL",
            bg="#202522",
            fg="#ffffff",
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left", padx=22)
        tk.Label(
            header,
            textvariable=self.connection_text,
            bg="#202522",
            fg="#f1c84a",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right", padx=(8, 22))
        self.connect_button = ttk.Button(
            header,
            text="BLE 연결",
            command=self.connect_hardware,
            style="Action.TButton",
        )
        self.connect_button.pack(side="right", pady=12)

        body = tk.Frame(self.root, bg="#f2f4f1")
        body.pack(fill="both", expand=True, padx=18, pady=16)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(2, weight=1)

        status = ttk.Frame(body, style="Panel.TFrame", padding=14)
        status.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        for index in range(4):
            status.columnconfigure(index, weight=1)
        self._status_item(status, 0, "통합 그룹 {} · Robot 1~4".format(self.config.group_label), self.group_status)
        self.motion_heading = self._status_item(status, 1, "주행 · Robot {}/{}".format(self.config.left_wheel_cube, self.config.right_wheel_cube), self.motion_status)
        self.umbrella_heading = self._status_item(status, 2, "우산 · Robot {}".format(self.config.umbrella_cube), self.umbrella_text)
        self.matrix_heading = self._status_item(status, 3, "LED 매트릭스 · Robot {}".format(self.config.led_matrix_cube), self.matrix_status)

        roles = ttk.Frame(body, style="Panel.TFrame", padding=(14, 10))
        roles.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        roles.columnconfigure(0, weight=1)
        ttk.Label(roles, text="로봇 역할 선택", style="Title.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        role_labels = (
            ("왼쪽 바퀴", "left_wheel"),
            ("오른쪽 바퀴", "right_wheel"),
            ("우산", "umbrella"),
            ("LED", "led_matrix"),
        )
        for column, (label, key) in enumerate(role_labels, start=1):
            field = ttk.Frame(roles, style="Panel.TFrame")
            field.grid(row=0, column=column, padx=5)
            ttk.Label(field, text=label, style="Label.TLabel").pack(anchor="w")
            ttk.Combobox(
                field,
                textvariable=self.role_variables[key],
                values=("Robot 1", "Robot 2", "Robot 3", "Robot 4"),
                state="readonly",
                width=9,
            ).pack(anchor="w", pady=(3, 0))
        self.apply_roles_button = ttk.Button(
            roles,
            text="선택 적용",
            command=self.apply_role_mapping,
        )
        self.apply_roles_button.grid(row=0, column=5, padx=(12, 0), sticky="s")

        mobility = ttk.Frame(body, style="Panel.TFrame", padding=18)
        mobility.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
        mobility.columnconfigure((0, 1, 2), weight=1)
        mobility.rowconfigure((1, 2, 3), weight=1, uniform="drive")
        ttk.Label(mobility, text="휠체어 방향 제어", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        self.direction_buttons = {}
        positions = {
            "Up": (1, 1, "▲\n전진"),
            "Left": (2, 0, "◀\n좌회전"),
            "Right": (2, 2, "▶\n우회전"),
            "Down": (3, 1, "▼\n후진"),
        }
        for key, (row, column, text) in positions.items():
            button = tk.Button(
                mobility,
                text=text,
                bg="#ffffff",
                fg="#252a27",
                activebackground="#e5f3eb",
                activeforeground="#176f4b",
                relief="solid",
                bd=1,
                font=("Segoe UI", 11, "bold"),
                takefocus=False,
            )
            button.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)
            button.bind("<ButtonPress-1>", lambda _event, k=key: self.start_direction(k))
            button.bind("<ButtonRelease-1>", lambda _event, k=key: self.stop_direction(k))
            self.direction_buttons[key] = button
        self.stop_button = ttk.Button(
            mobility,
            text="■  비상 정지  (Space)",
            command=self.emergency_stop,
            style="Emergency.TButton",
        )
        self.stop_button.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
        ttk.Label(
            mobility,
            text="방향키를 누르는 동안만 이동합니다. 키를 놓으면 정지합니다.",
            style="Label.TLabel",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(12, 0))

        side = tk.Frame(body, bg="#f2f4f1")
        side.grid(row=2, column=1, sticky="nsew", padx=(6, 0))
        side.columnconfigure(0, weight=1)
        side.rowconfigure(2, weight=1)

        umbrella = ttk.Frame(side, style="Panel.TFrame", padding=16)
        umbrella.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        umbrella.columnconfigure((0, 1), weight=1)
        ttk.Label(umbrella, text="우산 수동 제어", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttk.Button(umbrella, text="우산 펼치기", command=lambda: self.set_umbrella(True, "manual"), style="Action.TButton").grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(umbrella, text="우산 접기", command=lambda: self.set_umbrella(False, "manual"), style="Action.TButton").grid(row=1, column=1, sticky="ew", padx=(4, 0))

        weather = ttk.Frame(side, style="Panel.TFrame", padding=16)
        weather.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        weather.columnconfigure(0, weight=1)
        ttk.Label(weather, text="기상청 초단기실황", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(weather, textvariable=self.weather_status, style="Value.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 2))
        ttk.Label(weather, textvariable=self.weather_detail, style="Label.TLabel", wraplength=330).grid(row=2, column=0, sticky="w")
        options = ttk.Frame(weather, style="Panel.TFrame")
        options.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Checkbutton(options, text="날씨에 따라 우산 자동 개폐", variable=self.auto_weather).pack(side="left")
        ttk.Button(options, text="지금 조회", command=self.refresh_weather).pack(side="right")

        activity = ttk.Frame(side, style="Panel.TFrame", padding=16)
        activity.grid(row=2, column=0, sticky="nsew")
        activity.columnconfigure(0, weight=1)
        activity.rowconfigure(1, weight=1)
        ttk.Label(activity, text="활동 로그", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.log_text = tk.Text(
            activity,
            width=1,
            height=7,
            bg="#f7f8f6",
            fg="#444a46",
            relief="solid",
            bd=1,
            font=("Consolas", 9),
            state="disabled",
            wrap="word",
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.log("프로그램 준비 완료")

    def _status_item(self, parent, column, label, variable):
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 12, 0))
        heading = ttk.Label(frame, text=label, style="Label.TLabel")
        heading.pack(anchor="w")
        ttk.Label(frame, textvariable=variable, style="Value.TLabel").pack(anchor="w", pady=(4, 0))
        return heading

    def apply_role_mapping(self):
        try:
            roles = {
                key: int(variable.get().split()[-1])
                for key, variable in self.role_variables.items()
            }
            if len(set(roles.values())) != 4:
                raise ValueError("각 역할에는 서로 다른 Robot을 선택해야 합니다.")
        except ValueError as error:
            messagebox.showerror("로봇 역할 설정", str(error), parent=self.root)
            return

        self.active_direction = None
        self.motion_status.set("역할 변경 중")
        self.apply_roles_button.configure(state="disabled")

        def operation():
            if self.hardware.connected:
                self.hardware.emergency_stop()
            self.hardware.set_cube_roles(
                roles["left_wheel"],
                roles["right_wheel"],
                roles["umbrella"],
                roles["led_matrix"],
            )
            save_cube_roles(roles)

        if self.hardware.connected:
            self._submit_hardware(
                operation,
                "로봇 역할 적용 실패",
                lambda: self._roles_applied(roles),
                self._role_apply_failed,
            )
        else:
            try:
                operation()
            except Exception as error:
                self.apply_roles_button.configure(state="normal")
                self.motion_status.set("정지")
                messagebox.showerror("로봇 역할 설정", str(error), parent=self.root)
            else:
                self._roles_applied(roles)

    def _roles_applied(self, roles):
        self.motion_heading.configure(
            text="주행 · Robot {}/{}".format(roles["left_wheel"], roles["right_wheel"])
        )
        self.umbrella_heading.configure(text="우산 · Robot {}".format(roles["umbrella"]))
        self.matrix_heading.configure(text="LED 매트릭스 · Robot {}".format(roles["led_matrix"]))
        self.motion_status.set("정지")
        self.apply_roles_button.configure(state="normal")
        self.log(
            "역할 적용: 왼쪽 {}, 오른쪽 {}, 우산 {}, LED {}".format(
                roles["left_wheel"],
                roles["right_wheel"],
                roles["umbrella"],
                roles["led_matrix"],
            )
        )

    def _role_apply_failed(self):
        self.motion_status.set("정지")
        self.apply_roles_button.configure(state="normal")

    def _bind_controls(self):
        for key in self.DIRECTIONS:
            self.root.bind_all("<KeyPress-{}>".format(key), lambda event, k=key: self._key_press(event, k))
            self.root.bind_all("<KeyRelease-{}>".format(key), lambda event, k=key: self._key_release(event, k))
        self.root.bind_all("<KeyPress-space>", lambda _event: self.emergency_stop())
        self.root.bind_all("<FocusOut>", self._focus_out)

    def _key_press(self, event, key):
        if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.start_direction(key)

    def _key_release(self, event, key):
        if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return
        self.stop_direction(key)

    def _focus_out(self, _event):
        self.root.after(60, self._stop_if_unfocused)

    def _stop_if_unfocused(self):
        if not self.closed and self.root.focus_displayof() is None and self.active_direction:
            active = self.active_direction
            self.stop_direction(active)

    def connect_hardware(self):
        if self.connecting or self.hardware.connected:
            return
        self.connecting = True
        self.connect_button.configure(state="disabled")
        self.connection_text.set("BLE 검색 중")

        def task():
            try:
                self.hardware.connect(lambda message: self._post(self.log, message))
            except Exception as error:
                self._post(self._connection_failed, str(error))
            else:
                self._post(self._connection_ready)

        threading.Thread(target=task, daemon=True).start()

    def _connection_ready(self):
        self.connecting = False
        self.connection_text.set("4개 G-큐브 연결됨")
        self.group_status.set(self.hardware.group.name)
        self.log("통합 그룹 G-큐브 4개 연결 완료")
        self.refresh_weather()

    def _connection_failed(self, message):
        self.connecting = False
        self.connection_text.set("BLE 연결 실패")
        self.connect_button.configure(state="normal")
        self.log(message, "error")

    def start_direction(self, key):
        if key not in self.DIRECTIONS or self.active_direction == key:
            return
        if not self.hardware.connected:
            self.log("먼저 BLE 연결을 완료하세요.", "warning")
            return
        self.active_direction = key
        direction, label = self.DIRECTIONS[key]
        self.motion_status.set(label)
        self._submit_hardware(lambda: self.hardware.drive(direction), "{} 명령 실패".format(label))

    def stop_direction(self, key):
        if self.active_direction != key:
            return
        self.active_direction = None
        self.motion_status.set("정지")
        self._submit_hardware(self.hardware.stop_wheels, "휠 정지 실패")

    def emergency_stop(self):
        self.active_direction = None
        self.motion_status.set("비상 정지")
        self.log("비상 정지 명령")
        threading.Thread(target=self._emergency_task, daemon=True).start()

    def _emergency_task(self):
        try:
            self.hardware.emergency_stop()
        except Exception as error:
            self._post(self.log, str(error), "error")

    def set_umbrella(self, opened, source):
        if not self.hardware.connected:
            self.log("먼저 BLE 연결을 완료하세요.", "warning")
            return
        target = "open" if opened else "closed"
        if self.umbrella_state == target and source == "weather":
            return
        label = "펼칩니다" if opened else "접습니다"
        self.umbrella_text.set("동작 중")
        self.matrix_display_generation += 1
        generation = self.matrix_display_generation
        if self.matrix_clear_after_id is not None:
            try:
                self.root.after_cancel(self.matrix_clear_after_id)
            except tk.TclError:
                pass
            self.matrix_clear_after_id = None
        self.matrix_status.set("비 표시 중" if opened else "해 표시 중")
        self.tts.speak("우산을 {}".format(label))

        def task():
            self.hardware.set_umbrella(opened)
            self.hardware.show_weather_icon(opened)

        def success():
            self.umbrella_state = target
            self.umbrella_text.set("펼침" if opened else "접힘")
            self.log("우산 {} 완료 ({})".format("펼치기" if opened else "접기", source))
            self.matrix_clear_after_id = self.root.after(
                3000,
                self._clear_temporary_matrix,
                generation,
            )

        def failure():
            self.umbrella_text.set("동작 실패")
            self.matrix_status.set("표시 실패")

        self._submit_hardware(task, "우산 동작 실패", success, failure)

    def refresh_weather(self):
        if self.weather_running or self.closed:
            return
        if self.weather_after_id is not None:
            try:
                self.root.after_cancel(self.weather_after_id)
            except tk.TclError:
                pass
            self.weather_after_id = None
        self.weather_running = True
        self.weather_status.set("조회 중")

        def task():
            try:
                observation = self.weather.fetch()
            except Exception as error:
                self._post(self._weather_failed, str(error))
            else:
                self._post(self._weather_ready, observation)

        threading.Thread(target=task, daemon=True).start()

    def _weather_ready(self, observation):
        self.weather_running = False
        state = observation.description
        self.weather_status.set(state)
        details = "{} {} · 기온 {}°C · 습도 {}% · 1시간 강수량 {}mm".format(
            observation.base_date,
            observation.base_time,
            self._display_number(observation.temperature_c),
            self._display_number(observation.humidity_percent),
            self._display_number(observation.rainfall_mm),
        )
        self.weather_detail.set(details)
        self.log("날씨 갱신: {}".format(state))
        if self.auto_weather.get() and observation.is_precipitating != self.last_weather_rain:
            if self.hardware.connected:
                self.set_umbrella(observation.is_precipitating, "weather")
                self.last_weather_rain = observation.is_precipitating
        self._schedule_weather()

    def _weather_failed(self, message):
        self.weather_running = False
        self.weather_status.set("조회 실패")
        self.weather_detail.set(message)
        self.log(message, "error")
        self._schedule_weather()

    def _schedule_weather(self):
        if not self.closed:
            if self.weather_after_id is not None:
                try:
                    self.root.after_cancel(self.weather_after_id)
                except tk.TclError:
                    pass
            self.weather_after_id = self.root.after(
                self.config.weather_poll_seconds * 1000,
                self.refresh_weather,
            )

    def _clear_temporary_matrix(self, generation):
        if generation != self.matrix_display_generation:
            return
        self.matrix_clear_after_id = None
        self._submit_hardware(
            self.hardware.clear_matrix,
            "LED 매트릭스 지우기 실패",
            lambda: self.matrix_status.set("표시 종료"),
        )

    def log(self, message, level="info"):
        if self.closed:
            return
        prefix = {"error": "ERROR", "warning": "WARN"}.get(level, "INFO")
        line = "{}  {}  {}\n".format(datetime.now().strftime("%H:%M:%S"), prefix, message)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _submit_hardware(self, operation, error_prefix, on_success=None, on_error=None):
        def task():
            try:
                operation()
            except Exception as error:
                self._post(self.log, "{}: {}".format(error_prefix, error), "error")
                if on_error:
                    self._post(on_error)
            else:
                if on_success:
                    self._post(on_success)

        self.executor.submit(task)

    def _post(self, function, *args):
        if not self.closed:
            self.root.after(0, function, *args)

    @staticmethod
    def _display_number(value):
        if value is None:
            return "-"
        return "{:g}".format(value)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.hardware.close()
        finally:
            if self.weather_after_id is not None:
                try:
                    self.root.after_cancel(self.weather_after_id)
                except tk.TclError:
                    pass
            if self.matrix_clear_after_id is not None:
                try:
                    self.root.after_cancel(self.matrix_clear_after_id)
                except tk.TclError:
                    pass
            if self.tts:
                self.tts.close()
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.root.destroy()
