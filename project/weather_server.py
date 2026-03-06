"""
天气 MCP 服务器：仅使用 Open-Meteo URL，无需 API Key。
"""
import httpx
from fastmcp import FastMCP

mcp = FastMCP("weather-server")

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@mcp.tool()
def get_weather_by_city(city_name: str) -> str:
    """根据城市名称查询当前天气。使用 Open-Meteo 免费接口，无需 API Key。"""
    with httpx.Client() as client:
        r = client.get(GEO_URL, params={"name": city_name, "count": 1})
        r.raise_for_status()
        data = r.json()
        if not data.get("results"):
            return f"未找到城市: {city_name}"
        loc = data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        name = loc.get("name", city_name)
        r2 = client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
            },
        )
        r2.raise_for_status()
        fc = r2.json()
        cur = fc.get("current", {})
        return (
            f"{name} 当前: 气温 {cur.get('temperature_2m')}°C, "
            f"相对湿度 {cur.get('relative_humidity_2m')}%, "
            f"风速 {cur.get('wind_speed_10m')} km/h, 天气码 {cur.get('weather_code')}."
        )


@mcp.tool()
def get_weather_by_coords(latitude: float, longitude: float) -> str:
    """根据经纬度查询当前天气。使用 Open-Meteo 免费接口，无需 API Key。"""
    with httpx.Client() as client:
        r = client.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
            },
        )
        r.raise_for_status()
        fc = r.json()
        cur = fc.get("current", {})
        return (
            f"纬度 {latitude}, 经度 {longitude} 当前: "
            f"气温 {cur.get('temperature_2m')}°C, 湿度 {cur.get('relative_humidity_2m')}%, "
            f"风速 {cur.get('wind_speed_10m')} km/h."
        )


if __name__ == "__main__":
    mcp.run()
