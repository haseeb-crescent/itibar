"""Structural definitions on synthetic bundles with known answers."""

from itibar import pipeline
from tests.synthetic import chain, make_corpus

COMPANION = {"rank_no": 1, "tabaka": 1}
THIQA = {"rank_no": 3}
SADUQ = {"rank_no": 4}
DAIF = {"rank_no": 8}


def run(chains, people, books):
    corpus = make_corpus(people, books)
    return pipeline.analyse_group(1, chains, corpus, {"matn_no": 0, "nass": "", "sahaba_qty": 1})


def innama_like():
    # P -> U -> A -> T -> Y; Y -> S1 -> {X1, X2}; Y -> S2 -> {X3, X4}; Xi compiles book i
    U, A, T, Y, S1, S2 = 1, 2, 3, 4, 5, 6
    X = [11, 12, 13, 14]
    people = {U: {**COMPANION}, A: {"rank_no": 2, "tabaka": 2}, T: {"rank_no": 3, "tabaka": 4},
              Y: {"rank_no": 2, "tabaka": 5}, S1: {"rank_no": 3, "tabaka": 7}, S2: {"rank_no": 3, "tabaka": 7}}
    for x in X:
        people[x] = {"rank_no": 2, "tabaka": 9}
    books = {i + 1: {"author_no": 100 + i, "compiler_rawi": X[i]} for i in range(4)}
    chains = [chain(1, X[0], S1, Y, T, A, U), chain(2, X[1], S1, Y, T, A, U),
              chain(3, X[2], S2, Y, T, A, U), chain(4, X[3], S2, Y, T, A, U)]
    return chains, people, books


def test_single_strand_common_link():
    out = run(*innama_like())
    r = out["record"]
    assert r["kappa_all"] == 1 and r["kappa_thiqa_up"] == 1
    assert r["cut_vertices"] == ["r1", "r2", "r3", "r4"]
    assert {"r1", "r2", "r3"} <= set(r["single_strand"])
    assert "r4" in r["pcl_k2"] and "r4" not in r["pcl_k3"]
    assert r["common_links"] == ["r4"]
    assert r["bypass_paths"] == 0 and r["paths_total"] == 4
    assert r["companions"] == 1
    assert r["width_profile"][:4] == [{"layer": 1, "width": 1}, {"layer": 2, "width": 1},
                                      {"layer": 4, "width": 1}, {"layer": 5, "width": 1}]


def test_two_companions_and_menger_routes():
    C1, C2, a1, a2 = 1, 2, 11, 12
    people = {C1: COMPANION, C2: COMPANION, a1: THIQA, a2: THIQA}
    books = {1: {"author_no": 1, "compiler_rawi": a1}, 2: {"author_no": 2, "compiler_rawi": a2}}
    out = run([chain(1, a1, C1), chain(2, a2, C2)], people, books)
    r = out["record"]
    assert r["kappa_all"] == 2 and r["cut_vertices"] == []
    assert sorted(r["common_links"]) == []  # companions with single-strand branches are not PCLs
    assert r["companions"] == 2


def test_break_markers_never_fuse_routes():
    # two unrelated broken chains share the inqita' placeholder id; they must not join
    C1, C2, x1, x2, a1, a2 = 1, 2, 3, 4, 11, 12
    people = {C1: COMPANION, C2: COMPANION, x1: THIQA, x2: THIQA, a1: THIQA, a2: THIQA}
    books = {1: {"author_no": 1, "compiler_rawi": a1}, 2: {"author_no": 2, "compiler_rawi": a2}}
    out = run([chain(1, a1, x1, 30000, C1), chain(2, a2, x2, 30000, C2)], people, books)
    r = out["record"]
    assert r["kappa_all"] == 0
    assert r["n_inqita_marker_chains"] == 2
    gaps = [n for n in out["nodes"] if n["kind"] == "gap"]
    assert len(gaps) == 2  # one per chain occurrence


def test_irsal_is_mursal_without_prophet_edge():
    T, a = 3, 11
    people = {T: {"rank_no": 3, "tabaka": 3}, a: THIQA}
    books = {1: {"author_no": 1, "compiler_rawi": a}}
    out = run([chain(1, a, T, 30002), chain(1, a, T)], people, books)
    r = out["record"]
    assert r["kappa_all"] == 0
    assert r["n_mursal_chains"] == 2 and r["n_irsal_marker_chains"] == 1
    assert not any(e["u"] == "P" for e in out["edges"])


def test_unnamed_person_per_context_and_threshold():
    C, s1, s2, a1, a2 = 1, 3, 4, 11, 12
    people = {C: COMPANION, s1: THIQA, s2: THIQA, a1: THIQA, a2: THIQA}
    books = {1: {"author_no": 1, "compiler_rawi": a1}, 2: {"author_no": 2, "compiler_rawi": a2}}
    out = run([chain(1, a1, s1, 1131, C), chain(2, a2, s2, 1131, C)], people, books)
    r = out["record"]
    mub = sorted(n["node"] for n in out["nodes"] if n["kind"] == "mubham")
    assert mub == ["m3|1", "m4|1"]
    assert r["kappa_all"] == 1          # the companion is the only cut vertex
    assert r["kappa_above_matruk"] == 0  # unnamed persons have unknown grade
    assert r["kappa_lower_all"] == 1


def test_compiler_node_bottleneck_for_quoting_books():
    # a book whose compiler is absent from its chains: his teachers at pos 0 are
    # not parallel routes — the compiler node is a single point
    C1, C2, t1, t2 = 1, 2, 3, 4
    people = {C1: COMPANION, C2: COMPANION, t1: THIQA, t2: THIQA}
    books = {9: {"author_no": 900, "compiler_rawi": None}}
    out = run([chain(9, t1, C1), chain(9, t2, C2)], people, books)
    r = out["record"]
    assert r["kappa_all"] == 1 and r["cut_vertices"] == ["c900"]


def test_threshold_subgraphs():
    C1, C2, w, a1, a2 = 1, 2, 3, 11, 12
    people = {C1: COMPANION, C2: COMPANION, w: DAIF, a1: THIQA, a2: THIQA}
    books = {1: {"author_no": 1, "compiler_rawi": a1}, 2: {"author_no": 2, "compiler_rawi": a2}}
    out = run([chain(1, a1, w, C1), chain(2, a2, C2)], people, books)
    r = out["record"]
    assert (r["kappa_all"], r["kappa_above_matruk"], r["kappa_saduq_up"], r["kappa_thiqa_up"]) == (2, 2, 1, 1)


def test_low_grade_compiler_keeps_only_his_own_book():
    # F is level 5 and compiles book 2; he also narrates in book 1's chain
    C, F, a1 = 1, 5, 11
    people = {C: COMPANION, F: {"rank_no": 5}, a1: THIQA}
    books = {1: {"author_no": 1, "compiler_rawi": a1}, 2: {"author_no": 2, "compiler_rawi": F}}
    out = run([chain(1, a1, F, C), chain(2, F, C)], people, books)
    r = out["record"]
    assert r["kappa_all"] == 1
    assert r["kappa_thiqa_up"] == 1   # only book 2's own record survives
    edges = {(e["u"], e["v"]) for e in out["edges"]}
    assert ("r5", "r11") in edges


def test_kappa_lower_merges_homonyms_and_drops_stubs():
    C1, C2, h1, h2, a1, a2, st = 1, 2, 3, 4, 11, 12, 7
    people = {C1: COMPANION, C2: COMPANION, h1: {**THIQA, "homonym": 0}, h2: {**THIQA, "homonym": 0},
              a1: THIQA, a2: THIQA, st: {"rank_no": 0, "stub": 1}}
    books = {1: {"author_no": 1, "compiler_rawi": a1}, 2: {"author_no": 2, "compiler_rawi": a2}}
    out = run([chain(1, a1, h1, C1), chain(2, a2, h2, C2)], people, books)
    assert out["record"]["kappa_all"] == 2 and out["record"]["kappa_lower_all"] == 1
    out = run([chain(1, a1, st, C1), chain(2, a2, C2)], people, books)
    assert out["record"]["kappa_all"] == 2 and out["record"]["kappa_lower_all"] == 1


def test_continuity_flags():
    C, u, v, w, a = 1, 3, 4, 5, 11
    people = {C: COMPANION, u: {"rank_no": 3, "tabaka": 2, "death": 100},
              v: {"rank_no": 3, "tabaka": 4, "birth": 110}, w: {"rank_no": 3, "tabaka": 10},
              a: {"rank_no": 3, "tabaka": 11}}
    books = {1: {"author_no": 1, "compiler_rawi": a}}
    out = run([chain(1, a, w, v, u, C)], people, books)
    flags = {(e["u"], e["v"]): e["continuity"] for e in out["edges"]}
    assert flags[("r3", "r4")] == "incompatible"   # death 100 < birth 110
    assert flags[("r4", "r5")] == "incompatible"   # tabaka gap 6
    assert flags[("r5", "r11")] == "compatible"    # gap 1
    assert flags[("r1", "r3")] == "compatible"     # gap 1


def test_muanan_by_mudallis_reads_word_before_teacher():
    C, m, a = 1, 3, 11
    people = {C: COMPANION, m: {"rank_no": 3, "tabaka": 2, "tadlis": 1}, a: {"rank_no": 3, "tabaka": 3}}
    books = {1: {"author_no": 1, "compiler_rawi": a}}
    # pos 2 (the companion) is the teacher of the mudallis m: word before C's mention is 'عن'
    out = run([chain(1, a, m, C, words={2: ("عن", "عن", "an"), 1: ("حدثنا", "حدثنا", "haddathana")})],
              people, books)
    mu = {(e["u"], e["v"]): e["muanan_mudallis"] for e in out["edges"]}
    assert mu[("r1", "r3")] == "yes"
    assert mu[("r3", "r11")] == "not_mudallis"


def test_derived_grade_and_cap():
    C, t, s, w, a = 1, 3, 4, 5, 11
    people = {C: COMPANION, t: THIQA, s: SADUQ, w: {"rank_no": 3, "tabaka": 3}, a: THIQA}
    books = {1: {"author_no": 1, "compiler_rawi": a}}
    out = run([chain(1, a, s, C, max_rank=4), chain(1, a, t, C, max_rank=3), chain(1, a, w, 30002, max_rank=12)],
              people, books)
    r = out["record"]
    assert r["derived_ordinal"] == 10 and r["derived_code"] == 0
    ch = {c["chain_ordinal"]: c for c in out["chains"]}
    assert ch[9]["chain_code"] == 1
    mursal = [c for c in out["chains"] if not c["ends_companion"]][0]
    assert mursal["chain_code_raw"] == 0 and mursal["chain_code"] == 2 and mursal["chain_capped"]
    assert all(c["agree_full"] for c in out["chains"])


def test_compiler_excluded_from_chain_grade():
    C, t, a = 1, 3, 11
    people = {C: COMPANION, t: THIQA, a: {"rank_no": 7}}
    books = {1: {"author_no": 1, "compiler_rawi": a}}
    out = run([chain(1, a, t, C, max_rank=7)], people, books)
    c = out["chains"][0]
    assert c["chain_ordinal"] == 10
    assert c["agree_full"] and not c["agree_derived"]
    assert c["disagreement_class"] == "compiler_strictly_weakest"
