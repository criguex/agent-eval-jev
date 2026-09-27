from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

USER_AGENT = "agent-eval-jev/0.1 (https://github.com/criguex/agent-eval-jev)"
WMO_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


class ToolError(Exception):
    pass


def _get(url: str) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        return error.code, None


def geocode(name: str) -> dict:
    query = urllib.parse.urlencode({"name": name, "count": 3, "language": "en"})
    status, data = _get(f"https://geocoding-api.open-meteo.com/v1/search?{query}")
    results = (data or {}).get("results") or []
    if status != 200 or not results:
        raise ToolError(f"no place found for '{name}'")
    return {
        "matches": [
            {
                "name": r["name"],
                "admin1": r.get("admin1"),
                "country": r.get("country"),
                "country_code": r.get("country_code"),
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "timezone": r.get("timezone"),
            }
            for r in results
        ]
    }


def weather_forecast(latitude: float, longitude: float, days: int = 3) -> dict:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code",
            "timezone": "auto",
            "forecast_days": days,
        }
    )
    status, data = _get(f"https://api.open-meteo.com/v1/forecast?{query}")
    if status != 200 or not data:
        raise ToolError(f"forecast unavailable (HTTP {status})")
    daily = data["daily"]
    return {
        "timezone": data.get("timezone"),
        "units": {"temperature": "°C", "precipitation": "mm"},
        "days": [
            {
                "date": daily["time"][i],
                "max_c": daily["temperature_2m_max"][i],
                "min_c": daily["temperature_2m_min"][i],
                "precipitation_mm": daily["precipitation_sum"][i],
                "precipitation_probability": daily["precipitation_probability_max"][i],
                "conditions": WMO_CODES.get(daily["weather_code"][i], f"code {daily['weather_code'][i]}"),
            }
            for i in range(len(daily["time"]))
        ],
    }


def public_holidays(country_code: str, year: int) -> dict:
    status, data = _get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code.upper()}")
    if status == 204 or (status == 200 and not data):
        raise ToolError(f"no holiday data for country '{country_code}' in {year}")
    if status != 200:
        raise ToolError(f"holiday lookup failed (HTTP {status})")
    return {
        "country_code": country_code.upper(),
        "year": year,
        "holidays": [{"date": h["date"], "name": h["name"], "local_name": h["localName"]} for h in data],
    }


def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    query = urllib.parse.urlencode({"from": from_currency.upper(), "to": to_currency.upper(), "amount": amount})
    status, data = _get(f"https://api.frankfurter.dev/v1/latest?{query}")
    if status != 200 or not data or not data.get("rates"):
        raise ToolError(f"currency pair {from_currency.upper()}->{to_currency.upper()} not supported")
    converted = data["rates"][to_currency.upper()]
    return {
        "amount": amount,
        "from": from_currency.upper(),
        "to": to_currency.upper(),
        "converted": converted,
        "rate": round(converted / amount, 6) if amount else None,
        "rate_date": data["date"],
    }


def wikipedia_summary(title: str) -> dict:
    status, data = _get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")))
    if status != 200 or not data or data.get("type") == "https://mediawiki.org/wiki/HyperSwitch/errors/not_found":
        raise ToolError(f"no Wikipedia article titled '{title}'")
    return {"title": data.get("title"), "description": data.get("description"), "extract": data.get("extract")}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[..., dict]


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "geocode",
            "Find coordinates, country and timezone for a place name. Returns up to 3 matches.",
            {"name": {"type": "string", "required": True}},
            geocode,
        ),
        Tool(
            "weather_forecast",
            "Daily forecast (max/min °C, precipitation, conditions) for coordinates, starting today, 1-16 days.",
            {
                "latitude": {"type": "number", "required": True, "min": -90, "max": 90},
                "longitude": {"type": "number", "required": True, "min": -180, "max": 180},
                "days": {"type": "integer", "required": False, "min": 1, "max": 16},
            },
            weather_forecast,
        ),
        Tool(
            "public_holidays",
            "Public holidays for an ISO 3166-1 alpha-2 country code and a year.",
            {
                "country_code": {"type": "string", "required": True, "pattern": "^[A-Za-z]{2}$"},
                "year": {"type": "integer", "required": True, "min": 1975, "max": 2075},
            },
            public_holidays,
        ),
        Tool(
            "convert_currency",
            "Convert an amount between currencies using the latest ECB reference rates (major currencies only).",
            {
                "amount": {"type": "number", "required": True, "min": 0},
                "from_currency": {"type": "string", "required": True, "pattern": "^[A-Za-z]{3}$"},
                "to_currency": {"type": "string", "required": True, "pattern": "^[A-Za-z]{3}$"},
            },
            convert_currency,
        ),
        Tool(
            "wikipedia_summary",
            "Lead summary of an English Wikipedia article by exact title.",
            {"title": {"type": "string", "required": True}},
            wikipedia_summary,
        ),
    ]
}


def call_tool(name: str, args: dict) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool '{name}'"}
    try:
        return tool.fn(**args)
    except ToolError as error:
        return {"error": str(error)}
    except TypeError as error:
        return {"error": f"bad arguments: {error}"}
