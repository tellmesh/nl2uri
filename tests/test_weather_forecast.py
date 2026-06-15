from __future__ import annotations

import pytest

from nl2uri.weather_forecast import (
    extract_weather_days,
    extract_weather_place,
    is_weather_forecast_prompt,
    plan_weather_forecast,
    weather_forecast_uri,
)
from urish.backends.ask import ask_prompt
from urish.intent import detect_intent


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("prognoza pogody Gdańsk 7 dni", True),
        ("weather forecast Gdansk 14 days", True),
        ("generuj mape pogody dwa tygodnie do przodu w html", False),
        ("wygeneruj agenta pogodowego, uruchom go lokalnie", False),
        ("pokaż proces agenta weather-map-agent.local", False),
    ],
)
def test_is_weather_forecast_prompt(prompt: str, expected: bool):
    assert is_weather_forecast_prompt(prompt) is expected


def test_weather_forecast_uri_from_polish_prompt():
    assert weather_forecast_uri("prognoza pogody Gdańsk 7 dni") == "weather://forecast/Gdansk/7/html"


def test_extract_weather_place_and_days():
    assert extract_weather_place("prognoza pogody Gdańsk 7 dni") == "Gdansk"
    assert extract_weather_days("prognoza pogody Gdańsk 7 dni") == 7
    assert extract_weather_days("weather forecast Gdansk 14 days") == 14


def test_detect_weather_intent():
    intent = detect_intent("prognoza pogody Gdańsk 7 dni")
    assert intent["kind"] == "weather"
    assert intent["subtype"] == "forecast_html"
    assert intent["uri"] == "weather://forecast/Gdansk/7/html"


def test_ask_weather_forecast_plans_executable_uri():
    result = ask_prompt("prognoza pogody Gdańsk 7 dni")
    data = result["data"]
    assert data["detected_kind"] == "weather"
    assert data["planned_uris"] == ["weather://forecast/Gdansk/7/html"]
    assert "uri call weather://forecast/Gdansk/7/html" in data["next_steps"]


def test_plan_weather_forecast_payload():
    payload = plan_weather_forecast("prognoza pogody Gdańsk 7 dni")
    assert payload["place"] == "Gdansk"
    assert payload["days"] == 7
    assert payload["uri"] == "weather://forecast/Gdansk/7/html"
