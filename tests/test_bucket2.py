"""Bucket 2 on synthetic bundles with known answers: the corroborated grade
(both rulesets and the variants), divergence classes, number class, qara'in,
pooled bundles, and the list parser and matcher."""

import pytest
import yaml

from itibar import lists, paths, pipeline, pool, structure
from tests.synthetic import chain, make_corpus

C1, C2 = 1, 2
COMP = {"rank_no": 1, "tabaka": 1}


def thiqa(t=3):
    return {"rank_no": 3, "tabaka": t}


def level(n, t=4, **kw):
    return {"rank_no": n, "tabaka": t, **kw}


def books(*compilers):
    return {i + 1: {"author_no": 100 + i, "compiler_rawi": c} for i, c in enumerate(compilers)}


def run(chains, people, bks):
    corpus = make_corpus(people, bks)
    return pipeline.analyse_group(1, chains, corpus, {"matn_no": 1, "nass": "", "sahaba_qty": 1})


def row(out, sanad_id):
    return next(r for r in out["chains"] if r["sanad_id"] == sanad_id)


A1, A2, A3 = 91, 92, 93          # compilers
T, T2 = 10, 11                   # teachers at layer 3
W, S, S2 = 20, 21, 22            # the weak narrator and followers


def base_people(**extra):
    p = {C1: COMP, C2: COMP, T: thiqa(3), T2: thiqa(3), S: thiqa(5), S2: thiqa(5),
         A1: thiqa(9), A2: thiqa(9), A3: thiqa(9)}
    p.update(extra)
    return p


# ---------------------------------------------------------------- corroboration and divergence

def test_maqbul_followed_from_his_own_teacher_is_mutabaa_tamma():
    a = chain(1, A1, W, T, C1)
    b = chain(2, A2, S, T, C1)
    out = run([a, b], base_people() | {W: level(6)}, books(A1, A2))
    r = row(out, a.sanad_id)
    for rs in ("ibn_hajar", "ibn_al_salah"):
        assert r[f"rule_v2_{rs}"] == "hasan_li_ghayrihi" and r[f"code_v2_{rs}"] == 1
        assert r[f"divergence_v2_{rs}"] == "mutabaa_tamma"
        assert r[f"witness_sanad_v2_{rs}"] == b.sanad_id
    assert r["weak_nodes_v2_ibn_hajar"] == [f"r{W}"]
    assert row(out, b.sanad_id)["rule_v2_ibn_hajar"] == "sahih_li_dhatihi"


def test_follower_from_a_higher_teacher_is_qasira_and_another_companion_is_shahid():
    a = chain(1, A1, W, T, C1)
    q = chain(2, A2, S, T2, C1)
    out = run([a, q], base_people() | {W: level(6)}, books(A1, A2))
    assert row(out, a.sanad_id)["divergence_v2_ibn_hajar"] == "mutabaa_qasira"
    sh = chain(2, A2, S, T2, C2)
    out = run([a, sh], base_people() | {W: level(6)}, books(A1, A2))
    assert row(out, a.sanad_id)["divergence_v2_ibn_hajar"] == "shahid"


def test_uncorroborated_light_defect_is_daif_and_a_fatal_witness_does_not_count():
    a = chain(1, A1, W, T, C1)
    out = run([a], base_people() | {W: level(7)}, books(A1))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "daif"
    assert row(out, a.sanad_id)["code_v2_ibn_hajar"] == 2
    f = chain(2, A2, 30, T2, C1)                       # the only other route runs through a level-11 narrator
    out = run([a, f], base_people() | {W: level(7), 30: level(11)}, books(A1, A2))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "daif"


def test_fatal_and_unrepairable_defects_keep_the_v1_code():
    a = chain(1, A1, 30, T, C1)
    b = chain(2, A2, S, T, C1)
    out = run([a, b], base_people() | {30: level(11)}, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["rule_v2_ibn_hajar"] == "fatal" and r["code_v2_ibn_hajar"] == r["chain_code"] == 4
    out = run([a, b], base_people() | {30: level(9)}, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["rule_v2_ibn_hajar"] == "not_repairable" and r["code_v2_ibn_hajar"] == r["chain_code"] == 2


def test_hasan_li_dhatihi_and_sahih_li_ghayrihi():
    a = chain(1, A1, W, T, C1)
    out = run([a], base_people() | {W: level(4)}, books(A1))
    assert row(out, a.sanad_id)["rule_v2_ibn_hajar"] == "hasan_li_dhatihi"
    b = chain(2, A2, S, T2, C2)
    out = run([a, b], base_people() | {W: level(4)}, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["rule_v2_ibn_hajar"] == "sahih_li_ghayrihi" and r["code_v2_ibn_hajar"] == 0
    assert r["divergence_v2_ibn_hajar"] == "shahid"


def test_level_5_differs_between_the_rulesets():
    a = chain(1, A1, W, T, C1)
    out = run([a], base_people() | {W: level(5)}, books(A1))
    r = row(out, a.sanad_id)
    assert (r["rule_v2_ibn_hajar"], r["code_v2_ibn_hajar"]) == ("daif", 2)
    assert (r["rule_v2_ibn_al_salah"], r["code_v2_ibn_al_salah"]) == ("hasan_li_dhatihi", 1)
    b = chain(2, A2, S, T, C1)
    out = run([a, b], base_people() | {W: level(5)}, books(A1, A2))
    r = row(out, a.sanad_id)
    assert (r["rule_v2_ibn_hajar"], r["code_v2_ibn_hajar"]) == ("hasan_li_ghayrihi", 1)
    assert (r["rule_v2_ibn_al_salah"], r["code_v2_ibn_al_salah"]) == ("sahih_li_ghayrihi", 0)


def test_mursal_rules():
    M, M2 = 40, 41
    people = base_people() | {M: thiqa(3), M2: thiqa(3)}
    a = chain(1, A1, S, M)                               # mursal: M (not a companion) at the top
    b = chain(2, A2, S2, M, C1)                          # the same report connected through M
    out = run([a, b], people, books(A1, A2))
    r = row(out, a.sanad_id)
    assert (r["rule_v2_ibn_hajar"], r["divergence_v2_ibn_hajar"]) == ("hasan_li_ghayrihi", "wasl")
    assert r["code_v2_alt_mursal_shafii"] == 2           # al-Shafi'i: the witness must not come through M
    d = chain(3, A3, 23, M2)                             # a mursal by another mursil
    out = run([a, b, d], people | {23: thiqa(5)}, books(A1, A2, A3))
    assert row(out, a.sanad_id)["code_v2_alt_mursal_shafii"] == 1


def test_mudallis_muanan_is_a_light_defect():
    """An untiered flagged mudallis (treated as tier 3, derive.tadlis.untiered_tadlis) outside
    the Sahihayn: his 'an is a light defect. Tiers are tested in test_pr5.py."""
    D = 50
    people = base_people() | {D: {"rank_no": 3, "tabaka": 4, "tadlis": 1}}
    bks = {3: {"author_no": 100, "compiler_rawi": A1}, 4: {"author_no": 101, "compiler_rawi": A2}}
    a = chain(3, A1, D, T, C1, words={2: ("عن", "عن", "an")})
    out = run([a], people, bks)
    r = row(out, a.sanad_id)
    assert r["defects_v2_ibn_hajar"] == ["mudallis_muanan_tier_3"] and r["code_v2_ibn_hajar"] == 2
    b = chain(4, A2, S, T, C1)
    out = run([a, b], people, bks)
    assert row(out, a.sanad_id)["code_v2_ibn_hajar"] == 1


def test_weakest_positions_versus_every_light_defect():
    X, Y, Z = 60, 61, 62
    people = base_people() | {X: level(5, 6), Y: level(8, 4), Z: thiqa(4)}
    a = chain(1, A1, X, Y, T, C1)                        # weakest: Y (level 8); X (level 5) is light too
    b = chain(2, A2, X, Z, T, C1)                        # avoids Y, shares X
    out = run([a, b], people, books(A1, A2))
    r = row(out, a.sanad_id)
    assert r["weak_nodes_v2_ibn_hajar"] == [f"r{X}", f"r{Y}"]   # each_defect: both must be covered
    assert r["code_v2_ibn_hajar"] == 2
    assert r["code_v2_alt_weakest"] == 1                         # PR 4: the weakest only
    assert r["code_v2_alt_all_light_defects"] == 2


def test_group_v2_takes_the_best_chain_and_receipt_names_the_rule():
    import json
    a = chain(1, A1, W, T, C1)
    b = chain(2, A2, S, T2, C2)
    out = run([a, b], base_people() | {W: level(6)}, books(A1, A2))
    rec = out["record"]
    assert rec["code_v2_ibn_hajar"] == 0 and rec["rule_v2_ibn_hajar"] == "sahih_li_dhatihi"
    assert rec["derive_version"] == 4 and rec["structure_version"] == 5
    rc = json.loads(rec["receipt_v2"])
    assert set(rc) == {"ibn_hajar", "ibn_al_salah"}
    assert rc["ibn_hajar"][-1]["rule"] == "sahih_li_dhatihi"


# ---------------------------------------------------------------- number class and qara'in

def test_class_cut_points():
    assert structure.class_of_count(None) is None and structure.class_of_count(0) is None
    assert [structure.class_of_count(n, 10) for n in (1, 2, 3, 9, 10)] == \
        ["gharib", "aziz", "mashhur", "mashhur", "mutawatir_count"]
    assert structure.number_class(1, [1, 4], 10) == "gharib_mutlaq"
    assert structure.number_class(1, [4], 10) == "gharib_nisbi"
    assert structure.number_class(4, [], 4) == "mutawatir_count"


def test_number_class_on_bundles_and_qarain():
    # one companion, one student: gharib mutlaq
    S3 = 23
    people = base_people() | {S3: thiqa(5)}
    out = run([chain(1, A1, S, T, C1), chain(2, A2, S2, T, C1)], people, books(A1, A2))
    r = out["record"]
    assert r["number_class"] == "gharib_mutlaq" and 1 in r["tafarrud_layers"]
    assert r["in_sahihayn"] is True                      # book 1 is in config qarain.sahihayn_book_ids
    assert r["huffaz_chain"] is False                    # gharib: the hafiz-chain indicator does not apply
    # two companions, two teachers, two students at each layer: 'aziz both ways
    out = run([chain(1, A1, S, T, C1), chain(2, A2, S2, T2, C2)], people, books(A1, A2))
    r = out["record"]
    assert (r["number_class"], r["number_class_width"]) == ("aziz", "aziz")
    assert r["huffaz_chain"] is False                    # thiqa (level 3) is not a hafiz-imam (level <= 2)
    people2 = people | {T: level(2, 3), T2: level(2, 3), S: level(2, 5), S2: level(2, 5)}
    r = run([chain(1, A1, S, T, C1), chain(2, A2, S2, T2, C2)], people2, books(A1, A2))["record"]
    assert r["huffaz_chain"] is True and r["n_huffaz_chains"] == 2


def test_pool_joins_groups():
    people = base_people()
    corpus = make_corpus(people, books(A1, A2))
    g1, g2 = [chain(1, A1, S, T, C1)], [chain(2, A2, S2, T2, C2)]
    res = pool.analyse([7, 8], con=object(), corpus=corpus, by_group={7: g1, 8: g2}, label="test")
    assert res["n_chains"] == 2 and res["kappa_all"] == 2 and res["companions"] == 2
    assert res["number_class"] == "aziz"
    single = pool.analyse([7], con=object(), corpus=corpus, by_group={7: g1})
    assert single["kappa_all"] == 1


# ---------------------------------------------------------------- lists

def test_normalize_is_conservative_and_versioned():
    assert lists.NORMALIZE_VERSION == 1
    assert lists.normalize("مَنْ كَذَبَ عَلَيَّ مُتَعَمِّداً") == "من كذب علي متعمدا"
    assert lists.normalize("أَحَبَّ إِلَيْهِ مِنْ وَالِدِهِ") == "احب اليه من والده"
    assert lists.normalize("فـــليتبوأ مقعدَهُ") == "فليتبوا مقعده"
    assert lists.normalize("الصلاةُ ﷺ") == "الصلاه"


def test_count_words():
    assert lists.count_words("خمسة عشر") == 15
    assert lists.count_words("اثني عشر") == 12
    assert lists.count_words("عشرة") == 10
    assert lists.count_words("تسعة") == 9
    assert lists.count_words("ثلاثة وعشرين") == 23
    assert lists.count_words("نيف وعشرين") is None


def test_auto_rule():
    def c(rank, g, score, support, kind="wording", w="من كذب علي متعمدا فليتبوأ"):
        return {"list": "k", "entry": "1", "kind": kind, "rank": rank, "group_id": g, "score": score,
                "containment": 1.0, "opening": 1.0, "support": support, "wording": w}
    ok = lists.auto_rows([c(1, 1, 1.0, 700), c(2, 9, 0.7, 40)])[0]
    assert (ok["status"], ok["group_id"]) == ("auto", 1)
    assert lists.auto_rows([c(1, 1, 1.0, 700), c(2, 9, 0.8, 40)])[0]["status"] == "needs_review"   # margin
    assert lists.auto_rows([c(1, 1, 1.0, 1), c(2, 9, 0.3, 0)])[0]["status"] == "needs_review"      # support
    assert lists.auto_rows([c(1, 1, 1.0, 50, w="الحوض")])[0]["status"] == "needs_review"          # too short
    assert lists.auto_rows([c(1, 1, 1.0, 50, kind="topic")])[0]["status"] == "needs_review"


def test_kattani_parse_from_the_committed_source():
    ents = lists.parse_kattani()
    assert len(ents) == 308
    by = {e["index"]: e for e in ents}
    assert by["2"]["wording"].startswith("من كذب علي متعمد")
    assert by["8"]["in_azhar"] and by["8"]["suyuti"]["stated_count"] == 34
    assert by["9"]["suyuti"]["stated_count"] == 15 and by["9"]["companions_numbered"] == 19
    assert "238b" in by and "267b" in by
    assert sum(e["in_azhar"] for e in ents) == 111


@pytest.mark.skipif(not (paths.ROOT / "lists" / "suyuti.yaml").exists(), reason="run `make lists`")
def test_lists_files_say_where_they_come_from():
    k = yaml.safe_load((paths.ROOT / "lists" / "kattani.yaml").read_text(encoding="utf-8"))
    s = yaml.safe_load((paths.ROOT / "lists" / "suyuti.yaml").read_text(encoding="utf-8"))
    assert "7016" in k["meta"]["source"] and len(k["entries"]) == 308
    assert s["meta"]["source"].startswith("SECONDARY") and len(s["entries"]) == 111
    assert all(e["cited_sources"] is None for e in s["entries"])
    assert all(e["url"].startswith("https://shamela.ws/book/7016/") for e in k["entries"])
