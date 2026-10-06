"""Notificações push (ntfy.sh) quando há novidades de preços.

Opcional: só corre se a variável NTFY_TOPIC estiver definida (secret do repositório).
Envia uma mensagem por cada entrada nova do feed (nova edição francesa ou alteração em
Espanha), com destaque para as referências de data/seed/watchlist.yml.
"""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from html import unescape

import requests
import yaml

from . import CACHE_DIR, ROOT, SEED_DIR

ATOM = "{http://www.w3.org/2005/Atom}"
STATE = CACHE_DIR / "ntfy_sent.json"


def watchlist() -> list[str]:
    p = SEED_DIR / "watchlist.yml"
    if not p.exists():
        return []
    return [str(x).lower() for x in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("refs", []) or []]


def entries(feed_path=None) -> list[dict]:
    root = ET.parse(feed_path or (ROOT / "site" / "feed.xml")).getroot()
    out = []
    for e in root.findall(f"{ATOM}entry"):
        html = e.find(f"{ATOM}content").text or ""
        lines = [unescape(re.sub(r"<[^>]+>", "", li)) for li in re.findall(r"<li>(.*?)</li>", html)]
        summary = unescape(re.sub(r"<[^>]+>", "", (re.search(r"<p>(.*?)</p>", html) or [None, ""])[1]))
        out.append({"id": e.find(f"{ATOM}id").text, "title": e.find(f"{ATOM}title").text, "summary": summary, "lines": lines,
                    "url": e.find(f"{ATOM}link").get("href")})
    return out


def message(entry: dict, watch: list[str]) -> str:
    hits = [l for l in entry["lines"] if any(w in l.lower() for w in watch)] if watch else []
    body = entry["summary"]
    if hits:
        body += "\n⭐ Na tua lista:\n" + "\n".join("• " + h for h in hits[:8])
    else:
        body += "\n" + "\n".join("• " + l for l in entry["lines"][:5])
    return body[:3500]


def send_new(topic: str, server: str = "https://ntfy.sh", feed_path=None, dry: bool = False) -> list[str]:
    sent = set(json.loads(STATE.read_text())) if STATE.exists() else set()
    new = [e for e in entries(feed_path) if e["id"] not in sent]
    first_run = not STATE.exists()
    out = []
    for e in (new[:1] if first_run else new[:5]):  # na primeira vez só a mais recente, para não inundar
        if not dry:
            requests.post(f"{server.rstrip('/')}/{topic}", data=message(e, watchlist()).encode("utf-8"), timeout=30,
                          headers={"Title": e["title"].encode("utf-8"), "Click": e["url"], "Tags": "cigar"})
        out.append(e["id"])
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(sent | {e["id"] for e in new})))
    return out


if __name__ == "__main__":
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC não definido: sem notificações.")
    else:
        print("enviadas:", send_new(topic, os.environ.get("NTFY_SERVER", "https://ntfy.sh")))
