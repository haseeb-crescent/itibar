"""reports/audit.md, the PR 6 sections of §11 (the unnamed companion, conditional rulings, the
hearing check on tier 4, the two default flips; each against the stage before it, out/stages/)
and Appendix B (every designation of an unnamed person at a chain top). Called by itibar.audit."""

from __future__ import annotations

import csv
import re
from collections import Counter

import pandas as pd

from itibar import audit_pr5, conditional, lists, paths, stages, unnamed

PR5_FINAL, S_UNNAMED, S_COND, S_SHAHID, S_UNION = ("s7_named_elsewhere", "s8_unnamed_companion", "s9_conditional",
                                                   "s10_shahid_group", "s11_mudallis_union")


def _md(df, fmt="{:,.3f}"):
    return audit_pr5._md(df, fmt)


def _agree(r, col="code_v2_ibn_hajar"):
    return (r[col] == r["matn_no_group"]).mean()


def _changed(a, b, col="code_v2_ibn_hajar"):
    m = a[["group_id", col]].merge(b[["group_id", col]], on="group_id", suffixes=("_a", "_b"))
    return m[m[f"{col}_a"] != m[f"{col}_b"]]


def weakest_table(r: pd.DataFrame, ch: pd.DataFrame, con, top: int = 15, raw=None, names=None) -> pd.DataFrame:
    """Narrators most often among the weakest positions of the v2 chain in the disagreeing groups
    (the table of audit §11.13 and PR 5's §11.9)."""
    names = names or dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
    best = r[["group_id", "best_sanad_v2_ibn_hajar", "code_v2_ibn_hajar", "matn_no_group"]].merge(
        ch[["sanad_id", "weakest_positions"]], left_on="best_sanad_v2_ibn_hajar", right_on="sanad_id", how="left")
    dis = best[best["code_v2_ibn_hajar"] != best["matn_no_group"]]
    if raw is None:
        sids = [int(x) for x in dis["best_sanad_v2_ibn_hajar"].dropna()]
        con.execute("CREATE OR REPLACE TEMP TABLE _ws AS SELECT unnest(?::BIGINT[]) AS sid", [sids])
        raw = dict(con.sql("SELECT sanad_id, list(rawi_id ORDER BY pos) FROM sanad_rawis WHERE sanad_id IN "
                           "(SELECT sid FROM _ws) GROUP BY 1").fetchall())
    cnt: Counter = Counter()
    for sid, wp in zip(dis["best_sanad_v2_ibn_hajar"], dis["weakest_positions"]):
        rw = raw.get(int(sid), [])
        for p in set(wp if wp is not None else []):
            if p < len(rw):
                cnt[int(rw[p])] += 1
    return pd.DataFrame([{"rawi_id": k, "narrator": f"{names.get(k)} (r{k})", "groups_disagreeing": v}
                         for k, v in cnt.most_common(top)])


def _before_after_weakest(a, cha, b, chb, con, top=15) -> str:
    names = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
    ta = weakest_table(a, cha, con, 40, names=names)
    tb = weakest_table(b, chb, con, 40, names=names)
    ids = list(dict.fromkeys(list(ta["rawi_id"][:top]) + list(tb["rawi_id"][:top])))
    m = {int(x): int(y) for x, y in zip(ta["rawi_id"], ta["groups_disagreeing"])}
    n = {int(x): int(y) for x, y in zip(tb["rawi_id"], tb["groups_disagreeing"])}
    rows = [{"narrator": f"{names.get(i)} (r{i})", "before": m.get(i, 0), "after": n.get(i, 0)} for i in ids]
    return _md(pd.DataFrame(rows))


def designations() -> pd.DataFrame:
    p = paths.OUT_DIR / "unnamed_tops.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


# ---------------------------------------------------------------- §1 the unnamed companion

def unnamed_section(con, keep) -> str:
    out = ["### 11.9 PR 6 §1 The unnamed companion\n"]
    u = designations()
    if u.empty:
        return out[0] + "_(run `make words` first)_\n"
    out.append(f"{len(u):,} chains end in the unnamed person (`اسم مبهم`, r1131). His designation is read from "
               "`hadiths.nass`: the mention (`hadith_rawis` offsets, the chain aligned as in `words.py`) and the words "
               "after it up to the next mention, a delimiter or a transmission word (README). How the mention was "
               "found:\n")
    out.append(_md(u["method"].value_counts().rename_axis("method").reset_index(name="chain tops")))
    out.append("\n*sanad_fallback_text* (no mention of him at all): what stands before the matn is mostly the matn's own "
               "opening, so nothing is read as a designation (class `none_text`, D69). The classes "
               "(`config/structure.yaml: unnamed_companion.phrases`, by precedence companion, ansar_muhajir, none; "
               "*unclassified* = no phrase matched, read as none):\n")
    t = pd.crosstab(u["cls"], u["method"])
    t["total"] = t.sum(axis=1)
    out.append(_md(t.reset_index().rename(columns={"cls": "class"})))
    out.append("\nThe phrase that classified each companion and Anṣār/Muhājirūn designation:\n")
    ph = u[u["cls"].isin(["companion", "ansar_muhajir"])].groupby(["cls", "phrase"]).size().rename("chain tops")
    out.append(_md(ph.reset_index().sort_values(["cls", "chain tops"], ascending=[True, False]).rename(
        columns={"cls": "class"})))
    n_distinct = u.loc[u["method"] != "sanad_fallback_text", "designation"].map(lists.normalize).nunique()
    out.append(f"\n{n_distinct:,} distinct designations (normalized); the 40 most frequent are below and every one "
               "with its count is in Appendix B. The most frequent *unclassified* ones, for the reviewer completing "
               "the list:\n")
    dd = u[u["method"] != "sanad_fallback_text"].assign(d=lambda x: x["designation"].map(lists.normalize))
    top = dd.groupby(["d", "cls"]).size().rename("n").reset_index().sort_values("n", ascending=False)
    out.append(_md(top.head(40).rename(columns={"d": "designation (normalized)", "cls": "class", "n": "chain tops"})))
    out.append("")
    out.append(_md(top[top["cls"] == "unclassified"].head(20).rename(
        columns={"d": "designation (normalized)", "cls": "class", "n": "chain tops"})))
    a, cha = keep.get(PR5_FINAL, (None, None))
    b, chb = keep.get(S_UNNAMED, (None, None))
    if a is None or b is None:
        return "\n".join(out) + "\n_(run `make stages` for the before/after)_\n"
    ab = a.merge(b, on="group_id", suffixes=("_a", "_b"))
    up = ab[(ab["kappa_zero_reason_a"] == "no_companion_end") & (ab["kappa_all_b"] >= 1)]
    out.append(f"\n**Effect** (stage {S_UNNAMED} against {PR5_FINAL}, PR 5's defaults): chain tops read as an unnamed "
               f"companion {int(b['n_unnamed_companion_chains'].sum()):,} in {int(b['unnamed_companion_node'].sum()):,} "
               f"groups; chains not ending in a companion (mursal) {int(a['n_mursal_chains'].sum()):,} → "
               f"{int(b['n_mursal_chains'].sum()):,}; groups with `kappa_zero_reason: no_companion_end` "
               f"{int((a['kappa_zero_reason'] == 'no_companion_end').sum()):,} → "
               f"{int((b['kappa_zero_reason'] == 'no_companion_end').sum()):,}, of which {len(up):,} now have κ_all ≥ 1; "
               f"κ_all changes in {int((ab['kappa_all_a'] != ab['kappa_all_b']).sum()):,} groups; "
               f"`kappa_unnamed_split` (each unnamed companion a different man) exceeds the merged κ_all in "
               f"{int(((b['kappa_unnamed_split'].notna()) & (b['kappa_unnamed_split'] > b['kappa_all'])).sum()):,} "
               f"groups. v2 (`ibn_hajar`) changes in {len(_changed(a, b)):,} groups; agreement "
               f"{_agree(a):.4f} → {_agree(b):.4f} (`ibn_al_salah` {_agree(a, 'code_v2_ibn_al_salah'):.4f} → "
               f"{_agree(b, 'code_v2_ibn_al_salah'):.4f}; v1 {_agree(a, 'derived_code'):.4f} → "
               f"{_agree(b, 'derived_code'):.4f}).\n")
    nc = pd.crosstab(a["number_class"].fillna("no route"), b["number_class"].fillna("no route"))
    out.append("Number class, before (rows) and after (columns):\n")
    out.append(_md(nc.reset_index().rename(columns={"number_class": "before \\ after"})))
    # the PR 5 disagreements with the unnamed person among the weakest
    raw_ids = set()
    best = a[["group_id", "best_sanad_v2_ibn_hajar", "code_v2_ibn_hajar", "matn_no_group"]].merge(
        cha[["sanad_id", "weakest_positions", "length"]], left_on="best_sanad_v2_ibn_hajar", right_on="sanad_id")
    dis = best[best["code_v2_ibn_hajar"] != best["matn_no_group"]]
    sids = [int(x) for x in dis["sanad_id"]]
    con.execute("CREATE OR REPLACE TEMP TABLE _us AS SELECT unnest(?::BIGINT[]) AS sid", [sids])
    raw = dict(con.sql("SELECT sanad_id, list(rawi_id ORDER BY pos) FROM sanad_rawis WHERE sanad_id IN "
                       "(SELECT sid FROM _us) GROUP BY 1").fetchall())
    rows = []
    for g, sid, wp in zip(dis["group_id"], dis["sanad_id"], dis["weakest_positions"]):
        rw = raw.get(int(sid), [])
        ps = [p for p in (wp if wp is not None else []) if p < len(rw) and rw[p] == 1131]
        if ps:
            rows.append({"group_id": int(g), "where": "top" if all(p == len(rw) - 1 for p in ps) else "mid"})
            raw_ids.add(int(g))
    w = pd.DataFrame(rows)
    if len(w):
        bb = b.set_index("group_id")
        w["agree_after"] = [bool(bb.loc[g, "code_v2_ibn_hajar"] == bb.loc[g, "matn_no_group"]) for g in w["group_id"]]
        w["changed"] = [bool(bb.loc[g, "code_v2_ibn_hajar"] != a.set_index("group_id").loc[g, "code_v2_ibn_hajar"])
                        for g in w["group_id"]]
        t = w.groupby("where").agg(groups=("group_id", "size"), v2_changed=("changed", "sum"),
                                    agree_now=("agree_after", "sum")).reset_index()
        out.append(f"\nPR 5's {len(w):,} disagreeing groups with the unnamed person among the weakest positions of their "
                   "v2 chain (the brief's 631 counts his positions: a group can hold two), by where he sits, and how many "
                   "now agree:\n")
        out.append(_md(t))
    out.append("\nThe residue table before and after (narrators most often weakest in the disagreeing groups):\n")
    out.append(_before_after_weakest(a, cha, b, chb, con))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- §2 conditional rulings

def conditional_section(con, keep, r, ch) -> str:
    out = ["### 11.10 PR 6 §2 Conditional narrator rulings\n"]
    if not conditional.CONF_PATH.exists():
        return out[0] + "_(run `make conditional` first)_\n"
    conf = list(csv.DictReader(open(conditional.CONF_PATH, encoding="utf-8")))
    df = pd.DataFrame(conf)
    seeds = conditional.seed(con)
    why = Counter(w for s in seeds for w in s["why"])
    tq = conditional.load_taqrib()
    nas = dict(con.sql("SELECT id, nasab FROM rawis WHERE nasab IS NOT NULL").fetchall())
    ok_t = sum(1 for s in seeds if conditional.entry_ok((tq.get(s["rawi_id"]) or {}).get("taqrib_line"),
                                                        {**s, "nasab": nas.get(s["rawi_id"])},
                                                        int((tq.get(s["rawi_id"]) or {}).get("taqrib_prefix_words") or 0)))
    ok_h = sum(1 for s in seeds if conditional.entry_ok((tq.get(s["rawi_id"]) or {}).get("tahrir_line"),
                                                        {**s, "nasab": nas.get(s["rawi_id"])},
                                                        int((tq.get(s["rawi_id"]) or {}).get("tahrir_prefix_words") or 0)))
    kaw = conditional.kawakib_entries_matched(con)
    out.append(f"**Seed** ({len(seeds):,} narrators looked up; a narrator can carry several reasons): PR 5's residue table "
               f"{why.get('residue_table', 0)}, a conditional label {why.get('label', 0)}, the source's `has_ikhtilat` "
               f"flag {why.get('has_ikhtilat', 0)}, the brief's named cases {why.get('brief', 0)}, an entry of "
               f"al-Kawākib al-Nayyirāt {why.get('kawakib', 0)}, of al-ʿAlāʾī's al-Mukhtaliṭīn {why.get('alai', 0)}, of "
               f"al-Ightibāṭ {why.get('ightibat', 0)}, of Ibn Rajab's section {why.get('ibn_rajab', 0)} (entries matched "
               "to `rawis` by the mudallisin matcher, D71). Their entries were fetched from Shamela "
               f"(`lists/source/conditional_taqrib.jsonl`) and accepted after an identity check (README): Taqrīb "
               f"{ok_t:,}, Taḥrīr {ok_h:,}. al-Kawākib al-Nayyirāt (Shamela 309, `lists/source/kawakib_309.jsonl`): "
               f"{len(kaw):,} entries parsed, {sum(1 for e in kaw if e.get('match_status') == 'auto'):,} matched to "
               "`rawis` by the mudallisin matcher's auto rule.\n")
    t = pd.crosstab(df["kind"], df["status"])
    t["total"] = t.sum(axis=1)
    out.append("**Rulings by kind and status** (`lists/conditional_confirmed.csv`; `human` rows are the reviewer's):\n")
    out.append(_md(t.reset_index()))
    inforce = df[df["status"].isin(["auto", "human"])]
    eff = inforce.groupby(["kind", "effect"]).size().rename("rulings").reset_index()
    out.append(f"\nIn force: {len(inforce):,} rulings on {inforce['rawi_id'].nunique():,} narrators; by effect:\n")
    out.append(_md(eff))
    rv = Counter(re.sub(r" \(«.*", "", part).strip() for x in df.loc[df["status"] == "needs_review", "note"].fillna("")
                 for part in x.split("; ") if part.strip())
    out.append("\nWhy rows wait for review (a row can carry several reasons): "
               + "; ".join(f"{k} {v:,}" for k, v in rv.most_common(12)) + ".\n")
    fired = Counter(x.split(":")[1] for xs in ch.get("rulings_v2_ibn_hajar", pd.Series(dtype=object)).dropna() for x in xs)
    nch = int(ch.get("rulings_v2_ibn_hajar", pd.Series(dtype=object)).dropna().map(len).gt(0).sum())
    out.append(f"Links where a ruling fired, final run (`ibn_hajar`, a chain counted once per ruling): "
               + "; ".join(f"{k} {v:,}" for k, v in sorted(fired.items())) + f"; chains with any: {nch:,}.\n")
    a, cha = keep.get(S_UNNAMED, (None, None))
    b, chb = keep.get(S_COND, (None, None))
    if a is not None and b is not None:
        out.append(f"**Effect** (stage {S_COND} against {S_UNNAMED}): v2 changes in {len(_changed(a, b)):,} groups; "
                   f"agreement {_agree(a):.4f} → {_agree(b):.4f} (`ibn_al_salah` {_agree(a, 'code_v2_ibn_al_salah'):.4f} "
                   f"→ {_agree(b, 'code_v2_ibn_al_salah'):.4f}). The residue table before and after:\n")
        out.append(_before_after_weakest(a, cha, b, chb, con))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- §2 (end) tier-4 hearing

def tier4_section(con, r, ch) -> str:
    out = ["### 11.11 PR 6 §2 The hearing check on tier 4\n"]
    src = r["matn_no_group"]
    nt = Counter(n for ns in ch["notes_v2_ibn_hajar"].dropna() for n in ns if n.startswith("muanan_covered"))
    out.append("The brief took PR 5's hearing-elsewhere check for tier 3 only; PR 5's code already covered tiers 3–5 "
               "(D57's «a defect unless covered»; PR 5's audit counted `muanan_covered_tasrih_tier_4` on 4,832 chains). "
               "No change to the default is needed; the switch `tadlis.tasrih_tiers` makes the rule explicit and the "
               "variant `tasrih_tier_3_only` shows what the check on tiers 4–5 contributes (D73). Final run: "
               + "; ".join(f"`{k}` {v:,}" for k, v in sorted(nt.items())) + ".\n")
    if "code_v2_alt_tasrih_tier_3_only" in r:
        alt = r["code_v2_alt_tasrih_tier_3_only"]
        out.append(f"Agreement {(r['code_v2_ibn_hajar'] == src).mean():.4f} with the check on tiers 3–5, "
                   f"{(alt == src).mean():.4f} with tier 3 only; {int((alt != r['code_v2_ibn_hajar']).sum()):,} groups "
                   "differ.\n")
        names = {6811: "Ibn Isḥāq", 1919: "Baqiyya b. al-Walīd"}
        rows = []
        for rid, nm in names.items():
            w = r["residue_weakest"].map(lambda xs, rid=rid: xs is not None and rid in list(xs))
            dis_now = int((w & (r["code_v2_ibn_hajar"] != src)).sum())
            dis_alt = int((w & (alt != src)).sum())
            rows.append({"narrator": f"{nm} (r{rid})", "groups where weakest": int(w.sum()),
                         "disagreeing, tiers 3–5": dis_now, "disagreeing, tier 3 only": dis_alt})
        out.append(_md(pd.DataFrame(rows)))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- §4 the two default flips

def flips_section(con, keep, r, ch) -> str:
    out = ["### 11.12 PR 6 §4 The two default flips\n"]
    rows = []
    for x, y, what in ((S_COND, S_SHAHID, "sibling shawāhid off (`shahid_scope: group`; `siblings` the variant)"),
                       (S_SHAHID, S_UNION, "the mudallis set is the Ṭabaqāt union (`mudallis_set: union`)")):
        a, b = keep.get(x, (None, None))[0], keep.get(y, (None, None))[0]
        if a is None or b is None:
            continue
        rows.append({"change": what, "groups changed": len(_changed(a, b)), "agreement before": _agree(a),
                     "agreement after": _agree(b), "ibn_al_salah before": _agree(a, "code_v2_ibn_al_salah"),
                     "ibn_al_salah after": _agree(b, "code_v2_ibn_al_salah")})
    if rows:
        out.append(_md(pd.DataFrame(rows), "{:.4f}"))
    src = r["matn_no_group"]
    for col, name in (("code_v2_alt_siblings", "sibling shawāhid (`siblings`, PR 5's default)"),
                      ("code_v2_alt_siblings_strict", "siblings at the strict floor 0.38 (`siblings_strict`)"),
                      ("code_v2_alt_mudallis_source_flag", "the source's flagged mudallisūn only (`mudallis_source_flag`, PR 5's default)")):
        if col in r:
            out.append(f"- variant {name}: agreement {(r[col] == src).mean():.4f}")
    g = r[r["group_id"] == 2031]
    if len(g):
        out.append(f"\nThe sandals dowry (group 2031): code {int(g['code_v2_ibn_hajar'].iloc[0])} under the default (no "
                   f"witness inside the group), {int(g['code_v2_alt_siblings'].iloc[0])} under `siblings` (Sahl b. Saʿd's "
                   "report, group 763).")
    # al-Zuhri's uncovered 'an outside the Sahihayn
    z = ch[ch["defects_v2_ibn_hajar"].map(lambda d: d is not None and any(x.startswith("mudallis") for x in d))]
    zs = z[z["weak_nodes_v2_ibn_hajar"].map(lambda w: w is not None and "r7272" in list(w))]
    zg = r[r["best_sanad_v2_ibn_hajar"].isin(set(zs["sanad_id"]))]
    out.append(f"\nal-Zuhrī (r7272, tier 3 in the *Ṭabaqāt*, not flagged by the source): chains whose v2 defects include "
               f"his uncovered ʿan, final run: {len(zs):,}; groups whose v2 chain is one of them: {len(zg):,}, of which "
               f"{int((zg['code_v2_ibn_hajar'] != zg['matn_no_group']).sum()):,} disagree with the recorded grade "
               "(reports/residue.md names him under `tadlis_only`). His placement in tier 3 is disputed (D57).\n")
    return "\n".join(out) + "\n"


def appendix_designations() -> str:
    u = designations()
    if u.empty:
        return "_(run `make words` first)_\n"
    dd = u[u["method"] != "sanad_fallback_text"].assign(d=lambda x: x["designation"].map(lists.normalize))
    t = dd.groupby(["d", "cls"]).size().rename("n").reset_index().sort_values(["n", "d"], ascending=[False, True])
    return ("Every designation of an unnamed person at a chain top (normalized, `lists.normalize` v1) with its class "
            f"and count; {int((u['method'] == 'sanad_fallback_text').sum()):,} chain tops without a mention "
            "(`none_text`) are not listed.\n\n"
            + _md(t.rename(columns={"d": "designation", "cls": "class", "n": "chain tops"})) + "\n")
