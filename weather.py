import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen


KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class WeatherObservation:
    base_date: str
    base_time: str
    temperature_c: float | None
    humidity_percent: float | None
    precipitation_type: int
    rainfall_mm: float
    wind_speed_ms: float | None
    is_precipitating: bool

    @property
    def description(self):
        labels = {
            0: "강수 없음",
            1: "비",
            2: "비/눈",
            3: "눈",
            5: "빗방울",
            6: "빗방울/눈날림",
            7: "눈날림",
        }
        return labels.get(self.precipitation_type, "강수 코드 {}".format(self.precipitation_type))


class KmaWeatherClient:
    ENDPOINT = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"

    def __init__(self, service_key, nx, ny, rain_pty_codes, timeout=10):
        self.service_key = service_key
        self.nx = int(nx)
        self.ny = int(ny)
        self.rain_pty_codes = frozenset(rain_pty_codes)
        self.timeout = timeout

    def fetch(self, now=None):
        if not self.service_key:
            raise RuntimeError("KMA_SERVICE_KEY is empty. Add the API key to .env.")
        current = (now or datetime.now(KST)).astimezone(KST)
        first_base = current - timedelta(minutes=45)
        last_error = None
        for hours_back in range(3):
            base = first_base - timedelta(hours=hours_back)
            try:
                payload = self._request(base.strftime("%Y%m%d"), base.strftime("%H00"))
                return self.parse_response(payload, self.rain_pty_codes)
            except RuntimeError as error:
                last_error = error
                if "NO_DATA" not in str(error).upper() and "items" not in str(error):
                    raise
        raise last_error or RuntimeError("No recent KMA observation is available.")

    def _request(self, base_date, base_time):
        params = urlencode(
            {
                "pageNo": 1,
                "numOfRows": 100,
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": self.nx,
                "ny": self.ny,
            }
        )
        encoded_key = self.service_key if "%" in self.service_key else quote(self.service_key, safe="")
        url = "{}?serviceKey={}&{}".format(self.ENDPOINT, encoded_key, params)
        try:
            with urlopen(url, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError("KMA API HTTP error: {}".format(error.code))
        except URLError as error:
            raise RuntimeError("KMA API connection error: {}".format(error.reason))
        except json.JSONDecodeError:
            raise RuntimeError("KMA API returned an invalid JSON response.")

    @staticmethod
    def parse_response(payload, rain_pty_codes):
        try:
            response = payload["response"]
            header = response["header"]
        except (KeyError, TypeError):
            raise RuntimeError("KMA API response structure is invalid.")
        if str(header.get("resultCode")) != "00":
            raise RuntimeError(
                "KMA API error {}: {}".format(
                    header.get("resultCode", "?"), header.get("resultMsg", "Unknown error")
                )
            )
        try:
            items = response["body"]["items"]["item"]
        except (KeyError, TypeError):
            raise RuntimeError("KMA API response has no observation items (NO_DATA).")
        if not items:
            raise RuntimeError("KMA API response has no observation items (NO_DATA).")

        values = {item["category"]: item.get("obsrValue") for item in items}
        pty = int(float(values.get("PTY", 0)))
        rainfall = KmaWeatherClient._number(values.get("RN1"), 0.0)
        first = items[0]
        return WeatherObservation(
            base_date=str(first.get("baseDate", "")),
            base_time=str(first.get("baseTime", "")),
            temperature_c=KmaWeatherClient._number(values.get("T1H")),
            humidity_percent=KmaWeatherClient._number(values.get("REH")),
            precipitation_type=pty,
            rainfall_mm=rainfall,
            wind_speed_ms=KmaWeatherClient._number(values.get("WSD")),
            is_precipitating=pty in rain_pty_codes or rainfall > 0,
        )

    @staticmethod
    def _number(value, default=None):
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
