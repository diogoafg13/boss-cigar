"""Feed Atom de novidades de preços (França por edição; Espanha por recolha)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from xml.sax.saxutils import escape


def site_url() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "diogoafg13/boss-cigar")
    owner, name = repo.split("/", 1)
    return f"https://{owner}.github.io/{name}/"


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:,.2f} €".replace(",", " ").replace(".", ",")


def diff_snapshots(prev: dict, cur: dict, labels: dict | None = None, max_pct: float = 75.0) -> dict:
    """Mudanças entre duas edições: subidas, descidas, novas e retiradas (chaves 'nome|embalagem')."""
    labels = labels or {}
    name = lambda k: (cur.get("labels", {}).get(k) or prev.get("labels", {}).get(k) or [labels.get(k) or k.split("|")[0]])[0]
    up, down = [], []
    for k, v in cur["prices"].items():
        old = prev["prices"].get(k)
        if old is None or old == v or not old:
            continue
        pct = (v - old) / old * 100
        if abs(pct) > max_pct:
            continue
        (up if pct > 0 else down).append({"label": name(k), "from": old, "to": v, "pct": round(pct, 1)})
    new = [name(k) for k in cur["prices"].keys() - prev["prices"].keys()]
    gone = [name(k) for k in prev["prices"].keys() - cur["prices"].keys()]
    up.sort(key=lambda x: -x["pct"]); down.sort(key=lambda x: x["pct"])
    return {"up": up, "down": down, "new": sorted(set(new)), "removed": sorted(set(gone))}


def _entry(eid: str, title: str, updated: str, d: dict, url: str) -> str:
    li = lambda xs: "".join(f"<li>{escape(x)}</li>" for x in xs)
    chg = lambda xs: "".join(f"<li>{escape(c['label'])}: {_fmt(c['from'])} → {_fmt(c['to'])} ({c['pct']:+.1f}%)</li>" for c in xs)
    html = (f"<p>{len(d['up'])} subidas · {len(d['down'])} descidas · {len(d['new'])} novas · {len(d['removed'])} retiradas</p>"
            + (f"<h3>Maiores subidas</h3><ul>{chg(d['up'][:15])}</ul>" if d["up"] else "")
            + (f"<h3>Descidas</h3><ul>{chg(d['down'][:10])}</ul>" if d["down"] else "")
            + (f"<h3>Novas referências</h3><ul>{li(d['new'][:25])}</ul>" if d["new"] else "")
            + (f"<h3>Retiradas</h3><ul>{li(d['removed'][:25])}</ul>" if d["removed"] else ""))
    return (f"<entry><id>{escape(eid)}</id><title>{escape(title)}</title><updated>{updated}</updated>"
            f'<link href="{escape(url)}"/><content type="html">{escape(html)}</content></entry>')


def build_feed(fr_snaps: list[dict], es_snaps: list[dict], es_labels: dict | None = None, limit: int = 20) -> str:
    url = site_url()
    entries = []
    for prev, cur in zip(fr_snaps, fr_snaps[1:]):
        d = diff_snapshots(prev, cur)
        if any(d.values()):
            entries.append((cur["date"], _entry(f"tag:boss-cigar,{cur['date']}:fr", f"França — nova edição ({cur['date']}): "
                                               f"{len(d['up'])}↑ {len(d['down'])}↓ {len(d['new'])} novas", f"{cur['date']}T00:00:00Z", d, url)))
    for prev, cur in zip(es_snaps, es_snaps[1:]):
        d = diff_snapshots(prev, cur, es_labels)
        if any(d.values()):
            entries.append((cur["date"], _entry(f"tag:boss-cigar,{cur['date']}:es", f"Espanha — alterações ({cur['date']}): "
                                               f"{len(d['up'])}↑ {len(d['down'])}↓ {len(d['new'])} novas", f"{cur['date']}T06:00:00Z", d, url)))
    entries.sort(key=lambda e: e[0], reverse=True)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
            f"<id>tag:boss-cigar,2026:feed</id><title>Boss Cigar — preços oficiais de charutos</title>"
            f'<subtitle>Mudanças de preço, novidades e retiradas (França e Espanha)</subtitle><updated>{updated}</updated>'
            f'<link href="{escape(url)}"/><link rel="self" href="{escape(url)}feed.xml"/>'
            + "".join(e for _, e in entries[:limit]) + "</feed>")
