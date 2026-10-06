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
from .sources.douane_fr import french_catalog, link_seed, match_brands
from .sources.faostat import tobacco_production
from .sources.nasapower import climate_for_regions
from .sources.osm import shops_portugal
from .sources.wikidata import enrich_brands
from .sources.wikipedia import PAGE_URL, brand_catalog
from .transform import write_clean


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn" and ch.isalnum())


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

    brand_facts, wd_status = enrich_brands([c.brand for c in cigars])
    log(f"wikidata: {wd_status} ({sum(1 for f in brand_facts.values() if f.get('found'))}/{len({c.brand for c in cigars})} marcas)")

    climate, cl_status = climate_for_regions([r.model_dump() for r in regions])
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
            "cigarillo", "sampler", "new", "supplier")
    (SITE_DATA_DIR / "fr_catalog.json").write_text(json.dumps(
        {"edition": fr.get("edition"), "url": fr.get("url"), "fields": keys,
         "rows": [[it.get(k) for k in keys] for it in fr_items]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write("shops.json", {"license": "ODbL — © OpenStreetMap contributors", "shops": shops})
    write("meta.json", meta)
    write("quality.json", report)
    log("exportado para site/data/")
    return meta
