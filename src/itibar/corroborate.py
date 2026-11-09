"""Derived grade v2: the classical ladder with corroboration (i'tibar).

Every chain is classified by its defects (config/grades.yaml: weakness, and
config/structure.yaml: derive.corroboration, derive.tadlis):

  light         Taqrib levels 5-8 above the ruleset's hasan level; mursal (no
                companion at the top, or an irsal marker there); a tier-3 mudallis's
                mu'an'an link not covered by a hearing word (tadlis.tiers)
  unrepairable  level 9 (majhul al-'ayn); unnamed persons below the companion slot not
                named elsewhere in the report (unknown_repair), undescribed narrators;
                a tier-4/5 mudallis's uncovered mu'an'an link (tadlis.tier_4_5)
  fatal         levels 10-12; inqita' and ta'liq markers (an irsal marker
                anywhere but the top)

and graded by the ruleset (config/structure.yaml: derive.rulesets):

  fatal defect                   -> the v1 code, never upgraded          (fatal)
  unrepairable defect            -> max(v1 code, 2), never upgraded      (not_repairable)
  light defects, all covered     -> 1                                    (hasan_li_ghayrihi)
  light defects, one uncovered   -> 2                                    (daif)
  no defect, weakest <= sahih    -> 0                                    (sahih_li_dhatihi)
  no defect, weakest <= hasan    -> 1, or 0 with an independent witness of
                                    hasan-or-better grade               (hasan_li_dhatihi / sahih_li_ghayrihi)

A defect is covered by a witness: one attested chain (one sanads row) that is
continuous, light-or-better itself, and carries none of the nodes to avoid
(`witness: attested`; PR 4's `route` accepted any union-graph route). With `avoid:
each_defect` every light-defect position needs its own witness; `weakest` and
`all_light_defects` ask one witness to avoid a set. Witnesses come from the group, and
with `shahid_scope: siblings` from the sibling groups (siblings.py) when the group has
none. The divergence class is read off the deepest node the witness shares with the
chain above the covered position: the weak narrator's own teacher and the same
companion -> mutabaa_tamma; the same companion higher up -> mutabaa_qasira; a different
companion, or any witness from another group -> shahid; for a mursal chain, a witness
through the mursil himself -> wasl. Every quantity is defined in README.md, every choice
in DECISIONS.md.
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
    avoid: str                            # each_defect | weakest | all_light_defects
    mursal_rule: str                      # ibn_hajar | shafii
    top_mubham: str                       # mursal | unknown
    muanan_words: frozenset[str]
    witness: str = "attested"             # attested | route (PR 4)
    shahid_scope: str = "group"           # group | siblings
    shahid_min_overlap: float = 1.0
    unknown_repair: str = "none"          # none | named_elsewhere
    tadlis_tiers: bool = False
    mudallis_set: str = "source_flag"     # source_flag | union
    untiered_tadlis: int = 3
    tasrih_scope: str = "none"            # none | group | corpus
    hearing_classes: frozenset[str] = frozenset()
    sahihayn_muanan_accepted: bool = False
    sahihayn_book_ids: frozenset[int] = frozenset()
    tier_4_5: str = "not_repairable"      # not_repairable | light

    @property
    def light_or_better_max_level(self) -> int:
        return max(self.light_levels | {self.hasan_max_level})


def _merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _params(name: str, over: dict) -> Params:
    g = config.load("grades")["weakness"]
    s = config.load("structure")
    d = s["derive"]
    c = d["corroboration"]
    merged = _merge({**g, **c, "tadlis": d.get("tadlis") or {}}, over)
    t = merged["tadlis"]
    hasan_max = int(merged["hasan_max_level"])
    light = {int(x) for x in merged["light"]} - set(range(1, hasan_max + 1))
    unrep = {int(x) for x in merged["unrepairable"]}
    if not merged["light_includes_level_8"] and 8 in light:
        light.discard(8)
        unrep.add(8)
    avoid = str(merged["avoid"])
    if avoid == "light_defects":            # PR 4 spelling
        avoid = "all_light_defects"
    return Params(
        name=name, sahih_max_level=int(merged["sahih_max_level"]), hasan_max_level=hasan_max,
        light_levels=frozenset(light), unrepairable_levels=frozenset(unrep),
        fatal_levels=frozenset(int(x) for x in merged["fatal"]),
        light_includes_level_8=bool(merged["light_includes_level_8"]), unknown=str(merged["unknown"]),
        witness_threshold=str(merged["witness_threshold"]), min_routes=int(merged["min_corroborating_routes"]),
        witness_min=str(merged["witness_min"]), avoid=avoid, mursal_rule=str(merged["mursal_rule"]),
        top_mubham=str(merged["top_mubham"]), muanan_words=frozenset(s["continuity"]["muanan_words"]),
        witness=str(merged.get("witness", "route")), shahid_scope=str(merged.get("shahid_scope", "group")),
        shahid_min_overlap=float(merged.get("shahid_min_overlap", 1.0)),
        unknown_repair=str(merged.get("unknown_repair", "none")),
        tadlis_tiers=bool(t.get("tiers", False)), mudallis_set=str(t.get("mudallis_set", "source_flag")),
        untiered_tadlis=int(t.get("untiered_tadlis", 3)), tasrih_scope=str(t.get("tasrih_scope", "none")),
        hearing_classes=frozenset(t.get("hearing_classes") or ()),
        sahihayn_muanan_accepted=bool(t.get("sahihayn_muanan_accepted", False)),
        sahihayn_book_ids=frozenset(int(x) for x in s["qarain"]["sahihayn_book_ids"]),
        tier_4_5=str(t.get("tier_4_5", "not_repairable")),
    )


def rulesets() -> dict[str, Params]:
    """Every ruleset in derive.rulesets, then alt_<variant> on top of the default ruleset."""
    d = config.load("structure")["derive"]
    out = {name: _params(name, rs) for name, rs in d["rulesets"].items()}
    base = d["rulesets"][d["ruleset"]]
    for v, over in (d.get("variants") or {}).items():
        out[f"alt_{v}"] = _params(f"alt_{v}", _merge(base, over))
    return out


def ruleset_names() -> list[str]:
    return list(config.load("structure")["derive"]["rulesets"])


def uses_siblings(params: dict[str, Params]) -> bool:
    return any(P.shahid_scope == "siblings" for P in params.values())


# ---------------------------------------------------------------- group context

@dataclass
class GroupContext:
    """Evidence the classification reads from the whole report (meaning group)."""
    hearing: set[tuple[int, int]] = field(default_factory=set)       # (teacher, student) with a hearing word
    sahih_links: set[tuple[int, int]] = field(default_factory=set)   # (teacher, student) in a chain of the Sahihayn
    named: dict[tuple[str, str], set[int]] = field(default_factory=dict)   # (teacher node, student node) -> named rawi ids between


def group_context(chains: list[Chain], infos: list[ChainInfo], corpus: Corpus, classes: frozenset[str],
                  sahihayn: frozenset[int]) -> GroupContext:
    nar = corpus.narrators
    ctx = GroupContext()
    for ch, info in zip(chains, infos):
        r, nodes = ch.rawis, info.nodes
        in_sahih = ch.book_id in sahihayn
        for p in range(len(r) - 1):
            t, s = r[p + 1], r[p]
            if nar.placeholder_role.get(t) or nar.placeholder_role.get(s):
                continue
            w = ch.words.get(p + 1)
            if w and w[2] in classes:
                ctx.hearing.add((t, s))
            if in_sahih:
                ctx.sahih_links.add((t, s))
        for p in range(1, len(r) - 1):
            rid = r[p]
            if nar.placeholder_role.get(rid) or nar.is_stub[rid]:
                continue
            ctx.named.setdefault((nodes[p + 1], nodes[p - 1]), set()).add(int(rid))
    return ctx


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
    notes: list[tuple[int, str]] = field(default_factory=list)          # (pos, why a would-be defect is not one)
    hasan_pos: list[int] = field(default_factory=list)
    mursil_pos: int | None = None
    max_level: int | None = None          # weakest described level over graded positions
    level_at: dict[int, int] = field(default_factory=dict)              # level used per graded position

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


def _is_mudallis(nar, rid: int, P: Params) -> bool:
    if nar.has_tadlis[rid]:
        return True
    return P.tadlis_tiers and P.mudallis_set == "union" and nar.tadlis_tier is not None and nar.tadlis_tier[rid] > 0


def _tier(nar, rid: int, P: Params) -> int:
    t = int(nar.tadlis_tier[rid]) if nar.tadlis_tier is not None else 0
    return t if t > 0 else P.untiered_tadlis


def _level_class(lv: int, P: Params) -> str | None:
    if lv in P.fatal_levels:
        return FATAL
    if lv in P.unrepairable_levels:
        return UNREPAIRABLE
    if lv in P.light_levels:
        return LIGHT
    return None


def classify(i: int, ch: Chain, info: ChainInfo, g: ChainGrade, B: Bundle, corpus: Corpus, P: Params,
             ctx: GroupContext | None = None) -> ChainClass:
    nar = corpus.narrators
    ctx = ctx or GroupContext()
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
            if kind == "mubham" and P.unknown_repair == "named_elsewhere" and 0 < p < top:
                named = ctx.named.get((nodes[p + 1], nodes[p - 1]))
                lvls = sorted(int(nar.rank_no[x]) for x in named) if named else []
                lvls = [x for x in lvls if x >= 1]
                if lvls:
                    lv = max(lvls)                        # the weakest of the narrators named there
                    cc.notes.append((p, f"unnamed_named_elsewhere_level_{lv}"))
                    levels.append(lv)
                    cc.level_at[p] = lv
                    c = _level_class(lv, P)
                    if c is not None:
                        cc.defects.append((p, c, f"level_{lv}"))
                    elif P.sahih_max_level < lv <= P.hasan_max_level:
                        cc.hasan_pos.append(p)
                    continue
            cc.defects.append((p, UNREPAIRABLE if P.unknown == "unrepairable" else LIGHT,
                               "unnamed_narrator" if kind == "mubham" else "undescribed_narrator"))
            continue
        lv = int(nar.rank_no[rid])
        levels.append(lv)
        cc.level_at[p] = lv
        c = _level_class(lv, P)
        if c is not None:
            cc.defects.append((p, c, f"level_{lv}"))
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
        s, t = r[p], r[p + 1]
        if not _is_mudallis(nar, s, P):
            continue
        w = ch.words.get(p + 1)
        if not (w and w[0] in P.muanan_words):
            continue
        if not P.tadlis_tiers:
            cc.defects.append((p, LIGHT, "mudallis_muanan"))
            continue
        tier = _tier(nar, s, P)
        if tier <= 2:
            cc.notes.append((p, f"muanan_accepted_tier_{tier}"))
            continue
        if P.sahihayn_muanan_accepted and ch.book_id in P.sahihayn_book_ids:
            cc.notes.append((p, f"muanan_accepted_sahihayn_tier_{tier}"))
            continue
        link = (t, s)
        covered = False
        if P.tasrih_scope == "group":
            covered = link in ctx.hearing or (P.sahihayn_muanan_accepted and link in ctx.sahih_links)
        elif P.tasrih_scope == "corpus":
            covered = link in corpus.hearing_pairs or link in ctx.hearing or (
                P.sahihayn_muanan_accepted and link in ctx.sahih_links)
        if covered:
            cc.notes.append((p, f"muanan_covered_tasrih_tier_{tier}"))
            continue
        if tier == 3 or P.tier_4_5 == "light":
            cc.defects.append((p, LIGHT, f"mudallis_muanan_tier_{tier}"))
        else:
            cc.defects.append((p, UNREPAIRABLE, f"mudallis_muanan_tier_{tier}"))
    if not graded:
        cc.defects.append((0, UNREPAIRABLE, "no_graded_narrator"))
    return cc


def classify_group(B: Bundle, corpus: Corpus, chains: list[Chain], grades: list[ChainGrade],
                   params: dict[str, Params]) -> dict[str, list[ChainClass]]:
    info_by = {c.sanad_id: c for c in B.chains}
    infos = [info_by[c.sanad_id] for c in chains]
    ctxs: dict[tuple, GroupContext] = {}
    out = {}
    for name, P in params.items():
        key = (P.hearing_classes, P.sahihayn_book_ids)
        ctx = ctxs.get(key)
        if ctx is None:
            ctx = ctxs[key] = group_context(chains, infos, corpus, P.hearing_classes, P.sahihayn_book_ids)
        out[name] = [classify(i, c, infos[i], g, B, corpus, P, ctx) for i, (c, g) in enumerate(zip(chains, grades))]
    return out


def witness_bits(classes: dict[str, list[ChainClass]], params: dict[str, Params], names: list[str]
                 ) -> list[tuple[int, int]]:
    """Per chain: (light bits, hasan bits) over `names` (bit i <-> names[i])."""
    n = len(next(iter(classes.values()))) if classes else 0
    out = []
    for i in range(n):
        lb = hb = 0
        for j, name in enumerate(names):
            if name not in classes:
                continue
            cc = classes[name][i]
            if cc.light_ok and cc.connected:
                lb |= 1 << j
                if cc.defect_free:
                    hb |= 1 << j
        out.append((lb, hb))
    return out


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
    defects: list[str] = field(default_factory=list)      # reasons, e.g. level_6, mursal, mudallis_muanan_tier_3
    notes: list[str] = field(default_factory=list)        # why would-be defects are not defects
    witnesses: list[dict] = field(default_factory=list)   # one per covered target
    uncovered: list[int] = field(default_factory=list)    # target positions without a witness
    route_exists: bool | None = None                      # every target had a union-graph route avoiding it
    cross_group: bool | None = None
    witness_group: int | None = None


class Engine:
    """Corroboration for one bundle. Caches threshold graphs, reachability and
    witness lookups by (floor, W) so groups with thousands of chains stay fast."""

    def __init__(self, B: Bundle, corpus: Corpus, chains: list[Chain], grades: list[ChainGrade],
                 group_id: int | None = None, siblings=None):
        self.B, self.corpus, self.chains, self.grades = B, corpus, chains, grades
        info_by = {c.sanad_id: c for c in B.chains}
        self.infos = [info_by[c.sanad_id] for c in chains]
        self.unc = structure.uncuttable(B)
        self.group_id = group_id if group_id is not None else B.group_id
        self.siblings = siblings
        self._succ: dict[int, dict] = {}
        self._reach: dict[tuple, tuple] = {}
        self._witness: dict[tuple, tuple] = {}
        self._sib: dict[tuple, list] = {}
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

    def attested_witnesses(self, eligible: int, W: frozenset[str], exclude_idx: int, k: int = 1) -> list[int]:
        """The best k eligible chains (preference order) containing no node of W, other
        than the chain itself."""
        key = (eligible, W, k)
        top = self._witness.get(key)
        if top is None:
            excl = 0
            for v in W:
                excl |= self.node_mask.get(v, 0)
            cand = eligible & ~excl
            found: list[int] = []
            if cand:
                for i in self.order:
                    if cand >> i & 1:
                        found.append(i)
                        if len(found) == k + 1:
                            break
            top = self._witness[key] = tuple(found)
        return [i for i in top if i != exclude_idx][:k]

    def attested_witness(self, eligible: int, W: frozenset[str], exclude_idx: int) -> int | None:
        w = self.attested_witnesses(eligible, W, exclude_idx, 1)
        return w[0] if w else None

    def sibling_witnesses(self, hadith_id: int, W: frozenset[str], param: str, kind: str, min_overlap: float,
                          k: int, min_ordinal: int | None) -> list[tuple[int, float]]:
        if self.siblings is None:
            return []
        key = (hadith_id, W, param, kind, k, min_ordinal)
        hit = self._sib.get(key)
        if hit is None:
            hit = self._sib[key] = self.siblings.find(self.group_id, hadith_id, sorted(W), param, kind, min_overlap,
                                                      k, min_ordinal)
        return hit


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
    """PR 4's single set W (avoid = weakest | all_light_defects), as positions.

      weakest            the light-defect narrators of the lowest grade; with no graded
                         light narrator, the structural light defects
      all_light_defects  every light-defect position
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
            o = {p: 13 - cc.level_at[p] if p in cc.level_at else int(corpus.narrators.ordinal[B.rawi[cc.nodes[p]]])
                 for p in level}
            lo = min(o.values())
            wpos = {p for p in level if o[p] == lo}
        else:
            wpos = set(structural)
    else:
        wpos = set(level) | set(structural)
    if P.mursal_rule == "shafii" and cc.mursil_pos is not None and any(d[2] == "mursal" for d in cc.defects):
        wpos.add(cc.mursil_pos)
    return sorted(wpos)


@dataclass
class Target:
    positions: tuple[int, ...]
    W: frozenset[str]
    mursal: bool = False                  # the target includes the mursal defect


def light_targets(cc: ChainClass, P: Params, corpus: Corpus, B: Bundle) -> list[Target]:
    def node_set(pos) -> frozenset[str]:
        return frozenset(cc.nodes[p] for p in pos if B.kind[cc.nodes[p]] != "gap")

    is_mursal = any(d[2] == "mursal" for d in cc.defects)
    if P.avoid in ("weakest", "all_light_defects"):
        wpos = weak_positions(cc, P, corpus, B)
        return [Target(tuple(wpos), node_set(wpos), is_mursal)]
    by_pos: dict[int, set[str]] = {}
    for p, cls, why in cc.defects:
        if cls == LIGHT and why != "mursal":
            by_pos.setdefault(p, set()).add(why)
    out = [Target((p,), node_set([p])) for p in sorted(by_pos)]
    if is_mursal:
        mp = cc.mursil_pos
        out.append(Target((mp,) if mp is not None else (), node_set([mp]) if (P.mursal_rule == "shafii" and mp is not None)
                          else frozenset(), True))
    return out


def hasan_targets(cc: ChainClass, P: Params) -> list[Target]:
    pos = sorted(cc.hasan_pos)
    if P.avoid == "weakest" and pos:
        hi = max(cc.level_at[p] for p in pos)
        pos = [p for p in pos if cc.level_at[p] == hi]
    if P.avoid in ("weakest", "all_light_defects"):
        return [Target(tuple(pos), frozenset(cc.nodes[p] for p in pos))]
    return [Target((p,), frozenset([cc.nodes[p]])) for p in pos]


def grade_group(B: Bundle, corpus: Corpus, chains: list[Chain], grades: list[ChainGrade],
                params: dict[str, Params] | None = None, siblings=None,
                classes: dict[str, list[ChainClass]] | None = None) -> dict[str, list[Verdict]]:
    """ruleset name -> one Verdict per chain (same order as `chains`)."""
    params = params or rulesets()
    eng = Engine(B, corpus, chains, grades, siblings=siblings)
    thresholds = corpus.scale.thresholds
    classes = classes or classify_group(B, corpus, chains, grades, params)
    out: dict[str, list[Verdict]] = {}
    for name, P in params.items():
        cls = classes[name]
        base_floor = int(thresholds[P.witness_threshold])
        light_floor = max(base_floor, _ordinal_of_level(P.light_or_better_max_level))
        hasan_floor = max(base_floor, _ordinal_of_level(P.hasan_max_level))
        light_conn = hasan_conn = mursal_only = 0
        for cc in cls:
            bit = 1 << cc.idx
            if cc.light_ok and cc.connected:
                light_conn |= bit
                if cc.defect_free:
                    hasan_conn |= bit
            elif cc.light_ok and not cc.ends_companion and cc.mursil_pos is not None:
                mursal_only |= bit
        ge_mask: dict[int, int] = {}

        def at_least(o: int, cls=cls, ge_mask=ge_mask) -> int:
            m = ge_mask.get(o)
            if m is None:
                m = 0
                for c2 in cls:
                    if c2.ordinal >= o:
                        m |= 1 << c2.idx
                ge_mask[o] = m
            return m

        def cover(cc: ChainClass, T: Target, kind: str) -> tuple[dict | None, bool]:
            """A witness for target T (or None), and whether the union graph has a
            route avoiding T.W at the class's floor."""
            floor = light_floor if kind == "light" else hasan_floor
            elig = light_conn if kind == "light" else hasan_conn
            min_ord = None
            if kind == "light" and P.witness_min == "not_below":
                floor = max(floor, cc.ordinal)
                elig &= at_least(cc.ordinal)
                min_ord = cc.ordinal
            k = P.min_routes
            nroutes, route = eng.routes_avoiding(floor, T.W, k)
            route_ok = nroutes >= k
            ws = eng.attested_witnesses(elig, T.W, cc.idx, k)
            top_pos = max(T.positions) if T.positions else cc.mursil_pos
            if len(ws) >= k:
                i = ws[0]
                div, joins = divergence(cc, eng.infos[i].nodes, eng.infos[i].ends_companion, top_pos)
                return ({"positions": list(T.positions), "nodes": sorted(T.W), "witness_sanad": chains[i].sanad_id,
                         "attested": True, "cross_group": False, "group": None, "divergence": div, "joins_at": joins,
                         "witnesses": [chains[j].sanad_id for j in ws]}, route_ok)
            if P.witness == "route" and route_ok:
                return ({"positions": list(T.positions), "nodes": sorted(T.W), "witness_sanad": None,
                         "attested": False, "cross_group": False, "group": None, "route": route, "routes": nroutes,
                         "divergence": divergence(cc, route, True, top_pos)[0],
                         "joins_at": divergence(cc, route, True, top_pos)[1]}, route_ok)
            if T.mursal and P.mursal_rule == "shafii" and kind == "light":
                # a mursal whose mursil is another person, avoiding W (which holds this mursil)
                m_elig = mursal_only & (at_least(cc.ordinal) if P.witness_min == "not_below" else -1)
                mursil = cc.nodes[cc.mursil_pos] if cc.mursil_pos is not None else None
                if mursil is not None:
                    m_elig &= ~eng.node_mask.get(mursil, 0)
                i = eng.attested_witness(m_elig, T.W, cc.idx)
                if i is not None:
                    div, joins = divergence(cc, eng.infos[i].nodes, False, top_pos)
                    return ({"positions": list(T.positions), "nodes": sorted(T.W), "witness_sanad": chains[i].sanad_id,
                             "attested": True, "cross_group": False, "group": None, "divergence": div,
                             "joins_at": joins, "witnesses": [chains[i].sanad_id], "mursal_by_another": True},
                            route_ok)
            if P.shahid_scope == "siblings" and siblings is not None:
                need = k - len(ws)
                sib = eng.sibling_witnesses(chains[cc.idx].hadith_id, T.W, name, kind, P.shahid_min_overlap, need,
                                            min_ord)
                if len(sib) >= need:
                    j, ov = sib[0]
                    return ({"positions": list(T.positions), "nodes": sorted(T.W),
                             "witness_sanad": int(siblings.sanad[j]), "attested": True, "cross_group": True,
                             "group": int(siblings.group[j]), "overlap": round(ov, 4), "divergence": "shahid",
                             "joins_at": None, "witnesses": [chains[x].sanad_id for x in ws]
                             + [int(siblings.sanad[x]) for x, _ in sib]}, route_ok)
            return None, route_ok

        verdicts: list[Verdict] = []
        for cc in cls:
            b = cc.blocking
            if b is not None:
                fatal = b[1] == FATAL
                verdicts.append(Verdict(code=cc.v1_code if fatal else max(cc.v1_code, RULE_CODES["daif"]),
                                        rule="fatal" if fatal else "not_repairable",
                                        weak_positions=[b[0]], weak_nodes=[cc.nodes[b[0]]], blocking=b))
                continue
            if cc.defects:
                targets = light_targets(cc, P, corpus, B)
                kind = "light"
                ok_rule, fail_rule, fail_code = "hasan_li_ghayrihi", "daif", RULE_CODES["daif"]
            elif cc.max_level is not None and cc.max_level <= P.sahih_max_level:
                verdicts.append(Verdict(code=0, rule="sahih_li_dhatihi", weak_positions=[], weak_nodes=[]))
                continue
            else:
                targets = hasan_targets(cc, P)
                kind = "hasan"
                ok_rule, fail_rule, fail_code = "sahih_li_ghayrihi", "hasan_li_dhatihi", 1
                if not targets and P.avoid == "each_defect":
                    verdicts.append(Verdict(code=1, rule="hasan_li_dhatihi", weak_positions=[], weak_nodes=[]))
                    continue
            covered, uncovered, routes_ok = [], [], True
            for T in targets:
                w, rok = cover(cc, T, kind)
                routes_ok &= rok
                if w is None:
                    uncovered.extend(T.positions or [-1])
                else:
                    covered.append(w)
            wpos = sorted({p for T in targets for p in T.positions})
            wnodes = sorted({v for T in targets for v in T.W})
            if not uncovered:
                # the summary witness: the one covering the topmost target (D41)
                top = max(covered, key=lambda w: (max(w["positions"]) if w["positions"] else -1)) if covered else None
                verdicts.append(Verdict(
                    code=RULE_CODES[ok_rule], rule=ok_rule, weak_positions=wpos, weak_nodes=wnodes,
                    witness_sanad=top["witness_sanad"] if top else None,
                    witness_route=top.get("route") if top else None,
                    witness_attested=top["attested"] if top else None,
                    divergence=top["divergence"] if top else None, joins_at=top.get("joins_at") if top else None,
                    routes=top.get("routes") if top else None, witnesses=covered, route_exists=routes_ok,
                    cross_group=any(w["cross_group"] for w in covered) if covered else None,
                    witness_group=top.get("group") if top else None))
            else:
                verdicts.append(Verdict(code=fail_code, rule=fail_rule, weak_positions=wpos, weak_nodes=wnodes,
                                        witnesses=covered, uncovered=sorted(set(uncovered)), route_exists=routes_ok))
        for cc, v in zip(cls, verdicts):
            v.defects = sorted({d[2] for d in cc.defects})
            v.notes = sorted({why for _, why in cc.notes})
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
                  "witness": P.witness, "witness_threshold": P.witness_threshold, "witness_min": P.witness_min,
                  "avoid": P.avoid, "shahid_scope": P.shahid_scope, "shahid_min_overlap": P.shahid_min_overlap,
                  "unknown_repair": P.unknown_repair, "tadlis_tiers": P.tadlis_tiers,
                  "tasrih_scope": P.tasrih_scope, "sahihayn_muanan_accepted": P.sahihayn_muanan_accepted},
         "result": name},
        {"check": "chain selection", "rule": "lowest v2 code over all chains; ties: continuous, higher chain grade, lower sanad_id",
         "data": {"sanad_id": ch.sanad_id, "book_id": ch.book_id, "chains": len(chains),
                  "rules_fired": _count(v2.rule for v2 in verdicts)},
         "result": f"sanad {ch.sanad_id}"},
    ]
    if v.notes:
        steps.append({"check": "not defects", "rule": "mudallis 'an of tiers 1-2, in the Sahihayn, or covered by a "
                                                      "hearing word; unnamed persons named elsewhere in the report",
                      "data": {"notes": v.notes}, "result": f"{len(v.notes)} note(s)"})
    if v.blocking is not None:
        p, cls, why = v.blocking
        steps.append({"check": "defect", "rule": f"{cls}: not repaired by other routes",
                      "data": {"pos": p, "node": nodes[p], "reason": why}, "result": f"code {v.code} kept"})
    else:
        steps.append({"check": "positions to cover",
                      "rule": ({"each_defect": "every light defect, each by a witness of its own",
                                "weakest": "light defects of the lowest grade, one witness",
                                "all_light_defects": "every light defect, one witness"}[P.avoid]
                               if v.rule in ("daif", "hasan_li_ghayrihi") else
                               {"each_defect": "every hasan-level narrator, each by a witness of its own",
                                "weakest": "hasan-level narrators of the highest level, one witness",
                                "all_light_defects": "every hasan-level narrator, one witness"}[P.avoid]),
                      "data": {"positions": v.weak_positions, "nodes": v.weak_nodes, "defects": v.defects,
                               "chain_ordinal": g.ordinal}, "result": f"{len(v.weak_nodes)} node(s) to avoid"})
        if v.rule in UPGRADE_RULES:
            steps.append({"check": "witnesses",
                          "rule": ("an attested continuous light-or-better chain avoiding each position"
                                   if v.rule == "hasan_li_ghayrihi" else
                                   "an attested continuous hasan-or-better chain avoiding each hasan-level position")
                                  + ("; from a sibling group when the report's own group has none"
                                     if P.shahid_scope == "siblings" else ""),
                          "data": {"witnesses": v.witnesses, "route_exists": v.route_exists},
                          "result": v.divergence})
        elif v.rule in ("daif", "hasan_li_dhatihi"):
            steps.append({"check": "witnesses", "rule": "no witness covers these positions",
                          "data": {"uncovered": v.uncovered, "covered": v.witnesses, "route_exists": v.route_exists},
                          "result": "not corroborated"})
    steps.append({"check": "grade", "rule": v.rule, "data": {}, "result": f"code {v.code}"})
    return steps


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def receipt_json(rcpts: dict[str, list[dict]]) -> str:
    return json.dumps(rcpts, ensure_ascii=False)
