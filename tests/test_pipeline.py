import json

import pytest
from pydantic import ValidationError

from bosscigar import build as build_mod
from bosscigar.schema import Cigar
from bosscigar.seed import SeedError, load_seed
from bosscigar import pairing
from bosscigar.sources import faostat, http, nasapower, osm, wikidata, wikipedia

BASE = dict(id="x-y", brand="X", line="Y", country="Cuba", region="vuelta-abajo", strength=3,
            vitola="Robusto 5 x 50", wrapper="Cubano", flavors=["cedro"])


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


def test_nasapower_summarize():
    months = {m: 1.0 for m in nasapower.MONTHS}
    raw = {"properties": {"parameter": {
        "T2M": {**{m: 25.0 for m in nasapower.MONTHS}, "ANN": 25.0},
        "PRECTOTCORR": {**months, "ANN": 1.0},
        "RH2M": {**{m: 80.0 for m in nasapower.MONTHS}, "JAN": -999.0, "ANN": 78.0}}}}
    s = nasapower.summarize(raw)
    assert s["temp_c_annual"] == 25.0 and s["rh_pct_annual"] == 78.0
    assert s["rain_mm_monthly"][0] == 31  # 1 mm/dia x 31 dias
    assert s["rh_pct_monthly"][0] is None  # -999 = sem dados
    assert nasapower.summarize({}) == {}


def test_faostat_parse_and_summary():
    lines = [
        'Area Code,Area Code (M49),Area,Item Code,Item Code (CPC),Item,Element Code,Element,Year Code,Year,Unit,Value,Flag,Note',
        '"49","\'192","Cuba","826","\'01970","Unmanufactured tobacco","5510","Production","2023","2023","t","20000","A",',
        '"49","\'192","Cuba","826","\'01970","Unmanufactured tobacco","5312","Area harvested","2023","2023","ha","15000","A",',
        '"157","\'558","Nicaragua","826","\'01970","Unmanufactured tobacco","5510","Production","2023","2023","t","30000","A",',
        '"5000","\'001","World","826","\'01970","Unmanufactured tobacco","5510","Production","2023","2023","t","99","A",',
        '"49","\'192","Cuba","221","\'01371","Almonds","5510","Production","2023","2023","t","5","A",',
    ]
    data = faostat.parse_rows(lines)
    assert set(data) == {"Cuba", "Nicaragua"}  # agregados 'World'/'China' e outros itens excluídos
    s = faostat.summarize(data)
    assert s["latest_year"] == 2023 and s["world_t"] == 50000
    assert s["ranking"][0]["country"] == "Nicaragua" and s["ranking"][1]["area_ha"] == 15000
    assert s["latest_by_country"]["Cuba"] == {"year": 2023, "production_t": 20000.0}


WIKITEXT = """intro
{| class="wikitable sortable"
! Brand name
! Manufacturer
! Notes
! Source
|-
|  [[Cohiba]]
|  [[Habanos S.A.]]
|  Cuban brand; also a [[Dominican Republic|Dominican]] version made in the Dominican Republic<ref>x</ref>
|
|-
| ''Padrón''
| Padrón Cigars
| Made in [[Nicaragua]]
|
|}
outro"""


def test_wikipedia_parse_table():
    rows = wikipedia.parse_table(WIKITEXT)
    assert [r["brand"] for r in rows] == ["Cohiba", "Padrón"]
    assert rows[0]["manufacturer"] == "Habanos S.A."
    assert "<ref>" not in rows[0]["notes"]
    assert rows[0]["countries"] == ["República Dominicana"]  # "Cuban" não é "Cuba"
    assert rows[1]["countries"] == ["Nicarágua"]


def test_osm_parse_skips_unnamed():
    raw = {"elements": [
        {"type": "node", "id": 1, "lat": 38.7, "lon": -9.1, "tags": {"shop": "tobacco", "name": "Tabacaria X", "addr:city": "Lisboa"}},
        {"type": "way", "id": 2, "center": {"lat": 41.1, "lon": -8.6}, "tags": {"shop": "tobacco", "name": "Casa Y"}},
        {"type": "node", "id": 3, "lat": 40.0, "lon": -8.0, "tags": {"shop": "tobacco"}},
    ]}
    shops = osm.parse(raw)
    assert [s["name"] for s in shops] == ["Tabacaria X", "Casa Y"]
    assert shops[1]["osm"].endswith("/way/2")


def test_pairing_rules():
    strong = pairing.suggest(5, "Habano Oscuro")
    assert "Bourbon" in strong["drinks"] and "Porto Tawny 20 anos" in strong["drinks"]
    mild = pairing.suggest(1, "Connecticut Shade")
    assert "Café" in mild["drinks"] and "Bourbon" not in mild["drinks"]
    assert len(pairing.rules_doc()) == 5


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
    assert all("verifiedFields" in c and c["pairings"]["drinks"] for c in out["cigars"])
    assert (tmp_path / "clean" / "cigars.parquet").exists()
    q = json.loads((tmp_path / "site" / "quality.json").read_text(encoding="utf-8"))
    assert q["regions_without_climate"]  # sem cache, nenhuma região tem clima


# --- Douane FR -------------------------------------------------------------
from bosscigar.sources import douane_fr  # noqa: E402

FR_ROWS = [
    ["Arrêté du 29 septembre 2026, applicable au 1er novembre 2026", "", "", "", "", ""],
    ["FOURNISSEUR : LOGISTA France n°01", "", "", "", "", ""],
    ["FABRICANT : X", "", "", "", "", ""],
    ["Cigares et cigarillos", "", "", "", "", ""],
    ["Cohiba Robustos (5 étuis de 3), en 3 cigares", "", 82, 246, "Sans changement", "Sans changement"],
    ["Cohiba Siglo VI (tube - 5 étuis de 3), en 3 cigares", "", "", 351, "", "Sans changement"],
    ["Montecristo Petit n°2, en 25 cigares", "", 22.5, 562.5, "Sans changement", "Sans changement"],
    ["Montecristo n°2, en 25 cigares", "", 29.8, 745, "Sans changement", "Sans changement"],
    ["Alec Bradley Chunk XL, en 20 cigares", "", 10, 200, 10.5, 210],
    ["Alec Bradley Old LE, en 10 cigares", "", 29, 290, "Retrait", "Retrait"],
    ["", "Casa de Nicaragua Robusto, en 10 cigares", "", "", 5, 50],
    ["Davidoff mini cigarillos gold, en 20 cigares", "", "", 26, "", "Sans changement"],
    ["Eiroa Classique Robusto 50 x 5, en 20 cigares", "", 18, 360, "Sans changement", "Sans changement"],
    ["Cigarettes", "", "", "", "", ""],
    ["Marlboro, en 20 unités", "", 0.6, 12, "Sans changement", "Sans changement"],
]


def _fr_items():
    return douane_fr.parse_table(FR_ROWS)


def test_douane_parse_prices_and_sections():
    out = _fr_items()
    assert out["edition"].startswith("Arrêté du 29 septembre 2026")
    by = {i["label"]: i for i in out["items"]}
    assert "Marlboro" not in " ".join(by)                     # secção de cigarros fica de fora
    assert "Alec Bradley Old LE" not in by                     # "Retrait" excluído
    assert by["Alec Bradley Chunk XL"]["unit_eur"] == 10.5     # preço novo prevalece
    assert by["Cohiba Robustos (5 étuis de 3)"]["pack_size"] == 3  # vende-se o estojo de 3
    assert by["Cohiba Siglo VI (tube - 5 étuis de 3)"]["unit_eur"] == 117.0  # 351 / 3
    assert by["Casa de Nicaragua Robusto"]["new"] is True
    assert by["Davidoff mini cigarillos gold"]["cigarillo"] is True
    e = by["Eiroa Classique Robusto 50 x 5"]
    assert (e["vitola"], e["length_in"], e["ring"]) == ("Robusto", 5.0, 50)


def test_douane_brand_match_and_inference():
    items = _fr_items()["items"] + [{"label": f"Eiroa Linha {i}", "cigarillo": False} for i in range(2)]
    douane_fr.match_brands(items, ["Cohiba", "Montecristo", "Davidoff", "H. Upmann"])
    by = {i["label"]: i for i in items}
    assert by["Cohiba Robustos (5 étuis de 3)"]["brand"] == "Cohiba"
    assert by["Cohiba Robustos (5 étuis de 3)"]["brand_source"] == "catálogo"
    assert by["Eiroa Classique Robusto 50 x 5"]["brand"] == "Eiroa"     # 3 referências -> inferida
    assert by["Eiroa Classique Robusto 50 x 5"]["brand_source"] == "inferida"
    assert by["Alec Bradley Chunk XL"]["brand"] is None                 # só 1 referência: não infere
    hu = [{"label": "H.Upmann Magnum 50", "cigarillo": False}]
    douane_fr.match_brands(hu, ["H. Upmann"])
    assert hu[0]["brand"] == "H. Upmann"


def test_douane_link_seed_is_anchored():
    items = _fr_items()["items"]
    douane_fr.match_brands(items, ["Montecristo", "Cohiba"])
    seed = [Cigar(**{**BASE, "id": "mc2", "brand": "Montecristo", "line": "No. 2"}),
            Cigar(**{**BASE, "id": "cr", "brand": "Cohiba", "line": "Robusto"})]
    links = douane_fr.link_seed(items, seed)
    assert [i["label"] for i in links["mc2"]] == ["Montecristo n°2"]   # não apanha "Petit n°2"
    assert links["cr"][0]["label"].startswith("Cohiba Robustos")       # plural tolerado
