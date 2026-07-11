import os
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROLE_FILE = ROOT / "robot_roles.json"


def load_env(path=None):
    env_path = Path(path or ROOT / ".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def parse_group_id(value):
    text = str(value).strip().upper()
    if text.startswith("0X"):
        text = text[2:]
    if not 1 <= len(text) <= 2 or any(char not in "01234567" for char in text):
        raise ValueError("Group ID must use digits 0 to 7 and be between 00 and 77.")
    return int(text, 16)


def env_int(name, default, minimum=None, maximum=None):
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        raise ValueError("{} must be an integer.".format(name))
    if minimum is not None and value < minimum:
        raise ValueError("{} must be at least {}.".format(name, minimum))
    if maximum is not None and value > maximum:
        raise ValueError("{} must be at most {}.".format(name, maximum))
    return value


def load_cube_roles():
    defaults = {
        "left_wheel": env_int("LEFT_WHEEL_CUBE", 1, 1, 4),
        "right_wheel": env_int("RIGHT_WHEEL_CUBE", 2, 1, 4),
        "umbrella": env_int("UMBRELLA_CUBE", 3, 1, 4),
        "led_matrix": env_int("LED_MATRIX_CUBE", 4, 1, 4),
    }
    if ROLE_FILE.exists():
        try:
            saved = json.loads(ROLE_FILE.read_text(encoding="utf-8"))
            for role in defaults:
                defaults[role] = int(saved[role])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise ValueError("robot_roles.json is invalid. Delete it or correct all four roles.")
    validate_cube_roles(defaults)
    return defaults


def validate_cube_roles(roles):
    values = list(roles.values())
    if any(value < 1 or value > 4 for value in values):
        raise ValueError("Robot role numbers must be between 1 and 4.")
    if len(set(values)) != 4:
        raise ValueError("Each role must use a different robot number.")


def save_cube_roles(roles):
    normalized = {key: int(value) for key, value in roles.items()}
    validate_cube_roles(normalized)
    ROLE_FILE.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@dataclass(frozen=True)
class AppConfig:
    kma_service_key: str
    kma_nx: int
    kma_ny: int
    weather_poll_seconds: int
    rain_pty_codes: frozenset
    group_id: int
    ble_address: str
    left_wheel_cube: int
    right_wheel_cube: int
    umbrella_cube: int
    led_matrix_cube: int
    wheel_speed_sps: int
    turn_speed_sps: int
    left_motor_sign: int
    right_motor_sign: int
    umbrella_speed_sps: int
    umbrella_angle_degrees: int
    umbrella_open_sign: int
    led_brightness: int
    ble_scan_seconds: int

    @classmethod
    def from_env(cls, path=None):
        load_env(path)
        rain_codes = frozenset(
            int(item.strip())
            for item in os.environ.get("RAIN_PTY_CODES", "1,2,3,5,6,7").split(",")
            if item.strip()
        )
        left_sign = env_int("LEFT_MOTOR_SIGN", 1, -1, 1)
        right_sign = env_int("RIGHT_MOTOR_SIGN", -1, -1, 1)
        umbrella_sign = env_int("UMBRELLA_OPEN_SIGN", 1, -1, 1)
        if 0 in (left_sign, right_sign, umbrella_sign):
            raise ValueError("Motor direction signs must be either -1 or 1.")
        cube_roles = load_cube_roles()
        return cls(
            kma_service_key=os.environ.get("KMA_SERVICE_KEY", "").strip(),
            kma_nx=env_int("KMA_NX", 60, 1),
            kma_ny=env_int("KMA_NY", 127, 1),
            weather_poll_seconds=env_int("WEATHER_POLL_SECONDS", 600, 60),
            rain_pty_codes=rain_codes,
            group_id=parse_group_id(os.environ.get("GROUP_ID", "02")),
            ble_address=os.environ.get("BLE_ADDRESS", "").strip(),
            left_wheel_cube=cube_roles["left_wheel"],
            right_wheel_cube=cube_roles["right_wheel"],
            umbrella_cube=cube_roles["umbrella"],
            led_matrix_cube=cube_roles["led_matrix"],
            wheel_speed_sps=env_int("WHEEL_SPEED_SPS", 500, 100, 1000),
            turn_speed_sps=env_int("TURN_SPEED_SPS", 400, 100, 1000),
            left_motor_sign=left_sign,
            right_motor_sign=right_sign,
            umbrella_speed_sps=env_int("UMBRELLA_SPEED_SPS", 500, 100, 1000),
            umbrella_angle_degrees=env_int("UMBRELLA_ANGLE_DEGREES", 90, 1, 360),
            umbrella_open_sign=umbrella_sign,
            led_brightness=env_int("LED_BRIGHTNESS", 8, 0, 15),
            ble_scan_seconds=env_int("BLE_SCAN_SECONDS", 5, 1, 15),
        )

    @property
    def group_label(self):
        return "{:02X}".format(self.group_id)
