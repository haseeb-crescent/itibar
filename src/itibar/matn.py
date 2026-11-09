"""Matn tokens for the shahid overlap (derive.corroboration.shahid_min_overlap).

Every hadith with a meaning group is normalized with lists.normalize (v1: diacritics,
tatweel, alif/ya/ta marbuta and hamza carriers) and kept as a set of token ids; the
idf of a token is ln(N / df) + 1 over those N matns. The overlap of two matns is the
idf-weighted Dice coefficient

    overlap(A, B) = 2 * sum idf(t), t in A & B  /  (sum idf(t), t in A  +  sum idf(t), t in B)

It is symmetric: a three-word fragment contained in a long text does not score high
(the overlap coefficient, |A & B| / min(|A|, |B|), was inspected first and does; see
reports/shahid_inspection.md). Deterministic token overlap only; no embeddings.

Output: out/matn_tokens.parquet (hadith_id, group_id, toks) and out/matn_vocab.parquet
(tok_id, token, idf). When the Parquet directory holds matn_idf.parquet (the committed
fixture does, written by `make fixture` from the full corpus), its idf values are used,
so overlaps on the fixture equal the full run's."""

from __future__ import annotations

import math
import time
from collections import Counter

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from itibar import data, lists, paths

VERSION = 1   # bump with lists.NORMALIZE_VERSION or the overlap definition


def tokens_path():
    return paths.OUT_DIR / "matn_tokens.parquet"


def vocab_path():
    return paths.OUT_DIR / "matn_vocab.parquet"


def _matn(nass: str | None, a: int | None, b: int | None) -> str:
    if nass and a is not None and b is not None and b > a:
        return nass[a:b]
    return nass or ""


def build(con=None) -> dict:
    t0 = time.time()
    con = con or data.views()
    rows = con.sql("SELECT id, group_id, nass, matn_start, matn_end FROM hadiths WHERE group_id IS NOT NULL "
                   "ORDER BY id").fetchall()
    toks: list[list[str]] = []
    df: Counter = Counter()
    for _, _, nass, a, b in rows:
        t = sorted(set(lists.tokens(_matn(nass, a, b))))
        toks.append(t)
        df.update(t)
    fixed = paths.PARQUET_DIR / "matn_idf.parquet"
    if fixed.exists():
        it = pq.read_table(fixed).to_pydict()
        idf = dict(zip(it["token"], it["idf"]))
        n_docs = None
    else:
        n_docs = len(rows)
        idf = {t: math.log(n_docs / n) + 1 for t, n in df.items()}
    default = max(idf.values()) if idf else 1.0
    vocab = sorted(df)
    tid = {t: i for i, t in enumerate(vocab)}
    pq.write_table(pa.table({"tok_id": pa.array(range(len(vocab)), pa.int32()), "token": vocab,
                             "idf": pa.array([float(idf.get(t, default)) for t in vocab], pa.float32())}),
                   vocab_path(), compression="zstd")
    pq.write_table(pa.table({
        "hadith_id": pa.array([r[0] for r in rows], pa.int64()),
        "group_id": pa.array([r[1] for r in rows], pa.int64()),
        "toks": pa.array([[tid[x] for x in t] for t in toks], pa.list_(pa.int32())),
    }), tokens_path(), compression="zstd")
    return {"matns": len(rows), "vocab": len(vocab), "idf_from": "fixture table" if n_docs is None else "corpus",
            "seconds": round(time.time() - t0, 1), "version": VERSION}


def ensure(con=None) -> None:
    if not tokens_path().exists() or not vocab_path().exists():
        build(con)


class Matns:
    """Token sets and weights for a set of hadiths, with a cached overlap."""

    def __init__(self, hadith_ids=None):
        ensure()
        idf = pq.read_table(vocab_path(), columns=["idf"]).column("idf").to_numpy().astype(np.float64)
        t = pq.read_table(tokens_path())
        hid = t.column("hadith_id").to_numpy()
        toks = t.column("toks").to_pylist()
        want = None if hadith_ids is None else set(int(h) for h in hadith_ids)
        self.idf = idf
        self.toks: dict[int, np.ndarray] = {}
        self.weight: dict[int, float] = {}
        for h, tk in zip(hid, toks):
            h = int(h)
            if want is not None and h not in want:
                continue
            a = np.asarray(tk, dtype=np.int32)
            self.toks[h] = a
            self.weight[h] = float(idf[a].sum()) if len(a) else 0.0
        self._cache: dict[tuple[int, int], float] = {}

    def shared(self, h1: int, h2: int) -> tuple[float, float, float]:
        """(shared idf weight, weight of h1, weight of h2)."""
        a, b = self.toks.get(h1), self.toks.get(h2)
        if a is None or b is None or not len(a) or not len(b):
            return 0.0, self.weight.get(h1, 0.0), self.weight.get(h2, 0.0)
        common = np.intersect1d(a, b, assume_unique=True)
        return float(self.idf[common].sum()), self.weight[h1], self.weight[h2]

    def overlap(self, h1: int, h2: int) -> float:
        """The idf-weighted Dice coefficient 2 |A & B| / (|A| + |B|) (README; DECISIONS)."""
        if h1 == h2:
            return 1.0
        key = (h1, h2) if h1 < h2 else (h2, h1)
        v = self._cache.get(key)
        if v is None:
            ws, wa, wb = self.shared(h1, h2)
            v = 2 * ws / (wa + wb) if (wa + wb) else 0.0
            self._cache[key] = v
        return v

    def coefficient(self, h1: int, h2: int) -> float:
        """The idf-weighted overlap coefficient |A & B| / min(|A|, |B|) (inspected first, D58)."""
        ws, wa, wb = self.shared(h1, h2)
        return ws / min(wa, wb) if min(wa, wb) else 0.0


def write_fixture_idf(hadith_ids, out_dir) -> int:
    """The full corpus's idf for the tokens of the given hadiths (for the fixture)."""
    ensure()
    v = pq.read_table(vocab_path())
    t = pq.read_table(tokens_path())
    want = set(int(h) for h in hadith_ids)
    ids: set[int] = set()
    for h, tk in zip(t.column("hadith_id").to_pylist(), t.column("toks").to_pylist()):
        if h in want:
            ids.update(tk)
    keep = sorted(ids)
    tok = v.column("token").to_pylist()
    idf = v.column("idf").to_pylist()
    pq.write_table(pa.table({"token": [tok[i] for i in keep], "idf": pa.array([idf[i] for i in keep], pa.float32())}),
                   out_dir / "matn_idf.parquet", compression="zstd")
    return len(keep)


if __name__ == "__main__":
    print(build())
