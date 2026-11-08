"""Structural analysis of one bundle: layers, width profile, kappa at grade
thresholds (and its pessimistic bound kappa_lower), cut vertices, single
strands, partial common links, common links, bypass paths, terminus and
per-edge continuity. Every quantity is defined in README.md."""

from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field

import networkx as nx

from itibar import config
from itibar.bundle import PROPHET, SINK, Bundle
from itibar.flow import vertex_connectivity
from itibar.load import Corpus

NARRATOR_KINDS = ("narrator", "mubham")


# ---------------------------------------------------------------- helpers

def ordinal_of(B: Bundle, corpus: Corpus, node: str) -> int:
    k = B.kind[node]
    if k == "mubham":
        return 0
    if k == "narrator":
        return int(corpus.narrators.ordinal[B.rawi[node]])
    return 99


def threshold_succ(B: Bundle, corpus: Corpus, min_ordinal: int) -> dict[str, set[str]]:
    """Subgraph of nodes passing the threshold, plus book -> SINK edges."""
    exempt = B.exempt

    def keep(v: str) -> bool:
        k = B.kind[v]
        if k == "gap":
            return False
        if k in ("prophet", "book", "compiler") or v in exempt:
            return True
        return ordinal_of(B, corpus, v) >= min_ordinal

    ok = {v for v in B.kind if keep(v)}
    # A compiler who fails the threshold keeps only his compiler role: edges into
    # compiler nodes (his books). His links as a teacher in other chains are graded.
    compiler_only = {v for v in B.compiler_rawi_nodes if ordinal_of(B, corpus, v) < min_ordinal}
    succ = {}
    for u, vs in B.succ.items():
        if u not in ok:
            continue
        if u in compiler_only:
            succ[u] = {v for v in vs if v in ok and B.kind[v] == "compiler"}
        else:
            succ[u] = {v for v in vs if v in ok}
    for v in ok:
        if B.kind[v] == "book":
            succ.setdefault(v, set()).add(SINK)
    return succ


def reach(succ: dict[str, set[str]], start: str) -> set[str]:
    seen = {start}
    dq = deque([start])
    while dq:
        u = dq.popleft()
        for v in succ.get(u, ()):
            if v not in seen:
                seen.add(v)
                dq.append(v)
    return seen


def reverse(succ: dict[str, set[str]]) -> dict[str, set[str]]:
    pred: dict[str, set[str]] = defaultdict(set)
    for u, vs in succ.items():
        for v in vs:
            pred[v].add(u)
    return pred


def on_path_subgraph(succ: dict[str, set[str]]) -> tuple[set[str], dict[str, set[str]]]:
    fwd = reach(succ, PROPHET)
    bwd = reach(reverse(succ), SINK)
    on = fwd & bwd
    sub = {u: {v for v in vs if v in on} for u, vs in succ.items() if u in on}
    return on, sub


def uncuttable(B: Bundle) -> set[str]:
    return {PROPHET, SINK} | {n for n, k in B.kind.items() if k == "book"}


def lower_succ(B: Bundle, corpus: Corpus, min_ordinal: int, merge: bool = True
               ) -> tuple[dict[str, set[str]], set[str]]:
    """Graph for kappa_lower: stubs dropped and, when `merge`, each homonym
    cluster merged into one node (min ordinal of its members) and unnamed persons
    merged per student. Merging is not monotone — it can splice a dead-end
    half-route of one person onto a half-route of another and so *create* a
    route — so kappa_lower takes the minimum of the merged and unmerged graphs."""
    nar = corpus.narrators

    def m(v: str) -> str | None:
        k = B.kind[v]
        if k == "narrator":
            rid = B.rawi[v]
            if nar.is_stub[rid]:
                return None
            h = int(nar.homonym[rid])
            return f"h{h}" if (merge and h >= 0) else v
        if k == "mubham":
            return v.split("|", 1)[0] + "|*" if merge else v
        if k == "gap":
            return None
        return v

    members: dict[str, list[str]] = defaultdict(list)
    for v in B.kind:
        mv = m(v)
        if mv is not None:
            members[mv].append(v)
    keep, compiler_only = set(), set()
    for mv, vs in members.items():
        kinds = {B.kind[v] for v in vs}
        passes = all(ordinal_of(B, corpus, v) >= min_ordinal for v in vs
                     if B.kind[v] in NARRATOR_KINDS)
        if kinds & {"prophet", "book", "compiler"} or passes:
            keep.add(mv)
        elif any(v in B.compiler_rawi_nodes for v in vs):
            keep.add(mv)
            compiler_only.add(mv)
    succ: dict[str, set[str]] = defaultdict(set)
    for (u, v) in B.edges:
        mu, mv = m(u), m(v)
        if mu is None or mv is None or mu == mv or mu not in keep or mv not in keep:
            continue
        if mu in compiler_only and B.kind[v] != "compiler":
            continue
        succ[mu].add(mv)
    for mv in keep:
        if B.kind.get(members[mv][0]) == "book":
            succ[mv].add(SINK)
    unc = {PROPHET, SINK} | {mv for mv in keep if B.kind.get(members[mv][0]) == "book"}
    return dict(succ), unc


def condensation_order(succ: dict[str, set[str]], nodes: set[str]):
    """SCC condensation with a deterministic topological order (independent of
    set iteration order, hence of the process's string-hash seed)."""
    G = nx.DiGraph()
    G.add_nodes_from(sorted(nodes))
    for u in sorted(succ):
        if u not in nodes:
            continue
        for v in sorted(succ[u]):
            if v in nodes:
                G.add_edge(u, v)
    C = nx.condensation(G)
    first = {c: min(C.nodes[c]["members"]) for c in C}
    order = list(nx.lexicographical_topological_sort(C, key=lambda c: first[c]))
    member = C.graph["mapping"]
    return G, C, order, member


def count_paths(succ: dict[str, set[str]], nodes: set[str], avoid: set[str], cap: int) -> tuple[int, bool, bool]:
    """Number of PROPHET->SINK paths avoiding `avoid`. Returns (count, capped,
    approx) where approx means back edges were dropped to make the graph acyclic."""
    keepn = {v for v in nodes if v not in avoid or v in (PROPHET, SINK)}
    sub = {u: sorted(v for v in succ.get(u, ()) if v in keepn) for u in keepn}
    # iterative DFS from PROPHET; drop back edges
    color: dict[str, int] = {}
    order: list[str] = []
    approx = False
    if PROPHET not in keepn:
        return 0, False, False
    stack = [(PROPHET, iter(sub.get(PROPHET, ())))]
    color[PROPHET] = 1
    dropped: set[tuple[str, str]] = set()
    while stack:
        u, it = stack[-1]
        nxt = next(it, None)
        if nxt is None:
            color[u] = 2
            order.append(u)
            stack.pop()
            continue
        c = color.get(nxt, 0)
        if c == 0:
            color[nxt] = 1
            stack.append((nxt, iter(sub.get(nxt, ()))))
        elif c == 1:
            dropped.add((u, nxt))
            approx = True
    cnt: dict[str, int] = {}
    capped = False
    for u in order:                       # reverse topological (post-order)
        if u == SINK:
            cnt[u] = 1
            continue
        s = 0
        for v in sub.get(u, ()):
            if (u, v) in dropped:
                continue
            s += cnt.get(v, 0)
        if s > cap:
            s, capped = cap, True
        cnt[u] = s
    return cnt.get(PROPHET, 0), capped, approx


# ---------------------------------------------------------------- results

@dataclass
class Structure:
    on_path: set[str]
    layer: dict[str, int]
    layer_source: dict[str, str]
    width: dict[int, int]
    kappa: dict[str, int]
    kappa_lower: dict[str, int]
    kappa_lower_splice: dict[str, bool]
    cut_set: dict[str, list[str]]
    routes_all: list[list[str]]
    cut_vertices: list[str]
    cut_vertices_by: dict[str, list[str]]
    single_strand: set[str]
    pcl: dict[int, set[str]]
    common_links: list[str]
    cl_in_cycle: bool
    bypass_paths: int
    bypass_capped: bool
    paths_total: int
    paths_capped: bool
    paths_approx: bool
    bypass_chains: int
    backward_edges: int
    has_cycle: bool
    edge_continuity: dict[tuple[str, str], str] = field(default_factory=dict)
    edge_muanan: dict[tuple[str, str], str] = field(default_factory=dict)  # yes | no | unknown_word | n/a


def dominator_cut_vertices(sub: dict[str, set[str]], unc: set[str]) -> tuple[list[str], bool]:
    """Cuttable nodes lying on every PROPHET->SINK path (dominators of SINK),
    ordered from PROPHET down; plus whether the graph has a cycle."""
    G = nx.DiGraph()
    for u, vs in sub.items():
        for v in vs:
            G.add_edge(u, v)
    if PROPHET not in G or SINK not in G:
        return [], False
    has_cycle = not nx.is_directed_acyclic_graph(G)
    idom = nx.immediate_dominators(G, PROPHET)
    v = idom.get(SINK)
    chain = []
    while v is not None and v != PROPHET:
        chain.append(v)
        nv = idom.get(v)
        if nv == v:
            break
        v = nv
    return [x for x in reversed(chain) if x not in unc], has_cycle


def layers(B: Bundle, corpus: Corpus, on_path: set[str]) -> tuple[dict[str, int], dict[str, str], int]:
    cfg = config.load("structure")["layers"]
    missing = set(cfg["missing_tabaka"])
    max_back = int(cfg["max_backward"])
    nar = corpus.narrators
    layer: dict[str, int] = {PROPHET: 0}
    source: dict[str, str] = {PROPHET: "fixed"}
    tab = {}
    for v, k in B.kind.items():
        if k == "narrator":
            t = int(nar.tabaka[B.rawi[v]])
            if t not in missing:
                tab[v] = t
    # a narrator earlier than every one of its resolved teachers by > max_back is unusable here
    for v, t in list(tab.items()):
        teachers = [tab[u] for u in B.pred.get(v, ()) if u in tab]
        if teachers and all(tu - t > max_back for tu in teachers):
            del tab[v]
            source[v] = "fallback_backward"
    # resolve in topological order of the condensation; fallback = 1 + latest teacher
    nodes = set(B.kind) - {SINK}
    G, C, order, member = condensation_order(B.succ, nodes)
    comp_nodes = defaultdict(list)
    for v, c in sorted(member.items()):
        comp_nodes[c].append(v)
    for c in order:
        for v in comp_nodes[c]:
            if v in layer:
                continue
            k = B.kind[v]
            if v in tab:
                layer[v] = tab[v]
                source.setdefault(v, "tabaka")
                continue
            ts = [layer[u] for u in B.pred.get(v, ()) if u in layer]
            layer[v] = (max(ts) + 1) if ts else 1
            if k in NARRATOR_KINDS:
                source.setdefault(v, "fallback_missing")
            else:
                source.setdefault(v, k)
    backward = 0
    for (u, v) in B.edges:
        if u in tab and v in tab and tab[v] < tab[u] - max_back:
            backward += 1
    return layer, source, backward


def continuity(B: Bundle, corpus: Corpus) -> tuple[dict, dict]:
    cfg = config.load("structure")["continuity"]
    window = set(cfg["tabaka_window"])
    muanan = set(cfg["muanan_words"])
    nar = corpus.narrators
    cont, mu = {}, {}
    for (u, v), e in B.edges.items():
        if B.kind[u] != "narrator" or B.kind[v] != "narrator":
            cont[(u, v)] = "n/a"
            mu[(u, v)] = "n/a"
            continue
        ru, rv = B.rawi[u], B.rawi[v]
        du, bv = int(nar.death[ru]), int(nar.birth[rv])
        tu, tv = int(nar.tabaka[ru]), int(nar.tabaka[rv])
        if du >= 0 and bv >= 0:
            cont[(u, v)] = "compatible" if du >= bv else "incompatible"
        elif tu > 0 and tv > 0:
            cont[(u, v)] = "compatible" if (tv - tu) in window else "incompatible"
        else:
            cont[(u, v)] = "unknown"
        if nar.has_tadlis[rv]:
            words = [o[2] for o in e.occurrences]
            known = [w for w in words if w is not None]
            if any(w in muanan for w in known):
                mu[(u, v)] = "yes"
            elif known:
                mu[(u, v)] = "no"
            else:
                mu[(u, v)] = "unknown_word"
        else:
            mu[(u, v)] = "not_mudallis"
    return cont, mu


def analyse(B: Bundle, corpus: Corpus) -> Structure:
    cfg = config.load("structure")["structure"]
    scale = corpus.scale
    unc = uncuttable(B)
    kappa, kappa_lower, cut_set, cut_by, lower_splice = {}, {}, {}, {}, {}
    routes_all: list[list[str]] = []
    succ_all = None
    for name, theta in scale.thresholds.items():
        succ = threshold_succ(B, corpus, theta)
        if succ_all is None:
            succ_all = succ
        _, tsub = on_path_subgraph(succ)
        cut_by[name], _ = dominator_cut_vertices(tsub, unc)
        fr = vertex_connectivity(succ, PROPHET, SINK, unc)
        kappa[name] = fr.value
        cut_set[name] = fr.cut
        if name == "all":
            routes_all = [[v for v in r if v != SINK] for r in fr.routes]
        lsucc, lunc = lower_succ(B, corpus, theta, merge=True)
        merged = vertex_connectivity(lsucc, PROPHET, SINK, lunc).value
        usucc, uunc = lower_succ(B, corpus, theta, merge=False)
        unmerged = vertex_connectivity(usucc, PROPHET, SINK, uunc).value
        kappa_lower[name] = min(merged, unmerged)
        lower_splice[name] = merged > unmerged

    on, sub = on_path_subgraph(succ_all)
    layer, lsource, backward = layers(B, corpus, on)
    terminals = B.terminals
    narr_on = {v for v in on if B.kind.get(v) in NARRATOR_KINDS and v not in terminals}
    pred_on = reverse(sub)
    # width profile: on-path narrators (incl. compiler narrators) by layer
    width: Counter = Counter()
    for v in on:
        if B.kind.get(v) in NARRATOR_KINDS:
            width[layer[v]] += 1
    # cut vertices: cuttable dominators of SINK in the on-path graph
    cut_vertices, has_cycle = dominator_cut_vertices(sub, unc)
    # single strands
    ss = {v for v in narr_on if len(pred_on.get(v, ())) == 1 and len(sub.get(v, ())) == 1}
    # PCL: branches whose sub-bundle reaches a book through a non-single-strand
    # narrator, or that reach a compiler/book directly
    nss = {v for v in narr_on if v not in ss}
    G2, C2, order2, member2 = condensation_order(sub, narr_on)
    down_c: dict[int, bool] = {}
    comp_nodes = defaultdict(list)
    for v, c in member2.items():
        comp_nodes[c].append(v)
    for c in reversed(order2):
        val = any(v in nss for v in comp_nodes[c])
        if not val:
            for d in C2.successors(c):
                if down_c[d]:
                    val = True
                    break
        down_c[c] = val
    down = {v: down_c[member2[v]] for v in narr_on}

    def qualifies(w: str) -> bool:
        if w in terminals:
            return True
        return down.get(w, False)

    pcl: dict[int, set[str]] = {}
    nq = {v: sum(1 for w in sub.get(v, ()) if qualifies(w)) for v in narr_on}
    for k in cfg["pcl_k"]:
        pcl[k] = {v for v, q in nq.items() if q >= k}
    # common links: PCL(k) with no PCL ancestor
    kcl = cfg["common_link_k"]
    P = pcl.get(kcl, set())
    common_links: list[str] = []
    cl_in_cycle = False
    if P:
        up_c: dict[int, bool] = {}
        pcl_in = defaultdict(int)
        for v in P:
            pcl_in[member2[v]] += 1
        for c in order2:
            val = False
            for d in C2.predecessors(c):
                if pcl_in[d] or up_c[d]:
                    val = True
                    break
            up_c[c] = val
        for v in P:
            c = member2[v]
            if not up_c[c]:
                if pcl_in[c] > 1:
                    cl_in_cycle = True
                common_links.append(v)
        common_links.sort(key=lambda v: (layer.get(v, 0), v))
    # bypass paths
    cap = int(cfg["path_count_cap"])
    paths_total, paths_capped, approx = count_paths(sub, on, set(), cap)
    if common_links:
        bypass, bcapped, _ = count_paths(sub, on, set(common_links), cap)
    else:
        bypass, bcapped = paths_total, paths_capped
    cls = set(common_links)
    bypass_chains = sum(1 for c in B.chains if c.connected and not (cls & set(c.nodes)))
    cont, mu = continuity(B, corpus)
    return Structure(
        on_path=on, layer=layer, layer_source=lsource, width=dict(sorted(width.items())),
        kappa=kappa, kappa_lower=kappa_lower, kappa_lower_splice=lower_splice, cut_set=cut_set, routes_all=routes_all,
        cut_vertices=cut_vertices, cut_vertices_by=cut_by, single_strand=ss, pcl=pcl, common_links=common_links,
        cl_in_cycle=cl_in_cycle, bypass_paths=bypass, bypass_capped=bcapped,
        paths_total=paths_total, paths_capped=paths_capped, paths_approx=approx,
        bypass_chains=bypass_chains, backward_edges=backward, has_cycle=has_cycle,
        edge_continuity=cont, edge_muanan=mu,
    )


def routes_json(routes: list[list[str]]) -> str:
    return json.dumps(routes, ensure_ascii=False)
