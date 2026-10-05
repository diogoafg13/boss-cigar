"""Catálogo aberto de marcas: tabela 'List of cigar brands' da Wikipédia (CC BY-SA 4.0).

O texto é reutilizado com atribuição e mantém a licença CC BY-SA.
"""
from __future__ import annotations

import re

from .http import fetch_with_cache, get_json

API = "https://en.wikipedia.org/w/api.php"
PAGE = "List_of_cigar_brands"
PAGE_URL = "https://en.wikipedia.org/wiki/List_of_cigar_brands"

# Países produtores de charutos (inglês -> português) para detetar origem nas notas.
COUNTRIES = {
    "Cuba": "Cuba", "Dominican Republic": "República Dominicana", "Nicaragua": "Nicarágua",
    "Honduras": "Honduras", "Mexico": "México", "Brazil": "Brasil", "Ecuador": "Equador",
    "Cameroon": "Camarões", "Indonesia": "Indonésia", "Philippines": "Filipinas",
    "Costa Rica": "Costa Rica", "Panama": "Panamá", "Peru": "Peru", "Colombia": "Colômbia",
    "Jamaica": "Jamaica", "Puerto Rico": "Porto Rico", "United States": "Estados Unidos",
    "Canary Islands": "Canárias", "Germany": "Alemanha", "Netherlands": "Países Baixos",
    "Switzerland": "Suíça", "Italy": "Itália", "Denmark": "Dinamarca", "Belgium": "Bélgica",
    "Spain": "Espanha", "Sri Lanka": "Sri Lanka", "India": "Índia", "Guatemala": "Guatemala",
}


def fetch_wikitext() -> str:
    data = get_json(API, {"action": "parse", "page": PAGE, "prop": "wikitext|revid",
                          "format": "json", "formatversion": 2})
    return {"wikitext": data["parse"]["wikitext"], "revid": data["parse"].get("revid")}


def clean(cell: str) -> str:
    s = re.sub(r"<ref[^>]*/>", "", cell)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)        # [[a|b]] -> b
    s = re.sub(r"\[https?://\S+\s*([^\]]*)\]", r"\1", s)            # [url texto] -> texto
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip(" |")


def parse_table(wikitext: str) -> list[dict]:
    start = wikitext.find('{| class="wikitable')
    end = wikitext.find("|}", start)
    if start < 0 or end < 0:
        return []
    body = wikitext[start:end]
    out = []
    for row in body.split("\n|-")[1:]:
        cells, cur = [], None
        for line in row.split("\n"):
            if line.startswith("|") and not line.startswith("|-") and not line.startswith("|}"):
                if cur is not None:
                    cells.append(cur)
                cur = line[1:]
            elif line.startswith("!"):
                cur = None
            elif cur is not None:
                cur += " " + line
        if cur is not None:
            cells.append(cur)
        if len(cells) == 1 and "||" in cells[0]:
            cells = cells[0].split("||")
        cells = [clean(c) for c in cells]
        if not cells or not cells[0]:
            continue
        brand = cells[0]
        manufacturer = cells[1] if len(cells) > 1 else ""
        notes = cells[2] if len(cells) > 2 else ""
        text = f"{manufacturer} {notes}"
        countries = [pt for en, pt in COUNTRIES.items() if re.search(rf"\b{re.escape(en)}\b", text)]
        out.append({"brand": brand, "manufacturer": manufacturer, "notes": notes, "countries": countries})
    return out


def brand_catalog() -> tuple[dict, str]:
    """Guarda o wikitext bruto em cache, para o parsing poder evoluir sem novos pedidos."""
    raw, state = fetch_with_cache("wikipedia_cigar_brands_raw", fetch_wikitext)
    if not raw:
        return {"brands": []}, state.split(" ")[0].rstrip(":")
    return {"revid": raw.get("revid"), "brands": parse_table(raw["wikitext"])}, state.split(" ")[0].rstrip(":")
