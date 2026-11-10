"""PR 6 rules on synthetic bundles with known answers: the unnamed companion (phrase classes, the
per-group merge, kappa_unnamed_split), conditional narrator rulings of every kind (the
unobservable kind applying nothing), the hearing check on tier 4, the residue tags and their
precedence, and the two default flips."""

from itibar import config, corroborate, pipeline, residue, unnamed
from itibar.conditional import Ruling
from tests.synthetic import chain, make_corpus, override

C1, C2 = 1, 2
COMP = {"rank_no": 1, "tabaka": 1}
A1, A2, A3, A4 = 91, 92, 93, 94          # compilers
T, T2 = 10, 11                           # teachers
S, S2, S3 = 21, 22, 23                   # students
X = 50                                   # the conditional narrator
MUANAN = ("عن", "عن", "an")
HEARD = ("حدثنا", "حدثنا", "haddathana")
U = 1131                                 # the unnamed-person placeholder


def thiqa(t=3):
    return {"rank_no": 3, "tabaka": t}


def level(n, t=4, **kw):
    return {"rank_no": n, "tabaka": t, **kw}


def books(*compilers, first=3):
    return {first + i: {"author_no": 100 + i, "compiler_rawi": c} for i, c in enumerate(compilers)}


def people(**extra):
    p = {C1: COMP, C2: COMP, T: thiqa(3), T2: thiqa(3), S: thiqa(5), S2: thiqa(5), S3: thiqa(5),
         A1: thiqa(9), A2: thiqa(9), A3: thiqa(9), A4: thiqa(9)}
    p.update(extra)
    return p


def run(chains, ppl, bks, matn_no=1, rulings=None, regions=None, hearing=frozenset()):
    corpus = make_corpus(ppl, bks, hearing)
    corpus.rulings = rulings or {}
    corpus.regions = regions or {}
    return pipeline.analyse_group(1, chains, corpus, {"matn_no": matn_no, "nass": "", "sahaba_qty": 1}, None)


def row(out, sanad_id):
    return next(r for r in out["chains"] if r["sanad_id"] == sanad_id)


def utop(c, cls="companion"):
    c.top_unnamed = cls
    return c


# ---------------------------------------------------------------- 1. the unnamed companion

def test_phrase_classes_and_precedence():
    t = unnamed.phrases()
    assert unnamed.classify("رَجُلٍ مِنْ أَصْحَابِ النَّبِيِّ ﷺ", t)[0] == "companion"
    assert unnamed.classify("رجل من أصحاب رسول الله صلى الله عليه وسلم", t)[0] == "companion"
    assert unnamed.classify("بعض أزواج النبي", t)[0] == "companion"
    assert unnamed.classify("رجلا صحب النبي كما صحبه أبو هريرة", t)[0] == "companion"
    assert unnamed.classify("رجل من الأنصار", t)[0] == "ansar_muhajir"
    assert unnamed.classify("رجل من الأنصار من أصحاب النبي", t)[0] == "companion"   # companion first
    for bare in ("رجل", "شيخ من أهل البصرة", "رجل من بني سليم", "بعض أصحابنا", "أبيه", "رجل أدرك النبي"):
        assert unnamed.classify(bare, t)[0] == "none", bare
    assert unnamed.classify("الحسن", t) == ("unclassified", None)
    # the designation reads past the mention span to the next delimiter or transmission word
    text = "حدثنا فلان عن رجل من أصحاب النبي صلى الله عليه وسلم قال: نهى"
    a = text.index("رجل")
    assert unnamed.designation(text, a, a + 3, len(text), 80) == "رجل من أصحاب النبي صلى الله عليه وسلم"


def test_unnamed_companions_merge_per_group_and_are_companions():
    a = utop(chain(3, A1, S, U))
    b = utop(chain(4, A2, S2, U))
    out = run([a, b], people(), books(A1, A2), matn_no=0)
    rec = out["record"]
    assert rec["kappa_all"] == 1 and rec["kappa_unnamed_split"] == 2
    assert rec["cut_vertices"] == ["u1"] and rec["number_class"] == "gharib_mutlaq"
    assert rec["n_unnamed_companion_chains"] == 2 and rec["companions"] == 0
    assert rec["kappa_zero_reason"] is None and rec["n_mursal_chains"] == 0
    r = row(out, a.sanad_id)
    assert r["unnamed_companion"] is True and r["chain_ordinal"] == 10            # level 1 at the top, thiqat below
    assert (r["rule_v2_ibn_hajar"], r["defects_v2_ibn_hajar"]) == ("sahih_li_dhatihi", [])
    assert r["notes_v2_ibn_hajar"] == ["unnamed_companion_companion"]
    assert r["code_v2_alt_unnamed_top_mursal"] == 2    # PR 5 reading: mursal, no continuous chain to repair it
    nodes = {n["node"]: n for n in out["nodes"]}
    assert nodes["u1"]["kind"] == "ucomp" and nodes["u1"]["cut_vertex"]
    assert any(e["u"] == "P" and e["v"] == "u1" for e in out["edges"])


def test_bare_and_ansar_unnamed_tops():
    a = utop(chain(3, A1, S, U), "none")
    out = run([a], people(), books(A1))
    r = row(out, a.sanad_id)
    assert r["unnamed_companion"] is False and r["defects_v2_ibn_hajar"] == ["mursal"]
    assert out["record"]["kappa_zero_reason"] == "no_companion_end"
    b = utop(chain(3, A1, S, U), "ansar_muhajir")
    r = row(run([b], people(), books(A1)), b.sanad_id)
    assert r["unnamed_companion"] is True and r["code_v2_alt_ansar_muhajir_mursal"] == 2
    with override({"structure": {"unnamed_companion": {"ansar_muhajir": "mursal"}}}):
        r = row(run([b], people(), books(A1)), b.sanad_id)
        assert r["unnamed_companion"] is False and r["defects_v2_ibn_hajar"] == ["mursal"]
    with override({"structure": {"unnamed_companion": {"enabled": False}}}):    # PR 5
        c = utop(chain(3, A1, S, U))
        assert row(run([c], people(), books(A1)), c.sanad_id)["defects_v2_ibn_hajar"] == ["mursal"]


# ---------------------------------------------------------------- 2. conditional rulings

def rule(kind, effect, ids=(), region=None, observable=True, rid=X):
    return Ruling(rule_id=f"{rid}:{kind}:1", rawi_id=rid, kind=kind, condition="", ids=frozenset(ids),
                  region=region, effect=effect, observable=observable, source="test", quote="", status="auto")


def test_from_shaykh_light_defect():
    rul = {X: [rule("from_shaykh", "defect:light", [T])]}
    a = chain(3, A1, X, T, C1)
    b = chain(4, A2, X, T2, C1)
    out = run([a, b], people() | {X: thiqa(4)}, books(A1, A2), rulings=rul)
    ra, rb = row(out, a.sanad_id), row(out, b.sanad_id)
    assert ra["defects_v2_ibn_hajar"] == ["conditional"] and ra["rulings_v2_ibn_hajar"] == [f"{X}:from_shaykh:1"]
    assert ra["rule_v2_ibn_hajar"] == "daif"            # every other chain passes through X
    assert rb["defects_v2_ibn_hajar"] == [] and rb["rule_v2_ibn_hajar"] == "sahih_li_dhatihi"
    assert ra["code_v2_alt_conditional_off"] == 0
    with override({"structure": {"derive": {"conditional": False}}}):
        assert row(run([a, b], people() | {X: thiqa(4)}, books(A1, A2), rulings=rul), a.sanad_id)[
            "defects_v2_ibn_hajar"] == []


def test_via_student_level():
    rul = {X: [rule("via_student", "level:4", [S])]}
    a = chain(3, A1, S, X, T, C1)
    b = chain(4, A2, S2, X, T, C1)
    out = run([a, b], people() | {X: level(8)}, books(A1, A2), rulings=rul)
    assert (row(out, a.sanad_id)["rule_v2_ibn_hajar"], row(out, a.sanad_id)["code_v2_ibn_hajar"]) == (
        "hasan_li_dhatihi", 1)
    assert row(out, b.sanad_id)["defects_v2_ibn_hajar"] == ["level_8"]
    assert row(out, b.sanad_id)["code_v2_ibn_hajar"] == 2


def test_region_of_shaykh():
    rul = {X: [rule("region_of_shaykh", "level:4", region="sham")]}
    a = chain(3, A1, X, T, C1)
    b = chain(4, A2, X, T2, C1)
    out = run([a, b], people() | {X: level(5)}, books(A1, A2), rulings=rul, regions={T: frozenset({"sham"})})
    assert row(out, a.sanad_id)["code_v2_ibn_hajar"] == 1 and row(out, a.sanad_id)["defects_v2_ibn_hajar"] == []
    assert row(out, b.sanad_id)["defects_v2_ibn_hajar"] == ["level_5"]


def test_ikhtilat_before_after_unknown_and_sahihayn():
    rul = {X: [rule("ikhtilat_before", "none", [S]), rule("ikhtilat_after", "defect:light", [S2])]}
    ppl = people() | {X: thiqa(4)}
    a = chain(3, A1, S, X, T, C1)        # heard before
    b = chain(4, A2, S2, X, T, C1)       # heard after
    c = chain(5, A3, S3, X, T, C1)       # not placed: treated as after
    d = chain(1, A4, S3, X, T, C1)       # the same student in a chain of al-Bukhari: before
    out = run([a, b, c], ppl, books(A1, A2, A3), rulings=rul)
    assert row(out, a.sanad_id)["defects_v2_ibn_hajar"] == []
    assert row(out, b.sanad_id)["defects_v2_ibn_hajar"] == ["conditional"]
    assert row(out, c.sanad_id)["defects_v2_ibn_hajar"] == ["conditional"]
    assert row(out, b.sanad_id)["rule_v2_ibn_hajar"] == "daif"     # every witness shares X
    bk = books(A1, A2, A3) | {1: {"author_no": 99, "compiler_rawi": A4}}
    out = run([c, d], ppl, bk, rulings=rul)
    assert row(out, d.sanad_id)["defects_v2_ibn_hajar"] == []
    assert row(out, c.sanad_id)["defects_v2_ibn_hajar"] == []       # the link stands in the Sahihayn
    with override({"structure": {"derive": {"conditional_rules": {"sahihayn_ikhtilat_before": False}}}}):
        out = run([c, d], ppl, bk, rulings=rul)
        assert row(out, c.sanad_id)["defects_v2_ibn_hajar"] == ["conditional"]
    # a level ruling for the time before: a sadūq who became confused (level 5) heard before -> 4
    rul5 = {X: [rule("ikhtilat_before", "level:4", [S]), rule("ikhtilat_after", "defect:light", [])]}
    out = run([a, b], people() | {X: level(5)}, books(A1, A2), rulings=rul5)
    assert row(out, a.sanad_id)["code_v2_ibn_hajar"] == 1 and row(out, b.sanad_id)["code_v2_ibn_hajar"] == 2


def test_unobservable_applies_nothing():
    rul = {X: [rule("unobservable", "none", observable=False)]}
    a = chain(3, A1, X, T, C1)
    out = run([a], people() | {X: thiqa(4)}, books(A1), rulings=rul)
    r = row(out, a.sanad_id)
    assert r["defects_v2_ibn_hajar"] == [] and r["rulings_v2_ibn_hajar"] == []


# ---------------------------------------------------------------- 3. tier-4 hearing

def mud(tier, flag=1):
    return {"rank_no": 3, "tabaka": 4, "tadlis": flag, "tier": tier}


def test_tier_4_an_covered_by_hearing_in_another_chain():
    D = 60
    a = chain(3, A1, D, T, C1, words={2: MUANAN})
    h = chain(4, A2, S, D, T, C1, words={3: HEARD})
    out = run([a, h], people() | {D: mud(4)}, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["rule_v2_ibn_hajar"] == "sahih_li_dhatihi" and "muanan_covered_tasrih_tier_4" in r["notes_v2_ibn_hajar"]
    assert r["code_v2_alt_tasrih_tier_3_only"] == 2                 # without the check on tier 4: not repairable
    out = run([a], people() | {D: mud(4)}, books(A1))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "not_repairable"


# ---------------------------------------------------------------- 4. residue tags

def test_residue_direction_chain_choice_and_precedence():
    W = 70
    a = chain(3, A1, S, T, C1)                       # thiqat: code 0
    b = chain(4, A2, W, T2, C2)                      # level 9, not repairable: code 2
    out = run([a, b], people() | {W: level(9)}, books(A1, A2), matn_no=2)
    rec = out["record"]
    assert rec["code_v2_ibn_hajar"] == 0 and rec["residue_disagree"] is True
    assert rec["residue_direction"] == "lenient"
    assert rec["residue_tags"][0] == "chain_choice" and "level_only" in rec["residue_tags"]
    assert rec["residue_primary"] == "chain_choice"
    out = run([a], people(), books(A1), matn_no=4)    # nothing else to choose; source 3-5, every level <= 9
    rec = out["record"]
    assert rec["residue_tags"] == ["source_severe", "level_only"] and rec["residue_primary"] == "source_severe"
    out = run([a], people(), books(A1), matn_no=0)
    assert out["record"]["residue_disagree"] is False and out["record"]["residue_primary"] is None
    out = run([b], people() | {W: level(8)}, books(A1, A2), matn_no=1)   # no witness, the source higher (level 8)
    rec = out["record"]
    assert rec["residue_direction"] == "stricter" and rec["residue_primary"] == "corroboration"
    assert residue.precedence()[0] == "chain_choice"


def test_residue_tadlis_and_mursal_only():
    D = 60
    a = chain(3, A1, D, T, C1, words={2: MUANAN})
    out = run([a], people() | {D: mud(3)}, books(A1), matn_no=0)
    assert "tadlis_only" in out["record"]["residue_tags"]
    m = chain(3, A1, S, T)                            # T is no companion: mursal
    out = run([m], people(), books(A1), matn_no=0)
    assert "mursal_only" in out["record"]["residue_tags"]
    u = utop(chain(3, A1, S, U), "none")
    out = run([u], people(), books(A1), matn_no=0)
    assert "unnamed_top" in out["record"]["residue_tags"]


# ---------------------------------------------------------------- 5. the default flips

def test_default_flips():
    d = config.load("structure")["derive"]
    assert d["corroboration"]["shahid_scope"] == "group" and d["tadlis"]["mudallis_set"] == "union"
    assert "siblings" in d["variants"] and "mudallis_source_flag" in d["variants"]
    params = corroborate.rulesets()
    assert params["ibn_hajar"].shahid_scope == "group" and params["alt_siblings"].shahid_scope == "siblings"
    # a narrator matched to the book at tier 3 but not flagged by the source: a mudallis by default
    D = 60
    a = chain(3, A1, D, T, C1, words={2: MUANAN})
    r = row(run([a], people() | {D: mud(3, flag=0)}, books(A1)), a.sanad_id)
    assert r["defects_v2_ibn_hajar"] == ["mudallis_muanan_tier_3"] and r["code_v2_alt_mudallis_source_flag"] == 0


def test_the_successor_of_an_unnamed_companion_must_be_free_of_tadlis():
    """al-Nukat: connected when the Successor calls him a companion and is free of tadlis; a
    mudallis's 'an from the unnamed companion falls under the tadlis rule like any 'an."""
    D = 60
    a = utop(chain(3, A1, D, U, words={2: MUANAN}))
    r = row(run([a], people() | {D: mud(3)}, books(A1)), a.sanad_id)
    assert r["unnamed_companion"] is True and r["defects_v2_ibn_hajar"] == ["mudallis_muanan_tier_3"]
    h = utop(chain(4, A2, S, D, U, words={3: HEARD}))     # «حدثني رجل من أصحاب النبي» in another chain
    r = row(run([a, h], people() | {D: mud(3)}, books(A1, A2)), a.sanad_id)
    assert r["defects_v2_ibn_hajar"] == [] and "muanan_covered_tasrih_tier_3" in r["notes_v2_ibn_hajar"]


def test_a_student_vouched_for_is_heard_before():
    """Ibn Lahi'a: the 'Abadila named by the via_student ruling are not put after the burning by default."""
    rul = {X: [rule("via_student", "level:4", [S]), rule("ikhtilat_before", "none", [S2]),
               rule("ikhtilat_after", "defect:light", [])]}
    a = chain(3, A1, S, X, T, C1)
    b = chain(4, A2, S3, X, T, C1)
    out = run([a, b], people() | {X: level(8)}, books(A1, A2), rulings=rul)
    assert row(out, a.sanad_id)["defects_v2_ibn_hajar"] == [] and row(out, a.sanad_id)["code_v2_ibn_hajar"] == 1
    assert row(out, b.sanad_id)["defects_v2_ibn_hajar"] == ["level_8+conditional"]
