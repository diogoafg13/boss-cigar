"""Orquestração: seed -> validação -> fontes abertas -> Parquet -> JSON do site."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from . import CLEAN_DIR, SITE_DATA_DIR, __version__
from .quality import build_report
from .seed import load_seed
from .sources.openmeteo import climate_for_regions
from .sources.wikidata import enrich_brands
from .transform import write_clean


def build(verbose: bool = True) -> dict:
    log = (lambda *a: print(*a, file=sys.stderr)) if verbose else (lambda *a: None)

    regions, cigars = load_seed()
    log(f"seed ok: {len(cigars)} charutos, {len(regions)} regiões")

    brand_facts, wd_status = enrich_brands([c.brand for c in cigars])
    log(f"wikidata: {wd_status} ({sum(1 for f in brand_facts.values() if f.get('found'))}/{len({c.brand for c in cigars})} marcas)")

    climate, om_status = climate_for_regions([r.model_dump() for r in regions])
    log(f"open-meteo: {om_status} ({len(climate)}/{len(regions)} regiões)")

    con = write_clean(regions, cigars, climate, brand_facts, CLEAN_DIR)
    report = build_report(con)

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    region_out = []
    for r in regions:
        d = r.model_dump()
        d["climate"] = climate.get(r.id)
        region_out.append(d)

    cigar_out = []
    for c in cigars:
        d = c.model_dump(mode="json")
        d["verifiedFields"] = d.pop("verified_fields")
        facts = brand_facts.get(c.brand)
        if facts and facts.get("found"):
            d["brandFacts"] = {k: facts.get(k) for k in ("qid", "url", "inception_year", "countries")}
        cigar_out.append(d)

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": __version__,
        "mode": os.environ.get("BOSSCIGAR_MODE", "auto"),
        "sources": {
            "seed": "ok",
            "wikidata": wd_status,
            "open_meteo": om_status,
        },
        "counts": {"cigars": len(cigars), "regions": len(regions)},
        "quality": {k: report[k] for k in ("verified_share", "cigars_with_verified_fields")},
        "attribution": [
            "Dados de marcas: Wikidata (CC0)",
            "Clima: Open-Meteo (CC BY 4.0)",
            "Mapa: © OpenStreetMap contributors",
        ],
    }

    (SITE_DATA_DIR / "cigars.json").write_text(
        json.dumps({"meta": meta, "regions": region_out, "cigars": cigar_out}, ensure_ascii=False, indent=1), encoding="utf-8")
    (SITE_DATA_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (SITE_DATA_DIR / "quality.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log("exportado para site/data/")
    return meta
