"""Estancos (expendedurías) oficiais espanhóis perto da fronteira com Portugal.

O Comisionado para el Mercado de Tabacos publica em CSV a lista de todas as expendedurías
ativas (código, município, localidade, morada). Não tem coordenadas: usamos uma lista fixa de
cidades fronteiriças (com coordenadas aproximadas do centro) e juntamos os estancos de cada uma.
Origem dos dados: Ministerio de Hacienda (reutilização com citação da fonte).
"""
from __future__ import annotations

import csv
import io
import unicodedata

import requests

from .. import USER_AGENT
from .http import SourceError, fetch_with_cache

CSV_URL = "https://serviciostelematicosext.hacienda.gob.es/CMT/Visor/csvExpendedurias.aspx"
PAGE = "https://www.hacienda.gob.es/es-ES/Areas%20Tematicas/CMTabacos/Paginas/Red-Expendedurias-y-PVR.aspx"

# (município no CSV, nome, província, lat, lng, passagem/cidade portuguesa mais próxima)
BORDER_TOWNS = [
    ("GUARDA (A)", "A Guarda", "Pontevedra", 41.901, -8.874, "Caminha (ferry)"),
    ("TUI", "Tui", "Pontevedra", 42.047, -8.645, "Valença"),
    ("TOMINO", "Tomiño", "Pontevedra", 41.988, -8.741, "Vila Nova de Cerveira"),
    ("SALVATERRA DE MINO", "Salvaterra de Miño", "Pontevedra", 42.084, -8.501, "Monção"),
    ("VIGO", "Vigo", "Pontevedra", 42.240, -8.720, "Valença (30 km)"),
    ("VERIN", "Verín", "Ourense", 41.941, -7.436, "Chaves"),
    ("ALCANICES", "Alcañices", "Zamora", 41.700, -6.347, "Quintanilha / Bragança"),
    ("FUENTES DE ONORO", "Fuentes de Oñoro", "Salamanca", 40.589, -6.812, "Vilar Formoso"),
    ("CIUDAD RODRIGO", "Ciudad Rodrigo", "Salamanca", 40.600, -6.533, "Vilar Formoso (27 km)"),
    ("VALENCIA DE ALCANTARA", "Valencia de Alcántara", "Cáceres", 39.413, -7.244, "Marvão / Castelo de Vide"),
    ("ALBURQUERQUE", "Alburquerque", "Badajoz", 39.217, -6.993, "Campo Maior"),
    ("BADAJOZ", "Badajoz", "Badajoz", 38.878, -6.970, "Elvas / Caia"),
    ("OLIVENZA", "Olivenza", "Badajoz", 38.682, -7.100, "Elvas (ponte da Ajuda)"),
    ("ROSAL DE LA FRONTERA", "Rosal de la Frontera", "Huelva", 37.966, -7.218, "Vila Verde de Ficalho"),
    ("AYAMONTE", "Ayamonte", "Huelva", 37.213, -7.407, "Vila Real de Santo António"),
    ("ISLA CRISTINA", "Isla Cristina", "Huelva", 37.199, -7.320, "Vila Real de Santo António (15 km)"),
]


def fold(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", (s or "").upper()) if unicodedata.category(ch) != "Mn").strip()


def parse(text: str) -> dict:
    lines = text.lstrip("﻿").splitlines()
    as_of = lines[0].strip() if lines else ""
    start = next((i for i, l in enumerate(lines) if l.startswith("Estanco;")), None)
    if start is None:
        raise SourceError("CSV de expendedurías sem cabeçalho esperado")
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[start:])), delimiter=";"))
    by_muni: dict[str, list] = {}
    for r in rows:
        by_muni.setdefault(fold(r.get("Municipio")), []).append(r)
    towns = []
    for muni, name, prov, lat, lng, pt in BORDER_TOWNS:
        est = [{"code": r["Estanco"], "locality": (r.get("Localidad") or "").title(), "address": (r.get("Dirección") or "").strip()}
               for r in by_muni.get(muni, [])]
        towns.append({"municipality": muni, "name": name, "province": prov, "lat": lat, "lng": lng, "crossing": pt,
                      "estancos": sorted(est, key=lambda e: e["address"])})
    return {"as_of": as_of, "total_spain": len(rows), "towns": towns}


def download() -> str:
    r = requests.get(CSV_URL, timeout=90, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.content.decode("utf-8-sig", errors="replace")


def border_estancos() -> tuple[dict, str]:
    data, state = fetch_with_cache("cmt_estancos_fronteira", lambda: parse(download()))
    return data or {"towns": []}, state.split(" ")[0].rstrip(":")
