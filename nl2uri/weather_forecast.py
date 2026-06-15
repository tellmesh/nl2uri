from __future__ import annotations

import re
import unicodedata
from typing import Any

_WEATHER_FORECAST_RE = re.compile(r"\b(prognoz\w*|pogod\w*|weather|forecast)\b", re.I)
_WEATHER_BUILD_RE = re.compile(
    r"\b(stw[oó]rz|zbuduj|wygeneruj|generuj)\b.*\b(agent\w*|agenta|map[eę]|domen\w*|ekosystem\w*)\b",
    re.I,
)
_AGENT_OPS_RE = re.compile(r"\b(agent\w*|agenta|deployment|proces|process|inspect|diagnos\w*|repair)\b", re.I)

_KNOWN_PLACES: dict[str, str] = {
    "gdańsk": "Gdansk",
    "gdansk": "Gdansk",
    "warszawa": "Warsaw",
    "warsaw": "Warsaw",
    "kraków": "Krakow",
    "krakow": "Krakow",
    "wrocław": "Wroclaw",
    "wroclaw": "Wroclaw",
    "poznań": "Poznan",
    "poznan": "Poznan",
    "łódź": "Lodz",
    "lodz": "Lodz",
    "szczecin": "Szczecin",
    "berlin": "Berlin",
    "london": "London",
}


def is_weather_forecast_prompt(prompt: str) -> bool:
    text = prompt.strip()
    if not text or not _WEATHER_FORECAST_RE.search(text):
        return False
    if _WEATHER_BUILD_RE.search(text):
        return False
    if _AGENT_OPS_RE.search(text):
        return False
    if re.search(r"[\w.-]+-agent(?:\.local)?", text, re.I):
        return False
    return True


def _ascii_place(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name.strip())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z-]+", "", ascii_name)
    if not cleaned:
        return "Gdansk"
    return cleaned[0].upper() + cleaned[1:]


def extract_weather_place(prompt: str) -> str:
    lower = prompt.lower()
    for key, value in _KNOWN_PLACES.items():
        if key in lower:
            return value
    match = re.search(r"\b(?:w|in|for|dla)\s+([A-Za-zÀ-ž\-]+)", prompt, re.I)
    if match:
        return _ascii_place(match.group(1))
    for token in re.findall(r"[A-Za-zÀ-ž]{3,}", prompt):
        normalized = token.lower()
        if normalized in _KNOWN_PLACES:
            return _KNOWN_PLACES[normalized]
        if normalized not in {"prognoza", "pogody", "pogoda", "weather", "forecast", "dni", "html"}:
            return _ascii_place(token)
    return "Gdansk"


def extract_weather_days(prompt: str) -> int:
    if re.search(r"dwa\s*tygod|two\s*weeks|\b14\b", prompt, re.I):
        return 14
    match = re.search(r"\b(\d{1,2})\s*dni\b", prompt, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d{1,2})\b", prompt)
    if match:
        return int(match.group(1))
    return 7


def weather_forecast_uri(prompt: str) -> str:
    place = extract_weather_place(prompt)
    days = extract_weather_days(prompt)
    return f"weather://forecast/{place}/{days}/html"


def plan_weather_forecast(prompt: str) -> dict[str, Any]:
    place = extract_weather_place(prompt)
    days = extract_weather_days(prompt)
    uri = f"weather://forecast/{place}/{days}/html"
    return {
        "place": place,
        "days": days,
        "uri": uri,
        "capability": "weather.forecast.html",
        "registry": "examples/20_touri_capabilities",
    }
