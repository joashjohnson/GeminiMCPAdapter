from mcp.server.fastmcp import FastMCP
import httpx
import asyncio
from typing import Dict, Any, List, Optional

# Create an MCP server named "Weather"
mcp = FastMCP("Weather")

# Open-Meteo API base URL
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1"

# GeoCode API for city to coordinates
GEOCODE_API_URL = "https://geocoding-api.open-meteo.com/v1/search"


async def get_city_coordinates(city: str) -> Optional[Dict[str, float]]:
    """Get the latitude and longitude for a city.

    Args:
        city: The name of the city

    Returns:
        Dictionary with latitude and longitude or None if not found
    """
    try:
        params = {"name": city, "count": 1, "language": "en", "format": "json"}

        async with httpx.AsyncClient() as client:
            response = await client.get(GEOCODE_API_URL, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            if data.get("results") and len(data["results"]) > 0:
                result = data["results"][0]
                return {
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "name": result["name"],
                    "country": result.get("country", ""),
                }
            return None
    except Exception as e:
        print(f"Error getting coordinates for {city}: {str(e)}")
        return None


async def get_weather_data(
    latitude: float, longitude: float
) -> Optional[Dict[str, Any]]:
    """Get current weather data from Open-Meteo.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location

    Returns:
        Weather data dictionary or None if there was an error
    """
    try:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "timezone": "auto",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OPEN_METEO_BASE_URL}/forecast", params=params, timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error fetching weather data: {str(e)}")
        return None


async def get_forecast_data(
    latitude: float, longitude: float, days: int = 3
) -> Optional[Dict[str, Any]]:
    """Get forecast data from Open-Meteo.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        days: Number of days for the forecast

    Returns:
        Forecast data dictionary or None if there was an error
    """
    try:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "timezone": "auto",
            "forecast_days": days,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OPEN_METEO_BASE_URL}/forecast", params=params, timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Error fetching forecast data: {str(e)}")
        return None


def weather_code_to_condition(code: int) -> str:
    """Convert Open-Meteo weather code to a readable condition.

    Args:
        code: The weather code from Open-Meteo

    Returns:
        A readable weather condition string
    """
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }

    return weather_codes.get(code, "Unknown")


@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get the current weather for a specified city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        A string with the current weather information
    """
    # Get coordinates for the city
    city_info = await get_city_coordinates(city)
    if not city_info:
        return f"Sorry, I couldn't find coordinates for {city}."

    # Get weather data using the coordinates
    weather_data = await get_weather_data(city_info["latitude"], city_info["longitude"])
    if not weather_data:
        return f"Sorry, I couldn't fetch weather data for {city}."

    # Extract and format the weather information
    current = weather_data.get("current", {})
    units = weather_data.get("current_units", {})

    temp = current.get("temperature_2m")
    temp_unit = units.get("temperature_2m", "°C")

    humidity = current.get("relative_humidity_2m")
    humidity_unit = units.get("relative_humidity_2m", "%")

    weather_code = current.get("weather_code")
    condition = (
        weather_code_to_condition(weather_code)
        if weather_code is not None
        else "Unknown"
    )

    wind_speed = current.get("wind_speed_10m")
    wind_unit = units.get("wind_speed_10m", "km/h")

    location_name = f"{city_info['name']}, {city_info['country']}"

    return (
        f"Weather for {location_name}:\n"
        f"Temperature: {temp}{temp_unit}\n"
        f"Condition: {condition}\n"
        f"Humidity: {humidity}{humidity_unit}\n"
        f"Wind Speed: {wind_speed} {wind_unit}"
    )


@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get a weather forecast for a specified city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")
        days: Number of days for the forecast (default: 3, max: 7)

    Returns:
        A string with the forecast information
    """
    # Limit days to a reasonable range
    days = min(max(1, days), 7)

    # Get coordinates for the city
    city_info = await get_city_coordinates(city)
    if not city_info:
        return f"Sorry, I couldn't find coordinates for {city}."

    # Get forecast data using the coordinates
    forecast_data = await get_forecast_data(
        city_info["latitude"], city_info["longitude"], days
    )
    if not forecast_data:
        return f"Sorry, I couldn't fetch forecast data for {city}."

    # Extract and format the forecast information
    daily = forecast_data.get("daily", {})
    units = forecast_data.get("daily_units", {})

    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    weather_codes = daily.get("weather_code", [])

    temp_unit = units.get("temperature_2m_max", "°C")
    precip_unit = units.get("precipitation_sum", "mm")

    location_name = f"{city_info['name']}, {city_info['country']}"
    forecast = f"Weather Forecast for {location_name} (Next {days} days):\n\n"

    for i in range(min(len(dates), days)):
        condition = (
            weather_code_to_condition(weather_codes[i])
            if i < len(weather_codes)
            else "Unknown"
        )
        forecast += (
            f"Date: {dates[i]}:\n"
            f"  Temperature: {min_temps[i]}{temp_unit} to {max_temps[i]}{temp_unit}\n"
            f"  Condition: {condition}\n"
            f"  Precipitation: {precip[i]} {precip_unit}\n\n"
        )

    return forecast


@mcp.tool()
async def get_weather_by_coordinates(latitude: float, longitude: float) -> str:
    """Get the current weather for specified coordinates.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location

    Returns:
        A string with the current weather information
    """
    # Get weather data using the coordinates
    weather_data = await get_weather_data(latitude, longitude)
    if not weather_data:
        return f"Sorry, I couldn't fetch weather data for coordinates ({latitude}, {longitude})."

    # Extract and format the weather information
    current = weather_data.get("current", {})
    units = weather_data.get("current_units", {})

    temp = current.get("temperature_2m")
    temp_unit = units.get("temperature_2m", "°C")

    humidity = current.get("relative_humidity_2m")
    humidity_unit = units.get("relative_humidity_2m", "%")

    weather_code = current.get("weather_code")
    condition = (
        weather_code_to_condition(weather_code)
        if weather_code is not None
        else "Unknown"
    )

    wind_speed = current.get("wind_speed_10m")
    wind_unit = units.get("wind_speed_10m", "km/h")

    return (
        f"Weather for coordinates ({latitude}, {longitude}):\n"
        f"Temperature: {temp}{temp_unit}\n"
        f"Condition: {condition}\n"
        f"Humidity: {humidity}{humidity_unit}\n"
        f"Wind Speed: {wind_speed} {wind_unit}"
    )


@mcp.tool()
async def get_forecast_by_coordinates(
    latitude: float, longitude: float, days: int = 3
) -> str:
    """Get a weather forecast for specified coordinates.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        days: Number of days for the forecast (default: 3, max: 7)

    Returns:
        A string with the forecast information
    """
    # Limit days to a reasonable range
    days = min(max(1, days), 7)

    # Get forecast data using the coordinates
    forecast_data = await get_forecast_data(latitude, longitude, days)
    if not forecast_data:
        return f"Sorry, I couldn't fetch forecast data for coordinates ({latitude}, {longitude})."

    # Extract and format the forecast information
    daily = forecast_data.get("daily", {})
    units = forecast_data.get("daily_units", {})

    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    weather_codes = daily.get("weather_code", [])

    temp_unit = units.get("temperature_2m_max", "°C")
    precip_unit = units.get("precipitation_sum", "mm")

    forecast = f"Weather Forecast for coordinates ({latitude}, {longitude}) (Next {days} days):\n\n"

    for i in range(min(len(dates), days)):
        condition = (
            weather_code_to_condition(weather_codes[i])
            if i < len(weather_codes)
            else "Unknown"
        )
        forecast += (
            f"Date: {dates[i]}:\n"
            f"  Temperature: {min_temps[i]}{temp_unit} to {max_temps[i]}{temp_unit}\n"
            f"  Condition: {condition}\n"
            f"  Precipitation: {precip[i]} {precip_unit}\n\n"
        )

    return forecast


# Run the server
if __name__ == "__main__":
    mcp.run()
