"""PR 5 rules on synthetic bundles with known answers: attested witnesses only, tiered
tadlis with the hearing check and the Sahihayn convention, sibling shawahid with the
overlap floor, every light defect covered, unnamed persons named elsewhere, compiler
roles per edge, book transmitters, and the number class on kappa."""

from itibar import corroborate, pipeline, siblings
from tests.synthetic import chain, make_corpus, override

C1, C2 = 1, 2
COMP = {"rank_no": 1, "tabaka": 1}
A1, A2, A3, A4 = 91, 92, 93, 94          # compilers
T, T2 = 10, 11                           # teachers at layer 3
W, S, S2 = 20, 21, 22                    # the weak narrator and followers
MUANAN = ("عن", "عن", "an")
HEARD = ("حدثنا", "حدثنا", "haddathana")
LEGACY = {"structure": {"derive": {"corroboration": {"witness": "route", "avoid": "weakest",
                                                     "shahid_scope": "group", "unknown_repair": "none"},
                                   "tadlis": {"tiers": False, "tasrih_scope": "none",
                                              "sahihayn_muanan_accepted": False}}}}


def thiqa(t=3):
    return {"rank_no": 3, "tabaka": t}


def level(n, t=4, **kw):
    return {"rank_no": n, "tabaka": t, **kw}


def books(*compilers, first=3):
    """Books numbered from `first` (books 1 and 2 are the Sahihayn in config/structure.yaml: qarain)."""
    return {first + i: {"author_no": 100 + i, "compiler_rawi": c} for i, c in enumerate(compilers)}


def people(**extra):
    p = {C1: COMP, C2: COMP, T: thiqa(3), T2: thiqa(3), S: thiqa(5), S2: thiqa(5),
         A1: thiqa(9), A2: thiqa(9), A3: thiqa(9), A4: thiqa(9)}
    p.update(extra)
    return p


def run(chains, ppl, bks, sibling_idx=None, hearing=frozenset()):
    corpus = make_corpus(ppl, bks, hearing)
    return pipeline.analyse_group(1, chains, corpus, {"matn_no": 1, "nass": "", "sahaba_qty": 1}, sibling_idx)


def row(out, sanad_id):
    return next(r for r in out["chains"] if r["sanad_id"] == sanad_id)


# ---------------------------------------------------------------- 1. attested witnesses

def test_a_spliced_route_is_not_a_witness():
    """The union graph has a route avoiding W, spliced from a's top (C1 -> T) and a mursal
    chain (T -> S -> A2), but no single continuous light-or-better chain avoids W."""
    Z = 30
    a = chain(3, A1, W, T, C1)
    b = chain(4, A2, S, T, 30002)                    # T -> S -> A2, an irsal marker at the top: not continuous
    c = chain(5, A3, Z, T, C1)                       # continuous, through a level-11 narrator: not light-or-better
    ppl = people() | {W: level(6), Z: level(11)}
    out = run([a, b, c], ppl, books(A1, A2, A3))
    r = row(out, a.sanad_id)
    assert (r["rule_v2_ibn_hajar"], r["code_v2_ibn_hajar"]) == ("daif", 2)
    assert r["route_exists_v2_ibn_hajar"] is True    # the graph had a route but no chain
    with override(LEGACY):                           # PR 4: the spliced route counts
        r = row(run([a, b, c], ppl, books(A1, A2, A3)), a.sanad_id)
        assert r["rule_v2_ibn_hajar"] == "hasan_li_ghayrihi" and r["witness_sanad_v2_ibn_hajar"] is None
    d = chain(6, A4, S2, T, C1)                      # one attested chain avoiding W
    r = row(run([a, b, c, d], ppl, books(A1, A2, A3, A4)), a.sanad_id)
    assert r["rule_v2_ibn_hajar"] == "hasan_li_ghayrihi" and r["witness_sanad_v2_ibn_hajar"] == d.sanad_id


# ---------------------------------------------------------------- 2. tiered tadlis

D = 50


def mud(tier):
    return {"rank_no": 3, "tabaka": 4, "tadlis": 1, "tier": tier}


def test_tier_1_and_2_an_is_no_defect_tier_3_is_light_tier_4_not_repairable():
    a = chain(3, A1, D, T, C1, words={2: MUANAN})
    for tier, rule, code in ((1, "sahih_li_dhatihi", 0), (2, "sahih_li_dhatihi", 0), (3, "daif", 2),
                             (4, "not_repairable", 2), (5, "not_repairable", 2)):
        out = run([a], people() | {D: mud(tier)}, books(A1))
        r = row(out, a.sanad_id)
        assert (r["rule_v2_ibn_hajar"], r["code_v2_ibn_hajar"]) == (rule, code), tier
    # an untiered flagged narrator is treated as tier 3 (untiered_tadlis)
    out = run([a], people() | {D: mud(0)}, books(A1))
    assert row(out, a.sanad_id)["defects_v2_ibn_hajar"] == ["mudallis_muanan_tier_3"]
    # tier 3 is lifted by corroboration; tier 4 is not
    b = chain(4, A2, S, T, C1)
    out = run([a, b], people() | {D: mud(3)}, books(A1, A2))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "hasan_li_ghayrihi"
    out = run([a, b], people() | {D: mud(4)}, books(A1, A2))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "not_repairable"
    assert row(out, b.sanad_id)["rule_v2_ibn_hajar"] == "sahih_li_dhatihi"
    with override(LEGACY):                           # PR 4: every flagged narrator's 'an is a light defect
        out = run([a], people() | {D: mud(2)}, books(A1))
        assert row(out, a.sanad_id)["defects_v2_ibn_hajar"] == ["mudallis_muanan"]


def test_hearing_in_another_chain_covers_the_an():
    a = chain(3, A1, D, T, C1, words={2: MUANAN})
    h = chain(4, A2, S, D, T, C1, words={3: HEARD})    # D heard from T: "حدثنا" before T's mention
    out = run([a, h], people() | {D: mud(3)}, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["defects_v2_ibn_hajar"] == [] and "muanan_covered_tasrih_tier_3" in r["notes_v2_ibn_hajar"]
    assert r["rule_v2_ibn_hajar"] == "sahih_li_dhatihi"
    out = run([a, h], people() | {D: mud(4)}, books(A1, A2))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "sahih_li_dhatihi"   # tier 4: rejected unless hearing is shown
    # hearing elsewhere in the corpus counts only at tasrih_scope corpus
    out = run([a], people() | {D: mud(3)}, books(A1), hearing={(T, D)})
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "daif"
    assert row(out, a.sanad_id)["code_v2_alt_tasrih_corpus"] == 0


def test_the_sahihayn_carry_the_an_on_hearing():
    a = chain(1, A1, D, T, C1, words={2: MUANAN})      # book 1: al-Bukhari (config qarain.sahihayn_book_ids)
    out = run([a], people() | {D: mud(4)}, books(A1, first=1))
    r = row(out, a.sanad_id)
    assert r["defects_v2_ibn_hajar"] == [] and r["notes_v2_ibn_hajar"] == ["muanan_accepted_sahihayn_tier_4"]
    # and the link is then established for the report's other chains
    x = chain(3, A2, D, T, C1, words={2: MUANAN})
    bks = books(A1, first=1) | {3: {"author_no": 200, "compiler_rawi": A2}}
    out = run([a, x], people() | {D: mud(3)}, bks)
    assert "muanan_covered_tasrih_tier_3" in row(out, x.sanad_id)["notes_v2_ibn_hajar"]


def test_mudallis_set_source_flag_and_union():
    a = chain(3, A1, D, T, C1, words={2: MUANAN})
    ppl = people() | {D: {"rank_no": 3, "tabaka": 4, "tadlis": 0, "tier": 3}}   # in the book, not flagged
    out = run([a], ppl, books(A1))
    assert row(out, a.sanad_id)["code_v2_ibn_hajar"] == 0
    assert row(out, a.sanad_id)["code_v2_alt_mudallis_union"] == 2


# ---------------------------------------------------------------- 3. sibling shawahid

class FakeMatns:
    def __init__(self, table):
        self.table = table

    def overlap(self, a, b):
        return self.table.get((a, b), self.table.get((b, a), 0.0))


def _sibling_index(sib_chains, corpus, overlap):
    params = corroborate.rulesets()
    rows = pipeline.witness_rows(2, sib_chains, corpus, params)
    return siblings.SiblingIndex.build(rows, {1: (2,)}, list(params), FakeMatns(overlap))


def test_a_shahid_from_a_sibling_group_above_the_floor():
    a = chain(3, A1, W, T, C1)
    w = chain(4, A2, S, T2, C2)                       # another companion's report, in group 2
    ppl = people() | {W: level(6)}
    corpus = make_corpus(ppl, books(A1, A2))
    floor = corroborate.rulesets()["ibn_hajar"].shahid_min_overlap
    idx = _sibling_index([w], corpus, {(a.hadith_id, w.hadith_id): floor + 0.01})
    out = pipeline.analyse_group(1, [a], corpus, {"matn_no": 1}, idx)
    r = row(out, a.sanad_id)
    assert (r["rule_v2_ibn_hajar"], r["divergence_v2_ibn_hajar"]) == ("hasan_li_ghayrihi", "shahid")
    assert r["witness_sanad_v2_ibn_hajar"] == w.sanad_id and r["witness_group_v2_ibn_hajar"] == 2
    assert out["record"]["witness_cross_group_v2_ibn_hajar"] is True
    assert r["code_v2_alt_shahid_group"] == 2         # without siblings: no witness
    # below the floor: no witness
    idx = _sibling_index([w], corpus, {(a.hadith_id, w.hadith_id): floor - 0.01})
    out = pipeline.analyse_group(1, [a], corpus, {"matn_no": 1}, idx)
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "daif"


def test_a_sibling_witness_must_avoid_the_weak_narrator_and_be_light_or_better():
    a = chain(3, A1, W, T, C1)
    through_w = chain(4, A2, W, T2, C2)
    fatal = chain(5, A3, 40, T2, C2)
    ppl = people() | {W: level(6), 40: level(11)}
    corpus = make_corpus(ppl, books(A1, A2, A3))
    idx = _sibling_index([through_w, fatal], corpus, {(a.hadith_id, through_w.hadith_id): 0.9,
                                                      (a.hadith_id, fatal.hadith_id): 0.9})
    out = pipeline.analyse_group(1, [a], corpus, {"matn_no": 1}, idx)
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "daif"


# ---------------------------------------------------------------- 4. every light defect covered

def test_each_defect_needs_a_witness_and_witnesses_may_differ():
    X, Y, Z1, Z2 = 60, 61, 62, 63
    ppl = people() | {X: level(5, 6), Y: level(8, 4), Z1: thiqa(4), Z2: thiqa(6)}
    a = chain(3, A1, X, Y, T, C1)                     # light defects: X (level 5) and Y (level 8)
    b = chain(4, A2, X, Z1, T, C1)                    # avoids Y, shares X
    out = run([a, b], ppl, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["weak_nodes_v2_ibn_hajar"] == [f"r{X}", f"r{Y}"]
    assert r["code_v2_ibn_hajar"] == 2                # X is not covered
    assert r["code_v2_alt_weakest"] == 1              # PR 4: one witness avoiding the weakest (Y)
    assert r["code_v2_alt_all_light_defects"] == 2
    d = chain(5, A3, Z2, Y, T, C1)                    # avoids X, shares Y
    out = run([a, b, d], ppl, books(A1, A2, A3))
    r = row(out, a.sanad_id)
    assert r["code_v2_ibn_hajar"] == 1                # X covered by d, Y by b
    assert r["code_v2_alt_all_light_defects"] == 2    # no single witness avoids both


# ---------------------------------------------------------------- 8. the unnamed person

def test_an_unnamed_person_named_elsewhere_in_the_report():
    N = 70
    ppl = people() | {N: thiqa(4)}
    a = chain(3, A1, S, 1131, T, C1)                  # "a man" between T and S
    out = run([a], ppl, books(A1))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "not_repairable"
    b = chain(4, A2, S, N, T, C1)                     # the same link names him
    out = run([a, b], ppl, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["rule_v2_ibn_hajar"] == "sahih_li_dhatihi" and r["notes_v2_ibn_hajar"] == ["unnamed_named_elsewhere_level_3"]
    assert r["code_v2_alt_unknown_none"] == 2
    ppl[N] = level(7)                                 # named as a mastur: the position takes his level
    out = run([a, b], ppl, books(A1, A2))
    assert row(out, a.sanad_id)["defects_v2_ibn_hajar"] == ["level_7"]


# ---------------------------------------------------------------- 5. compiler roles and book transmitters

def test_a_compiler_narrator_is_terminal_only_on_his_edge_into_his_book():
    """M compiled book 3 (pos 0 there) and also taught S, who passed the report to the
    compilers of books 4 and 5: M's own book is one qualifying branch, S's another."""
    M = 80
    ppl = people() | {M: thiqa(7)}
    bks = {3: {"author_no": 100, "compiler_rawi": M}, 4: {"author_no": 101, "compiler_rawi": A2},
           5: {"author_no": 102, "compiler_rawi": A3}}
    chains = [chain(3, M, T, C1), chain(4, A2, S, M, T, C1), chain(5, A3, S, M, T, C1)]
    rec = run(chains, ppl, bks)["record"]
    assert f"r{M}" in rec["pcl_k2"]
    with override({"structure": {"structure": {"compiler_terminal": "node"}}}):
        rec = run(chains, ppl, bks)["record"]
        assert f"r{M}" not in rec["pcl_k2"]           # PR 4: the whole node is terminal


def test_a_compiler_only_narrator_is_not_a_single_strand():
    M = 80
    ppl = people() | {M: thiqa(7)}
    bks = {3: {"author_no": 100, "compiler_rawi": M}}
    rec = run([chain(3, M, T, C1)], ppl, bks)["record"]
    assert f"r{M}" not in rec["single_strand"] and f"r{T}" in rec["single_strand"]


def test_a_book_transmitter_is_exempt_and_out_of_the_chain_grade():
    X, AU = 81, 82                                    # X transmits AU's book: X at pos 0, AU at pos 1
    ppl = people() | {X: level(8, 12), AU: level(5, 9)}
    bks = {3: {"author_no": 100, "compiler_rawi": AU, "transmitter_rawi": X}}
    a = chain(3, X, AU, T, C1)
    out = run([a], ppl, bks)
    r = row(out, a.sanad_id)
    assert r["transmitter_at_pos0"] is True and r["book_role_positions"] == [0, 1]
    assert r["chain_code"] == 0 and r["code_v2_ibn_hajar"] == 0   # neither X (level 8) nor AU (level 5) is graded
    rec = out["record"]
    assert rec["kappa_thiqa_up"] == 1                 # exempt from the threshold in their book roles
    node = {n["node"]: n for n in out["nodes"]}
    assert node[f"r{X}"]["book_transmitter_role"] and not node[f"r{X}"]["narrator_role"]
    with override({"structure": {"bundle": {"book_transmitters": False}}}):
        bks2 = {3: {"author_no": 100, "compiler_rawi": X}}      # PR 4: X taken for the compiler
        r = row(run([a], ppl, bks2), a.sanad_id)
        assert r["chain_code"] == 2                   # AU (level 5) graded


# ---------------------------------------------------------------- 6. number class on kappa

def test_number_class_on_kappa_and_the_cut_vertex():
    ppl = people() | {23: thiqa(5)}
    one_companion = [chain(3, A1, S, T, C1), chain(4, A2, S2, T2, C1)]   # all routes through C1
    rec = run(one_companion, ppl, books(A1, A2))["record"]
    assert (rec["number_class"], rec["gharib_cut_kind"]) == ("gharib_mutlaq", "companion")
    funnel = [chain(3, A1, S, T, C1), chain(4, A2, S, T2, C2)]          # two companions, one narrator below
    rec = run(funnel, ppl, books(A1, A2))["record"]
    assert (rec["number_class"], rec["gharib_cut_kind"]) == ("gharib_nisbi", "narrator")
    two = [chain(3, A1, S, T, C1), chain(4, A2, S2, T2, C2)]
    rec = run(two, ppl, books(A1, A2))["record"]
    assert rec["number_class"] == "aziz" and rec["number_class_width"] == "aziz"
    with override({"structure": {"number_class": {"basis": "width"}}}):
        rec = run(funnel, ppl, books(A1, A2))["record"]
        assert rec["number_class"] == rec["number_class_width"]
