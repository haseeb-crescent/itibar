"""Derived grade v2: the classical ladder with corroboration (i'tibar).

Every chain is classified by its defects (config/grades.yaml: weakness):

  light         Taqrib levels 5-8 above the ruleset's hasan level; mursal (no
                companion at the top, or an irsal marker there); a mudallis's
                mu'an'an link
  unrepairable  level 9 (majhul al-'ayn); undescribed or unnamed narrators below
                the companion slot
  fatal         levels 10-12; inqita' and ta'liq markers (an irsal marker
                anywhere but the top)

and graded by the ruleset (config/structure.yaml: derive.rulesets):

  unrepairable or fatal defect   -> the v1 code, never upgraded          (not_repairable / fatal)
  light defects, corroborated    -> 1                                    (hasan_li_ghayrihi)
  light defects, uncorroborated  -> 2                                    (daif)
  no defect, weakest <= sahih    -> 0                                    (sahih_li_dhatihi)
  no defect, weakest <= hasan    -> 1, or 0 with an independent route of
                                    hasan-or-better grade                (hasan_li_dhatihi / sahih_li_ghayrihi)

A chain c is corroborated when the bundle has a PROPHET -> book route, in the
graph at `witness_threshold` restricted to light-or-better narrators, that
avoids every node of c's defect set W (vertex connectivity with W removed,
at least `min_corroborating_routes`). The witness recorded is an attested chain
where one exists, else one route of the flow. Its divergence class is read off
the deepest node it shares with c above c's topmost weak node: the weak
narrator's own teacher and the same companion -> mutabaa_tamma; the same
companion higher up -> mutabaa_qasira; a different companion -> shahid; for a
mursal chain, a witness through the mursil himself -> wasl, else shahid.
Every quantity is defined in README.md, every choice in DECISIONS.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from itibar import config, structure
from itibar.bundle import PROPHET, SINK, Bundle, ChainInfo
from itibar.derive import ChainGrade
from itibar.flow import vertex_connectivity
from itibar.load import Chain, Corpus

LIGHT, UNREPAIRABLE, FATAL = "light", "unrepairable", "fatal"
UPGRADE_RULES = ("hasan_li_ghayrihi", "sahih_li_ghayrihi")
RULE_CODES = {"sahih_li_dhatihi": 0, "sahih_li_ghayrihi": 0, "hasan_li_dhatihi": 1, "hasan_li_ghayrihi": 1, "daif": 2}


# ---------------------------------------------------------------- parameters

@dataclass(frozen=True)
class Params:
    name: str
    sahih_max_level: int
    hasan_max_level: int
    light_levels: frozenset[int]          # effective: light minus hasan-level, minus 8 when switched off
    unrepairable_levels: frozenset[int]
    fatal_levels: frozenset[int]
    light_includes_level_8: bool
    unknown: str                          # unrepairable | light
    witness_threshold: str
    min_routes: int
    witness_min: str                      # light | not_below
    avoid: str                            # light_defects | weakest
    mursal_rule: str                      # ibn_hajar | shafii
    top_mubham: str                       # mursal | unknown
    muanan_words: frozenset[str]

    @property
    def light_or_better_max_level(self) -> int:
        return max(self.light_levels | {self.hasan_max_level})


def _params(name: str, over: dict) -> Params:
    g = config.load("grades")["weakness"]
    s = config.load("structure")
    c = s["derive"]["corroboration"]
    merged = {**g, **c, **over}
    hasan_max = int(merged["hasan_max_level"])
    light = {int(x) for x in merged["light"]} - set(range(1, hasan_max + 1))
    unrep = {int(x) for x in merged["unrepairable"]}
    if not merged["light_includes_level_8"] and 8 in light:
        light.discard(8)
        unrep.add(8)
    return Params(
        name=name, sahih_max_level=int(merged["sahih_max_level"]), hasan_max_level=hasan_max,
        light_levels=frozenset(light), unrepairable_levels=frozenset(unrep),
        fatal_levels=frozenset(int(x) for x in merged["fatal"]),
        light_includes_level_8=bool(merged["light_includes_level_8"]), unknown=str(merged["unknown"]),
        witness_threshold=str(merged["witness_threshold"]), min_routes=int(merged["min_corroborating_routes"]),
        witness_min=str(merged["witness_min"]), avoid=str(merged["avoid"]), mursal_rule=str(merged["mursal_rule"]),
        top_mubham=str(merged["top_mubham"]), muanan_words=frozenset(s["continuity"]["muanan_words"]),
    )


def rulesets() -> dict[str, Params]:
    """Every ruleset in derive.rulesets, then alt_<variant> on top of the default ruleset."""
    d = config.load("structure")["derive"]
    out = {name: _params(name, rs) for name, rs in d["rulesets"].items()}
    base = d["rulesets"][d["ruleset"]]
    for v, over in (d.get("variants") or {}).items():
        out[f"alt_{v}"] = _params(f"alt_{v}", {**base, **over})
    return out


def ruleset_names() -> list[str]:
    return list(config.load("structure")["derive"]["rulesets"])


# ---------------------------------------------------------------- chain classes

@dataclass
class ChainClass:
    idx: int
    sanad_id: int
    nodes: list[str]
    ordinal: int
    v1_code: int
    connected: bool
    ends_companion: bool
    defects: list[tuple[int, str, str]] = field(default_factory=list)   # (pos, class, reason)
    hasan_pos: list[int] = field(default_factory=list)
    mursil_pos: int | None = None
    max_level: int | None = None          # weakest described level over graded positions

    def positions(self, cls: str) -> list[int]:
        return [p for p, c, _ in self.defects if c == cls]

    @property
    def blocking(self) -> tuple[int, str, str] | None:
        for want in (FATAL, UNREPAIRABLE):
            for d in self.defects:
                if d[1] == want:
                    return d
        return None

    @property
    def light_ok(self) -> bool:
        return self.blocking is None

    @property
    def defect_free(self) -> bool:
        return not self.defects


def classify(i: int, ch: Chain, info: ChainInfo, g: ChainGrade, B: Bundle, corpus: Corpus, P: Params) -> ChainClass:
    nar = corpus.narrators
    r, nodes = ch.rawis, info.nodes
    n = len(r)
    top = n - 1
    cc = ChainClass(idx=i, sanad_id=ch.sanad_id, nodes=nodes, ordinal=g.ordinal, v1_code=g.code,
                    connected=info.connected, ends_companion=info.ends_companion)
    graded = set(g.graded_positions)
    levels = []
    for p in range(n):
        rid = r[p]
        kind = B.kind[nodes[p]]
        if kind == "gap":
            pk = nar.placeholder_kind[rid]
            if pk == "irsal" and p == top:
                continue                                  # mursal: handled below
            cc.defects.append((p, FATAL, f"break_{pk}" + ("" if pk != "irsal" else "_not_at_top")))
            continue
        if p not in graded:
            continue
        if kind == "mubham" or (kind == "narrator" and nar.is_stub[rid]):
            if p == top and kind == "mubham" and P.top_mubham == "mursal":
                continue                                  # unnamed person in the companion slot: mursal
            cc.defects.append((p, UNREPAIRABLE if P.unknown == "unrepairable" else LIGHT,
                               "unnamed_narrator" if kind == "mubham" else "undescribed_narrator"))
            continue
        lv = int(nar.rank_no[rid])
        levels.append(lv)
        if lv in P.fatal_levels:
            cc.defects.append((p, FATAL, f"level_{lv}"))
        elif lv in P.unrepairable_levels:
            cc.defects.append((p, UNREPAIRABLE, f"level_{lv}"))
        elif lv in P.light_levels:
            cc.defects.append((p, LIGHT, f"level_{lv}"))
        elif P.sahih_max_level < lv <= P.hasan_max_level:
            cc.hasan_pos.append(p)
    cc.max_level = max(levels) if levels else None
    # mursal: no companion at the top
    if not info.ends_companion:
        if B.kind[nodes[top]] == "gap" or (B.kind[nodes[top]] == "mubham" and P.top_mubham == "mursal"):
            mp = top - 1
        else:
            mp = top
        if mp >= 0 and B.kind[nodes[mp]] in ("narrator", "mubham"):
            cc.mursil_pos = mp
        cc.defects.append((cc.mursil_pos if cc.mursil_pos is not None else top, LIGHT, "mursal"))
    # a mudallis's mu'an'an link: student at p, teacher at p+1
    for p in range(n - 1):
        if p not in graded or B.kind[nodes[p]] != "narrator" or B.kind[nodes[p + 1]] != "narrator":
            continue
        if not nar.has_tadlis[r[p]]:
            continue
        w = ch.words.get(p + 1)
        if w and w[0] in P.muanan_words:
            cc.defects.append((p, LIGHT, "mudallis_muanan"))
    if not graded:
        cc.defects.append((0, UNREPAIRABLE, "no_graded_narrator"))
    return cc


# ---------------------------------------------------------------- per-group engine

@dataclass
class Verdict:
    code: int
    rule: str
    weak_positions: list[int]
    weak_nodes: list[str]
    witness_sanad: int | None = None
    witness_route: list[str] | None = None
    witness_attested: bool | None = None
    divergence: str | None = None
    joins_at: str | None = None
    routes: int | None = None
    blocking: tuple | None = None
    defects: list[str] = field(default_factory=list)      # reasons, e.g. level_6, mursal, mudallis_muanan


class Engine:
    """Corroboration for one bundle. Caches threshold graphs and reachability by
    (floor, W) so groups with thousands of chains stay fast."""

    def __init__(self, B: Bundle, corpus: Corpus, chains: list[Chain], grades: list[ChainGrade]):
        self.B, self.corpus, self.chains, self.grades = B, corpus, chains, grades
        info_by = {c.sanad_id: c for c in B.chains}
        self.infos = [info_by[c.sanad_id] for c in chains]
        self.unc = structure.uncuttable(B)
        self._succ: dict[int, dict] = {}
        self._reach: dict[tuple, tuple] = {}
        self._witness: dict[tuple, tuple] = {}
        self.node_mask: dict[str, int] = {}
        for i, info in enumerate(self.infos):
            bit = 1 << i
            for v in set(info.nodes):
                self.node_mask[v] = self.node_mask.get(v, 0) | bit
        self.order = sorted(range(len(chains)), key=lambda i: (-grades[i].ordinal, not self.infos[i].connected,
                                                                chains[i].sanad_id))

    def succ(self, floor: int) -> dict:
        s = self._succ.get(floor)
        if s is None:
            s = self._succ[floor] = structure.threshold_succ(self.B, self.corpus, floor)
        return s

    def routes_avoiding(self, floor: int, W: frozenset[str], k: int) -> tuple[int, list[str] | None]:
        """(number of vertex-disjoint routes found, capped at k; one route) in the
        floor graph with the nodes of W removed."""
        key = (floor, W, k)
        hit = self._reach.get(key)
        if hit is not None:
            return hit
        succ = self.succ(floor)
        if k <= 1:
            parent: dict[str, str | None] = {PROPHET: None}
            frontier = [PROPHET]
            found = False
            while frontier and not found:
                nxt = []
                for u in frontier:
                    for v in sorted(succ.get(u, ())):
                        if v in parent or v in W:
                            continue
                        parent[v] = u
                        if v == SINK:
                            found = True
                            break
                        nxt.append(v)
                    if found:
                        break
                frontier = nxt
            if found:
                route, v = [], parent[SINK]
                while v is not None:
                    route.append(v)
                    v = parent[v]
                res = (1, route[::-1])
            else:
                res = (0, None)
        else:
            sub = {u: {v for v in vs if v not in W} for u, vs in succ.items() if u not in W}
            fr = vertex_connectivity(sub, PROPHET, SINK, self.unc)
            res = (min(fr.value, k), [v for v in fr.routes[0] if v != SINK] if fr.routes else None)
        self._reach[key] = res
        return res

    def attested_witness(self, eligible: int, W: frozenset[str], exclude_idx: int) -> int | None:
        """Best eligible chain (preference order) containing no node of W, other
        than the chain itself."""
        key = (eligible, W)
        top2 = self._witness.get(key)
        if top2 is None:
            excl = 0
            for v in W:
                excl |= self.node_mask.get(v, 0)
            cand = eligible & ~excl
            found: list[int] = []
            if cand:
                for i in self.order:
                    if cand >> i & 1:
                        found.append(i)
                        if len(found) == 2:
                            break
            top2 = self._witness[key] = tuple(found)
        for i in top2:
            if i != exclude_idx:
                return i
        return None


def _ordinal_of_level(level: int) -> int:
    return 13 - level


def divergence(c: ChainClass, wnodes: list[str], w_ends_companion: bool, top_weak: int | None) -> tuple[str, str | None]:
    shared = set(wnodes)
    comp_w = None
    if wnodes:
        if wnodes[0] == PROPHET:
            comp_w = wnodes[1] if len(wnodes) > 1 else None
        elif w_ends_companion:
            comp_w = wnodes[-1]
    t = top_weak if top_weak is not None else (c.mursil_pos if c.mursil_pos is not None else 0)
    joins = next((c.nodes[p] for p in range(t + 1, len(c.nodes)) if c.nodes[p] in shared), None)
    if c.ends_companion:
        comp_c = c.nodes[-1]
        if comp_w == comp_c:
            teacher = c.nodes[t + 1] if t + 1 < len(c.nodes) else None
            return ("mutabaa_tamma" if joins == teacher else "mutabaa_qasira"), joins
        return "shahid", joins
    m = c.nodes[c.mursil_pos] if c.mursil_pos is not None else None
    return ("wasl" if m is not None and m in shared else "shahid"), joins


def weak_positions(cc: ChainClass, P: Params, corpus: Corpus, B: Bundle) -> list[int]:
    """The set W a corroborating route must avoid, as positions of the chain.

      avoid = weakest        the light-defect narrators of the lowest grade (the
                             brief's "weakest positions"); with no graded light
                             narrator, the structural light defects (a mudallis's
                             mu'an'an link)
      avoid = light_defects  every light-defect position
    The mursal defect: under mursal_rule ibn_hajar the mursil is not avoided (any
    connected route repairs it) unless he carries another selected defect; under
    shafii he is always avoided (the witness must come through other people)."""
    by_pos: dict[int, set[str]] = {}
    for p, cls, why in cc.defects:
        if cls == LIGHT:
            by_pos.setdefault(p, set()).add(why)
    level = [p for p, ws in by_pos.items() if any(w.startswith("level_") for w in ws)]
    structural = [p for p, ws in by_pos.items() if ws - {"mursal"} and not any(w.startswith("level_") for w in ws)]
    if P.avoid == "weakest":
        if level:
            o = {p: int(corpus.narrators.ordinal[B.rawi[cc.nodes[p]]]) for p in level}
            lo = min(o.values())
            wpos = {p for p in level if o[p] == lo}
        else:
            wpos = set(structural)
    else:
        wpos = set(level) | set(structural)
    if P.mursal_rule == "shafii" and cc.mursil_pos is not None and any(d[2] == "mursal" for d in cc.defects):
        wpos.add(cc.mursil_pos)
    return sorted(wpos)


def grade_group(B: Bundle, corpus: Corpus, chains: list[Chain], grades: list[ChainGrade],
                params: dict[str, Params] | None = None) -> dict[str, list[Verdict]]:
    """ruleset name -> one Verdict per chain (same order as `chains`)."""
    params = params or rulesets()
    eng = Engine(B, corpus, chains, grades)
    thresholds = corpus.scale.thresholds
    out: dict[str, list[Verdict]] = {}
    for name, P in params.items():
        classes = [classify(i, c, eng.infos[i], g, B, corpus, P) for i, (c, g) in enumerate(zip(chains, grades))]
        base_floor = int(thresholds[P.witness_threshold])
        light_floor = max(base_floor, _ordinal_of_level(P.light_or_better_max_level))
        hasan_floor = max(base_floor, _ordinal_of_level(P.hasan_max_level))
        light_conn = hasan_conn = mursal_only = 0
        for cc in classes:
            bit = 1 << cc.idx
            if cc.light_ok and cc.connected:
                light_conn |= bit
                if cc.defect_free:
                    hasan_conn |= bit
            elif cc.light_ok and not cc.ends_companion and cc.mursil_pos is not None:
                mursal_only |= bit
        ge_mask: dict[int, int] = {}

        def at_least(o: int, classes=classes, ge_mask=ge_mask) -> int:
            m = ge_mask.get(o)
            if m is None:
                m = 0
                for c2 in classes:
                    if c2.ordinal >= o:
                        m |= 1 << c2.idx
                ge_mask[o] = m
            return m

        verdicts: list[Verdict] = []
        for cc in classes:
            b = cc.blocking
            if b is not None:
                verdicts.append(Verdict(code=cc.v1_code, rule="fatal" if b[1] == FATAL else "not_repairable",
                                        weak_positions=[b[0]], weak_nodes=[cc.nodes[b[0]]], blocking=b))
                continue
            if cc.defects:
                wpos = weak_positions(cc, P, corpus, B)
                is_mursal = any(d[2] == "mursal" for d in cc.defects)
                W = frozenset(cc.nodes[p] for p in wpos if B.kind[cc.nodes[p]] != "gap")
                floor = light_floor
                elig = light_conn
                if P.witness_min == "not_below":
                    floor = max(floor, cc.ordinal)
                    elig &= at_least(cc.ordinal)
                k = P.min_routes
                nroutes, route = eng.routes_avoiding(floor, W, k)
                wit = None
                ends_c = True
                if nroutes >= k:
                    wit = eng.attested_witness(elig, W, cc.idx)
                elif is_mursal and P.mursal_rule == "shafii":
                    # a mursal whose mursil is another person, avoiding W (which holds this mursil)
                    m_elig = mursal_only & (at_least(cc.ordinal) if P.witness_min == "not_below" else -1)
                    mursil = cc.nodes[cc.mursil_pos] if cc.mursil_pos is not None else None
                    if mursil is not None:
                        m_elig &= ~eng.node_mask.get(mursil, 0)
                    wit = eng.attested_witness(m_elig, W, cc.idx)
                    if wit is not None:
                        nroutes, route, ends_c = 1, None, False
                if nroutes >= k:
                    top_weak = max(wpos) if wpos else cc.mursil_pos
                    wn = eng.infos[wit].nodes if wit is not None else route
                    we = eng.infos[wit].ends_companion if wit is not None else ends_c
                    div, joins = divergence(cc, wn, we, top_weak)
                    verdicts.append(Verdict(code=RULE_CODES["hasan_li_ghayrihi"], rule="hasan_li_ghayrihi",
                                            weak_positions=wpos, weak_nodes=sorted(W),
                                            witness_sanad=chains[wit].sanad_id if wit is not None else None,
                                            witness_route=None if wit is not None else route,
                                            witness_attested=wit is not None, divergence=div, joins_at=joins,
                                            routes=nroutes))
                else:
                    verdicts.append(Verdict(code=RULE_CODES["daif"], rule="daif", weak_positions=wpos,
                                            weak_nodes=sorted(W), routes=nroutes))
                continue
            # defect-free: sahih or hasan li-dhatihi
            if cc.max_level is not None and cc.max_level <= P.sahih_max_level:
                verdicts.append(Verdict(code=0, rule="sahih_li_dhatihi", weak_positions=[], weak_nodes=[]))
                continue
            wpos = sorted(cc.hasan_pos)
            if P.avoid == "weakest" and wpos:
                lv = {p: int(corpus.narrators.rank_no[B.rawi[cc.nodes[p]]]) for p in wpos}
                hi = max(lv.values())
                wpos = [p for p in wpos if lv[p] == hi]
            W = frozenset(cc.nodes[p] for p in wpos)
            k = P.min_routes
            nroutes, route = eng.routes_avoiding(hasan_floor, W, k)
            if nroutes >= k:
                wit = eng.attested_witness(hasan_conn, W, cc.idx)
                wn = eng.infos[wit].nodes if wit is not None else route
                we = eng.infos[wit].ends_companion if wit is not None else True
                div, joins = divergence(cc, wn, we, max(wpos) if wpos else None)
                verdicts.append(Verdict(code=0, rule="sahih_li_ghayrihi", weak_positions=wpos, weak_nodes=sorted(W),
                                        witness_sanad=chains[wit].sanad_id if wit is not None else None,
                                        witness_route=None if wit is not None else route,
                                        witness_attested=wit is not None, divergence=div, joins_at=joins,
                                        routes=nroutes))
            else:
                verdicts.append(Verdict(code=1, rule="hasan_li_dhatihi", weak_positions=wpos, weak_nodes=sorted(W),
                                        routes=nroutes))
        for cc, v in zip(classes, verdicts):
            v.defects = sorted({d[2] for d in cc.defects})
        out[name] = verdicts
    return out


def best(verdicts: list[Verdict], chains: list[Chain], grades: list[ChainGrade], infos: list[ChainInfo]) -> int | None:
    """Index of the group's v2 chain: lowest code, then continuous, then highest
    chain grade, then lowest sanad_id (v1's tie order)."""
    if not verdicts:
        return None
    return min(range(len(verdicts)), key=lambda i: (verdicts[i].code, not infos[i].connected,
                                                     -grades[i].ordinal, chains[i].sanad_id))


def receipt(name: str, P: Params, i: int | None, verdicts: list[Verdict], chains: list[Chain],
            grades: list[ChainGrade], B: Bundle, corpus: Corpus) -> list[dict]:
    if i is None:
        return [{"check": "best chain", "rule": "none available", "data": {}, "result": "no grade"}]
    v, ch, g = verdicts[i], chains[i], grades[i]
    nodes = B.chains[[c.sanad_id for c in B.chains].index(ch.sanad_id)].nodes
    steps = [
        {"check": "ruleset", "rule": name,
         "data": {"sahih_max_level": P.sahih_max_level, "hasan_max_level": P.hasan_max_level,
                  "light_levels": sorted(P.light_levels), "unrepairable_levels": sorted(P.unrepairable_levels),
                  "fatal_levels": sorted(P.fatal_levels), "mursal_rule": P.mursal_rule,
                  "witness_threshold": P.witness_threshold, "witness_min": P.witness_min, "avoid": P.avoid},
         "result": name},
        {"check": "chain selection", "rule": "lowest v2 code over all chains; ties: continuous, higher chain grade, lower sanad_id",
         "data": {"sanad_id": ch.sanad_id, "book_id": ch.book_id, "chains": len(chains),
                  "rules_fired": _count(v2.rule for v2 in verdicts)},
         "result": f"sanad {ch.sanad_id}"},
    ]
    if v.blocking is not None:
        p, cls, why = v.blocking
        steps.append({"check": "defect", "rule": f"{cls}: not repaired by other routes",
                      "data": {"pos": p, "node": nodes[p], "reason": why}, "result": f"v1 code {v.code} kept"})
    else:
        steps.append({"check": "positions to avoid",
                      "rule": ("light defects, lowest grade first" if v.rule in ("daif", "hasan_li_ghayrihi")
                               else "hasan-level narrators"),
                      "data": {"positions": v.weak_positions, "nodes": v.weak_nodes,
                               "chain_ordinal": g.ordinal}, "result": f"{len(v.weak_nodes)} node(s) to avoid"})
        if v.rule in UPGRADE_RULES:
            steps.append({"check": "corroborating route",
                          "rule": "PROPHET -> book route avoiding those nodes, light-or-better"
                                  if v.rule == "hasan_li_ghayrihi" else
                                  "independent PROPHET -> book route of hasan-or-better grade avoiding the hasan-level nodes",
                          "data": {"witness_sanad_id": v.witness_sanad, "witness_route": v.witness_route,
                                   "attested": v.witness_attested, "joins_at": v.joins_at, "routes": v.routes},
                          "result": v.divergence})
        elif v.rule in ("daif", "hasan_li_dhatihi"):
            steps.append({"check": "corroborating route", "rule": "no route avoids those nodes",
                          "data": {"routes": v.routes}, "result": "not corroborated"})
    steps.append({"check": "grade", "rule": v.rule, "data": {}, "result": f"code {v.code}"})
    return steps


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def receipt_json(rcpts: dict[str, list[dict]]) -> str:
    return json.dumps(rcpts, ensure_ascii=False)

