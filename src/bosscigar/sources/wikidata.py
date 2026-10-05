"""Enriquecimento de marcas com factos abertos do Wikidata (CC0).

Nunca sobrepõe o seed curado: acrescenta um bloco `wikidata` e a qualidade
assinala discrepâncias (ex.: país diferente).
"""
from __future__ import annotations

import time

from .http import fetch_with_cache, get_json

API = "https://www.wikidata.org/w/api.php"
KEYWORDS = ("cigar", "charuto", "tobacco", "tabaco")


def _search(term: str) -> list[dict]:
    data = get_json(API, {"action": "wbsearchentities", "search": term, "language": "en",
                          "type": "item", "limit": 20, "format": "json"})
    return data.get("search", [])


def _search_brand(brand: str) -> list[dict]:
    """Pesquisa 'marca cigar' primeiro (evita apelidos e concelhos) e depois só a marca."""
    seen, out = set(), []
    for term in (f"{brand} cigar", f"{brand} cigars", brand):
        for hit in _search(term):
            if hit["id"] not in seen:
                seen.add(hit["id"])
                out.append(hit)
        time.sleep(0.3)
    return out


def _entities(ids: list[str]) -> dict:
    data = get_json(API, {"action": "wbgetentities", "ids": "|".join(ids), "format": "json",
                          "props": "claims|labels|descriptions", "languages": "en|pt"})
    return data.get("entities", {})


def _claim_ids(entity: dict, prop: str) -> list[str]:
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            out.append(v["id"])
    return out


def _inception_year(entity: dict) -> int | None:
    for c in entity.get("claims", {}).get("P571", []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("time"):
            try:
                return int(v["time"][1:5])
            except ValueError:
                continue
    return None


def lookup_brand(brand: str) -> dict:
    """Procura a marca; só aceita resultados cuja descrição fale de charutos/tabaco."""
    candidates = [s for s in _search_brand(brand)
                  if any(k in (s.get("description") or "").lower() for k in KEYWORDS)]
    if not candidates:
        return {"found": False}
    qid = candidates[0]["id"]
    ents = _entities([qid])
    ent = ents.get(qid, {})
    country_ids = _claim_ids(ent, "P495") + _claim_ids(ent, "P17")
    countries = {}
    if country_ids:
        for cid, cent in _entities(sorted(set(country_ids))).items():
            labels = cent.get("labels", {})
            countries[cid] = (labels.get("pt") or labels.get("en") or {}).get("value", cid)
    return {
        "found": True,
        "qid": qid,
        "url": f"https://www.wikidata.org/wiki/{qid}",
        "label": ent.get("labels", {}).get("en", {}).get("value"),
        "description": ent.get("descriptions", {}).get("en", {}).get("value"),
        "inception_year": _inception_year(ent),
        "countries": [countries[c] for c in country_ids if c in countries],
    }


def enrich_brands(brands: list[str]) -> tuple[dict[str, dict], str]:
    """Devolve ({marca: factos}, estado agregado)."""
    results: dict[str, dict] = {}
    states: set[str] = set()
    for b in sorted(set(brands)):
        name = "wikidata_" + "".join(ch if ch.isalnum() else "_" for ch in b.lower())
        data, state = fetch_with_cache(name, lambda b=b: lookup_brand(b))
        time.sleep(0.3)
        states.add(state.split(" ")[0].rstrip(":"))
        if data:
            results[b] = data
    if states <= {"ok"}:
        status = "ok"
    elif "ERRO" in states and "ok" not in states and "CACHE" not in states:
        status = "ERRO"
    elif "ERRO" in states:
        status = "PARCIAL"
    else:
        status = "CACHE"
    return results, status
