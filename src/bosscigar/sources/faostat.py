"""Produção de tabaco por país via FAOSTAT (CC BY 4.0).

Item 826 'Unmanufactured tobacco'; elementos 5510 (produção, t) e 5312 (área colhida, ha).
O ficheiro bulk tem ~34 MB comprimido; só se guarda em cache o resultado filtrado.
"""
from __future__ import annotations

import csv
import io
import tempfile
import zipfile

import requests

from .. import USER_AGENT
from .http import fetch_with_cache

BULK = "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip"
ITEM = "826"
ELEMENTS = {"5510": "production_t", "5312": "area_ha"}
FIRST_YEAR = 2000
AGGREGATE_CODES = {351}  # "China" = soma de China mainland, Hong Kong, Macau e Taiwan


def _download(path: str) -> None:
    with requests.get(BULK, stream=True, timeout=120, headers={"User-Agent": USER_AGENT}) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def parse_rows(lines) -> dict:
    """lines: iterável de linhas de texto do CSV normalizado. Devolve {país: {ano: {campo: valor}}}."""
    out: dict = {}
    for row in csv.DictReader(lines):
        if row.get("Item Code") != ITEM or row.get("Element Code") not in ELEMENTS:
            continue
        code = int(row["Area Code"])
        if code >= 5000 or code in AGGREGATE_CODES:  # Mundo, continentes, "China" (inclui mainland + Taiwan...)
            continue
        year = int(row["Year"])
        if year < FIRST_YEAR or not row.get("Value"):
            continue
        m49 = row["Area Code (M49)"].lstrip("'")
        country = out.setdefault(row["Area"], {"m49": m49, "years": {}})
        country["years"].setdefault(str(year), {})[ELEMENTS[row["Element Code"]]] = float(row["Value"])
    return out


def fetch_tobacco() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = f"{tmp}/fao.zip"
        _download(path)
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith("(Normalized).csv"))
            with z.open(name) as f:
                return parse_rows(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))


def summarize(data: dict, top: int = 25) -> dict:
    """Último ano disponível, ranking e séries por país."""
    latest = max((int(y) for c in data.values() for y in c["years"]), default=None)
    if latest is None:
        return {}
    ranking = []
    for name, c in data.items():
        y = c["years"].get(str(latest), {})
        if y.get("production_t"):
            ranking.append({"country": name, "m49": c["m49"], "production_t": y["production_t"],
                            "area_ha": y.get("area_ha")})
    ranking.sort(key=lambda r: -r["production_t"])
    world = sum(r["production_t"] for r in ranking)
    for r in ranking:
        r["share"] = round(r["production_t"] / world, 4) if world else None
    series = {name: {y: v.get("production_t") for y, v in sorted(c["years"].items())} for name, c in data.items()}
    latest_by_country = {}
    for name, c in data.items():
        years = [y for y, v in c["years"].items() if v.get("production_t")]
        if years:
            y = max(years)
            latest_by_country[name] = {"year": int(y), "production_t": c["years"][y]["production_t"]}
    return {"latest_year": latest, "world_t": world, "ranking": ranking[:top], "series": series, "latest_by_country": latest_by_country,
            "source": "FAOSTAT (CC BY 4.0)"}


def tobacco_production() -> tuple[dict, str]:
    data, state = fetch_with_cache("faostat_tobacco", lambda: summarize(fetch_tobacco()))
    return data or {}, state.split(" ")[0].rstrip(":")
