"""YAML configuration loading. All tunable parameters live under config/."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from itibar import paths


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    p = paths.CONFIG_DIR / f"{name}.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
