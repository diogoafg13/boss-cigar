"""Camada limpa: Parquet + DuckDB (como no imobAI)."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from . import CLEAN_DIR
from .pairing import suggest
from .schema import Cigar, Region


def _insert(con: duckdb.DuckDBPyConnection, sql: str, rows: list) -> None:
    """executemany rebenta com listas vazias (ex.: fonte indisponível sem cache)."""
    if rows:
        con.executemany(sql, rows)


def write_clean(regions: list[Region], cigars: list[Cigar], climate: dict, brand_facts: dict,
                out_dir: Path = CLEAN_DIR, wp_brands: list[dict] | None = None,
                tobacco: dict | None = None, shops: list[dict] | None = None) -> duckdb.DuckDBPyConnection:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    con.execute("CREATE TABLE regions(id VARCHAR, name VARCHAR, country VARCHAR, lat DOUBLE, lng DOUBLE, note VARCHAR)")
    _insert(con, "INSERT INTO regions VALUES (?,?,?,?,?,?)",
            [(r.id, r.name, r.country, r.lat, r.lng, r.note) for r in regions])

    con.execute("""CREATE TABLE cigars(id VARCHAR, brand VARCHAR, line VARCHAR, country VARCHAR, region VARCHAR,
                   strength INTEGER, vitola VARCHAR, wrapper VARCHAR, notes VARCHAR, n_verified INTEGER, n_sources INTEGER)""")
    _insert(con, "INSERT INTO cigars VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(c.id, c.brand, c.line, c.country, c.region, c.strength, c.vitola, c.wrapper, c.notes,
              len(c.verified_fields), len(c.sources)) for c in cigars])

    con.execute("CREATE TABLE cigar_flavors(cigar_id VARCHAR, flavor VARCHAR)")
    _insert(con, "INSERT INTO cigar_flavors VALUES (?,?)", [(c.id, f) for c in cigars for f in c.flavors])

    con.execute("CREATE TABLE cigar_pairings(cigar_id VARCHAR, kind VARCHAR, item VARCHAR)")
    rows = []
    for c in cigars:
        s = suggest(c.strength, c.wrapper)
        rows += [(c.id, "drink", d) for d in s["drinks"]] + [(c.id, "food", f) for f in s["food"]]
    _insert(con, "INSERT INTO cigar_pairings VALUES (?,?,?)", rows)

    con.execute("CREATE TABLE climate(region_id VARCHAR, temp_c_annual DOUBLE, rain_mm_annual DOUBLE, rh_pct_annual DOUBLE, "
                "temp_c_monthly VARCHAR, rain_mm_monthly VARCHAR, rh_pct_monthly VARCHAR)")
    _insert(con, "INSERT INTO climate VALUES (?,?,?,?,?,?,?)",
            [(rid, v.get("temp_c_annual"), v.get("rain_mm_annual"), v.get("rh_pct_annual"),
              json.dumps(v.get("temp_c_monthly")), json.dumps(v.get("rain_mm_monthly")), json.dumps(v.get("rh_pct_monthly")))
             for rid, v in climate.items()])

    con.execute("CREATE TABLE brand_facts(brand VARCHAR, qid VARCHAR, inception_year INTEGER, countries VARCHAR, url VARCHAR)")
    _insert(con, "INSERT INTO brand_facts VALUES (?,?,?,?,?)",
            [(b, f.get("qid"), f.get("inception_year"), json.dumps(f.get("countries", []), ensure_ascii=False), f.get("url"))
             for b, f in brand_facts.items() if f.get("found")])

    con.execute("CREATE TABLE wp_brands(brand VARCHAR, manufacturer VARCHAR, notes VARCHAR, countries VARCHAR)")
    _insert(con, "INSERT INTO wp_brands VALUES (?,?,?,?)",
            [(b["brand"], b["manufacturer"], b["notes"], json.dumps(b["countries"], ensure_ascii=False)) for b in (wp_brands or [])])

    con.execute("CREATE TABLE tobacco_production(country VARCHAR, year INTEGER, production_t DOUBLE)")
    _insert(con, "INSERT INTO tobacco_production VALUES (?,?,?)",
            [(country, int(y), v) for country, s in (tobacco or {}).get("series", {}).items() for y, v in s.items() if v is not None])

    con.execute("CREATE TABLE shops(name VARCHAR, kind VARCHAR, lat DOUBLE, lng DOUBLE, city VARCHAR, osm VARCHAR)")
    _insert(con, "INSERT INTO shops VALUES (?,?,?,?,?,?)",
            [(s["name"], s["kind"], s["lat"], s["lng"], s["city"], s["osm"]) for s in (shops or [])])

    for table in ("regions", "cigars", "cigar_flavors", "cigar_pairings", "climate", "brand_facts",
                  "wp_brands", "tobacco_production", "shops"):
        con.execute(f"COPY {table} TO '{out_dir / (table + '.parquet')}' (FORMAT PARQUET)")
    return con
