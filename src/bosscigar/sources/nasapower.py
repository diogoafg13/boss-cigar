"""Clima por zona de cultivo via NASA POWER (climatologia, domínio público).

https://power.larc.nasa.gov/ — dados NASA, sem restrições de uso; pede-se atribuição.
"""
from __future__ import annotations

from .http import fetch_with_cache, get_json

API = "https://power.larc.nasa.gov/api/temporal/climatology/point"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DAYS = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def fetch_climatology(lat: float, lng: float) -> dict:
    return get_json(API, {"parameters": "T2M,PRECTOTCORR,RH2M", "community": "AG",
                          "latitude": lat, "longitude": lng, "format": "JSON"}, timeout=60)


def summarize(raw: dict) -> dict:
    p = raw.get("properties", {}).get("parameter", {})
    t, pr, rh = p.get("T2M"), p.get("PRECTOTCORR"), p.get("RH2M")
    if not (t and pr and rh):
        return {}
    ok = lambda v: v is not None and v > -900  # -999 = sem dados
    temp = [round(t[m], 1) if ok(t.get(m)) else None for m in MONTHS]
    rain = [round(pr[m] * d, 0) if ok(pr.get(m)) else None for m, d in zip(MONTHS, DAYS)]  # mm/dia -> mm/mês
    hum = [round(rh[m], 0) if ok(rh.get(m)) else None for m in MONTHS]
    return {
        "period": "climatologia NASA POWER",
        "temp_c_monthly": temp,
        "rain_mm_monthly": rain,
        "rh_pct_monthly": hum,
        "temp_c_annual": round(t["ANN"], 1) if ok(t.get("ANN")) else None,
        "rain_mm_annual": round(sum(r for r in rain if r is not None), 0),
        "rh_pct_annual": round(rh["ANN"], 0) if ok(rh.get("ANN")) else None,
        "source": "NASA POWER",
    }


def climate_for_regions(regions: list[dict]) -> tuple[dict[str, dict], str]:
    out: dict[str, dict] = {}
    states: list[str] = []
    for r in regions:
        data, state = fetch_with_cache(f"climate_{r['id']}",
                                       lambda r=r: summarize(fetch_climatology(r["lat"], r["lng"])))
        states.append(state.split(" ")[0].rstrip(":"))
        if data:
            out[r["id"]] = data
    return out, aggregate(states)


def aggregate(states: list[str]) -> str:
    if not states or all(s == "ok" for s in states):
        return "ok"
    if all(s == "ERRO" for s in states):
        return "ERRO"
    if "ERRO" in states:
        return "PARCIAL"
    return "CACHE"
