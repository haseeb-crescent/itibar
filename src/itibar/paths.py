"""Filesystem layout. Every location can be overridden by an environment variable
so that CI (and `make fixture`) can point the whole pipeline at the committed
sample instead of the 1.6 GB source database."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env_path(var: str, default: Path) -> Path:
    v = os.environ.get(var)
    return Path(v).resolve() if v else default


DATA_DIR = _env_path("ITIBAR_DATA_DIR", ROOT / "data")
SOURCE_DB = _env_path("ITIBAR_SOURCE_DB", DATA_DIR / "hadith-kg.db")
PARQUET_DIR = _env_path("ITIBAR_PARQUET_DIR", DATA_DIR / "parquet")
OUT_DIR = _env_path("ITIBAR_OUT_DIR", ROOT / "out")
REPORTS_DIR = _env_path("ITIBAR_REPORTS_DIR", ROOT / "reports")
CONFIG_DIR = _env_path("ITIBAR_CONFIG_DIR", ROOT / "config")
FIXTURE_DIR = ROOT / "tests" / "fixture"
GOLD_FILE = ROOT / "tests" / "gold" / "gold.yaml"
FIGURES_DIR = _env_path("ITIBAR_FIGURES_DIR", ROOT / "figures")


def bundles_dir() -> Path:
    return OUT_DIR / "bundles"


def records_path() -> Path:
    return OUT_DIR / "records.parquet"


def chains_path() -> Path:
    return OUT_DIR / "chains.parquet"
