"""The machinery scored against the critics' own claims (PR 7 §5): reports/verdicts.md, figures/fig7_critics.*,
out/verdicts_scored.parquet.

  tafarrud     «لم يرو هذا الحديث عن X إلا Y», «تفرد به Y», «لا نعلم رواه عن X إلا Y», «لا يروى عن X إلا بهذا الإسناد»:
               in the group's bundle (on-path edges, threshold everyone), is Y a cut vertex of the routes through X —
               does every route from X to a book pass through Y? The claim is relative and is tested as such. A failure
               is printed with the attested chains that break it: the book, its compiler's death year against the
               critic's, whether the chain's links pass the continuity rule, and whether its divergence is a
               misresolution candidate (the narrator below X a namesake of Y, or an incompatible link there).
  gharib       al-Tirmidhī's «غريب» (and «لا نعرفه إلا من هذا الوجه»): absolute against the κ number class
               (κ_all = 1); «من هذا الوجه» relative to the chain's companion, «من حديث X» relative to X.
  hasan        al-Tirmidhī's verdict classes: κ at each threshold, a «وفي الباب» companion found, v1/v2 under both
               rulesets and both code maps, the weakest level of his chain.
  wafi_al_bab  every companion named: a chain ending at him in the same group, a sibling group (same lowest topic
               node), or under the same grandparent topic node; recall per scope; the idf-weighted Dice of the true
               pairs against non-pairs from the same siblings.
  shart        al-Ḥākim's «على شرط الشيخين / مسلم / البخاري»: every man of his chain up to the Ṣaḥīḥayn's generation
               a narrator of the named Ṣaḥīḥ (rawis.is_bukhari / is_muslim), and every link among them a pairing the
               Ṣaḥīḥ uses (the same teacher -> student link in a chain of book 1 or 2).
  verdict      grade words, critic by critic, against v1 and v2 (both rulesets, both code maps) of the critic's own
               chain and of the group.
  sahih_attribution  al-Bayhaqī's «رواه البخاري / مسلم في الصحيح عن X»: a chain of that Ṣaḥīḥ in the same group
               whose compiler's teacher is X.

A failed claim is reported with what breaks it, never as the critic being wrong: a later book, a misresolved name and a
route the critic did not accept are different findings and are kept apart.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as pads

from itibar import conditional, data, lists, matn, paths, siblings, verdicts

CRITIC_DEATH = {"al-Tirmidhi": 279, "al-Tabarani": 360, "al-Bazzar": 292, "al-Daraqutni": 385, "al-Bayhaqi": 458,
                "Abu Nuaym": 430, "al-Khatib": 463, "al-Hakim": 405, "Abu Dawud": 275, "al-Nasai": 303,
                "Ibn Khuzayma": 311, "Ibn Hibban": 354}
SAHIH_BOOKS = {"البخاري": (1,), "مسلم": (2,), "البخاري ومسلم": (1, 2)}
GAPS = {30000, 30001, 30002}
MUBHAM = 1131


def claim_critic(row) -> str:
    """Who made the claim: al-Khaṭīb relaying «قال سليمان …» is al-Ṭabarānī; Kashf al-Astār's «قال البزار» al-Bazzār."""
    if row["family"].startswith("tabarani_"):
        return "al-Tabarani"
    if row["book_id"] == 59:
        return "al-Bazzar" if not row["span"].startswith("قلت") else "al-Haythami"
    return row["critic"]


# ---------------------------------------------------------------- loading

class World:
    def __init__(self, con=None):
        self.con = con or data.views()
        con = self.con
        self.rec = pd.read_parquet(paths.records_path()).set_index("group_id")
        self.ch = pd.read_parquet(paths.chains_path())
        self.books = con.sql("SELECT id, name, author_name, author_death_year FROM books").df().set_index("id")
        r = con.sql("SELECT id, name, nickname, rank_no, is_bukhari, is_muslim, death_year, tabaka FROM rawis").df()
        self.rw = r.set_index("id")
        self.cluster = {}
        for (nm, nk), ids in r.groupby(["name", "nickname"])["id"]:
            if len(ids) > 1:
                for i in ids:
                    self.cluster[int(i)] = (nm, nk)
        self._chains: dict[int, list[tuple[int, int, int, list[int]]]] = {}
        self._graph: dict[int, tuple[dict, dict]] = {}

    def chains(self, gid: int) -> list[tuple[int, int, int, list[int]]]:
        """(sanad_id, hadith_id, book_id, rawis pos 0 first) of every chain of the group."""
        c = self._chains.get(gid)
        if c is None:
            c = [(int(a), int(b), int(d), [int(x) for x in e]) for a, b, d, e in self.con.sql(
                f"""SELECT s.id, s.hadith_id, h.book_id, list(sr.rawi_id ORDER BY sr.pos) FROM sanads s
                    JOIN hadiths h ON h.id = s.hadith_id JOIN sanad_rawis sr ON sr.sanad_id = s.id
                    WHERE h.group_id = {int(gid)} GROUP BY ALL ORDER BY s.id""").fetchall()]
            self._chains[gid] = c
        return c

    def load_graphs(self, gids) -> None:
        gids = sorted({int(g) for g in gids if g is not None and int(g) not in self._graph})
        if not gids:
            return
        d = pads.dataset(paths.bundles_dir() / "edges", format="parquet", partitioning="hive")
        t = d.to_table(filter=pads.field("group_id").isin(gids), columns=["group_id", "u", "v", "on_path",
                                                                         "continuity"]).to_pandas()
        for g in gids:
            self._graph[g] = ({}, {})
        for g, u, v, on, cont in zip(t["group_id"], t["u"], t["v"], t["on_path"], t["continuity"]):
            succ, contd = self._graph[int(g)]
            contd[(u, v)] = cont
            if on:
                succ.setdefault(u, []).append(v)

    def graph(self, gid: int) -> tuple[dict, dict]:
        if gid not in self._graph:
            self.load_graphs([gid])
        return self._graph[gid]


def reaches_book_avoiding(succ: dict, x: str, y) -> bool:
    """A route from x to a book node avoiding y (a node or a set of nodes)."""
    ys = {y} if isinstance(y, str) else set(y)
    if x in ys:
        return False
    seen = {x}
    stack = [x]
    while stack:
        u = stack.pop()
        for w in succ.get(u, ()):
            if w in ys or w in seen:
                continue
            if w.startswith("b"):
                return True
            seen.add(w)
            stack.append(w)
    return False


def node(rid) -> str | None:
    if rid is None or (isinstance(rid, float) and np.isnan(rid)):
        return None
    return "P" if rid == "P" else str(rid)


def rid_int(n: str | None) -> int | None:
    return int(n[1:]) if n and n.startswith("r") else None


# ---------------------------------------------------------------- tafarrud

def anchors(v: pd.DataFrame, W: World) -> pd.DataFrame:
    """(X, Y) for every tafarrud-type claim: X the narrator the claim is relative to, Y the one alone from him."""
    rows = []
    prev_y: dict[int, str] = {}
    for r in v.itertuples(index=False):
        fam = r.family
        X = Y = None
        how = None
        hid = int(r.hadith_id)
        hchains = [c for c in (W.chains(int(r.group_id)) if r.group_id is not None and not pd.isna(r.group_id) else [])
                   if c[1] == hid]

        def below(xn: str | None) -> str | None:
            """X's student in the hadith's own chain."""
            if xn == "P":
                tops = [c[3][-1] for c in hchains if c[3] and c[3][-1] not in GAPS | {MUBHAM}]
                return f"r{tops[0]}" if tops else None
            x = rid_int(xn)
            for c in hchains:
                if x in c[3]:
                    p = c[3].index(x)
                    if p > 0 and c[3][p - 1] not in GAPS | {MUBHAM}:
                        return f"r{c[3][p - 1]}"
            return None

        def above(yn: str | None) -> str | None:
            y = rid_int(yn)
            for c in hchains:
                if y in c[3]:
                    p = c[3].index(y)
                    if p + 1 < len(c[3]):
                        t = c[3][p + 1]
                        if t not in GAPS | {MUBHAM}:
                            return f"r{t}"
                    elif p + 1 == len(c[3]):
                        return "P"
            return None

        if fam in ("tabarani_lam_yarwi", "tabarani_lam_yarwihi", "bazzar_la_nalam_rawahu"):
            X, Y, how = node(r.x_id), node(r.y_id), "stated"
        elif fam == "wala_anhu_illa":
            X, Y, how = prev_y.get(hid), node(r.y_id), "chained"
        elif fam in ("tabarani_la_yurwa_isnad", "bazzar_la_nalamuhu_wajh"):
            X = node(r.x_id) if r.x_text else "P"
            Y, how = below(X), "student_in_chain"
        elif fam == "tafarrud_bihi":
            Y = node(r.z_id)
            X, how = above(Y), "teacher_in_chain"
        elif fam in ("tirmidhi_la_narifuhu_hadith", "bazzar_min_hadith", "lam_naktubhu") and r.y_text:
            X, Y, how = "P", node(r.y_id), "whole_report"
        elif fam == "abu_nuaym_gharib":
            X = node(r.x_id)
            if r.y_text:
                Y, how = node(r.y_id), "stated"
            else:
                Y, how = below(X), "student_in_chain"
        if Y is not None:
            prev_y[hid] = Y
        rows.append({"claim_id": r.claim_id, "X": X, "Y": Y, "anchor": how})
    return pd.DataFrame(rows)


def score_tafarrud(v: pd.DataFrame, W: World) -> pd.DataFrame:
    fams = {"tabarani_lam_yarwi", "tabarani_lam_yarwihi", "bazzar_la_nalam_rawahu", "wala_anhu_illa",
            "tabarani_la_yurwa_isnad", "bazzar_la_nalamuhu_wajh", "tafarrud_bihi", "tirmidhi_la_narifuhu_hadith",
            "bazzar_min_hadith", "lam_naktubhu", "abu_nuaym_gharib"}
    t = v[v["family"].isin(fams)].copy()
    t["critic_of_claim"] = [claim_critic(r) for _, r in t.iterrows()]
    W.load_graphs(t["group_id"].dropna().unique())
    a = anchors(t, W)
    t = t.merge(a, on="claim_id", how="left")
    out = []
    for r in t.itertuples(index=False):
        res = {"claim_id": r.claim_id, "status": None, "n_breaking": 0, "breaking": None}
        if r.group_id is None or pd.isna(r.group_id):
            res["status"] = "no_group"
        elif r.X is None or r.Y is None:
            res["status"] = "unresolved"
        else:
            gid = int(r.group_id)
            succ, contd = W.graph(gid)
            on_nodes = set(succ) | {w for ws in succ.values() for w in ws}
            if r.X not in on_nodes:
                res["status"] = "x_not_on_path"
            elif r.Y not in on_nodes:
                res["status"] = "y_not_on_path"
            else:
                # «إلا Y1 وY2»: the other named narrators directly below X in the group's chains join Y
                ys = [r.Y]
                alts = list(r.y_alt_ids) if r.y_alt_ids is not None and r.anchor == "stated" else []
                if alts:
                    xi = rid_int(r.X)
                    below = {c[3][c[3].index(xi) - 1] for c in W.chains(gid) if xi in c[3] and c[3].index(xi) > 0}
                    ys += [a for a in alts if rid_int(a) in below]
                res["Y_set"] = ys
                if reaches_book_avoiding(succ, r.X, ys):
                    res["status"] = "fails"
                    res.update(breaking_routes(W, gid, r, contd, ys))
                else:
                    res["status"] = "holds"
        out.append(res)
    s = pd.DataFrame(out)
    return t.merge(s, on="claim_id")


def breaking_routes(W: World, gid: int, r, contd: dict, ys=None) -> dict:
    """The attested chains of the group through X that avoid Y (every narrator of the Y slot) below him."""
    x, y = rid_int(r.X), rid_int(r.Y)
    yset = {rid_int(a) for a in (ys or [r.Y])}
    crit_d = CRITIC_DEATH.get(r.critic_of_claim)
    rows = []
    for sid, hid, bid, ch in W.chains(gid):
        if r.X == "P":
            if not ch or ch[-1] in GAPS | {MUBHAM} or yset & set(ch):
                continue
            p = len(ch)
            if int(W.rw.loc[ch[-1], "rank_no"]) != 1:
                continue
        else:
            if x not in ch:
                continue
            p = ch.index(x)
            if yset & set(ch[:p]):
                continue
        seg = ch[:p]
        if not seg:
            continue
        nodes = [f"r{q}" for q in ch]
        incompat = [(nodes[i + 1], nodes[i]) for i in range(len(ch) - 1)
                    if contd.get((nodes[i + 1], nodes[i])) == "incompatible"]
        w = ch[p - 1] if p - 1 >= 0 else None
        namesake = False
        if w is not None and y is not None and w not in GAPS | {MUBHAM}:
            cw = conditional._cand(w, 1, W.rw.loc[w, "name"], W.rw.loc[w, "nickname"])
            cy = conditional._cand(y, 1, W.rw.loc[y, "name"], W.rw.loc[y, "nickname"])
            namesake = (cw.ism == cy.ism and (cw.father or "") == (cy.father or "") and cw.father is not None) \
                or (W.cluster.get(w) is not None and W.cluster.get(w) == W.cluster.get(y))
        bd = W.books.loc[bid, "author_death_year"] if bid in W.books.index else None
        bd = None if bd is None or pd.isna(bd) else int(bd)
        own = W.books.loc[bid, "author_name"] if bid in W.books.index else None
        when = None
        if bd is not None and crit_d is not None:
            when = "earlier" if bd < crit_d else ("same_generation" if bd == crit_d else "later")
        x_link_bad = any(e == (f"r{x}" if x else "P", f"r{w}") for e in incompat) if w is not None else False
        rows.append({"sanad_id": sid, "hadith_id": hid, "book_id": bid, "book_death": bd, "when": when,
                     "own_book": bool(r.book_id == bid or (r.critic_of_claim == "al-Tabarani" and bid in (65, 66, 67, 45, 386))
                                      or (r.critic_of_claim == "al-Bazzar" and bid in (35, 36))),
                     "below_x": w, "continuity_ok": not incompat, "x_link_incompatible": x_link_bad,
                     "namesake_of_y": namesake})
    if not rows:
        return {"n_breaking": 0, "breaking": json.dumps([]), "break_kind": "spliced_route_only"}
    order = {"earlier": 0, "same_generation": 1, "later": 2, None: 3}
    rows.sort(key=lambda z: (not z["own_book"], order[z["when"]], z["sanad_id"]))
    first = rows[0]
    if any(z["own_book"] for z in rows):
        kind = "own_book"
    elif any(z["when"] in ("earlier", "same_generation") for z in rows):
        kind = "earlier_book"
    elif any(z["when"] == "later" for z in rows):
        kind = "later_book_only"
    else:
        kind = "undated_book"
    mis = all(z["namesake_of_y"] or z["x_link_incompatible"] for z in rows)
    return {"n_breaking": len(rows), "breaking": json.dumps(rows[:12], ensure_ascii=False, default=int),
            "break_kind": kind, "all_misresolution_candidates": mis,
            "all_breaking_continuity_ok": all(z["continuity_ok"] for z in rows),
            "first_breaking_book": first["book_id"], "first_breaking_when": first["when"]}


# ---------------------------------------------------------------- gharib, hasan, verdict words

def chain_codes(W: World, hadith_id: int) -> dict:
    if not hasattr(W, "_by_hadith"):
        W._by_hadith = {int(h): idx for h, idx in W.ch.groupby("hadith_id").indices.items()}
    idx = W._by_hadith.get(int(hadith_id))
    if idx is None:
        return {}
    c = W.ch.iloc[idx]
    out = {"chain_v1": int(c["chain_code"].min()), "chain_v1_source": int(c["chain_code_source"].min()),
           "chain_template": int(c["code_source_template"].min()),
           "chain_level": int(c["level_source_template"].min()) if c["level_source_template"].notna().any() else None}
    for rs in ("ibn_hajar", "ibn_al_salah"):
        for m in ("classical", "source"):
            out[f"chain_v2_{rs}_{m}"] = int(c[f"code_v2_{rs}_{m}"].min())
    return out


def group_codes(W: World, gid) -> dict:
    if gid is None or pd.isna(gid) or int(gid) not in W.rec.index:
        return {}
    g = W.rec.loc[int(gid)]
    out = {"group_v1": g["derived_code_classical"], "group_v1_source": g["derived_code_source"],
           "group_template": g["code_source_template"], "group_recorded": g["matn_no_group"],
           "kappa_all": g["kappa_all"], "kappa_above_matruk": g["kappa_above_matruk"],
           "kappa_saduq_up": g["kappa_saduq_up"], "kappa_thiqa_up": g["kappa_thiqa_up"],
           "number_class": g["number_class"]}
    for rs in ("ibn_hajar", "ibn_al_salah"):
        for m in ("classical", "source"):
            out[f"group_v2_{rs}_{m}"] = g[f"code_v2_{rs}_{m}"]
    return out


def tirmidhi_class(grade: str | None) -> str | None:
    if not grade:
        return None
    w = set(grade.split())
    return " ".join(x for x in ("حسن", "صحيح", "غريب") if x in w)


def score_gharib(v: pd.DataFrame, W: World, taf: pd.DataFrame) -> pd.DataFrame:
    """al-Tirmidhī's gharīb, absolute (κ class) and relative (one student below the anchor)."""
    t = v[(v["family"] == "tirmidhi_verdict") & v["grade"].fillna("").str.contains("غريب")
          | (v["family"] == "tirmidhi_la_narifuhu_wajh")].copy()
    rows = []
    for r in t.itertuples(index=False):
        g = group_codes(W, r.group_id)
        res = {"claim_id": r.claim_id, "kappa_all": g.get("kappa_all"), "number_class": g.get("number_class"),
               "absolute_holds": (g.get("kappa_all") == 1) if g else None, "relative": None, "relative_holds": None}
        if r.family == "tirmidhi_verdict" and r.scope in ("min_hadha_al_wajh", "min_hadith") and not pd.isna(r.group_id):
            gid = int(r.group_id)
            hch = [c for c in W.chains(gid) if c[1] == int(r.hadith_id)]
            succ, _ = W.graph(gid)
            X = None
            if r.scope == "min_hadith":
                X = node(r.x_id)
            elif hch and hch[0][3] and int(W.rw.loc[hch[0][3][-1], "rank_no"]) == 1:
                X = f"r{hch[0][3][-1]}"           # «من هذا الوجه»: relative to the chain's companion
            Y = None
            if X and X != "P":
                for c in hch:
                    xi = rid_int(X)
                    if xi in c[3]:
                        p = c[3].index(xi)
                        if p > 0 and c[3][p - 1] not in GAPS | {MUBHAM}:
                            Y = f"r{c[3][p - 1]}"
                            break
            res["relative"] = f"{X}->{Y}"
            if X and Y:
                on_nodes = set(succ) | {w for ws in succ.values() for w in ws}
                if X in on_nodes and Y in on_nodes:
                    res["relative_holds"] = not reaches_book_avoiding(succ, X, Y)
        rows.append(res)
    return t.merge(pd.DataFrame(rows), on="claim_id") if rows else t


def score_wafi(v: pd.DataFrame, W: World) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every companion named in «وفي الباب»: found in the group / a sibling group / under the grandparent topic."""
    t = v[v["family"] == "wafi_al_bab"].copy()
    con = W.con
    sib = siblings.sibling_groups(con)
    top = con.sql("SELECT id, parent_id, group_id FROM topics").df()
    parent = dict(zip(top["id"], top["parent_id"]))
    leaf_parents = defaultdict(set)
    for tid, pid, gid in zip(top["id"], top["parent_id"], top["group_id"]):
        if gid is not None and not pd.isna(gid):
            leaf_parents[int(gid)].add(pid)
    by_grand = defaultdict(set)
    grand_of = defaultdict(set)
    for gid, ps in leaf_parents.items():
        for p in ps:
            gp = parent.get(p)
            if gp is not None and not pd.isna(gp):
                by_grand[gp].add(gid)
                grand_of[gid].add(gp)
    # chain tops per group: companion rawi ids ending a chain, with the hadith ids
    tops = con.sql("""SELECT h.group_id, sr.rawi_id, h.id FROM sanads s JOIN hadiths h ON h.id = s.hadith_id
                      JOIN sanad_rawis sr ON sr.sanad_id = s.id
                      JOIN (SELECT sanad_id, max(pos) mp FROM sanad_rawis GROUP BY 1) m
                        ON m.sanad_id = s.id AND m.mp = sr.pos
                      JOIN rawis r ON r.id = sr.rawi_id WHERE r.rank_no = 1 AND h.group_id IS NOT NULL""").df()
    comp_groups = defaultdict(set)
    comp_hadith = defaultdict(lambda: defaultdict(set))
    for g, c, h in zip(tops["group_id"], tops["rawi_id"], tops["id"]):
        comp_groups[int(c)].add(int(g))
        comp_hadith[int(g)][int(c)].add(int(h))
    R = verdicts.Resolver(con)
    rows, pairs = [], []
    hids_needed = set()
    for r in t.itertuples(index=False):
        if r.group_id is None or pd.isna(r.group_id):
            continue
        g = int(r.group_id)
        s_groups = set(sib.get(g, ()))
        w_groups = set().union(*[by_grand[gp] for gp in grand_of.get(g, ())]) - {g} if grand_of.get(g) else set()
        scope_groups = {g} | s_groups | w_groups
        cands = sorted({c for gg in scope_groups for c in comp_hadith.get(gg, {})})
        own = {c[3][-1] for c in W.chains(g) if c[1] == int(r.hadith_id) and c[3]}
        ids_links = tuple(sorted((c, len(comp_groups[c])) for c in cands))
        for name in list(r.names) if r.names is not None else []:
            rid, why = R.resolve(name, ids_links) if ids_links else (None, "no_companion_in_scope")
            if rid is None:
                # resolve against every companion of the corpus, to tell "not in scope" from "unresolvable"
                rows.append({"claim_id": r.claim_id, "hadith_id": r.hadith_id, "group_id": g, "name": name,
                             "companion": None, "reason": why, "in_group": False, "in_siblings": False,
                             "in_grandparent": False})
                continue
            c = int(rid[1:])
            rows.append({"claim_id": r.claim_id, "hadith_id": r.hadith_id, "group_id": g, "name": name,
                         "companion": c, "reason": None, "in_group": c in comp_hadith.get(g, {}),
                         "in_siblings": any(c in comp_hadith.get(s, {}) for s in s_groups),
                         "in_grandparent": any(c in comp_hadith.get(s, {}) for s in w_groups)})
            # Dice pairs over the sibling groups: the named companion's matns against the other companions'
            for s in s_groups:
                for cc, hs in comp_hadith.get(s, {}).items():
                    if cc in own:
                        continue
                    pairs.append({"claim_id": r.claim_id, "hadith_id": int(r.hadith_id), "sibling": s, "companion": cc,
                                  "named": cc == c, "hadiths": sorted(hs)})
                    hids_needed.update(hs)
            hids_needed.add(int(r.hadith_id))
    w = pd.DataFrame(rows)
    p = pd.DataFrame(pairs)
    if len(p):
        # a companion of a sibling group is a pair if any «وفي الباب» name of the claim resolved to him
        named = set(zip(w["claim_id"], w["companion"].dropna().astype(int)))
        p["named"] = [(c, k) in named for c, k in zip(p["claim_id"], p["companion"])]
        p = p.drop_duplicates(["claim_id", "sibling", "companion"])
        M = matn.Matns(hids_needed)
        p["dice"] = [max((M.overlap(h, x) for x in hs), default=0.0) for h, hs in zip(p["hadith_id"], p["hadiths"])]
        p = p.drop(columns=["hadiths"])
    return w, p


def score_shart(v: pd.DataFrame, W: World) -> pd.DataFrame:
    t = v[v["family"] == "hakim_shart"].copy()
    pair_b, pair_m = sahih_links(W.con)
    rows = []
    for r in t.itertuples(index=False):
        hch = [c for c in W.chains(int(r.group_id)) if c[1] == int(r.hadith_id)] \
            if r.group_id is not None and not pd.isna(r.group_id) else []
        if not hch:
            rows.append({"claim_id": r.claim_id, "men_ok": None, "pairs_ok": None})
            continue
        ch = hch[0][3]
        men = []
        for p, x in enumerate(ch):
            if p == 0 or x in GAPS or x == MUBHAM:
                continue
            row = W.rw.loc[x]
            dy, tb = row["death_year"], row["tabaka"]
            if (not pd.isna(dy) and dy > 261) or (pd.isna(dy) and tb and tb > 11):
                continue             # after the Ṣaḥīḥayn's generation: al-Ḥākim's own teachers
            men.append(x)
        clause = r.clause
        need_b = clause in ("الشيخين", "البخاري")
        need_m = clause in ("الشيخين", "مسلم")
        bad = [x for x in men if (need_b and not W.rw.loc[x, "is_bukhari"]) or (need_m and not W.rw.loc[x, "is_muslim"])
               or int(W.rw.loc[x, "rank_no"]) == 1 and False]
        bad = [x for x in bad if int(W.rw.loc[x, "rank_no"]) != 1]     # companions are not judged
        links = [(ch[i + 1], ch[i]) for i in range(len(ch) - 1) if ch[i] in men and ch[i + 1] in men
                 and int(W.rw.loc[ch[i + 1], "rank_no"]) != 1]
        miss = [lk for lk in links if (need_b and need_m and lk not in pair_b and lk not in pair_m)
                or (need_b and not need_m and lk not in pair_b) or (need_m and not need_b and lk not in pair_m)
                or (need_b and need_m and not (lk in pair_b or lk in pair_m))]
        rows.append({"claim_id": r.claim_id, "n_men": len(men), "men_ok": not bad, "men_not_in_sahih": bad,
                     "n_links": len(links), "pairs_ok": not miss, "links_not_in_sahih": [list(x) for x in miss]})
    return t.merge(pd.DataFrame(rows), on="claim_id")


def sahih_links(con) -> tuple[set, set]:
    rows = con.sql("""SELECT h.book_id, a.rawi_id, b.rawi_id FROM sanad_rawis a
                      JOIN sanad_rawis b ON b.sanad_id = a.sanad_id AND b.pos = a.pos - 1
                      JOIN sanads s ON s.id = a.sanad_id JOIN hadiths h ON h.id = s.hadith_id
                      WHERE h.book_id IN (1, 2)""").fetchall()
    pb, pm = set(), set()
    for bk, t, s in rows:
        (pb if bk == 1 else pm).add((int(t), int(s)))
    return pb, pm


def score_attribution(v: pd.DataFrame, W: World) -> pd.DataFrame:
    t = v[v["family"] == "sahih_attribution"].copy()
    R = verdicts.Resolver(W.con)
    rows = []
    for r in t.itertuples(index=False):
        if r.group_id is None or pd.isna(r.group_id):
            rows.append({"claim_id": r.claim_id, "attr_status": "no_group"})
            continue
        books = SAHIH_BOOKS.get(r.clause, (1, 2))
        gch = [c for c in W.chains(int(r.group_id)) if c[2] in books]
        teachers = Counter(c[3][1] for c in gch if len(c[3]) > 1)
        if not gch:
            rows.append({"claim_id": r.claim_id, "attr_status": "no_sahih_chain_in_group"})
            continue
        rid, why = R.resolve(r.x_text, tuple(sorted(teachers.items())))
        rows.append({"claim_id": r.claim_id, "attr_status": "teacher_found" if rid else ("teacher_not_found:" + str(why).split(":")[0])})
    return t.merge(pd.DataFrame(rows), on="claim_id")


def score_words(v: pd.DataFrame, W: World) -> pd.DataFrame:
    t = v[v["claim_type"].isin(["verdict", "shart"])].copy()
    rows = []
    for r in t.itertuples(index=False):
        d = {"claim_id": r.claim_id}
        d.update(chain_codes(W, int(r.hadith_id)))
        d.update(group_codes(W, r.group_id))
        rows.append(d)
    return t.merge(pd.DataFrame(rows), on="claim_id")


# ---------------------------------------------------------------- everything

def score(write: bool = True) -> dict[str, pd.DataFrame]:
    v = pd.read_parquet(verdicts.out_path())
    W = World()
    taf = score_tafarrud(v, W)
    out = {"tafarrud": taf, "gharib": score_gharib(v, W, taf), "words": score_words(v, W),
           "shart": score_shart(v, W), "attribution": score_attribution(v, W)}
    wafi, pairs = score_wafi(v, W)
    out["wafi"], out["pairs"] = wafi, pairs
    if write:
        write_results(v, out)
        d = paths.OUT_DIR / "critics"
        d.mkdir(parents=True, exist_ok=True)
        for k, df in out.items():
            df2 = df.copy()
            for c in df2.columns:
                if df2[c].dtype == object and df2[c].map(lambda z: isinstance(z, (list, np.ndarray))).any():
                    df2[c] = df2[c].map(lambda z: json.dumps(list(z), ensure_ascii=False, default=int)
                                        if isinstance(z, (list, np.ndarray)) else z)
            df2.to_parquet(d / f"{k}.parquet", index=False)
    return out


def result_text(row, kind: str) -> str:
    """One short line on what scoring found, for out/verdicts.parquet `result` (the site requires the column and
    publishes the file in its Downloads; kept short, since the file counts toward the site's size budget)."""
    def ok(x):
        return x is not None and x == x
    if kind == "tafarrud":
        st = row.get("status")
        X = "the Prophet" if row.get("X") == "P" else row.get("X")
        if st == "holds":
            return f"holds: from {X}, every route passes {row.get('Y')}"
        if st == "fails":
            how = {"own_book": "in his own works", "earlier_book": "in an earlier book",
                   "later_book_only": "in later books only", "spliced_route_only": "spliced"}.get(row.get("break_kind"), "")
            return f"not here: {X} has another route ({how}, {int(row.get('n_breaking') or 0)})"
        return {"x_not_on_path": "untestable: the anchor is on no route", "y_not_on_path": "untestable: the named "
                "narrator is on no route", "unresolved": "untestable: a name unresolved",
                "no_group": "untestable: no group"}.get(st, "not scored")
    if kind == "gharib":
        s = f"κ_all {int(row['kappa_all'])}" if ok(row.get("kappa_all")) else "no κ"
        if ok(row.get("relative_holds")):
            s += "; relative: " + ("one student" if row["relative_holds"] else "several students")
        return s
    if kind == "shart":
        if not ok(row.get("men_ok")):
            return "untestable"
        s = "men in the named Ṣaḥīḥ" if row["men_ok"] else \
            f"outside the named Ṣaḥīḥ: {len(row.get('men_not_in_sahih') or [])}"
        return s + ("; pairings too" if row.get("pairs_ok") else "")
    if kind == "attribution":
        return "the Ṣaḥīḥ chain through him is in this group" if row.get("attr_status") == "teacher_found" else \
            "not in this group"
    if kind == "words":
        parts = [f"{lab} {int(row[c])}" for c, lab in (("chain_template", "template"), ("chain_v1", "v1"),
                                                         ("chain_v2_ibn_hajar_classical", "v2"),
                                                         ("group_v2_ibn_hajar_classical", "group v2"), ("kappa_all", "κ"))
                 if ok(row.get(c))]
        return " · ".join(parts) or "not scored"
    return "not scored"


def write_results(v: pd.DataFrame, out: dict[str, pd.DataFrame]) -> None:
    """Fill out/verdicts.parquet `result` from the scores (the claim's own row in each scored table)."""
    nick = dict(data.views().sql("SELECT id, nickname FROM rawis").fetchall())

    def nm(n):
        return n if not (isinstance(n, str) and n.startswith("r")) else nick.get(int(n[1:]), n)
    res: dict[int, str] = {}
    t = out.get("tafarrud")
    if t is not None and len(t):
        t = t.copy()
        t["X"] = t["X"].map(nm)
        t["Y"] = [" / ".join(nm(y) for y in ys) if isinstance(ys, list) and ys else nm(y)
                  for ys, y in zip(t.get("Y_set", [None] * len(t)), t["Y"])]
        out = {**out, "tafarrud": t}
    for kind in ("words", "attribution", "shart", "gharib", "tafarrud"):
        df = out.get(kind)
        if df is None or not len(df):
            continue
        for row in df.to_dict("records"):
            res[int(row["claim_id"])] = result_text(row, kind)
    wf = out.get("wafi")
    if wf is not None and len(wf):
        for cid, x in wf.groupby("claim_id"):
            found = x["in_group"] | x["in_siblings"] | x["in_grandparent"]
            res[int(cid)] = f"{int(found.sum())} of {len(x)} named companions found (group, siblings or topic)"
    v = v.copy()
    v["result"] = [res.get(int(c), "not scored") for c in v["claim_id"]]
    v.to_parquet(verdicts.out_path(), index=False)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("score", "all"):
        out = score()
        print({k: len(v) for k, v in out.items()})
    if cmd in ("report", "all"):
        from itibar import critics_report
        print(critics_report.write())


if __name__ == "__main__":
    main()
