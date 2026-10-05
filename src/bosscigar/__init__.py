"""Boss Cigar — pipeline de dados."""
from pathlib import Path

__version__ = "0.1.0"

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "data" / "seed"
CACHE_DIR = ROOT / "data" / "cache"
CLEAN_DIR = ROOT / "data" / "clean"
SITE_DATA_DIR = ROOT / "site" / "data"

USER_AGENT = "boss-cigar/0.1 (projeto pessoal; https://github.com/)"
