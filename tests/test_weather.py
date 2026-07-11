import unittest

from weather import KmaWeatherClient


class WeatherParsingTests(unittest.TestCase):
    def payload(self, pty="0", rainfall="0"):
        items = [
            {"baseDate": "20260711", "baseTime": "0900", "category": "PTY", "obsrValue": pty},
            {"baseDate": "20260711", "baseTime": "0900", "category": "RN1", "obsrValue": rainfall},
            {"baseDate": "20260711", "baseTime": "0900", "category": "T1H", "obsrValue": "24.3"},
            {"baseDate": "20260711", "baseTime": "0900", "category": "REH", "obsrValue": "77"},
            {"baseDate": "20260711", "baseTime": "0900", "category": "WSD", "obsrValue": "2.1"},
        ]
        return {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
                "body": {"items": {"item": items}},
            }
        }

    def test_rain_code_opens_umbrella(self):
        result = KmaWeatherClient.parse_response(self.payload(pty="1"), {1, 2, 3, 5, 6, 7})
        self.assertTrue(result.is_precipitating)
        self.assertEqual(result.description, "비")

    def test_rainfall_is_used_as_fallback(self):
        result = KmaWeatherClient.parse_response(self.payload(pty="0", rainfall="0.8"), {1})
        self.assertTrue(result.is_precipitating)

    def test_clear_observation_keeps_umbrella_closed(self):
        result = KmaWeatherClient.parse_response(self.payload(), {1, 2, 3, 5, 6, 7})
        self.assertFalse(result.is_precipitating)
        self.assertEqual(result.temperature_c, 24.3)


if __name__ == "__main__":
    unittest.main()
