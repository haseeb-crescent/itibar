"""YAML configuration loading. All tunable parameters live under config/.

`ITIBAR_CONFIG_OVERRIDE` may name a YAML file of the form {structure: {...}, grades:
{...}} whose keys are deep-merged over the files in config/. The audit's cumulative
before/after tables (`make stages`, config/stages/*.yaml) use it to rerun the pipeline
with one correction switched on at a time; nothing else sets it."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml

from itibar import paths


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@lru_cache(maxsize=None)
def _overrides() -> dict[str, Any]:
    p = os.environ.get("ITIBAR_CONFIG_OVERRIDE")
    if not p:
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    p = paths.CONFIG_DIR / f"{name}.yaml"
    with open(p, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    over = _overrides().get(name)
    return _merge(d, over) if over else d
