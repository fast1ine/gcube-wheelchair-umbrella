import unittest

from config import AppConfig
from hardware import WheelchairUmbrellaHardware


class FakeTransport:
    def __init__(self):
        self.is_open = True
        self.packets = []

    def write(self, packet):
        self.packets.append(bytes(packet))
        return len(packet)

    def close(self):
        self.is_open = False


def test_config():
    return AppConfig(
        kma_service_key="test",
        kma_nx=60,
        kma_ny=127,
        weather_poll_seconds=600,
        rain_pty_codes=frozenset({1, 2, 3, 5, 6, 7}),
        group_id=0x02,
        ble_address="",
        left_wheel_cube=1,
        right_wheel_cube=2,
        umbrella_cube=3,
        led_matrix_cube=4,
        wheel_speed_sps=500,
        turn_speed_sps=400,
        left_motor_sign=1,
        right_motor_sign=-1,
        umbrella_speed_sps=500,
        umbrella_angle_degrees=90,
        umbrella_open_sign=1,
        led_brightness=8,
        ble_scan_seconds=5,
    )


class HardwarePacketTests(unittest.TestCase):
    def setUp(self):
        self.hardware = WheelchairUmbrellaHardware(test_config())
        self.transport = FakeTransport()
        self.hardware.group.transport = self.transport

    def test_connect_packet_requests_four_cubes_in_one_group(self):
        packet = self.hardware.group._connect_packet()
        self.assertEqual(packet[4], 0x40)
        self.assertEqual(packet[6], 0xAD)
        self.assertEqual(packet[10], 0x02)

    def test_forward_uses_aggregate_packet_for_cube_one_and_two(self):
        self.hardware.drive("forward")
        packet = self.transport.packets[-1]
        self.assertEqual(packet[2], 0x02)
        self.assertEqual(packet[4], 0x40)
        self.assertEqual(packet[6], 0xCD)
        self.assertEqual(packet[13 + 3], 0)
        self.assertEqual(packet[13 + 15 + 3], 1)

    def test_umbrella_open_targets_cube_three(self):
        self.hardware.set_umbrella(True)
        packet = self.transport.packets[-1]
        self.assertEqual(packet[2], 0x02)
        self.assertEqual(packet[6], 0xCD)
        command = packet[13:]
        self.assertEqual(command[3], 2)
        self.assertEqual(command[6], 0xC1)
        self.assertEqual(int.from_bytes(command[17:19], "big"), 500)

    def test_role_menu_mapping_changes_umbrella_target(self):
        self.hardware.set_cube_roles(1, 2, 4, 3)
        self.hardware.set_umbrella(False)
        packet = self.transport.packets[-1]
        self.assertEqual(packet[6], 0xCD)
        self.assertEqual(packet[13 + 3], 3)

    def test_role_mapping_rejects_duplicate_robots(self):
        with self.assertRaises(ValueError):
            self.hardware.set_cube_roles(1, 2, 2, 4)

    def test_sun_icon_targets_cube_four_and_is_symmetric(self):
        pattern = self.hardware.SUN_PATTERN
        self.assertEqual(tuple(reversed(pattern)), pattern)
        self.assertTrue(all(row == row[::-1] for row in pattern))
        self.hardware.show_weather_icon(False)
        brightness, picture = self.transport.packets[-2:]
        self.assertEqual(brightness[3], 3)
        self.assertEqual(brightness[5], 0xE5)
        self.assertEqual(picture[3], 3)
        self.assertEqual(picture[5], 0xE2)
        self.assertEqual(len(picture), 18)

    def test_emergency_stop_targets_unified_group(self):
        self.hardware.emergency_stop()
        wheel_stop, umbrella_stop = self.transport.packets[-2:]
        self.assertEqual(wheel_stop[6], 0xCD)
        self.assertEqual(umbrella_stop[6], 0xCD)
        self.assertEqual(umbrella_stop[13 + 3], 2)
        self.assertEqual(umbrella_stop[13 + 6], 0xCC)


if __name__ == "__main__":
    unittest.main()
