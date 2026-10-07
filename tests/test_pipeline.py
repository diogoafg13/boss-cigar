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


# --- Histórico de preços e edições especiais --------------------------------

def test_edition_date():
    assert douane_fr.edition_date("Arrêté du 29 septembre 2026, applicable au 1er novembre 2026") == "2026-11-01"
    assert douane_fr.edition_date("Arrêté du 9 mai 2025") == "2025-05-09"
    assert douane_fr.edition_date("sem data") is None


def test_history_and_removed():
    items = _fr_items()["items"]
    old = douane_fr.snapshot({"edition": "Arrêté du 1 janvier 2026", "items": [
        {**i, "unit_eur": (i["unit_eur"] or 0) - 2} for i in items] + [
        {"label": "Velho Robusto", "pack_size": 10, "unit_eur": 9.0, "cigarillo": False}]})
    cur = douane_fr.snapshot({"edition": "Arrêté du 1 octobre 2026, applicable au 1er novembre 2026", "items": items})
    snaps = [old, cur]
    h = douane_fr.history_for(items, snaps)
    k = douane_fr.price_key(next(i for i in items if i["label"] == "Montecristo n°2"))
    assert h[k] == [["2026-01-01", 27.8], ["2026-11-01", 29.8]]
    removed = douane_fr.removed_since(snaps)
    assert [r["label"] for r in removed] == ["Velho Robusto"]


def test_special_editions():
    assert douane_fr.special_kind("Quai D'Orsay Clemenceau Edition Régionale 2020") == "Edição Regional"
    assert douane_fr.special_kind("Cohiba 55 Aniversario Edition Limitée 2021") == "Edição Limitada"
    assert douane_fr.special_kind("Davidoff Year of the Dragon (coffret)") == "Ano zodiacal chinês"
    assert douane_fr.special_kind("Montecristo n°2") is None


def test_price_summary_excludes_anomalies():
    from bosscigar.build import summarize_prices
    items = [
        {"label": "A Robusto", "brand": "A", "hist": [["2025-01-01", 10.0], ["2026-01-01", 11.0]]},
        {"label": "B Toro", "brand": "B", "hist": [["2025-01-01", 0.6], ["2026-01-01", 12.0]]},  # erro de origem
    ]
    s = summarize_prices(items, [{"date": "2025-01-01", "edition": "x", "prices": {}}], [])
    assert s["n_changed"] == 1 and s["n_anomalies"] == 1 and s["up"][0]["pct"] == 10.0


# --- Espanha (CMT), comparação e feed ----------------------------------------
from bosscigar.sources import cmt_es  # noqa: E402
from bosscigar import feed  # noqa: E402

ES_CSV = """Marca;Expendeduría Euros/Cajetilla;Con Recargo Euros/Cajetilla
COHIBA Robustos (25);80,5;92,6
MONTECRISTO Montecristo Nº 2 (10);25,8;29,65
MONTECRISTO Petit Nº 2 (25);18,3;21,05
3 TERCIOS Robusto 5 1/4x54 (20);3,6;4,15
ROMEO Y JULIETA Churchills Tubo (3);30;34,5
PARTAGAS Serie P Nº 2 Serie Sevilla (el envase de 21);577,5;664,1
A.FLORES A.Flores El Vinyet RC52 Robusto Clasico (10);8,5;9,8
"""


def test_cmt_parse():
    items = {i["label"]: i for i in cmt_es.parse_csv(ES_CSV)}
    assert items["Cohiba Robustos"]["brand"] == "Cohiba" and items["Cohiba Robustos"]["pack_size"] == 25
    assert items["Montecristo Nº 2"]["unit_eur"] == 25.8          # marca repetida no nome não duplica
    assert items["3 Tercios Robusto 5 1/4x54"]["brand"] == "3 Tercios"
    assert items["Romeo y Julieta Churchills Tubo"]["brand"] == "Romeo y Julieta"
    sev = items["Partagas Serie P Nº 2 Serie Sevilla"]
    assert sev["pack_eur"] == 577.5 and sev["unit_eur"] == 27.5      # "el envase de 21": preço do conjunto
    assert items["A.Flores El Vinyet RC52 Robusto Clasico"]["brand"] == "A.Flores"


def test_compare_fr_es():
    fr = douane_fr.parse_table(FR_ROWS)["items"]
    es = cmt_es.parse_csv(ES_CSV)
    rows = {r["label"]: r for r in cmt_es.compare_fr_es(fr, es)}
    mc = next(r for r in rows.values() if r["fr_label"] == "Montecristo n°2")
    assert (mc["fr"], mc["es"], mc["diff_pct"]) == (29.8, 25.8, -13.4)
    assert not any("Petit" in r["es_label"] and "n°2" in r["fr_label"] and "Petit" not in r["fr_label"] for r in rows.values())


def test_feed_diff_and_xml():
    prev = {"date": "2026-09-01", "prices": {"a|10": 10.0, "b|10": 5.0, "x|10": 1.0}, "labels": {"a|10": ["A Robusto", 10, False], "b|10": ["B Toro", 10, False], "x|10": ["X Corona", 10, False]}}
    cur = {"date": "2026-11-01", "prices": {"a|10": 11.0, "b|10": 4.5, "n|10": 7.0}, "labels": {"n|10": ["N Novo", 10, False]}}
    d = feed.diff_snapshots(prev, cur)
    assert [u["label"] for u in d["up"]] == ["A Robusto"] and d["down"][0]["pct"] == -10.0
    assert d["new"] == ["N Novo"] and d["removed"] == ["X Corona"]
    import xml.etree.ElementTree as ET
    root = ET.fromstring(feed.build_feed([prev, cur], []))
    assert len(root.findall("{http://www.w3.org/2005/Atom}entry")) == 1


# --- Vinhos portugueses -------------------------------------------------------
def test_pt_wines_rules():
    s = pairing.suggest(5, "Maduro")
    assert "Porto Vintage / LBV" in s["ptWines"] and "Madeira Malmsey" in s["ptWines"]
    assert "Moscatel de Setúbal" in pairing.suggest(3, "Cameroon")["ptWines"]
    assert pairing.suggest(None, "Cubano")["ptWines"] == ["Porto Tawny 10 anos"]


def test_history_keeps_each_seen_edition(tmp_path, monkeypatch):
    monkeypatch.setattr(douane_fr, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(douane_fr, "archive_urls", lambda: [])
    nov = {"edition": "Arrêté du 1 octobre 2026, applicable au 1er novembre 2026", "items": _fr_items()["items"]}
    snaps, _ = douane_fr.price_history(nov)
    assert [s["date"] for s in snaps] == ["2026-11-01"]
    dec_items = [{**i, "unit_eur": (i["unit_eur"] or 0) + 1} for i in _fr_items()["items"]]
    dec = {"edition": "Arrêté du 1 novembre 2026, applicable au 1er décembre 2026", "items": dec_items}
    snaps, _ = douane_fr.price_history(dec)
    assert [s["date"] for s in snaps] == ["2026-11-01", "2026-12-01"]  # novembro não se perde


def test_border_estancos_parse():
    from bosscigar.sources import cmt_estancos as c
    text = ("﻿Listado de expendedurías activas a 07 de octubre de 2026\n"
            "Estanco;Municipio;Localidad;Dirección\n"
            "360001;TUI;TUI;RUA AREAL 1\n"
            "060004;BADAJOZ;BADAJOZ;AV. RICARDO CARAPETO 100\n"
            "280001;MADRID;MADRID;GRAN VIA 1\n"
            "320010;VERÍN;VERIN;PLAZA MAYOR 2\n")
    d = c.parse(text)
    assert d["total_spain"] == 4 and "07 de octubre" in d["as_of"]
    by = {t["name"]: t for t in d["towns"]}
    assert len(by["Tui"]["estancos"]) == 1 and by["Tui"]["estancos"][0]["address"] == "RUA AREAL 1"
    assert len(by["Verín"]["estancos"]) == 1        # acentos no município
    assert all(t["lat"] and t["crossing"] for t in d["towns"])
