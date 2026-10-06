"""Orquestração: seed -> validação -> fontes abertas -> Parquet -> JSON do site."""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from datetime import datetime, timezone

from . import CLEAN_DIR, SITE_DATA_DIR, __version__
from .pairing import rules_doc, suggest
from .quality import build_report
from .seed import load_seed
from .sources.douane_fr import (french_catalog, history_for, link_seed, match_brands, price_history,
                                 price_key, removed_since)
from .sources.faostat import tobacco_production
from .sources.nasapower import climate_for_regions
from .sources.osm import shops_portugal
from .sources.wikidata import enrich_brands
from .sources.wikipedia import PAGE_URL, brand_catalog
from .transform import write_clean


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn" and ch.isalnum())


# Ponto de referência para conselhos de humidor (clima de casa).
HOME = {"id": "home-lisboa", "name": "Lisboa", "country": "Portugal", "lat": 38.72, "lng": -9.14}


MAX_PLAUSIBLE_PCT = 75.0


def _pct(a: float, b: float) -> float:
    return round((b - a) / a * 100, 1) if a else 0.0


def summarize_prices(items: list[dict], snaps: list[dict], removed: list[dict]) -> dict:
    """Maiores subidas/descidas, variação mediana por marca e retiradas."""
    import statistics
    changes = []
    for it in items:
        h = it.get("hist")
        if not h or it.get("cigarillo") or it.get("sampler"):
            continue
        changes.append({"label": it["label"], "brand": it.get("brand"), "pack_size": it.get("pack_size"),
                        "from": h[0][1], "to": h[-1][1], "since": h[0][0], "pct": _pct(h[0][1], h[-1][1])})
    by_brand: dict[str, list[float]] = {}
    for c in changes:
        if c["brand"]:
            by_brand.setdefault(c["brand"], []).append(c["pct"])
    brands = sorted(({"brand": b, "n": len(v), "median_pct": round(statistics.median(v), 1)}
                     for b, v in by_brand.items() if len(v) >= 5), key=lambda x: -x["median_pct"])
    # Variações enormes são quase sempre erros de origem (preço da embalagem posto como unitário).
    anomalies = [c for c in changes if abs(c["pct"]) > MAX_PLAUSIBLE_PCT]
    changes = [c for c in changes if abs(c["pct"]) <= MAX_PLAUSIBLE_PCT]
    by_brand = {}
    for c in changes:
        if c["brand"]:
            by_brand.setdefault(c["brand"], []).append(c["pct"])
    brands = sorted(({"brand": b, "n": len(v), "median_pct": round(statistics.median(v), 1)}
                     for b, v in by_brand.items() if len(v) >= 5), key=lambda x: -x["median_pct"])
    def dedup(xs):  # a mesma referência aparece em várias embalagens com a mesma variação
        seen, out = set(), []
        for c in xs:
            k = (c["label"].lower().split()[:6] and " ".join(c["label"].lower().split()), c["pct"])
            if k not in seen:
                seen.add(k); out.append(c)
        return out
    ups = dedup(sorted((c for c in changes if c["pct"] > 0), key=lambda c: -c["pct"]))
    downs = dedup(sorted((c for c in changes if c["pct"] < 0), key=lambda c: c["pct"]))
    return {
        "editions": [{"date": s["date"], "edition": s["edition"], "n": len(s["prices"])} for s in snaps],
        "n_changed": len(changes),
        "n_anomalies": len(anomalies),
        "median_pct": round(statistics.median([c["pct"] for c in changes]), 1) if changes else None,
        "up": ups[:40], "down": downs[:20], "brands": brands, "removed": removed,
        "source": "Douane française — nomenclature mensuelle des prix des tabacs",
    }


def build(verbose: bool = True) -> dict:
    log = (lambda *a: print(*a, file=sys.stderr)) if verbose else (lambda *a: None)

    regions, cigars = load_seed()
    log(f"seed ok: {len(cigars)} charutos, {len(regions)} regiões")

    wp, wp_status = brand_catalog()
    wp_brands = wp.get("brands", [])
    log(f"wikipedia: {wp_status} ({len(wp_brands)} marcas)")

    fr, fr_status = french_catalog()
    fr_items = fr.get("items", [])
    match_brands(fr_items, [b["brand"] for b in wp_brands] + [c.brand for c in cigars])
    fr_links = link_seed(fr_items, cigars)
    log(f"douane FR: {fr_status} ({len(fr_items)} referências, {len(fr_links)}/{len(cigars)} fichas ligadas) {fr.get('edition', '')}")

    snaps, hist_status = price_history(fr)
    hist = history_for(fr_items, snaps)
    for it in fr_items:
        h = hist.get(price_key(it))
        it["hist"] = h if h and len(h) > 1 else None
        it["first_seen"] = h[0][0] if h else None
    removed = removed_since(snaps)
    prices_summary = summarize_prices(fr_items, snaps, removed)
    log(f"histórico de preços: {hist_status} ({len(snaps)} edições, {prices_summary['n_changed']} referências com mudança, "
        f"{len(removed)} retiradas no último ano)")

    brand_facts, wd_status = enrich_brands([c.brand for c in cigars])
    log(f"wikidata: {wd_status} ({sum(1 for f in brand_facts.values() if f.get('found'))}/{len({c.brand for c in cigars})} marcas)")

    climate, cl_status = climate_for_regions([r.model_dump() for r in regions] + [HOME])
    home_climate = climate.pop(HOME["id"], None)
    log(f"nasa power: {cl_status} ({len(climate)}/{len(regions)} regiões)")

    tobacco, fao_status = tobacco_production()
    log(f"faostat: {fao_status} (ano {tobacco.get('latest_year')})")

    shops, osm_status = shops_portugal()
    log(f"osm: {osm_status} ({len(shops)} locais)")

    con = write_clean(regions, cigars, climate, brand_facts, CLEAN_DIR, wp_brands, tobacco, shops, fr_items)
    report = build_report(con)

    wp_index = {norm(b["brand"]): b for b in wp_brands}
    cigar_out = []
    for c in cigars:
        d = c.model_dump(mode="json")
        d["verifiedFields"] = d.pop("verified_fields")
        d["pairings"] = suggest(c.strength, c.wrapper)
        facts = brand_facts.get(c.brand)
        if facts and facts.get("found"):
            d["brandFacts"] = {k: facts.get(k) for k in ("qid", "url", "inception_year", "countries")}
        refs = fr_links.get(c.id)
        if refs:
            prices = [r["unit_eur"] for r in refs if r["unit_eur"]]
            d["priceFR"] = {"min": min(prices) if prices else None, "max": max(prices) if prices else None,
                            "edition": fr.get("edition"),
                            "hist": next((r["hist"] for r in refs if r.get("hist")), None),
                            "refs": [{k: r.get(k) for k in ("label", "pack_size", "unit_eur", "pack_eur")} for r in refs[:8]]}
        w = wp_index.get(norm(c.brand))
        if w:
            d["wikipedia"] = {"manufacturer": w["manufacturer"], "notes": w["notes"], "countries": w["countries"]}
        cigar_out.append(d)

    in_db = {norm(c.brand) for c in cigars}
    fr_by_brand: dict[str, list[float]] = {}
    for it in fr_items:
        if it.get("brand") and not it.get("cigarillo") and it.get("unit_eur"):
            fr_by_brand.setdefault(norm(it["brand"]), []).append(it["unit_eur"])
    catalog = []
    for b in wp_brands:
        p = fr_by_brand.get(norm(b["brand"]), [])
        catalog.append({**b, "inDb": norm(b["brand"]) in in_db,
                        "fr": {"n": len(p), "min": min(p), "max": max(p)} if p else None})

    region_out = [{**r.model_dump(), "climate": climate.get(r.id)} for r in regions]

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": __version__,
        "mode": os.environ.get("BOSSCIGAR_MODE", "auto"),
        "sources": {
            "seed": "ok",
            "wikipedia": wp_status,
            "wikidata": wd_status,
            "nasa_power": cl_status,
            "faostat": fao_status,
            "openstreetmap": osm_status,
            "douane_fr": fr_status,
            "douane_fr_historico": hist_status,
        },
        "douane_fr_edition": fr.get("edition"),
        "counts": {"cigars": len(cigars), "regions": len(regions), "brands_catalog": len(wp_brands),
                   "shops": len(shops),
                   "fr_references": len(fr_items)},
        "quality": {k: report[k] for k in ("verified_share", "cigars_with_verified_fields")},
        "licenses": [
            {"source": "Wikipédia — List of cigar brands", "license": "CC BY-SA 4.0", "url": PAGE_URL},
            {"source": "Wikidata", "license": "CC0", "url": "https://www.wikidata.org/"},
            {"source": "NASA POWER", "license": "Domínio público (NASA)", "url": "https://power.larc.nasa.gov/"},
            {"source": "FAOSTAT", "license": "CC BY 4.0", "url": "https://www.fao.org/faostat/"},
            {"source": "OpenStreetMap", "license": "ODbL", "url": "https://www.openstreetmap.org/copyright"},
            {"source": "Douane française — nomenclature des prix des tabacs", "license": "Informação pública reutilizável (CRPA art. L321-1), com menção da fonte",
             "url": "https://www.douane.gouv.fr/la-douane/opendata/categories/tabacs-manufactures"},
        ],
    }

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write = lambda name, obj: (SITE_DATA_DIR / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    write("cigars.json", {"meta": meta, "regions": region_out, "cigars": cigar_out, "pairingRules": rules_doc()})
    write("brands.json", {"source": PAGE_URL, "license": "CC BY-SA 4.0", "revid": wp.get("revid"), "brands": catalog})
    write("tobacco.json", tobacco)
    keys = ("label", "brand", "brand_source", "vitola", "length_in", "ring", "pack_size", "unit_eur", "pack_eur",
            "cigarillo", "sampler", "new", "supplier", "special", "hist", "first_seen")
    (SITE_DATA_DIR / "fr_catalog.json").write_text(json.dumps(
        {"edition": fr.get("edition"), "url": fr.get("url"), "fields": keys,
         "rows": [[it.get(k) for k in keys] for it in fr_items]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write("prices.json", prices_summary)
    write("home.json", {"place": HOME["name"], "climate": home_climate, "source": "NASA POWER"})
    write("shops.json", {"license": "ODbL — © OpenStreetMap contributors", "shops": shops})
    write("meta.json", meta)
    write("quality.json", report)
    log("exportado para site/data/")
    return meta
