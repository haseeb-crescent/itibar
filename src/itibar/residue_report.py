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
    prec = residue.precedence()
    L = ["# The residue: where the derived grade and the recorded grade differ", "",
         f"Generated by `make residue` from `out/records.parquet` (ruleset `{rs}`, derive version "
         f"{config.load('structure')['derive']['version']}). Every group with chains whose recorded grade "
         "(`meaning_groups.matn_no`, codes 0–5) differs from the derived grade v2 is tagged by the mechanical "
         "cause the machinery can name, with the receipts stored per group (`residue_*` columns). Tags are not "
         "exclusive; the primary tag is the first in `residue.precedence` "
         f"({', '.join(prec)}). The report states what the chain shows and what it cannot see; it issues no "
         "verdict on which grade is right.", "",
         f"**{n:,} of {n_all:,} groups disagree** ({n / n_all:.1%}). Direction: *stricter* = our code higher "
         "(a weaker grade) than the source's; *lenient* = lower.", ""]
    dirc = d["residue_direction"].value_counts()
    L.append(_md(pd.DataFrame([{"direction": k, "groups": int(v), "share": v / n} for k, v in dirc.items()])))
    L += ["", "*Lenient* means the source records a grade below what the chain, read through the narrator labels "
          "and the corroboration rules, reaches. That is a statement about the mechanics of the two gradings — "
          "what the source's grader saw that the labels do not carry (the tags below) — not a statement that the "
          "source is too severe.", ""]
    # chain choice first
    cc = d["tags"].map(lambda t: "chain_choice" in t)
    L += ["## 1. The unit of grading (`chain_choice`)", "",
          f"In **{int(cc.sum()):,} groups ({cc.mean():.1%})** another attested chain of the group yields exactly the "
          "source's code under the same ruleset: itibar grades the report by its best chain, the source may have "
          "graded a particular hadith. This is the one tag that is purely about the unit of grading. It is lenient by "
          "construction: the group's v2 chain is its lowest code, so another chain matching the source has a higher "
          "one.", ""]
    # primary x direction
    L += ["## 2. Primary tag by direction", ""]
    t = pd.crosstab(d["residue_primary"], d["residue_direction"]).reindex([p for p in prec if p in set(d["residue_primary"])])
    t["total"] = t.sum(axis=1)
    t["share"] = t["total"] / n
    t = t.reset_index().rename(columns={"residue_primary": "primary tag"})
    L.append(_md(t))
    L += ["", "Every tag a group carries (not exclusive):", ""]
    allc = pd.Series([x for ts in d["tags"] for x in ts]).value_counts()
    L.append(_md(pd.DataFrame([{"tag": k, "groups": int(allc.get(k, 0)), "share": allc.get(k, 0) / n}
                               for k in prec if k in allc.index])))
    # by weakest level
    lvl = _weakest_level(con, d)
    d["weakest_level"] = d["group_id"].map(lvl)
    L += ["", "## 3. By the weakest narrator's Taqrīb level in the v2 chain", ""]
    t = pd.crosstab(d["weakest_level"].fillna(99).astype(int), d["residue_primary"]).sort_index()
    t.index = ["unknown" if x == 99 else str(x) for x in t.index]
    t.index.name = "weakest_level"
    t = t[[p for p in prec if p in t.columns]]
    t["total"] = t.sum(axis=1)
    L.append(_md(t.reset_index().rename(columns={"weakest_level": "level"})))
    # collection class
    d["collection"] = d.apply(lambda x: "Ṣaḥīḥayn" if x["in_sahihayn"] else ("ṣaḥīḥ class" if x["in_sahih_class"]
                                                                           else "rest"), axis=1)
    L += ["", "## 4. By collection class", "", "Ṣaḥīḥayn: a chain in al-Bukhārī or Muslim; ṣaḥīḥ class: a chain in a "
          "`tasnif_no = 1` book; rest: neither.", ""]
    t = pd.crosstab(d["collection"], d["residue_primary"])
    t = t[[p for p in prec if p in t.columns]]
    t["total"] = t.sum(axis=1)
    t["of groups in class"] = [t.loc[k, "total"] / max(1, int(((r["in_sahihayn"]) if k == "Ṣaḥīḥayn" else
                                                               ((~r["in_sahihayn"]) & r["in_sahih_class"]) if k == "ṣaḥīḥ class"
                                                               else ((~r["in_sahihayn"]) & (~r["in_sahih_class"]))).sum()))
                               for k in t.index]
    L.append(_md(t.reset_index()))
    # chapter
    L += ["", "## 5. By level-1 chapter", "", "A group under several chapters counts in each.", ""]
    ch = _chapters(con, d)
    if len(ch):
        t = pd.crosstab(ch["chapter"], ch["residue_primary"])
        t = t[[p for p in prec if p in t.columns]]
        t["total"] = t.sum(axis=1)
        L.append(_md(t.reset_index()))
    # narrators per tag
    L += ["", "## 6. Narrators most often weakest, by primary tag", ""]
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
    L.append(_md(pd.DataFrame(rows)))
    # conditional
    L += ["", "## 7. Conditional narrators", ""]
    cs = r["residue_conditional"].value_counts()
    L.append(_md(pd.DataFrame([{"status": k, "groups": int(v)} for k, v in cs.items()])))
    L += ["", "*resolved*: the group agrees now and disagreed with the rulings off (`conditional_off`) — a ruling "
          "fired on its v2 chain; *unobservable*: the weakest narrator's only rulings are conditions the chain "
          "cannot show; *unresolved*: a ruling exists and the grades still differ.", ""]
    # unobservable conditions
    unob = _unobservable(con, d)
    L += ["## 8. What the chain cannot see", "",
          "Conditions recorded in `lists/conditional.yaml` with `observable: false` (applied nowhere), and the "
          "disagreeing groups whose weakest narrator carries one:", ""]
    L.append(_md(unob) if len(unob) else "(none)")
    see = [
        ("verdicts on the text (the matn) or on a narrator verdict not in the labels: the source's code is 3–5 "
         "while every narrator of our v2 chain is level ≤ 9", "source_severe"),
        ("an ʿilla, or the grader's narrator verdict differing from the label: no defect beyond the levels and no "
         "corroboration (a plain weakest-link mismatch)", "level_only"),
        ("pair-specific rulings not yet in §2: a weakest narrator with a ruling that does not resolve the difference",
         None),
        ("narrator verdicts other than the labels at the ṣaḥīḥ/ḥasan line: Ibn Hajar's verdict and Taḥrīr's differ "
         "in the direction that explains the difference", "tahrir"),
        ("the unit of grading: the source's code is reached by another chain of the group", "chain_choice"),
        ("none of the above", "unexplained"),
    ]
    L += ["", "The disagreement the chain cannot account for, by what lies outside it (groups carrying the tag; "
          "not exclusive):", ""]
    for text, tag in see:
        if tag is None:
            k = int((d["residue_conditional"] == "unresolved").sum())
        elif tag == "tahrir":
            k = int(d["residue_tahrir_vs_ibn_hajar"].notna().sum())
        else:
            k = int(d["tags"].map(lambda t, tag=tag: tag in t).sum())
        L.append(f"- {text}: **{k:,}**")
    # what "unexplained" holds
    ux = d[d["residue_primary"] == "unexplained"]
    if len(ux):
        chs = pd.read_parquet(paths.chains_path(), columns=["sanad_id", f"defects_v2_{rs}", f"rule_v2_{rs}"])
        m = ux[["group_id", f"best_sanad_v2_{rs}"]].merge(chs, left_on=f"best_sanad_v2_{rs}", right_on="sanad_id")
        kinds = m[f"defects_v2_{rs}"].map(lambda ds: " + ".join(sorted({
            "level" if x.startswith("level_") else "tadlis" if x.startswith("mudallis") else x for x in ds})) or "none")
        t = pd.crosstab(kinds, m[f"rule_v2_{rs}"])
        t["total"] = t.sum(axis=1)
        t = t.sort_values("total", ascending=False)
        L += ["", f"`unexplained` ({len(ux):,} groups) are chains carrying defects of more than one kind (no single "
              "kind accounts for the difference) under a fatal or unrepairable rule; by the kinds of defect:", ""]
        L.append(_md(t.reset_index().rename(columns={f"defects_v2_{rs}": "defect kinds"}).rename(columns={"index": "defect kinds"})))
    # boundary
    bv = residue.boundary_verdicts()
    L += ["", "## 9. The ṣaḥīḥ/ḥasan line (`boundary_0_1`)", "",
          f"Groups where both codes are 0 or 1: {int(d['tags'].map(lambda t: 'boundary_0_1' in t).sum()):,}. For the "
          f"{len(bv)} narrators most often weakest there whose Taqrīb and Taḥrīr entries were read "
          "(`lists/source/boundary_verdicts.jsonl`), Ibn Hajar's verdict level and Taḥrīr's differ for "
          f"{sum(1 for x in bv.values() if x.get('differ'))}; the labels follow Taḥrīr's formula (audit §11.7). "
          f"`tahrir_vs_ibn_hajar` (the difference explains the direction): "
          f"{int(d['residue_tahrir_vs_ibn_hajar'].notna().sum()):,} groups.", ""]
    # sample
    k = int(cfgr.get("sample_size", 50))
    seed = int(cfgr.get("sample_seed", 20261109))
    ids = sorted(d["group_id"].tolist())
    pick = sorted(random.Random(seed).sample(ids, min(k, len(ids))))
    L += [f"## 10. A deterministic sample of {len(pick)} disagreeing groups (seed {seed})", "",
          "Each with its tags and the receipt of its v2 chain (`receipt_v2`, the default ruleset), for the reader.", ""]
    for g in pick:
        x = d[d["group_id"] == g].iloc[0]
        rc = json.loads(x["receipt_v2"]).get(rs, [])
        L.append(f"### group {g}: ours {int(x[f'code_v2_{rs}'])}, source {int(x['matn_no_group'])} "
                 f"{GRADE.get(int(x['matn_no_group']), '')} — {x['residue_direction']}, "
                 f"primary `{x['residue_primary']}`, tags {', '.join(x['tags'])}")
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
    t = pd.crosstab(d["residue_primary"], d["residue_direction"]).reindex([p for p in prec if p in
                                                                          set(d["residue_primary"])]).fillna(0)
    for c in ("lenient", "stricter"):
        if c not in t.columns:
            t[c] = 0
    t = t[["lenient", "stricter"]]
    csv = t.reset_index().rename(columns={"residue_primary": "primary_tag"})
    csv.to_csv(paths.FIGURES_DIR / "fig6_residue.csv", index=False)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    y = range(len(t))
    ax.barh(list(y), t["lenient"], color=F.BLUE[300], label="lenient (our code lower)")
    ax.barh(list(y), t["stricter"], left=t["lenient"], color=F.BLUE[650], label="stricter (our code higher)")
    ax.set_yticks(list(y))
    ax.set_yticklabels(list(t.index))
    ax.invert_yaxis()
    ax.set_xlabel("disagreeing groups (primary tag)")
    ax.set_title("The residue: disagreement with the recorded grade by mechanical cause")
    ax.grid(axis="x", color=F.GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(paths.FIGURES_DIR / f"fig6_residue.{ext}", dpi=160)
    plt.close(fig)
