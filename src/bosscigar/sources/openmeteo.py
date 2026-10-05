"""Clima por zona de cultivo (terroir) via Open-Meteo Historical Weather API.

Open-Meteo: https://open-meteo.com/ — dados CC BY 4.0, uso gratuito não comercial.
"""
from __future__ import annotations

from collections import defaultdict

from .http import fetch_with_cache, get_json

API = "https://archive-api.open-meteo.com/v1/archive"
START_YEAR, END_YEAR = 2015, 2024


def fetch_daily(lat: float, lng: float) -> dict:
    return get_json(API, {
        "latitude": lat, "longitude": lng,
        "start_date": f"{START_YEAR}-01-01", "end_date": f"{END_YEAR}-12-31",
        "daily": "temperature_2m_mean,precipitation_sum", "timezone": "UTC",
    })


def summarize(daily: dict) -> dict:
    """Médias mensais de temperatura e precipitação acumulada média por mês."""
    d = daily.get("daily", {})
    dates, temps, rain = d.get("time", []), d.get("temperature_2m_mean", []), d.get("precipitation_sum", [])
    t_sum, t_n = defaultdict(float), defaultdict(int)
    r_sum = defaultdict(float)
    years = set()
    for date, t, r in zip(dates, temps, rain):
        month = int(date[5:7])
        years.add(date[:4])
        if t is not None:
            t_sum[month] += t
            t_n[month] += 1
        if r is not None:
            r_sum[month] += r
    if not t_n:
        return {}
    ny = max(len(years), 1)
    monthly_t = [round(t_sum[m] / t_n[m], 1) if t_n[m] else None for m in range(1, 13)]
    monthly_r = [round(r_sum[m] / ny, 1) for m in range(1, 13)]
    valid_t = [t for t in monthly_t if t is not None]
    return {
        "period": f"{START_YEAR}-{END_YEAR}",
        "temp_c_monthly": monthly_t,
        "rain_mm_monthly": monthly_r,
        "temp_c_annual": round(sum(valid_t) / len(valid_t), 1) if valid_t else None,
        "rain_mm_annual": round(sum(monthly_r), 0),
        "source": "Open-Meteo (CC BY 4.0)",
    }


def climate_for_regions(regions: list[dict]) -> tuple[dict[str, dict], str]:
    out: dict[str, dict] = {}
    states: list[str] = []
    for r in regions:
        data, state = fetch_with_cache(f"climate_{r['id']}", lambda r=r: summarize(fetch_daily(r["lat"], r["lng"])))
        states.append(state.split(" ")[0].rstrip(":"))
        if data:
            out[r["id"]] = data
    if all(s == "ok" for s in states):
        status = "ok"
    elif all(s == "ERRO" for s in states):
        status = "ERRO"
    elif "ERRO" in states:
        status = "PARCIAL"
    else:
        status = "CACHE"
    return out, status
