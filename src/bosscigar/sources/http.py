"""Cliente HTTP com retry/backoff e cache em disco (para fallback)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from .. import CACHE_DIR, USER_AGENT

MODE = lambda: os.environ.get("BOSSCIGAR_MODE", "auto")  # auto | cache | offline


class SourceError(RuntimeError):
    pass


def get_json(url: str, params: dict | None = None, retries: int = 4, timeout: int = 30) -> dict:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
            if r.status_code == 429 or r.status_code >= 500:
                raise SourceError(f"HTTP {r.status_code}: {r.text[:120]}")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and data.get("error") is True:
                # Open-Meteo devolve 200/4xx com {"error": true, "reason": ...}
                raise SourceError(str(data.get("reason", "erro da API"))[:160])
            return data
        except (requests.RequestException, SourceError, ValueError) as exc:
            last = exc
            msg = str(exc)
            # Limites diários não se resolvem com retry.
            if "limit exceeded" in msg.lower():
                break
            time.sleep(min(2 ** attempt, 20))
    raise SourceError(str(last))


def cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def cache_read(name: str):
    p = cache_path(name)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def cache_write(name: str, data) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(name).write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def fetch_with_cache(name: str, fetch):
    """Devolve (dados, estado). Estado: 'ok' (direto), 'CACHE' (fallback) ou 'ERRO' (sem dados)."""
    mode = MODE()
    if mode in ("cache", "offline"):
        cached = cache_read(name)
        return (cached, "CACHE") if cached is not None else (None, "ERRO: sem cache")
    try:
        data = fetch()
        cache_write(name, data)
        return data, "ok"
    except Exception as exc:  # noqa: BLE001 - qualquer falha de fonte cai no fallback
        cached = cache_read(name)
        if cached is not None:
            return cached, f"CACHE ({str(exc)[:80]})"
        return None, f"ERRO: {str(exc)[:100]}"
