"""Tiny synthetic corpora for unit tests (no data files needed)."""

from __future__ import annotations

import contextlib
import os
import tempfile

import numpy as np
import yaml

from itibar import config, grades
from itibar.load import Books, Chain, Corpus, Narrators


@contextlib.contextmanager
def override(cfg: dict):
    """Run with config overrides ({structure: {...}, grades: {...}}), as `make stages` does."""
    old = os.environ.get("ITIBAR_CONFIG_OVERRIDE")
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)
        path = f.name
    os.environ["ITIBAR_CONFIG_OVERRIDE"] = path
    config.load.cache_clear()
    config._overrides.cache_clear()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("ITIBAR_CONFIG_OVERRIDE", None)
        else:
            os.environ["ITIBAR_CONFIG_OVERRIDE"] = old
        config.load.cache_clear()
        config._overrides.cache_clear()
        os.unlink(path)

PLACEHOLDERS = {30002: ("gap", "irsal"), 30000: ("gap", "inqita"), 30001: ("gap", "taliq"), 1131: ("mubham", "mubham")}


def make_corpus(people: dict[int, dict], books: dict[int, dict], hearing_pairs=frozenset()) -> Corpus:
    """people: rid -> {rank_no, tabaka=0, birth=-1, death=-1, tadlis=0, tier=0, stub=0, homonym=-1, label=''}
    books:  book_id -> {author_no, compiler_rawi=None, transmitter_rawi=None}"""
    scale = grades.load()
    n = max(list(people) + list(PLACEHOLDERS)) + 1
    rank_no = np.full(n, -1, np.int16)
    tabaka = np.zeros(n, np.int16)
    birth = np.full(n, -1, np.int32)
    death = np.full(n, -1, np.int32)
    tadlis = np.zeros(n, np.int8)
    stub = np.zeros(n, np.int8)
    comp = np.zeros(n, np.int8)
    ordinal = np.zeros(n, np.int8)
    homonym = np.full(n, -1, np.int32)
    exists = np.zeros(n, np.int8)
    tier = np.zeros(n, np.int8)
    for rid in PLACEHOLDERS:
        rank_no[rid] = 12
        exists[rid] = 1
    for rid, p in people.items():
        rank_no[rid] = p["rank_no"]
        tabaka[rid] = p.get("tabaka", 0)
        birth[rid] = p.get("birth", -1)
        death[rid] = p.get("death", -1)
        tadlis[rid] = p.get("tadlis", 0)
        stub[rid] = p.get("stub", 0)
        homonym[rid] = p.get("homonym", -1)
        tier[rid] = p.get("tier", 0)
        exists[rid] = 1
        ordinal[rid] = scale.ordinal(p["rank_no"], bool(p.get("stub", 0)), rid)
        comp[rid] = 1 if scale.is_companion(p["rank_no"], p.get("label", "صحابي")) else 0
    nar = Narrators(rank_no=rank_no, tabaka=tabaka, birth=birth, death=death, has_tadlis=tadlis,
                    is_stub=stub, is_companion=comp, ordinal=ordinal, homonym=homonym, exists=exists,
                    placeholder_role={k: v[0] for k, v in PLACEHOLDERS.items()},
                    placeholder_kind={k: v[1] for k, v in PLACEHOLDERS.items()}, tadlis_tier=tier)
    bk = Books(
        compiler_node={b: f"c{v['author_no']}" for b, v in books.items()},
        compiler_rawi={b: v["compiler_rawi"] for b, v in books.items() if v.get("compiler_rawi") is not None},
        author_no={b: v["author_no"] for b, v in books.items()},
        author_name={b: f"author {v['author_no']}" for b, v in books.items()},
        author_death={b: None for b in books},
        tasnif_no={b: 1 for b in books},
        name={b: f"book {b}" for b in books},
        pos0_share={b: 1.0 for b in books},
        transmitter_rawi={b: v["transmitter_rawi"] for b, v in books.items() if v.get("transmitter_rawi") is not None},
    )
    return Corpus(narrators=nar, books=bk, scale=scale, hearing_pairs=frozenset(hearing_pairs))


_SID = [1000]


def chain(book_id: int, *rawis: int, max_rank: int | None = None, words: dict | None = None) -> Chain:
    """rawis in sanad_rawis order: pos 0 (compiler/first) ... companion last."""
    _SID[0] += 1
    return Chain(sanad_id=_SID[0], hadith_id=_SID[0], book_id=book_id, rawis=tuple(rawis), matn_no=0,
                 max_rank=max_rank, takhrij=None, hadith_matn_no=0, words=words or {})
