"""reports/audit.md, sections 11 and 12: the corroborated grade after the PR 5
corrections, each correction's before/after (out/stages/, `make stages`), and the
number class on kappa. Called by itibar.audit."""

from __future__ import annotations

import csv
from collections import Counter

import pandas as pd

from itibar import config, load, paths, stages, structure

STAGE_TITLES = {
    "s0_pr4": "PR 4 as merged (derive v2, structure v3)",
    "s1_attested": "+ §1 a witness is one attested chain",
    "s2_tadlis": "+ §2 tiered tadlīs, hearing check (group), Ṣaḥīḥayn convention",
    "s3_siblings": "+ §3 shawāhid from sibling groups",
    "s4_each_defect": "+ §4 every light defect covered",
    "s5_book_roles": "+ §5 compiler roles per edge, book transmitters",
    "s6_kappa_class": "+ §6 number class on κ (no effect on grades)",
    "s7_named_elsewhere": "+ §8 unnamed person named elsewhere (= PR 5 defaults)",
}
UP = ("hasan_li_ghayrihi", "sahih_li_ghayrihi")


def _md(df, floatfmt="{:,.3f}"):
    from itibar.audit import md_table
    return md_table(df, floatfmt)


def _ok(r):
    return r[r["status"] == "ok"]


def _stage(stem):
    d = stages.out_dir(stem)
    rp, cp = d / "records.parquet", d / "chains.parquet"
    if not rp.exists():
        return None, None
    return _ok(pd.read_parquet(rp)), (pd.read_parquet(cp) if cp.exists() else None)


def _block(r, rs="ibn_hajar"):
    """'ours 1 / source 3-5': groups we place at code 1 that the source records 3, 4 or 5."""
    return int(((r[f"code_v2_{rs}"] == 1) & (r["matn_no_group"] >= 3)).sum())


def _xt(r, col, hk, label):
    xt = pd.crosstab(r[col].astype(int), r["matn_no_group"].astype(int))
    xt.index = [f"ours {i}" for i in xt.index]
    xt.columns = [f"{cd} {hk.get(cd, '')}" for cd in xt.columns]
    return _md(xt.reset_index().rename(columns={"index": label}))


def stage_table() -> tuple[str, dict]:
    rows, keep = [], {}
    prev = None
    for f in stages.stage_files():
        r, ch = _stage(f.stem)
        if r is None:
            continue
        keep[f.stem] = (r, ch)
        src = r["matn_no_group"]
        changed = None
        if prev is not None:
            m = r[["group_id", "code_v2_ibn_hajar"]].merge(prev[["group_id", "code_v2_ibn_hajar"]], on="group_id",
                                                             suffixes=("", "_p"))
            changed = int((m["code_v2_ibn_hajar"] != m["code_v2_ibn_hajar_p"]).sum())
        rows.append({"stage": f.stem, "correction": STAGE_TITLES.get(f.stem, f.stem),
                     "v1": (r["derived_code"] == src).mean(),
                     "v2 ibn_hajar": (r["code_v2_ibn_hajar"] == src).mean(),
                     "v2 ibn_al_salah": (r["code_v2_ibn_al_salah"] == src).mean(),
                     "ours 1 / source 3–5": _block(r),
                     "upgraded groups": int(r["rule_v2_ibn_hajar"].isin(UP).sum()),
                     "groups changed vs previous": changed})
        prev = r
    if not rows:
        return "_(run `make stages` first)_\n", keep
    return _md(pd.DataFrame(rows), "{:.4f}"), keep


def _mubham_analysis(r0: pd.DataFrame, ch0: pd.DataFrame, con) -> tuple[str, dict]:
    """The disagreeing groups of PR 4 whose v2 chain has the unnamed person among its
    weakest positions: where he sits, the source's grade, and whether another chain of the
    report names someone between the same teacher and student."""
    dis = r0[r0["code_v2_ibn_hajar"] != r0["matn_no_group"]]
    best = dis[["group_id", "best_sanad_v2_ibn_hajar", "matn_no_group"]].merge(
        ch0[["sanad_id", "weakest_positions", "length"]], left_on="best_sanad_v2_ibn_hajar", right_on="sanad_id")
    sids = [int(x) for x in best["sanad_id"]]
    con.execute("CREATE OR REPLACE TEMP TABLE _sids AS SELECT unnest(?::BIGINT[]) AS sid", [sids])
    raw = dict(con.sql("SELECT sanad_id, list(rawi_id ORDER BY pos) FROM sanad_rawis WHERE sanad_id IN "
                       "(SELECT sid FROM _sids) GROUP BY 1").fetchall())
    rows = []
    for g, sid, src, wp in zip(best["group_id"], best["sanad_id"], best["matn_no_group"], best["weakest_positions"]):
        rw = raw.get(int(sid), [])
        ps = [p for p in (wp if wp is not None else []) if p < len(rw) and rw[p] == 1131]
        if not ps:
            continue
        top = len(rw) - 1
        rows.append({"group_id": int(g), "sanad_id": int(sid), "source": int(src),
                     "positions": ps, "where": "top" if all(p == top for p in ps) else "mid", "rawis": rw})
    gids = sorted({x["group_id"] for x in rows})
    chains = load.chains_by_group(con, gids) if gids else {}
    named = {}
    for g in gids:
        trip = set()
        for c in chains.get(g, []):
            r = c.rawis
            for p in range(1, len(r) - 1):
                if r[p] not in (1131, 30000, 30001, 30002):
                    trip.add((r[p + 1], r[p - 1]))
        named[g] = trip
    for x in rows:
        r = x["rawis"]
        x["named_elsewhere"] = any(0 < p < len(r) - 1 and (r[p + 1], r[p - 1]) in named.get(x["group_id"], set())
                                   for p in x["positions"])
    df = pd.DataFrame(rows)
    stats = {"groups": len(df)}
    if df.empty:
        return "_(no such groups)_\n", stats
    t = df.groupby(["where", "named_elsewhere"]).size().rename("groups").reset_index()
    xs = pd.crosstab(df["where"], df["source"])
    xs.columns = [f"source {c}" for c in xs.columns]
    stats.update({"top": int((df["where"] == "top").sum()), "mid": int((df["where"] == "mid").sum()),
                  "mid_named": int(((df["where"] == "mid") & df["named_elsewhere"]).sum())})
    return (_md(t) + "\n\nBy the source's recorded grade:\n\n" + _md(xs.reset_index().rename(columns={"where": "position"}))
            + "\n", stats)


def corrections_section(c, scale) -> str:
    hk = scale.hukm_codes
    r = _ok(pd.read_parquet(paths.records_path()))
    ch = pd.read_parquet(paths.chains_path())
    src = r["matn_no_group"]
    out = []
    books = c.sql("SELECT id, name FROM books WHERE id IN (1, 2) ORDER BY id").fetchall()
    out.append("Books used by the qarāʾin, the collection classes and the Ṣaḥīḥayn convention, verified: "
               + "; ".join(f"`books.id` {i} = {n}" for i, n in books) + ".\n")
    out.append("Agreement with the source's recorded grades is a **reported result, never a gate** (PR 5 removed the "
               "v2 ≥ v1 gate: a gate that rewards agreement invites tuning, DECISIONS D37, D63). Nothing below was "
               "tuned to it.\n")
    # ---------------------------------------------------------------- 11.1
    out.append("### 11.1 The corrections, applied cumulatively\n")
    out.append("Each row reruns the pipeline (`make stages`, `config/stages/`) with the corrections up to that row "
               "switched on, in the brief's order; stage 0 reproduces PR 4 and the last row equals the defaults. "
               "*ours 1 / source 3–5*: groups v2 (`ibn_hajar`) places at code 1 that the source records شديد "
               "الضعف, متهم بالوضع or موضوع.\n")
    st, keep = stage_table()
    out.append(st)
    r0, ch0 = keep.get("s0_pr4", (None, None))
    # ---------------------------------------------------------------- 11.2
    out.append("\n### 11.2 §1 A witness is one attested chain\n")
    if "s1_attested" in keep and r0 is not None:
        r1 = keep["s1_attested"][0]
        att0 = r0.loc[r0["rule_v2_ibn_hajar"].isin(UP), "witness_attested_v2_ibn_hajar"]
        out.append(f"PR 4 accepted a route spliced from several chains in the union graph: {(~att0.astype(bool)).sum():,} "
                   f"of its {len(att0):,} upgraded groups ({(~att0.astype(bool)).mean():.1%}) rested on one. With "
                   f"witnesses restricted to single attested chains, upgraded groups go from {len(att0):,} to "
                   f"{int(r1['rule_v2_ibn_hajar'].isin(UP).sum()):,} and the block *ours 1 / source 3–5* from "
                   f"{_block(r0):,} to {_block(r1):,}.\n")
    dd = r[r["rule_v2_ibn_hajar"] == "daif"]
    cd = ch[ch["rule_v2_ibn_hajar"] == "daif"]
    out.append(f"`witness_route_exists` (the union graph had a route avoiding the positions, no single chain did), "
               f"final run: {int(dd['witness_route_exists_v2_ibn_hajar'].fillna(False).sum()):,} of {len(dd):,} groups "
               f"whose v2 chain is ḍaʿīf; {int(cd['route_exists_v2_ibn_hajar'].fillna(False).sum()):,} of {len(cd):,} "
               "such chains.\n")
    # ---------------------------------------------------------------- 11.3
    out.append("### 11.3 §2 Tiered tadlīs, the hearing check, the Ṣaḥīḥayn convention\n")
    out.append(_mudallisin_join(c))
    if r0 is not None and "s2_tadlis" in keep:
        out.append(_an_redistribution(r0, ch0, *keep["s2_tadlis"]))
    nt = Counter(n for ns in ch["notes_v2_ibn_hajar"].dropna() for n in ns)
    dt = Counter(d for ds in ch["defects_v2_ibn_hajar"].dropna() for d in ds if d.startswith("mudallis"))
    out.append("Chain-level counts in the final run (`ibn_hajar`; a chain counts once per kind): "
               + "; ".join(f"`{k}` {v:,}" for k, v in sorted(nt.items()) if k.startswith("muanan"))
               + "; still defects: " + "; ".join(f"`{k}` {v:,}" for k, v in sorted(dt.items())) + ".\n")
    for col, name in (("code_v2_alt_tasrih_corpus", "hearing anywhere in the corpus (`tasrih_corpus`)"),
                      ("code_v2_alt_mudallis_union", "every narrator matched to the book a mudallis (`mudallis_union`)")):
        if col in r:
            out.append(f"- variant {name}: agreement {(r[col] == src).mean():.4f}")
    out.append("")
    # ---------------------------------------------------------------- 11.4
    out.append("### 11.4 §3 Shawāhid from sibling groups\n")
    up = r[r["rule_v2_ibn_hajar"].isin(UP)]
    cross = ch[ch["witness_group_v2_ibn_hajar"].notna()]
    same_comp = _same_companion_share(cross, c)
    out.append(f"Floor: idf-weighted Dice ≥ {config.load('structure')['derive']['corroboration']['shahid_min_overlap']} "
               "on lists.normalize tokens, set by reading 50 candidate pairs (reports/shahid_inspection.md, D58). In the "
               f"final run {int(up['witness_cross_group_v2_ibn_hajar'].fillna(False).sum()):,} of {len(up):,} upgraded "
               f"groups have a cross-group witness in their v2 chain; {len(cross):,} chains in all. Of those chains' "
               f"witnesses, {same_comp:.1%} come through the same companion as the chain (a mutābaʿa by the "
               "*Nuzha*'s definition; classed shāhid because the source files them as another report).\n")
    rows = [{"reading": "with sibling shawāhid (default)", "agreement": (r["code_v2_ibn_hajar"] == src).mean()}]
    for col, name in (("code_v2_alt_shahid_group", "in-group witnesses only (`shahid_group`)"),
                      ("code_v2_alt_shahid_strict", "siblings, strict floor 0.38 (`shahid_strict`)")):
        if col in r:
            rows.append({"reading": name, "agreement": (r[col] == src).mean()})
    out.append(_md(pd.DataFrame(rows), "{:.4f}"))
    out.append("\nThe sandals dowry (gold `sandals-asim-b-ubaydallah`, group 2031) is repaired by Sahl b. Saʿd's report "
               "in group 763 at overlap 0.333: above the floor, below the strict variant's.\n")
    # ---------------------------------------------------------------- 11.5
    out.append("### 11.5 §4 Every light defect covered\n")
    rows = [{"positions to cover": "each light defect, a witness of its own (`each_defect`, default)",
             "agreement": (r["code_v2_ibn_hajar"] == src).mean()}]
    for col, name in (("code_v2_alt_weakest", "the weakest light defects, one witness (`weakest`, PR 4)"),
                      ("code_v2_alt_all_light_defects", "every light defect, one witness (`all_light_defects`)")):
        if col in r:
            rows.append({"positions to cover": name, "agreement": (r[col] == src).mean()})
    out.append(_md(pd.DataFrame(rows), "{:.4f}"))
    nw = ch.loc[ch["rule_v2_ibn_hajar"] == "hasan_li_ghayrihi"]
    multi = r.loc[r["rule_v2_ibn_hajar"] == "hasan_li_ghayrihi", "n_witnesses_v2_ibn_hajar"]
    out.append(f"\nGroups whose v2 chain needed more than one witness (one per defect): {int((multi > 1).sum()):,} of "
               f"{len(multi):,} ḥasan li-ghayrihi groups (ḥasan li-ghayrihi chains in all: {len(nw):,}).\n")
    # ---------------------------------------------------------------- 11.6
    out.append("### 11.6 §5 Book transmitters and compiler roles\n")
    out.append(_book_transmitters(c))
    out.append("Compiler roles are per edge for single strands, partial common links and common links (D61); the "
               "census and the ranks of al-Zuhrī, Qatāda, al-Aʿmash, Shuʿba and Mālik are in reports/common_links.md.\n")
    # ---------------------------------------------------------------- 11.7
    out.append("### 11.7 §7 Whose verdicts are the labels: a sample against the Taqrīb and Taḥrīr al-Taqrīb\n")
    out.append(_provenance())
    # ---------------------------------------------------------------- 11.8
    out.append("### 11.8 §8 The unnamed person\n")
    if r0 is not None and ch0 is not None:
        txt, stx = _mubham_analysis(r0, ch0, c)
        out.append(f"In PR 4, {stx['groups']:,} disagreeing groups had the unnamed person (`اسم مبهم`) among the weakest "
                   f"positions of their v2 chain: {stx.get('top', 0):,} only in the companion slot (read as mursal, "
                   f"D36), {stx.get('mid', 0):,} below it, of which {stx.get('mid_named', 0):,} have another chain of the "
                   "report naming a narrator between the same teacher and student.\n")
        out.append(txt)
    if "code_v2_alt_unknown_none" in r:
        out.append(f"Effect: agreement {(r['code_v2_ibn_hajar'] == src).mean():.4f} with `unknown_repair: "
                   f"named_elsewhere`, {(r['code_v2_alt_unknown_none'] == src).mean():.4f} without "
                   f"(`unknown_none`). Chains whose unnamed person is named elsewhere: "
                   f"{sum(1 for ns in ch['notes_v2_ibn_hajar'].dropna() if any(n.startswith('unnamed_named') for n in ns)):,}.\n")
    # ---------------------------------------------------------------- 11.9
    out.append("### 11.9 The final grade\n")
    rows = [("v1 (best single chain)", (r["derived_code"] == src).mean())]
    for col in sorted(x for x in r.columns if x.startswith("code_v2_")):
        rows.append((col.replace("code_v2_", "v2 ").replace("alt_", "variant "), (r[col] == src).mean()))
    out.append(f"**Agreement with `meaning_groups.matn_no`** over the {len(r):,} groups with chains (variants run on "
               "`ibn_hajar` with one switch changed, `derive.variants`):\n")
    out.append(_md(pd.DataFrame(rows, columns=["grade", "agreement_with_matn_no"]), "{:.4f}"))
    for rs in ("ibn_hajar", "ibn_al_salah"):
        out.append(f"\n**Disagreement table, `{rs}`**: our v2 code (rows) by the source's code (columns):\n")
        out.append(_xt(r, f"code_v2_{rs}", hk, "v2 code"))
    out.append("\n**For comparison, v1**:\n")
    out.append(_xt(r, "derived_code", hk, "v1 code"))
    rules = r["rule_v2_ibn_hajar"].value_counts().rename_axis("rule").reset_index(name="groups")
    rules["share"] = rules["groups"] / len(r)
    out.append("\n**Rule that fired for the group's v2 chain (`ibn_hajar`)**:\n")
    out.append(_md(rules))
    dv = r["divergence_v2_ibn_hajar"].value_counts().rename_axis("divergence").reset_index(name="groups")
    out.append("\n**Divergence class of the summary witness** (upgraded groups; the witness covering the topmost "
               "position, D41):\n")
    out.append(_md(dv))
    best = r[["group_id", "best_sanad_v2_ibn_hajar", "code_v2_ibn_hajar", "matn_no_group", "derived_code"]].merge(
        ch[["sanad_id", "weakest_positions", "chain_ordinal"]], left_on="best_sanad_v2_ibn_hajar", right_on="sanad_id",
        how="left")
    best["weakest_level"] = [13 - int(o) if 1 <= o <= 12 else "unknown" for o in best["chain_ordinal"]]
    bl = best.groupby("weakest_level").apply(lambda d: pd.Series({
        "groups": len(d), "agree_v1": (d["derived_code"] == d["matn_no_group"]).mean(),
        "agree_v2_ibn_hajar": (d["code_v2_ibn_hajar"] == d["matn_no_group"]).mean()}), include_groups=False)
    out.append("\n**By the weakest narrator's Taqrīb level** in the group's v2 chain (`ibn_hajar`):\n")
    out.append(_md(bl.reset_index()))
    names = dict(c.sql("SELECT id, nickname FROM rawis").fetchall())
    chains_rawis = dict(c.sql("SELECT sanad_id, list(rawi_id ORDER BY pos) FROM sanad_rawis GROUP BY 1").fetchall())
    dis = best[best["code_v2_ibn_hajar"] != best["matn_no_group"]]
    cnt: Counter = Counter()
    for sid, wp in zip(dis["best_sanad_v2_ibn_hajar"], dis["weakest_positions"]):
        rw = chains_rawis.get(int(sid), [])
        for p in (wp if wp is not None else []):
            if p < len(rw):
                cnt[int(rw[p])] += 1
    top = pd.DataFrame([{"narrator": f"{names.get(k)} (r{k})", "groups_disagreeing": v} for k, v in cnt.most_common(15)])
    out.append("\n**Narrators most often weakest in the disagreeing groups** (`ibn_hajar`):\n")
    out.append(_md(top))
    down = r[(r["derived_code"] == 0) & (r["code_v2_ibn_hajar"] > 0)]
    dch = ch[["sanad_id", "defects_v2_ibn_hajar"]].set_index("sanad_id")
    comp = Counter(",".join(dch.loc[int(s), "defects_v2_ibn_hajar"]) or "none" for s in down["best_sanad_v2_ibn_hajar"])
    out.append(f"\n**Downgrades.** {len(down):,} groups that v1 grades 0 get a higher v2 code under `ibn_hajar` "
               f"({int((down['matn_no_group'] == 0).sum()):,} of them recorded 0 by the source). The defects of their "
               "v2 chain: " + "; ".join(f"{k} {v:,}" for k, v in comp.most_common(12)) + ".\n")
    return "\n".join(out)


def _same_companion_share(cross: pd.DataFrame, con) -> float:
    if cross.empty:
        return 0.0
    sids = sorted(set(int(x) for x in cross["sanad_id"]) | set(int(x) for x in cross["witness_sanad_v2_ibn_hajar"]))
    con.execute("CREATE OR REPLACE TEMP TABLE _s2 AS SELECT unnest(?::BIGINT[]) AS sid", [sids])
    top = dict(con.sql("""SELECT sanad_id, arg_max(rawi_id, pos) FROM sanad_rawis WHERE sanad_id IN (SELECT sid FROM _s2)
                          GROUP BY 1""").fetchall())
    same = [top.get(int(a)) == top.get(int(b)) for a, b in zip(cross["sanad_id"], cross["witness_sanad_v2_ibn_hajar"])]
    return sum(same) / len(same)


def _mudallisin_join(con) -> str:
    from itibar import mudallisin
    ents = mudallisin.load_entries() if mudallisin.YAML_PATH.exists() else []
    rows = list(csv.DictReader(open(mudallisin.CONF_PATH, encoding="utf-8"))) if mudallisin.CONF_PATH.exists() else []
    tiers = mudallisin.confirmed_tiers()
    flagged = {int(r[0]) for r in con.sql("SELECT id FROM rawis WHERE has_tadlis = 1").fetchall()}
    st = Counter(r["status"] for r in rows)
    by_tier = Counter(tiers[x] for x in flagged if x in tiers)
    tt = Counter(e["tier"] for e in ents)
    lines = [f"Ibn Hajar's *Ṭabaqāt al-Mudallisīn* (Shamela 1186, ed. al-Qaryūtī): {len(ents)} entries parsed "
             f"(tiers {', '.join(f'{k}: {v}' for k, v in sorted(tt.items()))}; the book states 152, tier heads 33, 33, "
             "50, 12, 24). Joined to `rawis` by deterministic name matching (README): "
             f"{st.get('auto', 0)} entries auto-confirmed, {st.get('human', 0)} by the reviewer, "
             f"{st.get('needs_review', 0)} awaiting review in `lists/mudallisin_confirmed.csv`.",
             f"Of the {len(flagged)} narrators the source flags (`has_tadlis = 1`), {sum(1 for x in flagged if x in tiers)} "
             f"are matched to the book (tier 1: {by_tier.get(1, 0)}, 2: {by_tier.get(2, 0)}, 3: {by_tier.get(3, 0)}, "
             f"4: {by_tier.get(4, 0)}, 5: {by_tier.get(5, 0)}) and {sum(1 for x in flagged if x not in tiers)} are not "
             "(unmatched or pending review; they take `untiered_tadlis`, tier 3). "
             f"{sum(1 for x in tiers if x not in flagged)} narrators matched to the book are not flagged by the source "
             "(`mudallis_set: source_flag` leaves them without a tadlīs defect; variant `mudallis_union` adds them).", ""]
    unf = sorted((x for x in flagged if x not in tiers))
    if unf:
        names = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
        lines.append("Flagged narrators without a confirmed tier: " + ", ".join(f"{names.get(x)} (r{x})" for x in unf) + ".\n")
    return "\n".join(lines) + "\n"


def _an_redistribution(r0, ch0, r2, ch2) -> str:
    """PR 4's groups downgraded from v1 code 0 only because of a mudallis's 'an: where
    each one's v2 chain stands once tadlis is tiered."""
    d0 = ch0[["sanad_id", "defects_v2_ibn_hajar"]].set_index("sanad_id")
    down = r0[(r0["derived_code"] == 0) & (r0["code_v2_ibn_hajar"] > 0)]
    only = [g for g, s in zip(down["group_id"], down["best_sanad_v2_ibn_hajar"])
            if list(d0.loc[int(s), "defects_v2_ibn_hajar"]) == ["mudallis_muanan"]]
    sub = r2[r2["group_id"].isin(only)]
    c2 = ch2.set_index("sanad_id")

    def why(sid, code, rule):
        if code == 0:
            notes = list(c2.loc[int(sid), "notes_v2_ibn_hajar"])
            kinds = sorted({n.split("_tier")[0].replace("muanan_", "") for n in notes if n.startswith("muanan")})
            return "code 0: " + (" + ".join(kinds) if kinds else "another chain")
        return f"{rule} (code {code})"

    cnt = Counter(why(s, c, ru) for s, c, ru in zip(sub["best_sanad_v2_ibn_hajar"], sub["code_v2_ibn_hajar"],
                                                    sub["rule_v2_ibn_hajar"]))
    t = pd.DataFrame([{"after §2": k, "groups": v} for k, v in cnt.most_common()])
    return (f"PR 4 downgraded {len(only):,} groups from v1 code 0 only because of a mudallis's ʿan (its binary flag). "
            "With tiers, the hearing check and the Ṣaḥīḥayn convention (stage 2), their v2 chains stand as follows "
            "(*accepted* = tier 1–2; *accepted_sahihayn* = a chain of al-Bukhārī or Muslim; *covered_tasrih* = the "
            "link heard in another chain of the report):\n\n" + _md(t) + "\n")


def _book_transmitters(con) -> str:
    bc = con.sql("SELECT * FROM book_compilers").df()
    if "transmitter_rawi_id" not in bc:
        return "_(book_compilers predates PR 5; run `python -m itibar.load book_compilers`)_\n"
    x = bc[bc["transmitter_rawi_id"].notna()]
    names = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
    rows = [{"book": f"{r.name} ({r.book_id})", "chains": int(r.chains),
             "transmitter at pos 0": f"{names.get(int(r.transmitter_rawi_id))} (r{int(r.transmitter_rawi_id)})",
             "share (transmitter at 0, author at 1)": round(float(r.transmitter_share), 3),
             "compiler, PR 4 rule": (f"{names.get(int(r.compiler_rawi_id_pos0))} (r{int(r.compiler_rawi_id_pos0)})"
                                     if pd.notna(r.compiler_rawi_id_pos0) else ""),
             "compiler now": f"{names.get(int(r.compiler_rawi_id))} (r{int(r.compiler_rawi_id)})",
             "PR 4 misidentified him": "yes" if bool(r.pos0_misidentified) else "no"} for r in x.itertuples(index=False)]
    cfg = config.load("structure")["bundle"]
    return ("Book transmitters (`bundle.book_transmitter_min_share` = "
            f"{cfg.get('book_transmitter_min_share')}): a narrator at pos 0 while the book's author (death year = "
            "`books.author_death_year` ± 1) sits at pos 1 in at least that share of the book's chains. The next "
            "largest share in the corpus is under 0.02. The brief's examples are not of this shape in this data: "
            "ʿAbd al-Razzāq himself is at pos 0 of 94.5% of the *Muṣannaf*'s chains (al-Dabarī is not in them), and "
            "Aḥmad of 99.4% of the *Musnad*'s (ʿAbdallāh b. Aḥmad's chains with Aḥmad at pos 1 are in ʿAbdallāh's own "
            "books, *al-Sunna* and *Faḍāʾil ʿUthmān*, where he is the author).\n\n" + _md(pd.DataFrame(rows)) + "\n")


def _provenance() -> str:
    from itibar import provenance
    if not provenance.OUT.exists():
        return "_(run `make provenance-fetch`)_\n"
    rows = provenance.compare(provenance.load())
    readings = ["Tahrir's revision", "Ibn Hajar's wording", "formula over Ibn Hajar's verdict", "neither"]
    lines = []
    for stratum in ("formula", "other"):
        s = [x for x in rows if x["stratum"] == stratum]
        c = Counter(x["reading"] for x in s)
        lines.append({"stratum": "«صدوق حسن الحديث»" if stratum == "formula" else "other labels", "sampled": len(s),
                      "read whole in both": sum(1 for x in s if x["found"]),
                      "Taḥrīr revises Ibn Hajar": sum(1 for x in s if x["found"] and x["tahrir_revision"]),
                      **{r.replace("Tahrir", "Taḥrīr"): c.get(r, 0) for r in readings}})

    def status(x):
        if x["found"]:
            return x["reading"].replace("Tahrir", "Taḥrīr")
        if x.get("taqrib_namesake"):
            return "not read: the entry found is a namesake (tabaqa)"
        if x.get("tahrir_cut"):
            return "not read: Taḥrīr's entry continues on the next page"
        if x.get("taqrib_line"):
            return "not read: found in the Taqrīb only"
        return "not found by name search"

    det = [{"rawi": f"r{x['rawi_id']}", "source label": x["label"], "Taqrīb (Ibn Hajar)": x["ibn_hajar"] or "",
            "Taḥrīr «بل:»": x["tahrir_revision"] or "", "entry": x.get("taqrib_number") or "",
            "Taqrīb page": (x.get("taqrib_citation") or "").split("](")[-1].rstrip(")"), "reading": status(x)}
           for x in rows]
    return ("40 narrators of al-Bukhārī or Muslim (all of whom the Taqrīb covers), 20 labelled «صدوق حسن الحديث» "
            "and 20 with other labels of levels 2–9 (seed in `itibar.provenance`), looked up in Shamela's *Taqrīb "
            "al-Tahdhīb* (book 8609) and *Taḥrīr Taqrīb al-Tahdhīb* (book 127715), which reprints each entry and adds "
            "its own verdict after «بل:» where it disagrees; raw lines in `lists/source/taqrib_sample.jsonl`. "
            "*reading*: the label is Taḥrīr's revision; or, where Taḥrīr keeps Ibn Hajar's verdict, his wording, or the "
            "formula «صدوق حسن الحديث» put over it; or neither. A label *is* a wording when one contains the other after "
            "normalization; an entry whose tabaqa is more than one layer from the narrator's tabaka, without agreeing on "
            "the grandfather, is a namesake. Every row is printed for checking.\n\n"
            + _md(pd.DataFrame(lines)) + "\n\n" + _md(pd.DataFrame(det)) + "\n")


def number_section(c) -> str:
    r = _ok(pd.read_parquet(paths.records_path()))
    N = structure.tawatur_n()
    out = []
    order = ["gharib_mutlaq", "gharib_nisbi", "aziz", "mashhur", "mutawatir_count"]
    nc = r["number_class"].fillna("no route").value_counts().reindex(order + ["no route"], fill_value=0)
    t = pd.DataFrame({"number_class": nc.index, "groups": nc.values, "share": nc.values / len(r)})
    out.append(f"`number_class` on κ_all (structure version 4, D60): 1 gharīb, 2 ʿazīz, 3–{N - 1} mashhūr, ≥ {N} "
               "mutawātir by count; gharīb muṭlaq when a companion is among the cut vertices. `no route`: κ_all = 0.\n")
    out.append(_md(t))
    ck = r.loc[r["number_class"].isin(["gharib_mutlaq", "gharib_nisbi"]), "gharib_cut_kind"].value_counts()
    out.append("\n**The topmost cut vertex of the gharīb groups**: " + "; ".join(f"{k} {v:,}" for k, v in ck.items())
               + " (*compiler*: every route ends in one compiler's books, so the tafarrud is his).\n")
    xt = pd.crosstab(r["number_class_width"].fillna("no route"), r["number_class"].fillna("no route"))
    out.append("**The width reading (rows, diagnostic, `number_class_width`) against the κ reading (columns)**:\n")
    out.append(_md(xt.reset_index().rename(columns={"number_class_width": "width \\ κ"})))
    dis = r["number_class_disagree"].mean()
    wide = ((r["number_class_width"].isin(["gharib_mutlaq", "gharib_nisbi"])) & (r["kappa_all"] >= 2)).sum()
    out.append(f"\nThe readings differ in {dis:.1%} of groups. The width reading treats each Taqrīb layer as a cut, but "
               "routes skip layers (tabaka steps of 2–4 are normal on this scale, §8.5), so a layer is a cut only when "
               f"every route has a narrator in it: {wide:,} groups read gharīb by width while κ_all ≥ 2. Tafarrud is one "
               "man through whom every route passes, which is a cut vertex; hence the κ reading is the class.\n")
    rows = []
    for n in sorted(set([4, 5, 10, 12, 40, 70] + [N])):
        rows.append({"tawatur_n": n, "mutawatir_count (κ_all)": int((r["kappa_all"] >= n).sum()),
                     "mashhur (κ_all)": int(((r["kappa_all"] >= 3) & (r["kappa_all"] < n)).sum()),
                     "mutawatir_count (width)": int((r["min_width"] >= n).sum())})
    out.append("\n**Sensitivity to tawatur_n** (the numbers the books report as proposed):\n")
    out.append(_md(pd.DataFrame(rows)))
    q = pd.DataFrame([{"flag": f, "groups": int(r[f].sum()), "share": r[f].mean(),
                       "recorded 0 (صحيح) among them": (r.loc[r[f], "matn_no_group"] == 0).mean()}
                      for f in ("in_sahihayn", "in_sahih_class", "sound_distinct_routes", "huffaz_chain")])
    out.append("\n**Qarāʾin flags** (reported, never combined; knowledge yield is not computed; `huffaz_chain` "
               "now excludes gharīb by κ):\n")
    out.append(_md(q))
    allq = (r["in_sahihayn"] & r["sound_distinct_routes"] & r["huffaz_chain"]).sum()
    out.append(f"\nAll three flags together: {allq:,} groups.\n")
    return "\n".join(out)
