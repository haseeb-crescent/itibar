"""Corpus-level gates over out/records.parquet and out/chains.parquet."""

import json
import re

import pytest

pytestmark = pytest.mark.gate

DOCUMENTED_CLASSES = {"compiler_strictly_weakest"}


def test_weakest_link_matches_max_rank(chains_table):
    """Our weakest link per chain equals sanads.max_rank for > 99% of chains
    (like-for-like: whole stored chain, as the source computes it)."""
    t = chains_table
    share = t["agree_full"].mean()
    assert share > 0.99, f"agree_full = {share:.4%}"


def test_every_derived_disagreement_is_documented(chains_table):
    """The derived chain grade excludes the compiler at pos 0 and max_rank does
    not; every resulting disagreement must fall in a documented class."""
    t = chains_table
    bad = t[~t["agree_derived"]]
    classes = set(bad["disagreement_class"].dropna())
    assert classes <= DOCUMENTED_CLASSES, classes - DOCUMENTED_CLASSES
    assert bad["disagreement_class"].notna().all()
    # and the class means what it says
    cw = bad[bad["disagreement_class"] == "compiler_strictly_weakest"]
    assert (cw["compiler_rank_no"] == cw["max_rank"]).all()
    assert (cw["weakest_rank_no_derived"] < cw["max_rank"]).all()


def test_companion_count_within_upstream_band(records):
    """Our chain-end companion count sits within the band the upstream audit
    shows against the declared sahaba_qty: for the most-narrated groups,
    upstream's recount <= ours <= declared; corpus-wide the median ratio
    ours/declared lies inside upstream's spot-check ratio range."""
    r = records[records["status"] == "ok"]
    top = r.sort_values("repeat_qty", ascending=False).head(10)
    assert (top["companions_upstream_def"] <= top["companions_chain_end"]).all()
    assert (top["companions_chain_end"] <= top["sahaba_qty"]).all()
    lo = (top["companions_upstream_def"] / top["sahaba_qty"]).min()
    hi = (top["companions_upstream_def"] / top["sahaba_qty"]).max()
    big = r[r["sahaba_qty"] >= 10]
    med = (big["companions_chain_end"] / big["sahaba_qty"]).median()
    assert lo <= med <= max(hi, 1.0), (lo, med, hi)
    assert (big["companions_chain_end"] > big["sahaba_qty"]).mean() < 0.02
    assert (r["companions_chain_end"] >= r["companions_upstream_def"]).all()


def test_one_record_per_group(records, con):
    n = con.sql("SELECT count(*) FROM meaning_groups").fetchall()[0][0]
    assert len(records) == n
    assert records["group_id"].is_unique


def test_kappa_lower_is_the_minimum_over_three_hypotheses(records):
    """kappa_lower = min(unmerged, merged, nocompat). We store nocompat and the
    name of the hypothesis attaining the minimum; the bound never exceeds kappa
    or nocompat, and nocompat (edges removed from the unmerged graph) never
    exceeds kappa."""
    r = records[records["status"] == "ok"]
    for th in ("all", "above_matruk", "saduq_up", "thiqa_up"):
        assert (r[f"kappa_lower_{th}"] <= r[f"kappa_{th}"]).all(), th
        assert (r[f"kappa_lower_{th}"] <= r[f"kappa_nocompat_{th}"]).all(), th
        assert (r[f"kappa_nocompat_{th}"] <= r[f"kappa_{th}"]).all(), th
        assert set(r[f"kappa_lower_source_{th}"]) <= {"unmerged", "merged", "nocompat"}, th
        nc = r[r[f"kappa_lower_source_{th}"] == "nocompat"]
        assert (nc[f"kappa_lower_{th}"] == nc[f"kappa_nocompat_{th}"]).all(), th
    assert (records["structure_version"] == 3).all()
    assert (records["derive_version"] == 2).all()
    # dropping only the years-incompatible links removes a subset of what nocompat drops
    for th in ("all", "above_matruk", "saduq_up", "thiqa_up"):
        assert (r[f"kappa_nocompat_{th}"] <= r[f"kappa_nocompat_years_{th}"]).all(), th
        assert (r[f"kappa_nocompat_years_{th}"] <= r[f"kappa_{th}"]).all(), th
    # thresholds are nested: a stricter threshold never raises kappa
    assert (r["kappa_above_matruk"] <= r["kappa_all"]).all()
    assert (r["kappa_saduq_up"] <= r["kappa_above_matruk"]).all()
    assert (r["kappa_thiqa_up"] <= r["kappa_saduq_up"]).all()


def test_every_zero_kappa_has_a_reason_and_none_is_other(records):
    """kappa_zero_reason is set exactly when there is no PROPHET -> book route at
    `everyone`, and every such group is explained by its chains: no chains, no
    chain ending in a companion, or a break marker in every companion-ending
    chain. `other` (a continuous chain exists yet no route) must not occur."""
    reason = records["kappa_zero_reason"]
    zero = (records["status"] == "no_chains") | (records["kappa_all"] == 0)
    assert (reason.notna() == zero).all()
    assert ((reason == "no_chains") == (records["status"] == "no_chains")).all()
    assert (reason == "other").sum() == 0, records.loc[reason == "other", "group_id"].head(10).tolist()
    nce = records[reason == "no_companion_end"]
    assert (nce["n_chains_companion_end"] == 0).all()
    bo = records[reason == "broken_only"]
    assert (bo["n_chains_companion_end"] > 0).all() and (bo["n_chains_connected"] == 0).all()
    ok = records[records["status"] == "ok"]
    assert (ok.loc[ok["n_chains_connected"] > 0, "kappa_all"] > 0).all()
    # The converse does not hold: a route can be assembled from chains broken at
    # different places (DECISIONS D31); those groups are listed in the audit, §9.
    spliced = ok[(ok["kappa_all"] > 0) & (ok["n_chains_connected"] == 0)]
    assert len(spliced) <= 0.001 * len(ok), len(spliced)


def test_cut_vertices_iff_kappa_one(records):
    r = records[(records["status"] == "ok") & (records["kappa_all"] > 0)]
    has_cut = r["n_cut_vertices"] > 0
    assert (has_cut == (r["kappa_all"] == 1)).all()
    # bypass paths are zero iff the common links form a cut
    one_cl = r[r["n_common_links"] == 1]
    cl_is_cut = [cl[0] in set(cv) for cl, cv in zip(one_cl["common_links"], one_cl["cut_vertices"])]
    assert ((one_cl["bypass_paths"] == 0).to_numpy() == cl_is_cut).all()


def test_recorded_values_are_never_overwritten(records, con):
    mg = con.sql("SELECT id AS group_id, matn_no, sahaba_qty FROM meaning_groups").df()
    m = records.merge(mg, on="group_id", suffixes=("", "_src"))
    assert (m["matn_no_group"] == m["matn_no"]).all()
    assert (m["sahaba_qty"] == m["sahaba_qty_src"]).all()


VERDICT_WORDS = re.compile(r"\b(?:weak|fabricat\w*|forged|spurious|authentic|unreliable|liar)\b", re.I)


def test_outputs_issue_no_verdict_words(records):
    """itibar reports structure and derives grades mechanically; its own text
    never uses verdict words (source labels are quoted in Arabic)."""
    for col in ("receipt", "receipt_v2", "derived_level", "status", "rule_v2_ibn_hajar", "rule_v2_ibn_al_salah",
                "divergence_v2_ibn_hajar", "number_class"):
        vals = records[col].dropna().astype(str)
        hits = vals[vals.str.contains(VERDICT_WORDS)]
        assert hits.empty, (col, hits.head(3).tolist())
    rc = json.loads(records.dropna(subset=["receipt"])["receipt"].iloc[0])
    assert [s["check"] for s in rc][:3] == ["chains read", "best chain selection", "chain grade"]


def test_v2_agreement_is_at_least_v1_under_both_rulesets(records):
    """The corroborated grade must agree with the source's recorded group grade at
    least as often as the best-single-chain grade, under every ruleset. Nothing is
    tuned to make this pass (README, reports/audit.md section 11). A corpus-level
    property: on the CI fixture (a few hundred sampled groups) a two-group swing
    decides it, so it is enforced on the full corpus only."""
    if len(records) < 20000:
        pytest.skip(f"corpus-level gate; {len(records)} records is a sample (run on the full corpus)")
    r = records[records["status"] == "ok"]
    v1 = (r["derived_code"] == r["matn_no_group"]).mean()
    for rs in ("ibn_hajar", "ibn_al_salah"):
        v2 = (r[f"code_v2_{rs}"] == r["matn_no_group"]).mean()
        assert v2 >= v1, (rs, round(v2, 4), round(v1, 4))


def test_v2_rules_are_consistent(chains_table, records):
    """Unrepairable and fatal chains keep their v1 code; an upgrade always names
    its witness (an attested chain or a route) and its divergence class; codes
    follow the rule."""
    t = chains_table
    for rs in ("ibn_hajar", "ibn_al_salah"):
        kept = t[t[f"rule_v2_{rs}"].isin(["fatal", "not_repairable"])]
        assert (kept[f"code_v2_{rs}"] == kept["chain_code"]).all(), rs
        up = t[t[f"rule_v2_{rs}"].isin(["hasan_li_ghayrihi", "sahih_li_ghayrihi"])]
        assert up[f"divergence_v2_{rs}"].notna().all(), rs
        codes = {"sahih_li_dhatihi": 0, "sahih_li_ghayrihi": 0, "hasan_li_dhatihi": 1, "hasan_li_ghayrihi": 1,
                 "daif": 2}
        for rule, code in codes.items():
            assert (t.loc[t[f"rule_v2_{rs}"] == rule, f"code_v2_{rs}"] == code).all(), (rs, rule)
    r = records[records["status"] == "ok"]
    assert r["code_v2_ibn_hajar"].notna().all() and r["code_v2_ibn_al_salah"].notna().all()


def test_number_class_follows_its_definition(records):
    """number_class is read off min_width with the configured cut points; gharib
    splits by whether layer 1 is a tafarrud layer; the kappa reading uses kappa_all."""
    from itibar import structure
    N = structure.tawatur_n()
    r = records[records["status"] == "ok"]
    for mw, taf, nc in zip(r["min_width"], r["tafarrud_layers"], r["number_class"]):
        import math
        exp = structure.number_class(None if math.isnan(mw) else int(mw), list(taf) if taf is not None else [], N)
        nc = nc if isinstance(nc, str) else None
        assert nc == exp, (mw, taf, nc, exp)
    for k, nk in zip(r["kappa_all"], r["number_class_kappa"]):
        assert (nk if isinstance(nk, str) else None) == structure.class_of_count(int(k), N)


def test_qarain_flags_follow_their_definitions(records):
    r = records[records["status"] == "ok"]
    assert (r["sound_distinct_routes"] == (r["kappa_saduq_up"] >= 3)).all()
    assert not r.loc[r["huffaz_chain"], "number_class"].isin(["gharib_mutlaq", "gharib_nisbi"]).any()
    assert (r.loc[r["huffaz_chain"], "n_huffaz_chains"] > 0).all()
    assert (r["in_sahihayn"] <= r["in_sahih_class"]).all()
