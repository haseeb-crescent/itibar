"""Shawahid across meaning groups (derive.corroboration.shahid_scope: siblings).

A shahid is another companion's report of the same meaning (Nuzhat al-Nazar). The
source files many such reports as separate meaning groups under one topic. The sibling
groups of g are the other groups whose leaf rows in `topics` share a parent with one of
g's leaf rows (a group's rows are always leaves; their parent is the lowest topic node
holding the report).

The index keeps, for every chain of every group that can lend a witness, its sanad id,
group, hadith, chain ordinal, the narrators it carries (node codes: rawi id, or a
negative code per unnamed-person context), and one bit per parameter set for each of
the two witness classes the engine asks for:

  light   light-or-better (no fatal or unrepairable defect) and continuous
  hasan   defect-free (hasan-or-better under the ruleset) and continuous

The bits come from the same classification the chain gets in its own group
(corroborate.classify_group), so a sibling witness is judged exactly as it would be at
home. A candidate must avoid the positions to be covered and its matn must overlap the
corroborated chain's matn by at least shahid_min_overlap (matn.Matns.overlap)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from itibar import matn as matn_mod


def sibling_groups(con, group_ids=None) -> dict[int, tuple[int, ...]]:
    rows = con.sql("""SELECT DISTINCT a.group_id g, b.group_id s FROM topics a JOIN topics b
                      ON a.parent_id = b.parent_id AND a.group_id <> b.group_id
                      WHERE a.group_id IS NOT NULL AND b.group_id IS NOT NULL ORDER BY 1, 2""").fetchall()
    out: dict[int, list[int]] = defaultdict(list)
    want = None if group_ids is None else set(int(g) for g in group_ids)
    for g, s in rows:
        if want is None or int(g) in want:
            out[int(g)].append(int(s))
    return {g: tuple(v) for g, v in out.items()}


def node_code(node: str, mubham: dict[str, int], add: bool = False) -> int | None:
    if node.startswith("r"):
        return int(node[1:])
    if node.startswith(("m", "u")):
        c = mubham.get(node)
        if c is None and add:
            c = mubham[node] = -(len(mubham) + 1)
        return c
    return None


@dataclass
class SiblingIndex:
    params: list[str]                                  # bit i <-> params[i]
    siblings: dict[int, tuple[int, ...]]
    sanad: np.ndarray
    group: np.ndarray
    hadith: np.ndarray
    ordinal: np.ndarray
    light: np.ndarray
    hasan: np.ndarray
    companion: np.ndarray
    node_ptr: np.ndarray
    node_codes: np.ndarray
    mubham: dict[str, int]
    group_rows: dict[int, tuple[int, int]]             # group -> [start, end) rows (sorted by group, sanad)
    matns: matn_mod.Matns | None = None
    _cand: dict = field(default_factory=dict)

    @staticmethod
    def build(rows: list[tuple], siblings: dict[int, tuple[int, ...]], params: list[str],
              matns: matn_mod.Matns | None = None) -> "SiblingIndex":
        """rows: (group_id, sanad_id, hadith_id, ordinal, light_bits, hasan_bits, companion_rawi, nodes)."""
        rows = sorted(rows, key=lambda r: (r[0], r[1]))
        mub: dict[str, int] = {}
        ptr = [0]
        codes: list[int] = []
        for r in rows:
            for v in r[7]:
                c = node_code(v, mub, add=True)
                if c is not None:
                    codes.append(c)
            ptr.append(len(codes))
        g = np.array([r[0] for r in rows], dtype=np.int64)
        grows: dict[int, tuple[int, int]] = {}
        if len(g):
            starts = np.flatnonzero(np.r_[True, g[1:] != g[:-1]])
            ends = np.r_[starts[1:], len(g)]
            for s, e in zip(starts, ends):
                grows[int(g[s])] = (int(s), int(e))
        return SiblingIndex(
            params=list(params), siblings=siblings, sanad=np.array([r[1] for r in rows], dtype=np.int64), group=g,
            hadith=np.array([r[2] for r in rows], dtype=np.int64),
            ordinal=np.array([r[3] for r in rows], dtype=np.int16),
            light=np.array([r[4] for r in rows], dtype=np.int64), hasan=np.array([r[5] for r in rows], dtype=np.int64),
            companion=np.array([r[6] if r[6] is not None else -1 for r in rows], dtype=np.int64),
            node_ptr=np.array(ptr, dtype=np.int64), node_codes=np.array(codes, dtype=np.int64), mubham=mub,
            group_rows=grows, matns=matns,
        )

    def hadith_ids(self) -> set[int]:
        return set(int(h) for h in self.hadith)

    def bit(self, param: str) -> int:
        return 1 << self.params.index(param) if param in self.params else 0

    def candidates(self, gid: int) -> np.ndarray:
        c = self._cand.get(gid)
        if c is None:
            idx = [np.arange(*self.group_rows[s]) for s in self.siblings.get(gid, ()) if s in self.group_rows]
            c = np.concatenate(idx) if idx else np.zeros(0, dtype=np.int64)
            if len(c):
                anyb = (self.light[c] | self.hasan[c]) != 0
                c = c[anyb]
                order = np.lexsort((self.sanad[c], -self.ordinal[c]))
                c = c[order]
            self._cand[gid] = c
        return c

    def nodes_of(self, i: int) -> np.ndarray:
        return self.node_codes[self.node_ptr[i]:self.node_ptr[i + 1]]

    def find(self, gid: int, hadith_id: int, avoid: list[str], param: str, kind: str, min_overlap: float,
             k: int = 1, min_ordinal: int | None = None) -> list[tuple[int, float]]:
        """Up to k sibling chains (row, overlap): eligible under `param` as `kind`
        (light | hasan), carrying none of `avoid`, matn overlap >= min_overlap, of chain
        ordinal >= min_ordinal when given; best chain grade first, then overlap, then
        lowest sanad id."""
        b = self.bit(param)
        if not b or self.matns is None:
            return []
        cand = self.candidates(gid)
        if not len(cand):
            return []
        mask = self.light if kind == "light" else self.hasan
        av = {c for c in (node_code(v, self.mubham) for v in avoid) if c is not None}
        found: list[tuple[int, float, int]] = []
        tier = None
        for i in cand:                      # sorted by chain ordinal (best first), then sanad id
            o = int(self.ordinal[i])
            if tier is not None and o != tier and len(found) >= k:
                break                       # the best tier with k hits is complete
            if not (int(mask[i]) & b):
                continue
            if min_ordinal is not None and o < min_ordinal:
                continue
            if av and av.intersection(self.nodes_of(i).tolist()):
                continue
            ov = self.matns.overlap(hadith_id, int(self.hadith[i]))
            if ov < min_overlap:
                continue
            tier = o if tier is None else tier
            found.append((int(i), ov, o))
        found.sort(key=lambda x: (-x[2], -x[1], int(self.sanad[x[0]])))
        return [(i, ov) for i, ov, _ in found[:k]]


# ---------------------------------------------------------------- floor inspection

def inspection_sample(n_per_bin: int = 3, bins: int = 10, seed: int = 20261109, chains_path=None, con=None,
                      measure: str = "coefficient", lo: float = 0.0, hi: float = 1.0):
    """Candidate cross-group witnesses for reading: chains of the default run with light
    defects only that have no witness inside their own group (code 2 under the
    shahid_group variant), in groups that have siblings, paired with every sibling chain
    eligible as a light-or-better witness that avoids the chain's positions to cover;
    `n_per_bin` pairs drawn per overlap decile. Deterministic (seed)."""
    import random

    import pandas as pd

    from itibar import corroborate, data, load, paths
    from itibar import pipeline as pl
    con = con or data.views()
    chains_path = chains_path or paths.chains_path()
    ch = pd.read_parquet(chains_path, columns=["sanad_id", "group_id", "hadith_id", "rule_v2_ibn_hajar",
                                               "code_v2_alt_shahid_group", "weak_nodes_v2_ibn_hajar"])
    sib = sibling_groups(con)
    pool = ch[ch["rule_v2_ibn_hajar"].isin(["daif", "hasan_li_ghayrihi"]) & (ch["code_v2_alt_shahid_group"] == 2)
              & ch["group_id"].isin(list(sib))]
    rng = random.Random(seed)
    picked = rng.sample(sorted(pool["group_id"].unique().tolist()), min(400, pool["group_id"].nunique()))
    params = {"ibn_hajar": corroborate.rulesets()["ibn_hajar"]}
    corpus = load.corpus(con)
    need = sorted({s for g in picked for s in sib[g]} | set(picked))
    gc = load.chains_by_group(con, need)
    rows = []
    for s in sorted({s for g in picked for s in sib[g]}):
        rows.extend(pl.witness_rows(s, gc.get(s, []), corpus, params))
    hids = {r[2] for r in rows} | set(pool[pool["group_id"].isin(picked)]["hadith_id"])
    idx = SiblingIndex.build(rows, {g: sib[g] for g in picked}, list(params), matn_mod.Matns(hids))
    pairs = []
    for g in picked:
        sub = pool[pool["group_id"] == g]
        c = sub.iloc[rng.randrange(len(sub))]
        av = {x for x in (node_code(v, idx.mubham) for v in c["weak_nodes_v2_ibn_hajar"]) if x is not None}
        for i in idx.candidates(g):
            if not int(idx.light[i]) & 1 or (av and av.intersection(idx.nodes_of(i).tolist())):
                continue
            f = idx.matns.coefficient if measure == "coefficient" else idx.matns.overlap
            pairs.append((int(c["sanad_id"]), int(c["hadith_id"]), g, int(idx.sanad[i]), int(idx.hadith[i]),
                          int(idx.group[i]), f(int(c["hadith_id"]), int(idx.hadith[i]))))
    width = (hi - lo) / bins

    def bin_of(x: float) -> int | None:
        if x < lo or x > hi:
            return None
        return min(bins - 1, int((x - lo) / width))

    by_bin: dict[int, list] = defaultdict(list)
    for p in pairs:
        b = bin_of(p[6])
        if b is not None:
            by_bin[b].append(p)
    out = []
    for b in range(bins):
        cand = sorted(by_bin.get(b, []))
        seen_h: set = set()
        rng2 = random.Random(seed + b)
        rng2.shuffle(cand)
        for p in cand:
            if (p[1], p[4]) in seen_h:
                continue
            seen_h.add((p[1], p[4]))
            out.append(p)
            if sum(1 for q in out if bin_of(q[6]) == b) >= n_per_bin:
                break
    texts = dict(con.sql(f"""SELECT id, CASE WHEN matn_start IS NOT NULL AND matn_end > matn_start
                                  THEN substr(nass, matn_start + 1, matn_end - matn_start) ELSE nass END
                             FROM hadiths WHERE id IN ({",".join(str(h) for p in out for h in (p[1], p[4])) or "-1"})""").fetchall())
    dist = pd.Series([p[6] for p in pairs])
    return out, texts, dist


def write_inspection(con=None) -> str:
    """reports/shahid_inspection.md from lists/shahid_inspection.yaml: every inspected pair
    with both overlap measures, the label and the matns, and the share of pairs that carry
    the chain's content (same or partial) per band of the Dice coefficient."""
    import yaml

    from itibar import config, data, paths
    con = con or data.views()
    y = yaml.safe_load((paths.ROOT / "lists" / "shahid_inspection.yaml").read_text(encoding="utf-8"))
    pairs = []
    for sname in ("sample_1", "sample_2"):
        for key, v in y[sname]["pairs"].items():
            a, b = (int(x) for x in key.split("-"))
            pairs.append((sname, a, b, v["label"], v.get("note", "")))
    sids = sorted({p[1] for p in pairs} | {p[2] for p in pairs})
    meta = {r[0]: (r[1], r[2], r[3]) for r in con.sql(
        f"""SELECT s.id, s.hadith_id, h.group_id,
                   CASE WHEN h.matn_start IS NOT NULL AND h.matn_end > h.matn_start
                        THEN substr(h.nass, h.matn_start + 1, h.matn_end - h.matn_start) ELSE h.nass END
            FROM sanads s JOIN hadiths h ON h.id = s.hadith_id WHERE s.id IN ({",".join(map(str, sids))})""").fetchall()}
    M = matn_mod.Matns({meta[s][0] for s in sids})
    floor = float(config.load("structure")["derive"]["corroboration"]["shahid_min_overlap"])
    rows = []
    for sname, a, b, lab, note in pairs:
        ha, hb = meta[a][0], meta[b][0]
        rows.append({"sample": sname, "chain": a, "group": meta[a][1], "witness": b, "witness_group": meta[b][1],
                     "coefficient": M.coefficient(ha, hb), "dice": M.overlap(ha, hb), "label": lab, "note": note,
                     "A": meta[a][2] or "", "B": meta[b][2] or ""})
    bands = [(0.0, 0.2), (0.2, 0.26), (0.26, 0.32), (0.32, 0.38), (0.38, 1.01)]
    hi_coef = [r for r in rows if r["sample"] == "sample_1" and r["coefficient"] >= 0.5]
    hi_diff = sum(1 for r in hi_coef if r["label"] == "different")
    L = ["# Inspection of cross-group witness candidates", "",
         "Generated by `python -m itibar.siblings inspect` from `lists/shahid_inspection.yaml` (the labels are the",
         "reader's; DECISIONS D58). Each pair is a chain with light defects only and no witness in its own meaning",
         "group, and an attested light-or-better chain of a sibling group (same lowest topic node) that avoids the",
         "chain's positions to cover. Labels against Ibn Hajar's shahid, «يشبهه في اللفظ والمعنى أو في المعنى فقط»:",
         "**same** (the report, in wording or meaning), **partial** (one component of the matn, or the topic with",
         "different content), **different**.", "",
         "Sample 1 (30 pairs, three per decile of the idf-weighted overlap coefficient |A∩B| / min(|A|, |B|)) showed",
         "that the coefficient scores a three-word fragment contained in a long text near 1 "
         f"({hi_diff} of the {len(hi_coef)} pairs at",
         "≥ 0.5 were different). The idf-weighted Dice coefficient 2|A∩B| / (|A| + |B|) does not; sample 2 (20 pairs,",
         "four per band of 0.06 of Dice between 0.20 and 0.50, bands fixed before reading) was drawn to place the",
         f"floor. **Rule:** the lowest band in which at least four in five pairs are same or partial. **Floor: {floor}.**", "",
         "| Dice band | pairs | same | partial | different | same or partial |", "|---|---|---|---|---|---|"]
    for lo, hi in bands:
        sub = [r for r in rows if lo <= r["dice"] < hi]
        if not sub:
            continue
        n = len(sub)
        k = {lab: sum(1 for r in sub if r["label"] == lab) for lab in ("same", "partial", "different")}
        L.append(f"| {lo:.2f}–{min(hi, 1.0):.2f} | {n} | {k['same']} | {k['partial']} | {k['different']} | "
                 f"{(k['same'] + k['partial']) / n:.0%} |")
    L += ["", "Token overlap cannot read meaning: at any floor some admitted pairs carry only part of the chain's matn,",
          "and one pair whose witness negates the chain («لا يصافح النساء») scores 0.60. The floor bounds that error; it",
          "does not remove it.", "",
          "| # | sample | chain (group) | witness (group) | coefficient | Dice | label | note |",
          "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(sorted(rows, key=lambda r: (r["dice"], r["chain"], r["witness"])), 1):
        L.append(f"| {i} | {r['sample'][-1]} | {r['chain']} ({r['group']}) | {r['witness']} ({r['witness_group']}) | "
                 f"{r['coefficient']:.3f} | {r['dice']:.3f} | {r['label']} | {r['note']} |")
    L += ["", "## The matns", ""]
    for i, r in enumerate(sorted(rows, key=lambda r: (r["dice"], r["chain"], r["witness"])), 1):
        L += [f"**{i}.** Dice {r['dice']:.3f}, {r['label']}", "",
              f"- chain {r['chain']}: {r['A'][:400].strip()}", f"- witness {r['witness']}: {r['B'][:400].strip()}", ""]
    text = "\n".join(L)
    (paths.REPORTS_DIR / "shahid_inspection.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "inspect":
        write_inspection()
        print("wrote reports/shahid_inspection.md")
