"""Carregamento e validação cruzada do seed."""
from __future__ import annotations

from pathlib import Path

import yaml

from . import SEED_DIR
from .schema import Cigar, Region


class SeedError(ValueError):
    pass


def _load(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SeedError(f"{path.name}: esperava-se uma lista")
    return data


def load_seed(seed_dir: Path = SEED_DIR) -> tuple[list[Region], list[Cigar]]:
    regions = [Region(**r) for r in _load(seed_dir / "regions.yml")]
    cigars = [Cigar(**c) for c in _load(seed_dir / "cigars.yml")]

    errors: list[str] = []
    region_ids = [r.id for r in regions]
    if len(set(region_ids)) != len(region_ids):
        errors.append("ids de região duplicados")
    cigar_ids = [c.id for c in cigars]
    dupes = {i for i in cigar_ids if cigar_ids.count(i) > 1}
    if dupes:
        errors.append(f"ids de charuto duplicados: {sorted(dupes)}")
    for c in cigars:
        if c.region not in set(region_ids):
            errors.append(f"{c.id}: região '{c.region}' não existe em regions.yml")
    if errors:
        raise SeedError("; ".join(errors))
    return regions, cigars
