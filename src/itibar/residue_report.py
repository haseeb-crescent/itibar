"""reports/residue.md and figures/fig6_residue.* (PR 6 §3), from out/records.parquet; and the fetch of
Ibn Hajar's and Tahrir's verdicts on the narrators most often weakest at the sahih/hasan line.

The report explains disagreement by mechanism and issues no verdict on who is right."""

from __future__ import annotations

import json
import random

import duckdb
import pandas as pd

from itibar import conditional, config, data, lists, paths, residue

GRADE = {0: "صحيح", 1: "حسن", 2: "ضعيف", 3: "شديد الضعف", 4: "متهم بالوضع", 5: "موضوع"}


def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        cells = []
        for v in r:
            if isinstance(v, float):
                cells.append("" if pd.isna(v) else (f"{v:.1%}" if 0 <= v <= 1 and not float(v).is_integer() else f"{v:,.0f}"))
            elif isinstance(v, int):
                cells.append(f"{v:,}")
            else:
                cells.append("" if v is None else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def records() -> pd.DataFrame:
    r = pd.read_parquet(paths.records_path())
    return r[(r["status"] == "ok") & r["matn_no_group"].between(0, 5)].copy()


def names(con, ids) -> dict[int, str]:
    ids = sorted({int(x) for x in ids})
    if not ids:
        return {}
    con.execute("CREATE OR REPLACE TEMP TABLE _rn AS SELECT unnest(?::BIGINT[]) AS rid", [ids])
    return {int(a): b for a, b in con.sql("SELECT id, nickname FROM rawis WHERE id IN (SELECT rid FROM _rn)").fetchall()}


# ---------------------------------------------------------------- the boundary verdicts

def fetch_boundary() -> str:
    """Ibn Hajar's (Taqrib) and Tahrir's verdict levels for the narrators most often weakest in the
    boundary_0_1 groups -> lists/source/boundary_verdicts.jsonl. Entries already fetched for the
    conditional rulings are reused."""
    from itibar import provenance
    con = data.views()
    n_top = int(residue.cfg().get("boundary_top_narrators", 100))
    r = records()
    b = r[r["residue_tags"].map(lambda t: t is not None and "boundary_0_1" in list(t))]
    cnt: dict[int, int] = {}
    for w in b["residue_weakest"]:
        for x in (w if w is not None else []):
            cnt[int(x)] = cnt.get(int(x), 0) + 1
    top = sorted(cnt, key=lambda x: (-cnt[x], x))[:n_top]
    have = conditional.load_taqrib()
    if residue.BOUNDARY_SRC.exists():                     # resumable: entries already read are kept
        for line in open(residue.BOUNDARY_SRC, encoding="utf-8"):
            x = json.loads(line)
            have.setdefault(int(x["rawi_id"]), x)
    rows = {x[0]: x for x in con.sql("SELECT id, name, nickname, rank_no, rank, death_year, tabaka, nasab FROM rawis"
                                     ).fetchall()}
    out = []
    lists._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "itibar", "version": "0.5"}})
    for rid in top:
        _, name, nick, rn, lab, dy, tab, nas = rows[rid]
        s = {"rawi_id": rid, "name": name, "nickname": nick, "rank_no": rn, "label": lab, "death_year": dy,
             "tabaka": tab, "nasab": nas}
        rec = dict(have.get(rid) or {})
        if not rec:
            rec = dict(s)
            for book, tag in ((conditional.TAQRIB, "taqrib"), (conditional.TAHRIR, "tahrir")):
                best = (None, None, 0, None, None)
                for q in ([] if int(tab or 0) > 12 else conditional._queries(s)[:3]):
                    res = provenance._call("shamela_find_scoped", {"query": q, "book_ids": [book], "limit": 5,
                                                                   "difficulty": "easy"})
                    for src in (res.get("evidence") or {}).get("sources") or []:
                        line, num, k = conditional.entry_line(src.get("text", ""), name)
                        if k > best[2] and provenance._same_person(line, tab, name):
                            best = (line, num, k, src.get("citation", {}).get("markdown"), src.get("page_id"))
                    import time
                    time.sleep(1.0)
                    if best[2] >= 3:
                        break
                rec[f"{tag}_line"], rec[f"{tag}_number"], rec[f"{tag}_citation"] = best[0], best[1], best[3]
                rec[f"{tag}_page"], rec[f"{tag}_prefix_words"] = best[4], best[2]
        out.append({**s, **{k: rec.get(k) for k in ("taqrib_line", "taqrib_citation", "taqrib_prefix_words",
                                                      "tahrir_line", "tahrir_citation", "tahrir_prefix_words")},
                    "groups_weakest_boundary": cnt[rid]})
    with open(residue.BOUNDARY_SRC, "w", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(score_boundary(x), ensure_ascii=False) + "\n")
    return f"{len(out)} narrators -> {residue.BOUNDARY_SRC}"


def score_boundary(x: dict) -> dict:
    """Ibn Hajar's verdict level (the Taqrib entry's head formula) and Tahrir's (its «بل:» revision,
    else Ibn Hajar's reprinted), with the identity check of conditional.entry_ok."""
    from itibar import provenance
    out = dict(x)
    ok_t = conditional.entry_ok(x.get("taqrib_line"), x, int(x.get("taqrib_prefix_words") or 0))
    ok_h = conditional.entry_ok(x.get("tahrir_line"), x, int(x.get("tahrir_prefix_words") or 0))
    ih = conditional.head_level(provenance._verdict(x.get("taqrib_line"), x["name"]) or "") if ok_t else None
    th = None
    if ok_h:
        line = x.get("tahrir_line") or ""
        bal = next((ln for ln in line.split("\n") if ln.strip().startswith("•") and "بل" in ln[:8]), None)
        th = conditional.head_level(bal.split(":", 1)[1] if bal and ":" in bal else
                                    (provenance._verdict(line, x["name"]) or ""))
    out.update({"taqrib_ok": ok_t, "tahrir_ok": ok_h, "ibn_hajar_level": ih, "tahrir_level": th,
                "differ": (ih is not None and th is not None and ih != th)})
    return out


# ---------------------------------------------------------------- report

def write() -> str:
    con = data.views()
    cfgr = residue.cfg()
    rs = cfgr.get("ruleset", "ibn_hajar")
    r = records()
    n_all = len(r)
    d = r[r["residue_disagree"] == True].copy()  # noqa: E712
    n = len(d)
    d["tags"] = d["residue_tags"].map(lambda t: list(t) if t is not None else [])
    d["layers"] = d["residue_layers"].map(lambda t: list(t) if t is not None else [])
    prec = residue.precedence()
    L = ["# The residue: where the derived grade and the recorded grade differ, in three layers", "",
         f"Generated by `make residue` from `out/records.parquet` (ruleset `{rs}`, classical code map, derive version "
         f"{config.load('structure')['derive']['version']}). PR 7 decoded the recorded grade "
         "([reports/source_grade.md](source_grade.md)): a template reads each chain off the narrator table (the "
         "*template code*: levels 1–3 → 0, 4–6 → 1, 7–9 → 2, 10 → 3, 11 → 4, 12 → 5, every position graded, breaks "
         "raising the code), and the group's grade is its best chain's, with the editors' exceptions. So every group "
         "whose recorded grade differs from the derived grade v2 is decomposed exactly:", "",
         "    recorded − v2  =  (recorded − R)     aggregation layer: the recorded group grade against its recorded best chain R",
         "                   +  (R − ST)           chain layer: R against the template on itibar's chains (`source_template`, ST)",
         "                   +  (ST − v2)          substance layer: the template against the classical ladder (v2)", "",
         "A disagreeing group is attributed to the first layer that is not zero, so the three counts add up to the "
         "disagreement count (gated); `residue_layers` keeps every non-zero layer. Tags are mechanical and not "
         f"exclusive; the primary tag is the first in `residue.precedence` among the layer's own tags ({', '.join(prec)}). "
         "The report states what the chains show and what they cannot; it issues no verdict on which grade is right.", "",
         f"**{n:,} of {n_all:,} groups disagree** ({n / n_all:.1%}). Direction: *stricter* = our code higher (a weaker "
         "grade) than the source's; *lenient* = lower.", ""]
    # ---- 1. layers
    lay = d["residue_layer"].value_counts()
    rows = []
    for k in residue.LAYERS:
        x = d[d["residue_layer"] == k]
        rows.append({"layer": k, "groups": len(x), "share": len(x) / n if n else 0,
                     "lenient": int((x["residue_direction"] == "lenient").sum()),
                     "stricter": int((x["residue_direction"] == "stricter").sum())})
    rows.append({"layer": "total", "groups": int(lay.sum()), "share": "100%",
                 "lenient": int((d["residue_direction"] == "lenient").sum()),
                 "stricter": int((d["residue_direction"] == "stricter").sum())})
    L += ["## 1. The three layers", "", _md(pd.DataFrame(rows)), ""]
    combo = d["layers"].map(lambda t: " + ".join(t) if t else "(none)").value_counts()
    L += ["Every combination of non-zero layers:", "",
          _md(pd.DataFrame([{"layers": k, "groups": int(v), "share": v / n} for k, v in combo.items()])), ""]
    tot = {k: int(d[f"residue_d_{k}"].fillna(0).sum()) for k in residue.LAYERS}
    L += [f"Summed over the disagreeing groups, recorded − v2 = {int((d['matn_no_group'] - d[f'code_v2_{rs}']).sum()):+,} "
          f"code steps = aggregation {tot['aggregation']:+,} + chain {tot['chain']:+,} + substance {tot['substance']:+,}.",
          "", "**Agreement under each reading** (all groups with chains): the recorded grade against its best chain, the "
          "template, v1 and v2 under both code maps — the distance from v1's 72.7% to full agreement is the code map "
          "(levels 5–6), the editors' exceptions, and then the ladder:", ""]
    src = r["matn_no_group"]
    ag = [("recorded best chain R (min sanads.matn_no)", (r["matn_no_best_chain"] == src).mean()),
          ("source_template on itibar's chains (ST)", (r["code_source_template"] == src).mean()),
          ("v1, source map", (r["derived_code_source"] == src).mean()),
          ("v1, classical map", (r["derived_code_classical"] == src).mean())]
    for rr in ("ibn_hajar", "ibn_al_salah"):
        for m in ("source", "classical"):
            ag.append((f"v2 {rr}, {m} map", (r[f"code_v2_{rr}_{m}"] == src).mean()))
    L += [_md(pd.DataFrame(ag, columns=["reading", "agreement with meaning_groups.matn_no"])), ""]
    L += ["**Retired tags.** PR 6's `chain_choice` (\"another attested chain of the group yields exactly the source's "
          "code\", 44.8% of the disagreement, read as \"the source may have graded a particular hadith\") read the "
          "per-chain `sanads.matn_no`, which in multi-chain hadith is attached to the wrong chain about as often as "
          "chance (source_grade.md §3), and the source grades the group by its best chain, as itibar does; its "
          "groups are now the aggregation layer (the editors placed the group below its best chain) and the "
          "substance layer. `source_severe` (\"source 3–5 over narrators ≤ 9\", read as verdicts on the text) is "
          "what the aggregation layer measures directly: a group coded below every chain it has. Every other PR 6 "
          "tag stays and is now read against the template, chain by chain, in the substance layer (`tadlis_only` and "
          "`mursal_only` became `tadlis` and `mursal`: a chain carrying both shows both; D74 amended, D89).", ""]
    # ---- 2. aggregation
    ag_d = d[d["residue_layer"] == "aggregation"]
    L += ["## 2. The aggregation layer: what the editors did beyond the template", "",
          f"{len(ag_d):,} groups ({len(ag_d) / n:.1%} of the disagreement): the recorded group grade is not the best "
          "recorded chain's. By the recorded best chain (rows) and the recorded group grade (columns):", ""]
    t = pd.crosstab(ag_d["matn_no_best_chain"].astype(int), ag_d["matn_no_group"].astype(int))
    t.index = [f"best chain {i}" for i in t.index]
    t.columns = [f"group {c} {GRADE.get(c, '')}" for c in t.columns]
    L += [_md(t.reset_index().rename(columns={"index": ""})), ""]
    below = int((ag_d["residue_primary"] == "group_below_best_chain").sum())
    L += [f"*group_below_best_chain* {below:,}, *group_above_best_chain* {len(ag_d) - below:,}. Neither the chains nor "
          "any field of the dump says why: the editors' reasons (a verdict on the text — munkar, mawḍūʿ —, a narrator "
          "verdict beyond the label, an ʿilla) are outside the data; source_grade.md §4 prints a sample with the "
          "hadith texts.", ""]
    # ---- 3. chain
    ch_d = d[d["residue_layer"] == "chain"]
    L += ["## 3. The chain layer: reading the narrator table", "",
          f"{len(ch_d):,} groups ({len(ch_d) / n:.1%}): the group's best recorded chain code is not the template's "
          "best code on itibar's chains. The template reproduces the per-hadith codes for 99.6% of chains; what is "
          "left (source_grade.md §3.1) is narrators re-labelled or re-resolved after the sentence was written, the "
          "generator's variants, and hand-written sentences. The classes of the chains involved:", ""]
    stp = paths.OUT_DIR / "source_template.parquet"
    if stp.exists() and len(ch_d):
        st = pd.read_parquet(stp, columns=["sanad_id", "group_id", "residual", "matn_no", "template_code"])
        st = st[st["group_id"].isin(set(ch_d["group_id"])) & st["residual"].notna()]
        st = st[~st["residual"].str.startswith("misattached")]
        cnt = st.groupby("residual")["group_id"].nunique().sort_values(ascending=False)
        L += [_md(pd.DataFrame({"residual class (a chain of the group)": cnt.index, "groups": cnt.values})), ""]
    # ---- 4. substance
    sb = d[d["residue_layer"] == "substance"]
    L += ["## 4. The substance layer: what the classical ladder changes", "",
          f"{len(sb):,} groups ({len(sb) / n:.1%}): the recorded grade is the template's on itibar's chains and v2 "
          "differs. The compared chain is v2's chain when v2 is lower than the template, else the template's best "
          "chain as v2 grades it; the tags say which defects or rules v2 applies there that the template does not. "
          "Under each ruleset and code map, the groups where v2 differs from the template (all groups, not only "
          "disagreeing ones):", ""]
    rows = []
    stc = r["code_source_template"]
    for rr in ("ibn_hajar", "ibn_al_salah"):
        for m in ("classical", "source"):
            col = f"code_v2_{rr}_{m}"
            diff = r[col] != stc
            rows.append({"ruleset": rr, "code map": m, "v2 ≠ template": int(diff.sum()),
                         "v2 lower (ladder lifts)": int((r[col] < stc).sum()),
                         "v2 higher (ladder lowers)": int((r[col] > stc).sum())})
    L += [_md(pd.DataFrame(rows)), "",
          "Under the source map the code-map convention is gone and what remains is the ladder itself: corroboration "
          "(lifts), tiered tadlīs, the unnamed person, the conditional rulings, the compiler at pos 0 and the break "
          "rule (lowers or lifts).", ""]
    sd = sb.copy()
    t = pd.crosstab(sd["residue_primary"], sd["residue_direction"]).reindex(
        [p for p in prec if p in set(sd["residue_primary"])])
    t["total"] = t.sum(axis=1)
    t["share of layer"] = t["total"] / max(len(sd), 1)
    L += ["Primary tag by direction (default ruleset, classical map):", "",
          _md(t.reset_index().rename(columns={"residue_primary": "primary tag"})), "",
          "Every tag a substance-layer group carries (not exclusive):", ""]
    allc = pd.Series([x for ts in sd["tags"] for x in ts if x in residue.SUBSTANCE_TAGS]).value_counts()
    L += [_md(pd.DataFrame([{"tag": k, "groups": int(allc.get(k, 0)), "share": allc.get(k, 0) / max(len(sd), 1)}
                            for k in prec if k in allc.index])), ""]
    L += ["- *code_map*: v2 under the source map equals the template — the classical map's code 2 for an uncovered "
          "level 5–6 narrator is the whole difference.",
          "- *book_role*: the template's code is set by the compiler (or the book transmitter) at pos 0.",
          "- *break_rule*: the template's «two breaks → 3» against v2's reading of the breaks.",
          "- *conditional_narrator*, *unnamed_top*, *unnamed_mid*, *undescribed*, *tadlis*, *mursal*: defects v2 counts on "
          "the compared chain that the template does not (it grades neither the unnamed person nor tadlīs; it reads an "
          "undescribed narrator as «مجهول الحال»).",
          "- *corroboration*: v2 lifted the chain by a witness (the template never corroborates), or found none for a "
          "defect the template does not count.", ""]
    lvl = _weakest_level(con, sd)
    sd["weakest_level"] = sd["group_id"].map(lvl)
    t = pd.crosstab(sd["weakest_level"].fillna(99).astype(int), sd["residue_primary"]).sort_index()
    t.index = ["unknown" if x == 99 else str(x) for x in t.index]
    t = t[[p for p in prec if p in t.columns]]
    t["total"] = t.sum(axis=1)
    L += ["By the weakest narrator's Taqrīb level in the v2 chain:", "",
          _md(t.reset_index().rename(columns={"index": "level"})), ""]
    # ---- 5. collection, chapters
    d["collection"] = d.apply(lambda x: "Ṣaḥīḥayn" if x["in_sahihayn"] else ("ṣaḥīḥ class" if x["in_sahih_class"]
                                                                           else "rest"), axis=1)
    t = pd.crosstab(d["collection"], d["residue_layer"])
    t["total"] = t.sum(axis=1)
    L += ["## 5. By collection class and chapter", "", "Ṣaḥīḥayn: a chain in al-Bukhārī or Muslim; ṣaḥīḥ class: a chain "
          "in a `tasnif_no = 1` book; rest: neither.", "", _md(t.reset_index()), ""]
    chp = _chapters(con, d)
    if len(chp):
        chp = chp.merge(d[["group_id", "residue_layer"]], on="group_id")
        t = pd.crosstab(chp["chapter"], chp["residue_layer"])
        t["total"] = t.sum(axis=1)
        L += ["A group under several level-1 chapters counts in each:", "", _md(t.reset_index()), ""]
    # ---- 6. narrators
    L += ["## 6. Narrators most often weakest, by primary tag", ""]
    nm = names(con, [x for w in d["residue_weakest"] for x in (w if w is not None else [])])
    rows = []
    for tag in prec:
        sub = d[d["residue_primary"] == tag]
        cnt: dict[int, int] = {}
        for w in sub["residue_weakest"]:
            for x in set(w if w is not None else []):
                cnt[int(x)] = cnt.get(int(x), 0) + 1
        top = sorted(cnt, key=lambda x: (-cnt[x], x))[:6]
        if top:
            rows.append({"primary tag": tag, "groups": len(sub),
                         "narrators (groups)": "; ".join(f"{nm.get(x, x)} r{x} ({cnt[x]})" for x in top)})
    L += [_md(pd.DataFrame(rows)), ""]
    # ---- 7. conditional
    cs = r["residue_conditional"].value_counts()
    L += ["## 7. Conditional narrators", "", _md(pd.DataFrame([{"status": k, "groups": int(v)} for k, v in cs.items()])),
          "", "*resolved*: the group agrees now and disagreed with the rulings off (`conditional_off`) — a ruling fired "
          "on its v2 chain; *unobservable*: the weakest narrator's only rulings are conditions the chain cannot show; "
          "*unresolved*: a ruling exists and the grades still differ.", ""]
    unob = _unobservable(con, d)
    L += ["## 8. What the chain cannot see", "",
          "Conditions recorded in `lists/conditional.yaml` with `observable: false` (applied nowhere), and the "
          "disagreeing groups whose weakest narrator carries one:", "", _md(unob) if len(unob) else "(none)", "",
          f"Beyond them: the editors' exceptions (the aggregation layer, {len(ag_d):,} groups) — a grade below every "
          "chain the report has, or above it — and the template's inputs the dump does not carry (which narrators "
          "al-Bukhārī cites only muʿallaq or maqrūn, source_grade.md §2).", ""]
    # ---- 9. boundary
    bv = residue.boundary_verdicts()
    L += ["## 9. The ṣaḥīḥ/ḥasan line (`boundary_0_1`)", "",
          f"Substance-layer groups where v2 and the template are both 0 or 1: "
          f"{int(d['tags'].map(lambda t: 'boundary_0_1' in t).sum()):,}. For the {len(bv)} narrators most often weakest "
          "there whose Taqrīb and Taḥrīr entries were read (`lists/source/boundary_verdicts.jsonl`), Ibn Hajar's verdict "
          f"level and Taḥrīr's differ for {sum(1 for x in bv.values() if x.get('differ'))}; the labels follow Taḥrīr's "
          f"formula (audit §11.7). `tahrir_vs_ibn_hajar` (the difference explains the direction): "
          f"{int(d['residue_tahrir_vs_ibn_hajar'].notna().sum()):,} groups.", ""]
    # ---- 10. sample
    k = int(cfgr.get("sample_size", 50))
    seed = int(cfgr.get("sample_seed", 20261109))
    ids = sorted(d["group_id"].tolist())
    pick = sorted(random.Random(seed).sample(ids, min(k, len(ids))))
    L += [f"## 10. A deterministic sample of {len(pick)} disagreeing groups (seed {seed})", "",
          "Each with its layers, tags and the receipt of its v2 chain (`receipt_v2`, the default ruleset).", ""]
    for g in pick:
        x = d[d["group_id"] == g].iloc[0]
        rc = json.loads(x["receipt_v2"]).get(rs, [])
        L.append(f"### group {g}: ours {int(x[f'code_v2_{rs}'])}, source {int(x['matn_no_group'])} "
                 f"{GRADE.get(int(x['matn_no_group']), '')} (best chain {int(x['matn_no_best_chain'])}, template "
                 f"{int(x['code_source_template'])}) — {x['residue_direction']}, layer `{x['residue_layer']}`, primary "
                 f"`{x['residue_primary']}`, tags {', '.join(x['tags'])}")
        L.append("")
        for step in rc:
            data_s = json.dumps(step.get("data"), ensure_ascii=False)
            if len(data_s) > 600:
                data_s = data_s[:600] + " …"
            L.append(f"- **{step['check']}** — {step['rule']}: {step['result']}  `{data_s}`")
        L.append("")
    out = paths.REPORTS_DIR / "residue.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    fig6(d, prec)
    return str(out)


def _weakest_level(con, d: pd.DataFrame) -> dict[int, int]:
    out = {}
    lv = dict(con.sql("SELECT id, rank_no FROM rawis").fetchall())
    for g, w in zip(d["group_id"], d["residue_weakest"]):
        vals = [int(lv.get(int(x), 0)) for x in (w if w is not None else []) if 1 <= int(lv.get(int(x), 0)) <= 12]
        out[int(g)] = max(vals) if vals else None
    return out


def _chapters(con, d: pd.DataFrame) -> pd.DataFrame:
    topics = con.sql("SELECT id, name, level, lft, rgt, tree_id, group_id FROM topics").df()
    dd = duckdb.connect()
    dd.register("t", topics)
    dd.register("d", d[["group_id", "residue_primary"]])
    return dd.sql("""WITH n AS (SELECT id, name, lft, rgt, tree_id FROM t WHERE level = 1),
                          leaf AS (SELECT lft, tree_id, group_id FROM t WHERE group_id IS NOT NULL)
                     SELECT DISTINCT n.name AS chapter, n.lft, d.group_id, d.residue_primary FROM n
                     JOIN leaf ON leaf.tree_id = n.tree_id AND leaf.lft BETWEEN n.lft AND n.rgt
                     JOIN d ON d.group_id = leaf.group_id ORDER BY n.lft""").df()


def _unobservable(con, d: pd.DataFrame) -> pd.DataFrame:
    """Unobservable conditions (lists/conditional.yaml, observable false) and the disagreeing groups
    whose weakest narrator carries one."""
    rul = conditional.load_rulings()
    by: dict[str, set[int]] = {}
    who: dict[str, set[int]] = {}
    for g, w in zip(d["group_id"], d["residue_weakest"]):
        for x in (w if w is not None else []):
            for ru in rul.get(int(x), []):
                if not ru.observable:
                    by.setdefault(ru.condition, set()).add(int(g))
                    who.setdefault(ru.condition, set()).add(int(x))
    nm = names(con, [x for s in who.values() for x in s])
    rows = []
    for k in sorted(by, key=lambda k: (-len(by[k]), k)):
        rows.append({"condition": k, "disagreeing groups": len(by[k]), "narrators": len(who[k]),
                     "for example": "; ".join(f"{nm.get(x, x)} r{x}" for x in sorted(who.get(k, ()))[:6])})
    return pd.DataFrame(rows)


def fig6(d: pd.DataFrame, prec: list[str]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from itibar import figures as F
    order = [(lay, p) for lay in residue.LAYERS for p in prec
             if ((d["residue_layer"] == lay) & (d["residue_primary"] == p)).any()]
    rows = []
    for lay, p in order:
        x = d[(d["residue_layer"] == lay) & (d["residue_primary"] == p)]
        rows.append({"layer": lay, "primary_tag": p, "lenient": int((x["residue_direction"] == "lenient").sum()),
                     "stricter": int((x["residue_direction"] == "stricter").sum())})
    t = pd.DataFrame(rows)
    t.to_csv(paths.FIGURES_DIR / "fig6_residue.csv", index=False)
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    y = list(range(len(t)))
    ax.barh(y, t["lenient"], color=F.BLUE[300], label="lenient (our code lower)")
    ax.barh(y, t["stricter"], left=t["lenient"], color=F.BLUE[650], label="stricter (our code higher)")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{lay}: {p}" for lay, p in zip(t["layer"], t["primary_tag"])], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("disagreeing groups (primary tag within the layer)")
    ax.set_title("The residue in three layers: aggregation (the editors), chain (the table), substance (the ladder)",
                 fontsize=9)
    ax.grid(axis="x", color=F.GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(paths.FIGURES_DIR / f"fig6_residue.{ext}", dpi=160)
    plt.close(fig)
