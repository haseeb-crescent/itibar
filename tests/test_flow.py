"""The custom vertex-connectivity routine against networkx, and Menger's theorem."""

import random

import networkx as nx
import pytest

from itibar.flow import vertex_connectivity


def random_layered(seed: int, layers: int = 6, width: int = 6, p: float = 0.35):
    rng = random.Random(seed)
    G = nx.DiGraph()
    G.add_nodes_from(["s", "t"])
    prev = ["s"]
    for li in range(layers):
        cur = [f"n{li}_{i}" for i in range(rng.randint(1, width))]
        for v in cur:
            for u in prev:
                if rng.random() < p or u == "s" and rng.random() < 0.6:
                    G.add_edge(u, v)
        # occasional back/skip edges make cycles and long jumps
        if li > 1 and rng.random() < 0.3:
            G.add_edge(rng.choice(cur), rng.choice(prev))
        prev = cur
    for u in prev:
        G.add_edge(u, "t")
    return G


@pytest.mark.parametrize("seed", range(60))
def test_matches_networkx(seed):
    G = random_layered(seed)
    if not nx.has_path(G, "s", "t"):
        return
    succ = {u: set(G.successors(u)) for u in G}
    fr = vertex_connectivity(succ, "s", "t", {"s", "t"})
    H = G.copy()
    if H.has_edge("s", "t"):
        H.remove_edge("s", "t")
    expected = nx.node_connectivity(H, "s", "t")
    assert fr.value == expected
    # Menger: the routes are internally vertex-disjoint s->t paths, one per unit
    assert len(fr.routes) == fr.value
    seen = set()
    for r in fr.routes:
        assert r[0] == "s" and r[-1] == "t"
        for a, b in zip(r, r[1:]):
            assert G.has_edge(a, b)
        inner = set(r[1:-1])
        assert not (inner & seen)
        seen |= inner
    # the cut separates s from t
    K = G.copy()
    K.remove_nodes_from(fr.cut)
    assert not nx.has_path(K, "s", "t")
    assert len(fr.cut) == fr.value


def test_uncuttable_middle_nodes():
    # two routes share an uncuttable node B: kappa counts only cuttable nodes
    succ = {"s": {"a", "b"}, "a": {"B"}, "b": {"B"}, "B": {"c", "d"}, "c": {"t"}, "d": {"t"}}
    fr = vertex_connectivity(succ, "s", "t", {"s", "t", "B"})
    assert fr.value == 2


def test_no_path():
    assert vertex_connectivity({"s": {"a"}, "b": {"t"}}, "s", "t", {"s", "t"}).value == 0
