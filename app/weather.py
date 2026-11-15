"""Current conditions for the wall screens.

Two sources, tried in this order:

1. Your own weather station, if "Weather station address" is set in Settings. The station must publish the
   WeeWX "Belchertown" data files, which is what a WeeWX site with that skin does by itself:
     <address>/json/weewx_data.json   live sensor readings (temperature, wind, rain rate, humidity)
     <address>/json/forecast.json     optional: sky cover from the nearest airport, if the site has forecasts on
2. Open-Meteo (free, no account or key), if a latitude and longitude are set. Only those two numbers are sent.
   It is also the fallback when the station has not reported for 30 minutes.

Results are cached for a few minutes, and the last good reading is reused if the network is down.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from datetime import date
from typing import Optional

CONDITIONS = ["clear", "partly_cloudy", "cloudy", "fog", "rain", "snow", "thunder", "windy", "hot", "cold"]
LABELS = {
    "clear": "Clear", "partly_cloudy": "Partly cloudy", "cloudy": "Cloudy", "fog": "Fog", "rain": "Rain",
    "snow": "Snow", "thunder": "Thunderstorm", "windy": "Windy", "hot": "Hot", "cold": "Bitter cold",
}
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
STALE_SECONDS = 1800
_cache = {"key": None, "at": 0.0, "data": None}

# Weather and cloud codes used in the "current" block of a Belchertown forecast.json (Aeris/Xweather format).
_SKY_CODES = {"CL": "clear", "FW": "clear", "SC": "partly_cloudy", "BK": "cloudy", "OV": "cloudy"}
_WX_CODES = {
    "T": "thunder",
    "S": "snow", "SW": "snow", "BS": "snow", "IP": "snow", "SI": "snow", "WM": "snow", "RS": "snow", "IC": "snow",
    "R": "rain", "RW": "rain", "L": "rain", "ZR": "rain", "ZL": "rain", "UP": "rain", "A": "rain",
    "F": "fog", "ZF": "fog", "IF": "fog", "BR": "fog", "H": "fog", "K": "fog",
}


def condition_for(code: int) -> str:
    """Open-Meteo (WMO) weather code -> our condition name."""
    if code in (0, 1):
        return "clear"
    if code == 2:
        return "partly_cloudy"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunder"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    return "cloudy"


def season_for(day: date) -> str:
    return {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer"}.get(day.month, "fall")


def _num(value) -> Optional[float]:
    """First number in a reading such as '38.1 &#176;F', '4 mph' or 'N/A'."""
    found = re.search(r"-?\d+(?:\.\d+)?", html.unescape(str(value if value is not None else "")).replace(",", ""))
    return float(found.group()) if found else None


def _get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "OpsBoard"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)


def _finish(main: str, temp_f, wind, gust, wind_dir, humidity, rain_rate, sky, is_day, fahrenheit, source) -> dict:
    """Shared by both sources: pick the tags and build what the wall screens receive."""
    wind, gust = wind or 0, max(gust or 0, wind or 0)
    tags = [main]            # every tag that applies, most specific first; GIFs are matched against these in order
    if (wind >= 18 or gust >= 25) and main not in ("thunder", "snow"):
        tags.insert(0, "windy")
    if temp_f is not None and main in ("clear", "partly_cloudy", "cloudy"):
        if temp_f >= 90:
            tags.insert(0, "hot")
        elif temp_f <= 15:
            tags.insert(0, "cold")
    temp = None if temp_f is None else (temp_f if fahrenheit else (temp_f - 32) * 5 / 9)
    return {
        "condition": tags[0], "tags": tags, "label": LABELS[tags[0]], "sky": main,
        "temp": None if temp is None else round(temp), "unit": "F" if fahrenheit else "C",
        "temp_f": None if temp_f is None else round(temp_f, 1),
        "wind_mph": round(wind), "gust_mph": round(gust),
        "wind_dir": None if wind_dir is None else round(wind_dir) % 360,
        "wind_from": None if wind_dir is None else COMPASS[int((wind_dir % 360) / 22.5 + 0.5) % 16],
        "humidity": None if humidity is None else round(humidity),
        "rain_rate": round(rain_rate or 0, 2),            # inches per hour
        "cloud_cover": sky,                                # 0-100, or None if unknown
        "is_day": bool(is_day), "source": source,
    }


def from_station(data: dict, forecast: Optional[dict], fahrenheit: bool, now: float) -> Optional[dict]:
    """Turn the station's data files into conditions. None if the station has gone quiet."""
    cur, labels = data.get("current") or {}, data.get("unit_label") or {}
    stamp = _num(cur.get("epoch")) or _num(cur.get("datetime_raw"))
    if stamp is None or now - stamp > STALE_SECONDS:
        return None
    temp = _num(cur.get("outTemp_formatted")) if cur.get("outTemp_formatted") else _num(cur.get("outTemp"))
    temp_f = temp if temp is None or "C" not in str(labels.get("outTemp", "F")) else temp * 9 / 5 + 32

    speed_label = str(labels.get("windSpeed", "mph")).lower()
    to_mph = 0.621 if "km" in speed_label else 2.237 if "m/s" in speed_label else 1.151 if "kn" in speed_label else 1.0
    wind = (_num(cur.get("windspeed")) or 0) * to_mph
    gust = (_num(cur.get("windGust_formatted") or cur.get("windGust")) or 0) * to_mph
    wind_dir = _num(cur.get("winddir_formatted") or cur.get("winddir"))
    humidity = _num(cur.get("outHumidity"))
    rate_label = str(labels.get("rainRate", "in")).lower()
    rain_rate = (_num(cur.get("rainRate")) or 0) / (25.4 if "mm" in rate_label else 2.54 if "cm" in rate_label else 1)

    almanac = data.get("almanac") or {}
    rise, sets = _num(almanac.get("sunrise_epoch")), _num(almanac.get("sunset_epoch"))
    is_day = rise <= now < sets if rise and sets else True

    # Sky cover and weather type come from the nearest airport report, when the site carries one.
    sky_cond, wx_cond, cover = None, None, None
    try:
        ob = forecast["current"][0]["response"]["ob"]
        if now - float(ob.get("timestamp") or 0) < 3 * 3600:
            code = str(ob.get("weatherPrimaryCoded") or "").split(":")[-1].upper()
            sky_cond = _SKY_CODES.get(code) or _SKY_CODES.get(str(ob.get("cloudsCoded") or "").upper())
            wx_cond = _WX_CODES.get(code)
            cover = None if ob.get("sky") is None else int(ob["sky"])
            if not (rise and sets) and ob.get("isDay") is not None:
                is_day = bool(ob["isDay"])
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    if cover is not None and sky_cond is None:
        sky_cond = "clear" if cover < 20 else "partly_cloudy" if cover < 70 else "cloudy"

    freezing = temp_f is not None and temp_f <= 33
    if rain_rate > 0:                       # the station's own gauge is tipping: it is raining here, now
        main = "thunder" if wx_cond == "thunder" else "snow" if freezing else "rain"
    elif wx_cond in ("snow", "fog", "thunder"):
        main = wx_cond                      # a rain gauge cannot see these, so trust the airport
    elif wx_cond == "rain" and (humidity or 0) >= 85:
        main = "snow" if freezing else "rain"   # light rain the gauge has not caught yet
    else:
        main = sky_cond or ("clear" if is_day and (_num(cur.get("uv")) or 0) >= 3 else "partly_cloudy")
    return _finish(main, temp_f, wind, gust, wind_dir, humidity, rain_rate, cover, is_day, fahrenheit, "station")


def _station(base: str, fahrenheit: bool) -> Optional[dict]:
    base = base.rstrip("/")
    if base.endswith(".json"):
        base = base.rsplit("/json/", 1)[0]
    data = _get(base + "/json/weewx_data.json")
    try:
        forecast = _get(base + "/json/forecast.json")
    except Exception:
        forecast = None                     # plenty of stations do not publish one
    return from_station(data, forecast, fahrenheit, time.time())


def _open_meteo(lat, lon, fahrenheit: bool) -> dict:
    cur = _get(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={float(lat):.4f}&longitude={float(lon):.4f}"
        "&current=temperature_2m,weather_code,wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
        "relative_humidity_2m,precipitation,cloud_cover,is_day"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch"
    )["current"]
    return _finish(condition_for(int(cur.get("weather_code") or 0)), cur.get("temperature_2m"),
                   cur.get("wind_speed_10m"), cur.get("wind_gusts_10m"), cur.get("wind_direction_10m"),
                   cur.get("relative_humidity_2m"), cur.get("precipitation"), cur.get("cloud_cover"),
                   cur.get("is_day", 1), fahrenheit, "open-meteo")


def current(settings: dict, fresh: bool = False):
    """Return a dict describing current conditions, or None if no source is set up."""
    station = str(settings.get("station_url") or "").strip()
    lat, lon = settings.get("latitude"), settings.get("longitude")
    has_location = lat not in (None, "") and lon not in (None, "")
    if not station and not has_location:
        return None
    fahrenheit = settings.get("temp_unit", "F") == "F"
    key = (station, lat, lon, fahrenheit)
    if not fresh and _cache["key"] == key and time.time() - _cache["at"] < 240:
        return _cache["data"]
    data = None
    if station:
        try:
            data = _station(station, fahrenheit)
        except Exception:
            data = None
    if data is None and has_location:
        try:
            data = _open_meteo(lat, lon, fahrenheit)
        except Exception:
            data = None
    if data is None:
        if _cache["key"] != key:
            _cache.update(key=key, data=None)
        _cache["at"] = time.time() - 120      # keep the last good reading and try again in two minutes
        return _cache["data"]
    _cache.update(key=key, at=time.time(), data=data)
    return data
