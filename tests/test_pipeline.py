import json

import pytest
from pydantic import ValidationError

from bosscigar import build as build_mod
from bosscigar.schema import Cigar
from bosscigar.seed import SeedError, load_seed
from bosscigar.sources import http, openmeteo, wikidata

BASE = dict(id="x-y", brand="X", line="Y", country="Cuba", region="vuelta-abajo", strength=3,
            vitola="Robusto 5 x 50", wrapper="Cubano", flavors=["cedro"],
            pairings={"drinks": ["Rum"], "food": []})


def test_real_seed_is_valid():
    regions, cigars = load_seed()
    assert len(cigars) >= 20
    assert {c.region for c in cigars} <= {r.id for r in regions}


def test_verified_fields_require_sources():
    with pytest.raises(ValidationError):
        Cigar(**BASE, verified_fields=["wrapper"])
    ok = Cigar(**BASE, verified_fields=["wrapper"], sources=[{"title": "t", "url": "https://example.com/a"}])
    assert ok.verified_fields == ["wrapper"]


def test_unknown_verified_field_rejected():
    with pytest.raises(ValidationError):
        Cigar(**BASE, verified_fields=["preco"], sources=[{"title": "t", "url": "https://example.com/a"}])


def test_strength_range():
    with pytest.raises(ValidationError):
        Cigar(**{**BASE, "strength": 6})


def test_seed_rejects_unknown_region(tmp_path):
    (tmp_path / "regions.yml").write_text(
        "- {id: a, name: A, country: C, lat: 1, lng: 1, note: n}\n", encoding="utf-8")
    bad = {**BASE, "region": "nope"}
    import yaml
    (tmp_path / "cigars.yml").write_text(yaml.safe_dump([bad]), encoding="utf-8")
    with pytest.raises(SeedError):
        load_seed(tmp_path)


def test_openmeteo_summarize():
    dates = [f"2020-{m:02d}-15" for m in range(1, 13)]
    daily = {"daily": {"time": dates, "temperature_2m_mean": [20.0] * 12, "precipitation_sum": [10.0] * 12}}
    s = openmeteo.summarize(daily)
    assert s["temp_c_annual"] == 20.0
    assert s["rain_mm_annual"] == 120.0
    assert openmeteo.summarize({"daily": {"time": [], "temperature_2m_mean": [], "precipitation_sum": []}}) == {}


def test_wikidata_lookup_filters_non_cigar_hits(monkeypatch):
    monkeypatch.setattr(wikidata, "_search_brand", lambda b: [
        {"id": "Q1", "description": "family name"},
        {"id": "Q2", "description": "Swiss brand of cigars"},
    ])
    ent = {"Q2": {"labels": {"en": {"value": "Davidoff"}}, "descriptions": {"en": {"value": "brand"}},
                  "claims": {"P571": [{"mainsnak": {"datavalue": {"value": {"time": "+1875-00-00T00:00:00Z"}}}}],
                             "P495": [{"mainsnak": {"datavalue": {"value": {"id": "Q39"}}}}]}},
           "Q39": {"labels": {"pt": {"value": "Suíça"}}}}
    monkeypatch.setattr(wikidata, "_entities", lambda ids: {i: ent[i] for i in ids if i in ent})
    r = wikidata.lookup_brand("Davidoff")
    assert r["found"] and r["qid"] == "Q2" and r["inception_year"] == 1875 and r["countries"] == ["Suíça"]


def test_wikidata_not_found(monkeypatch):
    monkeypatch.setattr(wikidata, "_search_brand", lambda b: [{"id": "Q1", "description": "family name"}])
    assert wikidata.lookup_brand("Padrón") == {"found": False}


def test_fetch_with_cache_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("BOSSCIGAR_MODE", "auto")
    data, state = http.fetch_with_cache("t", lambda: {"a": 1})
    assert (data, state) == ({"a": 1}, "ok")

    def boom():
        raise RuntimeError("sem rede")
    data, state = http.fetch_with_cache("t", boom)
    assert data == {"a": 1} and state.startswith("CACHE")
    data, state = http.fetch_with_cache("outro", boom)
    assert data is None and state.startswith("ERRO")


def test_build_offline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSSCIGAR_MODE", "offline")
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(build_mod, "CLEAN_DIR", tmp_path / "clean")
    monkeypatch.setattr(build_mod, "SITE_DATA_DIR", tmp_path / "site")
    meta = build_mod.build(verbose=False)
    assert meta["sources"]["seed"] == "ok"
    assert meta["sources"]["wikidata"] == "ERRO"  # sem cache em modo offline
    out = json.loads((tmp_path / "site" / "cigars.json").read_text(encoding="utf-8"))
    assert len(out["cigars"]) == meta["counts"]["cigars"]
    assert all("verifiedFields" in c for c in out["cigars"])
    assert (tmp_path / "clean" / "cigars.parquet").exists()
    q = json.loads((tmp_path / "site" / "quality.json").read_text(encoding="utf-8"))
    assert q["regions_without_climate"]  # sem cache, nenhuma região tem clima
