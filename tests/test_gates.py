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


def test_kappa_lower_is_a_lower_bound(records):
    r = records[records["status"] == "ok"]
    for th in ("all", "above_matruk", "saduq_up", "thiqa_up"):
        assert (r[f"kappa_lower_{th}"] <= r[f"kappa_{th}"]).all(), th
    # thresholds are nested: a stricter threshold never raises kappa
    assert (r["kappa_above_matruk"] <= r["kappa_all"]).all()
    assert (r["kappa_saduq_up"] <= r["kappa_above_matruk"]).all()
    assert (r["kappa_thiqa_up"] <= r["kappa_saduq_up"]).all()


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
    for col in ("receipt", "derived_level", "status"):
        vals = records[col].dropna().astype(str)
        hits = vals[vals.str.contains(VERDICT_WORDS)]
        assert hits.empty, (col, hits.head(3).tolist())
    rc = json.loads(records.dropna(subset=["receipt"])["receipt"].iloc[0])
    assert [s["check"] for s in rc][:3] == ["chains read", "best chain selection", "chain grade"]
