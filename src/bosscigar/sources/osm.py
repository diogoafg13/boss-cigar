"""Tabacarias em Portugal via OpenStreetMap / Overpass (ODbL).

Os dados são da comunidade OSM: podem estar incompletos ou desatualizados.
"""
from __future__ import annotations

import requests

from .. import USER_AGENT
from .http import SourceError, fetch_with_cache

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
QUERY = """[out:json][timeout:60];
area["ISO3166-1"="PT"][admin_level=2]->.pt;
(nwr["shop"="tobacco"](area.pt);
 nwr["shop"="cigar"](area.pt);
 nwr["amenity"="smoking_lounge"](area.pt););
out center tags;"""


def _post(query: str) -> dict:
    last = None
    for ep in ENDPOINTS:
        try:
            r = requests.post(ep, data={"data": query}, timeout=90, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
    raise SourceError(f"Overpass indisponível: {last}")


def parse(raw: dict) -> list[dict]:
    out = []
    for el in raw.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        name = tags.get("name")
        if not name:
            continue  # sem nome não é útil para o utilizador
        out.append({
            "name": name,
            "kind": tags.get("shop") or tags.get("amenity"),
            "lat": round(lat, 6), "lng": round(lon, 6),
            "city": tags.get("addr:city"),
            "street": " ".join(x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x) or None,
            "website": tags.get("website") or tags.get("contact:website"),
            "opening_hours": tags.get("opening_hours"),
            "osm": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        })
    out.sort(key=lambda s: (s["city"] or "~", s["name"]))
    return out


def shops_portugal() -> tuple[list[dict], str]:
    data, state = fetch_with_cache("osm_shops_pt", lambda: parse(_post(QUERY)))
    return data or [], state.split(" ")[0].rstrip(":")
