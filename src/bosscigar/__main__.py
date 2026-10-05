"""CLI: python -m bosscigar [validate|build|quality]"""
from __future__ import annotations

import json
import sys

from . import SITE_DATA_DIR
from .build import build
from .seed import SeedError, load_seed


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "build"
    if cmd == "validate":
        try:
            regions, cigars = load_seed()
        except (SeedError, ValueError) as exc:
            print(f"ERRO no seed: {exc}", file=sys.stderr)
            return 1
        print(f"ok: {len(cigars)} charutos, {len(regions)} regiões")
        return 0
    if cmd == "build":
        try:
            meta = build()
        except (SeedError, ValueError) as exc:
            print(f"ERRO no seed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(meta, ensure_ascii=False))
        return 0
    if cmd == "quality":
        print((SITE_DATA_DIR / "quality.json").read_text(encoding="utf-8"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
