"""Preços oficiais dos charutos em Espanha (Comisionado para el Mercado de Tabacos).

O buscador "Precios de labores" do Ministerio de Hacienda tem um botão "Exportar a CSV".
O pipeline reproduz esse pedido (postback ASP.NET) para a zona "Península e Illes Balears"
e a labor "Cigarros". O CSV traz: nome (marca em MAIÚSCULAS + produto + embalagem),
preço por unidade na Expendeduría e preço com recargo (pontos de venda com recargo).

Reutilização: informação do setor público espanhol (Ley 37/2007), com citação da fonte.
Cada execução guarda um snapshot datado, para construir histórico ao longo do tempo.
"""
from __future__ import annotations

import csv
import html
import io
import re
from datetime import date

import requests

from .. import USER_AGENT
from .douane_fr import _enrich, squash
from .http import SourceError, cache_read, cache_write, fetch_with_cache

PAGE = "https://www.hacienda.gob.es/es-ES/Areas%20Tematicas/CMTabacos/Paginas/PreciosLabores.aspx"
ZONE = "Península e Illes Balears"
UPPER_TOKEN = re.compile(r"^[0-9A-ZÁÉÍÓÚÑÜÇ.&'´`+\-/]+$")
PACK = re.compile(r"\((?:el\s+envase\s+de\s+)?(\d+)\)\s*$", re.I)


def _form_fields(page_html: str) -> dict:
    form = re.search(r'<form[^>]*id="aspnetForm"[^>]*>(.*)</form>', page_html, re.S)
    if not form:
        raise SourceError("formulário do CMT não encontrado (a página mudou?)")
    data = {}
    for m in re.finditer(r"<input\b[^>]*>", form.group(1)):
        tag = m.group(0)
        n = re.search(r'name="([^"]+)"', tag)
        if not n:
            continue
        ty = (re.search(r'type="([^"]+)"', tag) or [None, "text"])[1].lower()
        if ty in ("submit", "image", "button", "checkbox", "radio"):
            continue
        v = re.search(r'value="([^"]*)"', tag)
        data[n.group(1)] = html.unescape(v.group(1)) if v else ""
    return data


def download_csv() -> str:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    page = s.get(PAGE, timeout=60)
    page.raise_for_status()
    data = _form_fields(page.text)
    data.update({"MinPortalTabacosZona": ZONE, "MinPortalTabacosLabor": "Cigarros", "MinPortalTabacosMarca": "",
                 "exportToCsv": "Exportar a CSV", "__EVENTTARGET": "", "__EVENTARGUMENT": ""})
    r = s.post(PAGE, data=data, timeout=120, headers={"Referer": PAGE})
    r.raise_for_status()
    if "csv" not in (r.headers.get("content-disposition") or "").lower():
        raise SourceError("o CMT não devolveu um CSV")
    return r.content.decode("cp1252", errors="replace")


def split_brand(name: str) -> tuple[str | None, str]:
    """'MONTECRISTO Montecristo Nº 2 (10)' -> ('MONTECRISTO', 'Montecristo Nº 2 (10)')."""
    toks = name.split()
    i = 0
    while i < len(toks) and UPPER_TOKEN.match(toks[i]) and not re.fullmatch(r"\(?\d+\)?", toks[i]):
        i += 1
    # marca que começa por número: "3 TERCIOS Robusto"
    if i == 0 and len(toks) > 1 and toks[0].isdigit() and UPPER_TOKEN.match(toks[1]) and not toks[1].isdigit():
        i = 2
        while i < len(toks) and UPPER_TOKEN.match(toks[i]) and not re.fullmatch(r"\(?\d+\)?", toks[i]):
            i += 1
    if i == 0:
        return None, name
    if i == len(toks):  # tudo em maiúsculas: a marca é a primeira palavra (ou duas, se a 1.ª for curta)
        i = 2 if len(toks) > 2 and len(toks[0]) <= 3 else 1
    return " ".join(toks[:i]), " ".join(toks[i:])


SMALL = {"DE", "DEL", "LA", "EL", "Y", "LOS", "LAS", "DI", "DU", "OF", "THE"}


def pretty_brand(b: str) -> str:
    """'ROMEO Y JULIETA' -> 'Romeo y Julieta'; 'A.FLORES' -> 'A.Flores'; siglas curtas ficam (CAO, PDR)."""
    out, words = [], b.split()
    for i, w in enumerate(words):
        if w in SMALL and i > 0:
            out.append(w.lower())
        elif len(words) == 1 and len(w) <= 3:  # sigla isolada: CAO, PDR, EGM
            out.append(w)
        else:
            out.append(re.sub(r"[A-ZÁÉÍÓÚÑÜÇ]+", lambda m: m.group(0)[0] + m.group(0)[1:].lower(), w))
    return " ".join(out)


def _num(s: str):
    try:
        return float(s.strip().replace(".", "").replace(",", ".")) if s.strip() else None
    except ValueError:
        return None


def parse_csv(text: str) -> list[dict]:
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    out = []
    for r in rows[1:]:
        if len(r) < 2 or not r[0].strip():
            continue
        name = r[0].strip()
        brand_raw, product = split_brand(name)
        # o produto repete muitas vezes a marca: "MONTECRISTO Montecristo Nº 2"
        if brand_raw and squash(product).startswith(squash(brand_raw)):
            label_core = product
        else:
            label_core = f"{pretty_brand(brand_raw)} {product}".strip() if brand_raw else product
        m = PACK.search(label_core)
        pack = int(m.group(1)) if m else None
        label = PACK.sub("", label_core).strip()
        unit = _num(r[1])
        envase = bool(re.search(r"el\s+envase\s+de", name, re.I))
        it = {"name": name, "label": label, "brand": pretty_brand(brand_raw) if brand_raw else None,
              "brand_source": "oficial", "pack_size": pack,
              # "(el envase de N)": o preço é o do conjunto, não por unidade
              "unit_eur": round(unit / pack, 2) if envase and unit and pack else unit,
              "pack_eur": unit if envase else (round(unit * pack, 2) if unit and pack else None),
              "surcharge_eur": _num(r[2]) if len(r) > 2 else None}
        it = _enrich({**it, "new": False, "supplier": None})
        # _enrich deduz a embalagem do formato francês ("en N cigares"); aqui vem entre parênteses
        it["label"], it["brand_source"], it["pack_size"] = label, "oficial", pack
        out.append(it)
    return out


def snapshot(items: list[dict], day: str) -> dict:
    return {"date": day, "prices": {f"{squash(i['label'])}|{i.get('pack_size') or ''}": i["unit_eur"]
                                    for i in items if i.get("unit_eur") is not None}}


def spanish_catalog(today: str | None = None) -> tuple[dict, str]:
    def fetch():
        items = parse_csv(download_csv())
        if len(items) < 500:
            raise SourceError(f"CSV do CMT com poucas linhas ({len(items)})")
        return {"zone": ZONE, "fetched": today or date.today().isoformat(), "items": items}
    data, state = fetch_with_cache("cmt_es_cigars", fetch)
    data = data or {"items": []}
    # histórico: um snapshot por data de recolha (acumula entre execuções via cache no repositório)
    snaps = cache_read("cmt_es_snapshots") or []
    if data["items"] and state == "ok":
        d = data.get("fetched") or (today or date.today().isoformat())
        snaps = [s for s in snaps if s["date"] != d] + [snapshot(data["items"], d)]
        snaps = sorted(snaps, key=lambda s: s["date"])[-104:]  # ~2 anos de execuções semanais
        cache_write("cmt_es_snapshots", snaps)
    data["snapshots"] = snaps
    return data, state.split(" ")[0].rstrip(":")


# ---------------------------------------------------------------------------
# Comparação França / Espanha

def compare_key(label: str) -> str:
    s = re.sub(r"\btubos?\b|\btube\b|\btubo\b|\(tube[^)]*\)|\bT\b", " tubo ", label, flags=re.I)
    s = re.sub(r"\((?:\d+\s*)?[ée]tuis?[^)]*\)|\(coffret\)|\(bo[iî]te\)|\bcoffret\b", " ", s, flags=re.I)
    s = re.sub(r"\bn[°ºo]\.?\s*", "no ", s, flags=re.I)
    return squash(s)


def compare_fr_es(fr_items: list[dict], es_items: list[dict]) -> list[dict]:
    def best(items):
        out = {}
        for it in items:
            if it.get("cigarillo") or it.get("sampler") or not it.get("unit_eur"):
                continue
            k = compare_key(it["label"])
            if k not in out or it["unit_eur"] < out[k]["unit_eur"]:
                out[k] = it
        return out
    fr, es = best(fr_items), best(es_items)
    rows = []
    for k in fr.keys() & es.keys():
        a, b = fr[k], es[k]
        label = min((a["label"], b["label"]), key=len)
        rows.append({"label": label, "fr_label": a["label"], "es_label": b["label"],
                     "brand": a.get("brand") or b.get("brand"), "fr": a["unit_eur"], "es": b["unit_eur"],
                     "diff_pct": round((b["unit_eur"] - a["unit_eur"]) / a["unit_eur"] * 100, 1)})
    return sorted(rows, key=lambda r: r["label"].lower())
