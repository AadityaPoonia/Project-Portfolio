"""
Weather Tools
=============
Consolidated weather tools using the Open-Meteo API.
Includes: current weather, forecast, past weather, and city comparison.
"""

import requests
from pydantic import BaseModel, Field
from langchain_core.tools import tool


def get_lat_lon_candidates(city_input: str) -> list:
    """
    Intelligently handles "City, Region" queries with context filtering.
    Returns a list of geocoding candidates from Open-Meteo.
    """
    try:
        if "," in city_input:
            parts = [p.strip() for p in city_input.split(",")]
            city_name = parts[0]
            context = " ".join(parts[1:]).lower()
        else:
            city_name = city_input
            context = ""

        abbreviations = {"BC": "British Columbia", "UK": "United Kingdom", "US": "United States"}
        for abbr, full in abbreviations.items():
            city_name = city_name.replace(abbr, full)

        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={city_name}&count=10&language=en&format=json"
        )
        response = requests.get(url, timeout=10).json()
        raw_results = response.get("results", [])

        if not raw_results:
            return []

        if context:
            filtered = []
            for result in raw_results:
                result_text = (
                    f"{result.get('name')} {result.get('country')} {result.get('admin1')}"
                ).lower()
                if any(term in result_text for term in context.split()):
                    filtered.append(result)
            if filtered:
                return filtered

        return raw_results

    except Exception:
        return []


def _check_ambiguity(candidates: list) -> str | None:
    """Return an ambiguity message if multiple countries match."""
    if len(candidates) > 1 and candidates[0].get("country_id") != candidates[1].get("country_id"):
        options = [
            f"{candidate['name']} ({candidate.get('country')}, {candidate.get('admin1')})"
            for candidate in candidates[:4]
        ]
        return (
            "AMBIGUITY_DETECTED: Found multiple locations: "
            f"{', '.join(options)}. Please ask the user to clarify which one."
        )
    return None


class CityInput(BaseModel):
    city: str = Field(description="The city name (e.g. 'London', 'Victoria, BC')")
    dummy: str = Field(default="", description="Leave this empty string always")


class ForecastInput(BaseModel):
    city: str = Field(description="The city name")
    days: str = Field(description="Number of forecast days (1-14, default '3')", default="3")


class PastWeatherInput(BaseModel):
    city: str = Field(description="The city name")
    date: str = Field(description="Date in YYYY-MM-DD format")


class CompareCitiesInput(BaseModel):
    cities_str: str = Field(description="Comma-separated list of cities (e.g. 'London, Paris, Tokyo')")
    dummy: str = Field(default="", description="Leave this empty string always")


@tool(args_schema=CityInput)
def get_current_weather(city: str, dummy: str = "") -> str:
    """Get current weather conditions for a city.
    Use this tool ONLY when the user explicitly asks about current weather or temperature."""
    candidates = get_lat_lon_candidates(city)
    if not candidates:
        return f"Error: City '{city}' not found."

    ambiguity = _check_ambiguity(candidates)
    if ambiguity:
        return ambiguity

    match = candidates[0]
    lat, lon = match["latitude"], match["longitude"]
    name = f"{match['name']}, {match.get('country', '')}"

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true"
        )
        data = requests.get(url, timeout=10).json()
        current_weather = data["current_weather"]
        return (
            f"Current weather in {name}: "
            f"Temperature: {current_weather['temperature']}C, "
            f"Wind: {current_weather['windspeed']} km/h, "
            f"Condition code: {current_weather['weathercode']}"
        )
    except Exception as e:
        return f"Error fetching weather: {e}"


@tool(args_schema=ForecastInput)
def get_forecast(city: str, days: str = "3") -> str:
    """Get a multi-day weather forecast for a city.
    Use this when the user asks about upcoming weather or forecasts."""
    try:
        clean_days = "".join(filter(str.isdigit, str(days)))
        days_int = int(clean_days) if clean_days else 3
        days_int = max(1, min(14, days_int))
    except (ValueError, TypeError):
        days_int = 3

    candidates = get_lat_lon_candidates(city)
    if not candidates:
        return "Error: City not found."

    ambiguity = _check_ambiguity(candidates)
    if ambiguity:
        return ambiguity

    match = candidates[0]
    lat, lon = match["latitude"], match["longitude"]
    name = f"{match['name']}, {match.get('country', '')}"

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&forecast_days={days_int}"
        )
        data = requests.get(url, timeout=10).json()
        daily = data["daily"]
        lines = [f"{days_int}-day forecast for {name}:"]
        for i in range(len(daily["time"])):
            lines.append(
                f"  {daily['time'][i]}: "
                f"High {daily['temperature_2m_max'][i]}C, "
                f"Low {daily['temperature_2m_min'][i]}C, "
                f"Precip {daily['precipitation_sum'][i]}mm"
            )
        return "\n".join(lines)
    except Exception:
        return "Error fetching forecast data."


@tool(args_schema=PastWeatherInput)
def get_past_weather(city: str, date: str) -> str:
    """Get historical weather for a city on a specific past date.
    Use this when the user asks about weather on a past date (e.g. 'yesterday', 'last week')."""
    candidates = get_lat_lon_candidates(city)
    if not candidates:
        return "Error: City not found."

    ambiguity = _check_ambiguity(candidates)
    if ambiguity:
        return ambiguity

    match = candidates[0]
    lat, lon = match["latitude"], match["longitude"]
    name = f"{match['name']}, {match.get('country', '')}"

    try:
        url = (
            "https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={date}&end_date={date}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        )
        data = requests.get(url, timeout=10).json()
        if "daily" not in data:
            return f"No historical data found for {name} on {date}."
        daily = data["daily"]
        return (
            f"Past weather in {name} on {date}: "
            f"High {daily['temperature_2m_max'][0]}C, "
            f"Low {daily['temperature_2m_min'][0]}C, "
            f"Precip {daily['precipitation_sum'][0]}mm"
        )
    except Exception:
        return "Error fetching past weather. Ensure date format is YYYY-MM-DD."


@tool(args_schema=CompareCitiesInput)
def compare_cities(cities_str: str, dummy: str = "") -> str:
    """Compare current weather across multiple cities side by side.
    Use this when the user lists multiple cities or asks for a comparison."""
    cities = [city.strip() for city in cities_str.replace(" and ", ",").split(",") if city.strip()]
    if len(cities) < 2:
        return "Please provide at least 2 cities to compare."

    report = "Weather Comparison (3-Day Avg High):\n"
    for city in cities:
        candidates = get_lat_lon_candidates(city)
        if not candidates:
            report += f"  {city}: Not found\n"
            continue

        match = candidates[0]
        lat, lon = match["latitude"], match["longitude"]
        name = f"{match['name']}, {match.get('country', '')}"

        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&daily=temperature_2m_max&forecast_days=3"
            )
            data = requests.get(url, timeout=10).json()
            temps = data["daily"]["temperature_2m_max"]
            avg = sum(temps) / len(temps)
            report += f"  {name}: Avg High {avg:.1f}C\n"
        except Exception:
            report += f"  {name}: Error fetching data\n"

    return report
