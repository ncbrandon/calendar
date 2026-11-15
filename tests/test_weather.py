from app import weather

NOW = 1794765100.0


def station(**current):
    cur = {"epoch": "1794765015", "outTemp": "38.1 &#176;F", "outTemp_formatted": "38.1", "outHumidity": "76%",
           "windspeed": "4 mph", "winddir_formatted": "141", "windGust_formatted": "9", "uv": "1.0", "rainRate": "0.00 in/hr"}
    cur.update(current)
    return {"current": cur, "unit_label": {"outTemp": " \u00b0F", "windSpeed": " mph", "rainRate": " in/h"},
            "almanac": {"sunrise_epoch": "1794744172.3", "sunset_epoch": "1794781076.9"}}


def airport(code="::OV", sky=100, age=3000):
    return {"current": [{"response": {"ob": {"timestamp": NOW - age, "weatherPrimaryCoded": code, "sky": sky, "isDay": True}}}]}


def test_station_reading_with_airport_sky():
    w = weather.from_station(station(), airport(), True, NOW)
    assert (w["temp"], w["wind_mph"], w["gust_mph"], w["wind_from"], w["humidity"]) == (38, 4, 9, "SE", 76)
    assert w["condition"] == "cloudy" and w["is_day"] and w["source"] == "station" and w["cloud_cover"] == 100


def test_station_rain_gauge_wins_and_freezing_means_snow():
    assert weather.from_station(station(rainRate="0.12 in/hr"), airport(), True, NOW)["sky"] == "rain"
    cold = station(rainRate="0.12 in/hr", outTemp_formatted="30.0")
    assert weather.from_station(cold, airport(), True, NOW)["sky"] == "snow"
    # A rain gauge cannot see snow or fog, so those come from the airport report.
    assert weather.from_station(station(), airport(":L:S"), True, NOW)["sky"] == "snow"
    assert weather.from_station(station(), airport("::F"), True, NOW)["sky"] == "fog"


def test_station_units_night_wind_and_stale():
    metric = station(outTemp_formatted="20.0", windspeed="40 km/h", windGust_formatted="50")
    metric["unit_label"] = {"outTemp": " \u00b0C", "windSpeed": " km/h", "rainRate": " mm/h"}
    w = weather.from_station(metric, None, False, NOW)
    assert w["temp"] == 20 and w["wind_mph"] == 25 and w["tags"][0] == "windy"
    assert weather.from_station(station(), airport("::CL", 0), True, NOW + 6 * 3600)  is None      # six hours old
    night = station(epoch=str(int(NOW + 5 * 3600)))
    assert weather.from_station(night, airport("::CL", 0, age=-5 * 3600), True, NOW + 5 * 3600 + 60)["is_day"] is False
    assert weather.from_station(station(), None, True, NOW)["sky"] == "partly_cloudy"               # no sky data at all
