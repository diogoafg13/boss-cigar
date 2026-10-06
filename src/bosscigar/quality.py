"""Relatório de qualidade dos dados, calculado em SQL sobre o DuckDB."""
from __future__ import annotations

import json

import duckdb


def _norm(s: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(ch) != "Mn")


def build_report(con: duckdb.DuckDBPyConnection) -> dict:
    q = lambda sql: con.execute(sql).fetchall()
    n_cigars = q("SELECT count(*) FROM cigars")[0][0]
    n_verified = q("SELECT count(*) FROM cigars WHERE n_verified > 0")[0][0]

    empty_regions = [r[0] for r in q(
        "SELECT r.id FROM regions r LEFT JOIN cigars c ON c.region = r.id WHERE c.id IS NULL ORDER BY 1")]
    no_climate = [r[0] for r in q(
        "SELECT r.id FROM regions r LEFT JOIN climate c ON c.region_id = r.id WHERE c.region_id IS NULL ORDER BY 1")]
    no_wikidata = [r[0] for r in q(
        "SELECT DISTINCT c.brand FROM cigars c LEFT JOIN brand_facts b ON b.brand = c.brand WHERE b.brand IS NULL ORDER BY 1")]
    strength_dist = {int(k): v for k, v in q("SELECT strength, count(*) FROM cigars GROUP BY 1 ORDER BY 1")}
    unverified = [r[0] for r in q("SELECT id FROM cigars WHERE n_verified = 0 ORDER BY 1")]
    thin = [r[0] for r in q(
        "SELECT c.id FROM cigars c LEFT JOIN cigar_flavors f ON f.cigar_id = c.id GROUP BY c.id HAVING count(f.flavor) < 3 ORDER BY 1")]

    mismatches = []
    for cigar_id, country, brand, countries in q(
            "SELECT c.id, c.country, c.brand, b.countries FROM cigars c JOIN brand_facts b ON b.brand = c.brand"):
        wd = json.loads(countries or "[]")
        if wd and _norm(country) not in {_norm(x) for x in wd}:
            mismatches.append({"id": cigar_id, "seed": country, "wikidata": wd})

    n_wp = q("SELECT count(*) FROM wp_brands")[0][0]
    missing_in_wp = [r[0] for r in q(
        "SELECT DISTINCT c.brand FROM cigars c WHERE NOT EXISTS (SELECT 1 FROM wp_brands w "
        "WHERE lower(strip_accents(w.brand)) = lower(strip_accents(c.brand))) ORDER BY 1")] if n_wp else []

    fr_total, fr_cig, fr_brand_cat, fr_brand_inf, fr_bad = q(
        "SELECT count(*), count(*) FILTER (WHERE NOT cigarillo), "
        "count(*) FILTER (WHERE NOT cigarillo AND brand_source = 'catálogo'), "
        "count(*) FILTER (WHERE NOT cigarillo AND brand_source = 'inferida'), "
        "count(*) FILTER (WHERE pack_size > 0 AND unit_eur IS NOT NULL AND pack_eur IS NOT NULL "
        "AND abs(unit_eur * pack_size - pack_eur) > 0.06 * pack_eur) FROM fr_cigars")[0]

    return {
        "cigars": n_cigars,
        "fr_references": fr_total,
        "fr_cigars_excluding_cigarillos": fr_cig,
        "fr_brand_from_catalog": fr_brand_cat,
        "fr_brand_inferred": fr_brand_inf,
        "fr_price_inconsistencies": fr_bad,
        "brands_in_open_catalog": n_wp,
        "brands_not_in_wikipedia_list": missing_in_wp,
        "shops_pt": q("SELECT count(*) FROM shops")[0][0],
        "tobacco_countries": q("SELECT count(DISTINCT country) FROM tobacco_production")[0][0],
        "regions": q("SELECT count(*) FROM regions")[0][0],
        "verified_share": round(n_verified / n_cigars, 3) if n_cigars else 0,
        "cigars_with_verified_fields": n_verified,
        "strength_distribution": strength_dist,
        "regions_without_cigars": empty_regions,
        "regions_without_climate": no_climate,
        "brands_without_wikidata": no_wikidata,
        "cigars_with_fewer_than_3_flavors": thin,
        "country_mismatch_vs_wikidata": mismatches,
        "unverified_cigars": unverified,
    }
