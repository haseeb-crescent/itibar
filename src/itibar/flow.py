"""Vertex connectivity between two terminals by node splitting + max flow.

Every cuttable node v becomes v_in -> v_out with capacity 1; uncuttable nodes
(PROPHET, book records, the super-sink) get unbounded capacity. By Menger's
theorem the max flow equals both the minimum number of cuttable nodes whose
removal separates source from sink and the maximum number of internally
vertex-disjoint source->sink routes. We return the value, one minimum cut and
one maximum set of disjoint routes, and assert the two agree.

Unit capacities make BFS augmenting paths (Edmonds-Karp) fast enough here;
tests check the result against networkx on random graphs.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

INF = 1 << 30


@dataclass
class FlowResult:
    value: int
    cut: list            # cuttable nodes forming one minimum vertex cut
    routes: list         # vertex-disjoint routes, each a node list from source to sink


def vertex_connectivity(succ: dict, source, sink, uncuttable: set) -> FlowResult:
    """succ: node -> iterable of successor nodes (only nodes present as keys or
    successors are used). Returns FlowResult. source and sink must be uncuttable."""
    nodes = set(succ)
    for vs in succ.values():
        nodes.update(vs)
    if source not in nodes or sink not in nodes:
        return FlowResult(0, [], [])
    idx: dict = {}
    names: list = []
    for v in sorted(nodes, key=str):          # deterministic across processes
        idx[v] = len(names)
        names.append(v)
    n = len(names)
    # split: in = i, out = i + n for cuttable; uncuttable use out = in
    out_of = [i + n if names[i] not in uncuttable else i for i in range(n)]
    head: list[int] = [-1] * (2 * n)
    to: list[int] = []
    cap: list[int] = []
    nxt: list[int] = []

    def add(u: int, v: int, c: int) -> None:
        to.append(v); cap.append(c); nxt.append(head[u]); head[u] = len(to) - 1
        to.append(u); cap.append(0); nxt.append(head[v]); head[v] = len(to) - 1

    for i in range(n):
        if out_of[i] != i:
            add(i, out_of[i], 1)
    for u in sorted(succ, key=str):
        ui = out_of[idx[u]]
        for v in sorted(succ[u], key=str):
            if v == u:
                continue
            add(ui, idx[v], INF)
    s, t = out_of[idx[source]], idx[sink]
    flow = 0
    N = 2 * n
    while True:
        prev_e = [-1] * N
        seen = [False] * N
        seen[s] = True
        dq = deque([s])
        found = False
        while dq and not found:
            u = dq.popleft()
            e = head[u]
            while e != -1:
                v = to[e]
                if cap[e] > 0 and not seen[v]:
                    seen[v] = True
                    prev_e[v] = e
                    if v == t:
                        found = True
                        break
                    dq.append(v)
                e = nxt[e]
        if not found:
            break
        # bottleneck (always 1 unless the path has no cuttable node)
        b, v = INF, t
        while v != s:
            e = prev_e[v]
            b = min(b, cap[e])
            v = to[e ^ 1]
        if b >= INF:
            raise ValueError("unbounded flow: a source->sink path with no cuttable node")
        v = t
        while v != s:
            e = prev_e[v]
            cap[e] -= b
            cap[e ^ 1] += b
            v = to[e ^ 1]
        flow += b
    # residual reachability from s gives the minimum cut
    seen = [False] * N
    seen[s] = True
    dq = deque([s])
    while dq:
        u = dq.popleft()
        e = head[u]
        while e != -1:
            if cap[e] > 0 and not seen[to[e]]:
                seen[to[e]] = True
                dq.append(to[e])
            e = nxt[e]
    cut = [names[i] for i in range(n) if out_of[i] != i and seen[i] and not seen[out_of[i]]]
    # decompose flow into routes: forward edges (even index) with flow = reverse cap
    used = {}
    for e in range(0, len(to), 2):
        f = cap[e + 1]
        if f > 0:
            used.setdefault(to[e + 1], []).append([e, f])
    routes = []
    for _ in range(flow):
        path_idx = [s]
        u = s
        guard = 0
        while u != t:
            lst = used.get(u)
            while lst and lst[-1][1] == 0:
                lst.pop()
            if not lst:
                break
            lst[-1][1] -= 1
            u = to[lst[-1][0]]
            path_idx.append(u)
            guard += 1
            if guard > 4 * N:
                break
        if u != t:
            break
        route: list = []
        pos: dict = {}
        for i in path_idx:
            base = i - n if i >= n else i
            nm = names[base]
            if route and route[-1] == nm:
                continue
            if nm in pos:                      # flow cycle: cut the loop out
                del route[pos[nm] + 1:]
                pos = {x: k for k, x in enumerate(route)}
                continue
            pos[nm] = len(route)
            route.append(nm)
        routes.append(route)
    if len(cut) != flow:
        raise AssertionError(f"Menger check failed: cut {len(cut)} != flow {flow}")
    return FlowResult(flow, sorted(cut, key=str), routes)
