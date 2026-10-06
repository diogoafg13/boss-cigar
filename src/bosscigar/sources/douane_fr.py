"""Nomenclatura oficial de preços dos tabacos em França (douane.gouv.fr).

A Direção-Geral das Alfândegas publica todos os meses, em ODS, a lista homologada
de todos os tabacos à venda em França continental (arrêté publicado no JORF).
A secção "Cigares et cigarillos" tem milhares de referências com nome comercial,
quantidade por embalagem e preço oficial de venda ao público.

Reutilização: informação pública (Code des relations entre le public et
l'administration, art. L321-1 e seg.), com menção da fonte e da data.

A página de listagem bloqueia pedidos automáticos a partir de alguns IPs. Por isso:
1. tenta descobrir o .ods mais recente na página de dados abertos;
2. senão usa o URL em data/seed/sources.yml (atualizável à mão ou por PR);
3. senão usa a cache.
"""
from __future__ import annotations

import io
import re
import unicodedata

import requests
import yaml

from .. import SEED_DIR, USER_AGENT
from .http import SourceError, fetch_with_cache

LISTING = "https://www.douane.gouv.fr/la-douane/opendata/categories/tabacs-manufactures"
BASE = "https://www.douane.gouv.fr"
SECTION = "Cigares et cigarillos"
OTHER_SECTIONS = ("Cigarettes", "Tabac", "Tabacs", "Autres tabacs")

VITOLAS = [  # mais específico primeiro
    "Double Corona", "Petit Corona", "Corona Gorda", "Gran Corona", "Corona Extra", "Half Corona",
    "Petit Robusto", "Short Robusto", "Robusto Extra", "Double Robusto", "Super Robusto",
    "Gran Toro", "Short Churchill", "Petit Churchill",
    "Robusto", "Churchill", "Corona", "Toro", "Torpedo", "Belicoso", "Piramide", "Pirámide", "Lancero",
    "Panetela", "Panatela", "Lonsdale", "Gordo", "Gordito", "Perfecto", "Figurado", "Culebra",
    "Julieta", "Laguito", "Salomon", "Salomón", "Diadema", "Presidente", "Rothschild", "Corona",
]
SAMPLER = re.compile(r"\b(s[ée]lection|collection|sampler|assortiment|d[ée]gustation|vari[ée]t)", re.I)
CIGARILLO = re.compile(r"\b(cigarillos?|mini|club|puritos?|filter|filtre|sweets?|aromatic|vanill?a|cherry)\b", re.I)
SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:\"|''|pouces?)?\s*[x×X]\s*(\d{2})(?!\d)")
SIZE_REV = re.compile(r"\b(\d{2})\s*[x×X]\s*(\d(?:[.,]\d+)?)\b")  # ex.: "44 x 5"
PACK_END = re.compile(r"(?:en|de)\s+(?:bo[iî]te\s+de\s+|coffret\s+de\s+)?(\d+)\s*(?:cigares?|unit[ée]s?)?\s*$", re.I)
PACK = re.compile(r"(?:en|de)\s+(?:bo[iî]te\s+de\s+|coffret\s+de\s+|étui\s+de\s+)?(\d+)\s*(?:cigares?|unit[ée]s?)?", re.I)


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def configured_url() -> str | None:
    p = SEED_DIR / "sources.yml"
    if p.exists():
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("douane_fr_ods")
    return None


def discover_url() -> str | None:
    try:
        r = requests.get(LISTING, timeout=30, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
    except requests.RequestException:
        return None
    links = re.findall(r'href="([^"]+?Maquette[^"]+?\.ods)"', r.text)
    if not links:
        return None
    # a página lista o mais recente primeiro; o caminho tem /AAAA-MM/DD/
    links.sort(key=lambda u: re.search(r"/(\d{4}-\d{2})/(\d{2})/", u).groups() if re.search(r"/(\d{4}-\d{2})/(\d{2})/", u) else ("", ""), reverse=True)
    u = links[0]
    return u if u.startswith("http") else BASE + u


def parse_table(rows: list[list]) -> dict:
    """rows: linhas da folha (6 colunas). Devolve {'edition': str, 'items': [...]}."""
    edition = str(rows[0][0]).strip() if rows and rows[0] else ""
    supplier = maker = None
    in_cigars = False
    items = []
    for r in rows:
        r = (list(r) + [""] * 6)[:6]
        a, new_label = str(r[0] or "").strip(), str(r[1] or "").strip()
        if a.startswith("FOURNISSEUR"):
            supplier = a.split(":", 1)[1].strip(); in_cigars = False; continue
        if a.startswith("FABRICANT"):
            maker = a.split(":", 1)[1].strip(); in_cigars = False; continue
        if a == SECTION:
            in_cigars = True; continue
        if a.startswith(OTHER_SECTIONS) and not new_label and _num(r[2]) is None and _num(r[3]) is None:
            in_cigars = False; continue
        if not in_cigars:
            continue
        name = new_label or a
        if not name:
            continue
        status_u, status_p = str(r[4]).strip(), str(r[5]).strip()
        if status_u == "Retrait" or status_p == "Retrait":
            continue
        unit = _num(r[4]) if _num(r[4]) is not None else _num(r[2])
        pack_price = _num(r[5]) if _num(r[5]) is not None else _num(r[3])
        if unit is None and pack_price is None:
            continue
        items.append(_enrich({"name": name, "supplier": supplier, "maker": maker,
                              "unit_eur": unit, "pack_eur": pack_price,
                              "new": bool(new_label) and not a}))
    return {"edition": edition, "items": items}


def _enrich(it: dict) -> dict:
    name = it["name"]
    # a embalagem vendida é o "en N cigares" do fim ("(5 étuis de 3), en 3 cigares" = estojo de 3)
    m = PACK_END.search(name) or PACK.search(name)
    n = int(m.group(1)) if m else None
    it["pack_size"] = n if n and 0 < n <= 500 else None
    if it["unit_eur"] is None and it["pack_eur"] and it["pack_size"]:
        it["unit_eur"] = round(it["pack_eur"] / it["pack_size"], 2)
    low = name.lower()
    it["vitola"] = next((v for v in VITOLAS if v.lower() in low), None)
    s = SIZE.search(name)
    if s:
        it["length_in"], it["ring"] = float(s.group(1).replace(",", ".")), int(s.group(2))
    else:
        s = SIZE_REV.search(name)
        if s and 30 <= int(s.group(1)) <= 70:
            it["length_in"], it["ring"] = float(s.group(2).replace(",", ".")), int(s.group(1))
    it["sampler"] = bool(SAMPLER.search(name))
    # cigarilha: pelo nome ou preço unitário muito baixo (heurística assinalada no site)
    it["cigarillo"] = bool(CIGARILLO.search(name)) or (it["unit_eur"] is not None and it["unit_eur"] < 1.5)
    it["label"] = re.sub(r",?\s*(en|de)\s+(bo[iî]te\s+de\s+|coffret\s+de\s+)?\d+\s*(cigares?|unit[ée]s?)?\s*$", "", name, flags=re.I).strip(" ,")
    return it


def read_ods(content: bytes) -> list[list]:
    import pandas as pd  # import tardio: pandas+odfpy só são precisos aqui
    df = pd.read_excel(io.BytesIO(content), engine="odf", header=None, sheet_name=0).fillna("")
    return df.values.tolist()


def fetch() -> dict:
    url = discover_url() or configured_url()
    if not url:
        raise SourceError("sem URL do ODS (descoberta falhou e data/seed/sources.yml não tem douane_fr_ods)")
    r = requests.get(url, timeout=90, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    out = parse_table(read_ods(r.content))
    out["url"] = url
    return out


def norm(s: str) -> str:
    s = re.sub(r"\bn\s*[°º]\s*|\bno\.\s*|\bnum(?:ero|ber)?\.?\s*", "no ", s.lower())
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch if (ch.isalnum() or ch == " ") else " " for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def squash(s: str) -> str:
    return norm(s).replace(" ", "")


# Primeiras palavras genéricas: a marca inferida usa então as duas primeiras palavras.
GENERIC = {"el", "la", "las", "los", "le", "les", "don", "dona", "casa", "flor", "san", "santa", "new", "a",
           "the", "black", "gran", "grand", "vegas", "de", "del", "royal", "old", "gold", "golden", "red", "blue"}


def match_brands(items: list[dict], brands: list[str], min_inferred: int = 3) -> None:
    """1) marca conhecida pelo prefixo mais longo (sem pontos/espaços: 'H.Upmann' = 'H. Upmann');
    2) senão marca inferida: prefixo de 1-2 palavras partilhado por >= min_inferred referências."""
    keys = sorted({(squash(b), b) for b in brands if b and len(squash(b)) >= 3}, key=lambda t: -len(t[0]))
    for it in items:
        toks = norm(it["label"]).split()
        it["brand"], it["brand_source"] = None, None
        # testa prefixos de palavras completas, do mais longo para o mais curto
        prefixes = {"".join(toks[:i]): i for i in range(len(toks), 0, -1)}
        for k, b in keys:
            if k in prefixes:
                it["brand"], it["brand_source"] = b, "catálogo"
                break
    groups: dict[str, list] = {}
    for it in items:
        if it["brand"]:
            continue
        words = [w.strip(",;:()\"'") for w in re.split(r"[\s–\-]+", it["label"])]
        words = [w for w in words if w]
        if not words:
            continue
        n = 1
        if (norm(words[0]) in GENERIC or len(norm(words[0])) < 3) and len(words) > 1:
            n = 2
        if n == 2 and norm(words[1]) in {"de", "del", "y"} and len(words) > 2:
            n = 3  # "Flor de Selva", "Vegas de Santiago"
        if any(ch.isdigit() for ch in words[0]):
            continue  # "03 robusto": não é marca
        groups.setdefault(norm(" ".join(words[:n])), []).append((it, " ".join(words[:n])))
    for key, members in groups.items():
        if len(members) < min_inferred or len(key) < 3:
            continue
        forms = {}
        for _, f in members:
            forms[f] = forms.get(f, 0) + 1
        best = max(forms, key=lambda f: (forms[f], f != f.upper()))  # forma mais comum, preferindo não-maiúsculas
        best = best.title() if best.isupper() and len(best) > 4 else best
        for it, _ in members:
            it["brand"], it["brand_source"] = best, "inferida"


STOP = {"de", "la", "el", "y", "the", "by", "cigars", "cigar", "serie", "series", "edicion", "edition", "original"}


def _tokens(s: str) -> list[str]:
    # singular simples ('Churchills' = 'Churchill', 'Robustos' = 'Robusto')
    return [t[:-1] if len(t) > 4 and t.endswith("s") else t for t in norm(s).split() if t not in STOP]


def _starts_with(toks: list[str], phrase: list[str]) -> int | None:
    """Se toks começa por phrase (comparando sem espaços: 'Opus X' = 'OpusX'), devolve quantos tokens consumiu."""
    target, acc = "".join(phrase), ""
    for i, t in enumerate(toks):
        acc += t
        if acc == target:
            return i + 1
        if not target.startswith(acc):
            return None
    return None


def link_seed(items: list[dict], cigars: list) -> dict[str, list[dict]]:
    """Referências francesas de cada charuto do seed: o nome tem de começar pela marca e continuar
    logo com a linha (evita 'Montecristo No. 2' -> 'Montecristo Petit n°2'). Aceita o nome sem a
    marca quando a linha é distintiva (>= 2 palavras, ex.: 'Liga Privada N°9')."""
    out: dict[str, list[dict]] = {}
    for c in cigars:
        brand, line = _tokens(c.brand), _tokens(c.line)
        if not line:
            continue
        hits, seen = [], set()
        for it in items:
            if it.get("cigarillo"):
                continue
            toks = _tokens(it["label"])
            k = _starts_with(toks, brand)
            ok = (k is not None and _starts_with(toks[k:], line) is not None) or \
                 (len(line) >= 3 and _starts_with(toks, line) is not None)
            if ok:
                key = (it["label"].lower(), it["unit_eur"], it["pack_size"])
                if key not in seen:
                    seen.add(key); hits.append(it)
        if hits:
            out[c.id] = sorted(hits, key=lambda x: (x["unit_eur"] or 1e9))
    return out


def french_catalog() -> tuple[dict, str]:
    data, state = fetch_with_cache("douane_fr_cigars", fetch)
    return data or {"items": []}, state.split(" ")[0].rstrip(":")
