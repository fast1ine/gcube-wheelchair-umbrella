import threading
import time

from connection.bletransport import BleSerialTransport
from protocols.ledmatrixprotocol import LEDMatrixProtocol
from protocols.motorprotocol import MotorProtocol


class GcubeGroup:
    def __init__(self, group_id, cube_count, address="", scan_seconds=5):
        self.group_id = group_id
        self.cube_count = cube_count
        self.address = address
        self.scan_seconds = scan_seconds
        self.transport = None
        self.motor_protocol = MotorProtocol(cube_count)
        self.matrix_protocol = LEDMatrixProtocol(cube_count)
        self.name = "-"
        self._write_lock = threading.Lock()

    @property
    def group_label(self):
        return "{:02X}".format(self.group_id)

    @property
    def connected(self):
        return bool(self.transport and self.transport.is_open)

    def connect(self):
        if self.connected:
            return
        address = self.address
        name = address
        if not address:
            devices = BleSerialTransport.scan(
                timeout=self.scan_seconds,
                group_label=self.group_label,
            )
            if not devices:
                raise RuntimeError(
                    "No advertising PingPong BLE device was found for group {}.".format(
                        self.group_label
                    )
                )
            address = devices[0]["address"]
            name = devices[0]["name"]
        transport = BleSerialTransport(address, name=name, connect_timeout=15)
        try:
            transport.write(self._connect_packet())
            time.sleep(1.2)
        except Exception:
            transport.close()
            raise
        self.transport = transport
        self.address = address
        self.name = name

    def write(self, packet):
        if not self.connected:
            raise RuntimeError("Group {} is not connected.".format(self.group_label))
        with self._write_lock:
            self.transport.write(packet)

    def close(self):
        transport = self.transport
        self.transport = None
        if transport:
            transport.close()

    def _connect_packet(self):
        return bytes(
            [
                0xFF,
                0xFF,
                0xFF,
                0xAA,
                self.cube_count << 4,
                0x00,
                0xAD,
                0x00,
                0x0B,
                0x1A,
                self.group_id,
            ]
        )


class WheelchairUmbrellaHardware:
    CUBE_COUNT = 4
    STEPS_PER_REVOLUTION = 2000

    SUN_PATTERN = (
        "00100100",
        "00011000",
        "01011010",
        "10111101",
        "10111101",
        "01011010",
        "00011000",
        "00100100",
    )
    UMBRELLA_PATTERN = (
        "00011000",
        "00111100",
        "01111110",
        "11111111",
        "00001000",
        "00001000",
        "00101000",
        "00010000",
    )

    def __init__(self, config):
        self.config = config
        self.group = GcubeGroup(
            config.group_id,
            self.CUBE_COUNT,
            config.ble_address,
            config.ble_scan_seconds,
        )
        self.left_wheel_cube = config.left_wheel_cube - 1
        self.right_wheel_cube = config.right_wheel_cube - 1
        self.umbrella_cube = config.umbrella_cube - 1
        self.led_matrix_cube = config.led_matrix_cube - 1
        self._command_lock = threading.RLock()

    def set_cube_roles(self, left_wheel, right_wheel, umbrella, led_matrix):
        roles = [int(left_wheel), int(right_wheel), int(umbrella), int(led_matrix)]
        if any(value < 1 or value > 4 for value in roles):
            raise ValueError("Robot numbers must be between 1 and 4.")
        if len(set(roles)) != 4:
            raise ValueError("Each role must use a different robot number.")
        with self._command_lock:
            self.left_wheel_cube = roles[0] - 1
            self.right_wheel_cube = roles[1] - 1
            self.umbrella_cube = roles[2] - 1
            self.led_matrix_cube = roles[3] - 1

    @property
    def connected(self):
        return self.group.connected

    def connect(self, progress=None):
        notify = progress or (lambda _message: None)
        notify("그룹 {}에서 G-큐브 4개 검색 중".format(self.group.group_label))
        try:
            self.group.connect()
        except Exception:
            self.close()
            raise
        notify("4-Cube 그룹 연결 완료: {}".format(self.group.name))

    def drive(self, direction):
        speed = self.config.wheel_speed_sps
        turn = self.config.turn_speed_sps
        left_sign = self.config.left_motor_sign
        right_sign = self.config.right_motor_sign
        commands = {
            "forward": (left_sign * speed, right_sign * speed),
            "backward": (-left_sign * speed, -right_sign * speed),
            "left": (-left_sign * turn, right_sign * turn),
            "right": (left_sign * turn, -right_sign * turn),
            "stop": (0, 0),
        }
        if direction not in commands:
            raise ValueError("Unknown drive direction: {}".format(direction))
        self._write_wheel_speeds(*commands[direction])

    def stop_wheels(self):
        if self.connected:
            self._write_wheel_speeds(0, 0)

    def set_umbrella(self, opened):
        with self._command_lock:
            self._require_connection()
            sign = self.config.umbrella_open_sign if opened else -self.config.umbrella_open_sign
            speed = sign * self.config.umbrella_speed_sps
            steps = round(
                self.STEPS_PER_REVOLUTION * self.config.umbrella_angle_degrees / 360.0
            )
            command = self.group.motor_protocol.SetSingleSteps_bytes(
                self.umbrella_cube,
                speed,
                steps,
                self.config.group_id,
                False,
            )
            packet = self.group.motor_protocol.SetAggregateSteps_bytes(
                self.config.group_id,
                command,
            )
            self.group.write(packet)

    def stop_umbrella(self):
        if not self.connected:
            return
        command = self.group.motor_protocol.SetContinuousSteps_bytes(
            self.umbrella_cube,
            0,
            self.config.group_id,
            True,
        )
        packet = self.group.motor_protocol.SetAggregateSteps_bytes(
            self.config.group_id,
            command,
        )
        self.group.write(packet)

    def show_weather_icon(self, precipitating):
        with self._command_lock:
            self._require_connection()
            pattern = self.UMBRELLA_PATTERN if precipitating else self.SUN_PATTERN
            brightness = self.group.matrix_protocol.ArduinoI2CLEDMatrixSetBrightness_bytes(
                self.led_matrix_cube,
                self.config.led_brightness,
                self.config.group_id,
            )
            picture = self.group.matrix_protocol.ArduinoI2CLEDMatrixWritePicture_bytes(
                self.led_matrix_cube,
                self._matrix_rows(pattern),
                self.config.group_id,
            )
            self.group.write(brightness)
            time.sleep(0.05)
            self.group.write(picture)

    def clear_matrix(self):
        with self._command_lock:
            if not self.connected:
                return
            packet = self.group.matrix_protocol.ArduinoI2CLEDMatrixSetDisplay_bytes(
                self.led_matrix_cube,
                2,
                self.config.group_id,
            )
            self.group.write(packet)

    def emergency_stop(self):
        errors = []
        for operation in (self.stop_wheels, self.stop_umbrella):
            try:
                operation()
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError(" / ".join(errors))

    def close(self):
        try:
            self.emergency_stop()
        except Exception:
            pass
        self.group.close()

    def _write_wheel_speeds(self, left_speed, right_speed):
        with self._command_lock:
            self._require_connection()
            commands = (
                (self.left_wheel_cube, left_speed),
                (self.right_wheel_cube, right_speed),
            )
            packets = [
                self.group.motor_protocol.SetContinuousSteps_bytes(
                    cube_id,
                    speed,
                    self.config.group_id,
                    speed == 0,
                )
                for cube_id, speed in commands
            ]
            aggregate = self.group.motor_protocol.SetAggregateSteps_bytes(
                self.config.group_id,
                b"".join(packets),
            )
            self.group.write(aggregate)

    def _require_connection(self):
        if not self.connected:
            raise RuntimeError("The 4-Cube G-cube group is not connected.")

    @staticmethod
    def _matrix_rows(pattern):
        if len(pattern) != 8 or any(len(row) != 8 for row in pattern):
            raise ValueError("LED matrix pattern must be 8 by 8.")
        result = [0] * 8
        for row_index, row in enumerate(pattern):
            value = sum((1 << column) for column, pixel in enumerate(row) if pixel == "1")
            result[(row_index + 1) % 8] = value
        return result
