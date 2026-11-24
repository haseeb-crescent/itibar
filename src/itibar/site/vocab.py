"""The site's words: the hand-written glossary and the plain-English scales it defines (config/glossary.yaml)."""
from __future__ import annotations

import math
from functools import lru_cache

import yaml

from itibar import paths


@lru_cache(maxsize=1)
def glossary():
    return yaml.safe_load((paths.CONFIG_DIR / "glossary.yaml").read_text(encoding="utf-8"))


def terms():
    return {t["id"]: t for t in glossary()["terms"]}


def level(rank_no):
    """The narrator's Taqrīb level in words: {n, name, arabic, translit, meaning} or None."""
    if not rank_no:
        return None
    entry = glossary()["levels"].get(int(rank_no))
    return {"n": int(rank_no), **entry} if entry else None


def generation(tabaka):
    """A generation in words: Ibn Ḥajar's name for 1–12, "generation N" beyond."""
    if not tabaka:
        return None
    entry = glossary()["generations"].get(int(tabaka))
    if entry:
        return {"n": int(tabaka), **entry}
    return {"n": int(tabaka), "name": f"Later transmitters (generation {tabaka})", "arabic": None}


def generation_label(gen):
    if gen == 0:
        return "The Prophet"
    if gen == "books":
        return "The books"
    entry = generation(gen)
    return entry["name"] if gen <= 12 else f"Generation {gen}"


def threshold(name):
    return glossary()["thresholds"][name]


def grade_rule(rule):
    return glossary()["grades"].get(rule)


def grade_code(code):
    return glossary()["codes"].get(int(code)) if code is not None else None


def number_class(name):
    return glossary()["number_classes"].get(name) if name else None


def tadlis_tier(tier):
    return glossary()["tadlis_tiers"].get(int(tier)) if tier else None


def ce(ah):
    """The Common Era year(s) an AH year falls in: '741–742 CE' (the Hijri year spans two CE years mostly)."""
    if ah is None or ah <= 0:
        return None
    start = 622.5370 + (ah - 1) * 0.970224
    first, last = math.floor(start), math.floor(start + 0.970224)
    return f"{first} CE" if first == last else f"{first}–{last} CE"


def died(year, raw=None):
    """'d. 124 AH (741–742 CE)'; the source's own wording when it gives a range or several dates."""
    if raw and str(raw).strip() not in ("", str(year)):
        return f"d. {raw} AH (as recorded)"
    if year and year > 0:
        return f"d. {year} AH ({ce(year)})"
    return None
