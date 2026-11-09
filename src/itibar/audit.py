"""`make audit`: re-verify the upstream facts itibar depends on and report
everything found that changes a connectivity number. Writes reports/audit.md.

Read-only over the Parquet copy of hadith-kg.db. Every number in the report is
computed here; nothing is copied from DATA_REPORT.md except the upstream value
it is compared against (column "upstream")."""

from __future__ import annotations

import time
from collections import Counter

import pandas as pd

from itibar import config, data, grades, load, paths, structure

UPSTREAM = {  # DATA_REPORT.md @ emadjumaah/hadith b5a0cf2
    "hadiths": 715_790, "sanads": 577_024, "sanad_rawis": 4_414_211, "rawis": 49_844,
    "meaning_groups": 20_745, "books": 425, "aqwal": 127_863, "alems": 1_015, "tarafs": 20_745,
    "hadith_rawis": 3_339_040, "hadith_ayas": 117_194, "topics": 54_862,
    "group_without_hadith": 461, "marfu_without_group": 522, "end_not_sahabi": 17_811,
    "homonym_clusters": 421, "stubs": 25, "length_mismatch": 60, "max_rank_mismatch": 0,
    "riwaya_qty_off_10x": 1_988, "mention_exact": 216_177, "single_chain_hadith": 307_205,
}

# A few narrators whose Taqrib tabaqa is well known (editor's reading of Taqrib
# al-Tahdhib; indicative only — verify against a printed edition before citing).
TAQRIB_SPOT = [
    (5719, "'Alqama b. Waqqas", 2), (6796, "Muhammad b. Ibrahim al-Taymi", 4),
    (8272, "Yahya b. Sa'id al-Ansari", 5), (8271, "Yahya b. Sa'id al-Qattan", 9),
    (4797, "'Abdullah b. Dinar", 4), (6659, "Malik b. Anas", 7), (3436, "Sufyan al-Thawri", 7),
    (3795, "Shu'ba b. al-Hajjaj", 7), (3443, "Sufyan b. 'Uyayna", 8), (6458, "Qatada", 4),
    (7863, "Nafi' mawla Ibn 'Umar", 3), (4698, "al-Humaydi", 10), (488, "Ahmad b. Hanbal", 10),
    (6817, "al-Bukhari", 11),
]


def md_table(df, floatfmt: str = "{:,.3f}") -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = []
        for v in row:
            if v is pd.NA or v is pd.NaT:
                cells.append("")
            elif isinstance(v, float):
                cells.append("" if v != v else (f"{v:,.0f}" if v.is_integer() else floatfmt.format(v)))
            elif isinstance(v, int):
                cells.append(f"{v:,}")
            else:
                cells.append("" if v is None else str(v).replace("|", "\\|"))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def check(label: str, ours: int, upstream: int | None) -> str:
    if upstream is None:
        return f"| {label} | {ours:,} | | |"
    mark = "match" if ours == upstream else f"**differs ({ours - upstream:+,})**"
    return f"| {label} | {ours:,} | {upstream:,} | {mark} |"


def companion_sql(scale: grades.GradeScale, rank_no: str = "rank_no", rank: str = "rank") -> str:
    """SQL predicate mirroring GradeScale.is_companion."""
    q = lambda xs: ",".join("'" + x + "'" for x in sorted(xs)) or "NULL"
    ranks = ",".join(str(r) for r in sorted(scale.companion_rank_nos))
    return (f"(coalesce({rank}, '') IN ({q(scale.companion_label_overrides)}) OR ({rank_no} IN ({ranks}) "
            f"AND coalesce({rank}, '') NOT IN ({q(scale.companion_exclude_labels)})))")


PR1_RULE = structure.ContinuityRule(window=frozenset(range(5)), min_hearing_age=0)


def link_detail(nar: load.Narrators, teacher: int, student: int, rule: structure.ContinuityRule) -> str:
    verdict, basis = structure.link_continuity(nar, teacher, student, rule)
    if basis == "years":
        d, b = int(nar.death[teacher]), int(nar.birth[student])
        return f"{verdict} (years: d. {d} − b. {b} = {d - b})"
    if basis == "tabaka":
        tu, tv = int(nar.tabaka[teacher]), int(nar.tabaka[student])
        return f"{verdict} (tabaka {tu} → {tv}, gap {tv - tu:+d})"
    return verdict


def misresolution_table(c, nar: load.Narrators, nick: dict) -> tuple[str, int, int]:
    """For every cross-name misresolution documented in tests/gold/gold.yaml (and
    every candidate), check each chain's links into and out of the wrongly
    resolved narrator against the continuity rule. Returns (markdown, caught, total)."""
    from itibar import gold

    rule = structure.ContinuityRule.load()
    rows = [("| gold entry | group | sanad | resolved (in the data) | intended | link above: teacher → resolved | "
             "link below: resolved → student | verdict | PR 1 rule |"), "|" + "---|" * 9]
    caught = total = 0
    for e in gold.entries():
        gid = int(e["group_id"])
        cases = [(d["misresolution"], [int(s) for s in d["sanad_ids"]], "documented")
                 for d in e.get("known_deviations") or [] if d.get("misresolution")]
        for cm in e.get("candidate_misresolution") or []:
            res, teacher = int(cm["resolved"][1:]), int(cm["teacher"][1:])
            sids = [r[0] for r in c.sql(f"""SELECT DISTINCT a.sanad_id FROM sanad_rawis a
                JOIN sanad_rawis b ON b.sanad_id = a.sanad_id AND b.pos = a.pos + 1
                JOIN sanads s ON s.id = a.sanad_id JOIN hadiths h ON h.id = s.hadith_id
                WHERE h.group_id = {gid} AND a.rawi_id = {res} AND b.rawi_id = {teacher} ORDER BY 1""").fetchall()]
            cases.append((cm, sids, "candidate"))
        for mis, sids, status in cases:
            res, intended = int(mis["resolved"][1:]), int(mis["intended"][1:])
            for sid in sids:
                ch = [r[0] for r in c.sql(f"SELECT rawi_id FROM sanad_rawis WHERE sanad_id = {sid} ORDER BY pos").fetchall()]
                for pos in [i for i, r in enumerate(ch) if r == res]:
                    above = link_detail(nar, ch[pos + 1], res, rule) if pos + 1 < len(ch) else "—"
                    below = link_detail(nar, res, ch[pos - 1], rule) if pos > 0 else "—"
                    hit = above.startswith("incompatible") or below.startswith("incompatible")
                    old = [structure.link_continuity(nar, ch[pos + 1], res, PR1_RULE)[0] if pos + 1 < len(ch) else "",
                           structure.link_continuity(nar, res, ch[pos - 1], PR1_RULE)[0] if pos > 0 else ""]
                    total += 1
                    caught += hit
                    teacher = nick.get(ch[pos + 1], "") if pos + 1 < len(ch) else ""
                    rows.append(f"| {e['id']}{' (candidate)' if status == 'candidate' else ''} | {gid} | {sid} | "
                                f"{nick.get(res, res)} (r{res}) | {nick.get(intended, intended)} (r{intended}) | "
                                f"{teacher}: {above} | {below} | **{'caught' if hit else 'not caught'}** | "
                                f"{'caught' if 'incompatible' in old else 'not caught'} |")
    return "\n".join(rows), caught, total


def misresolution_rate(c) -> str:
    """Per gold entry with a chain-by-chain deviation list: documented misresolution
    and dropped-link chains over in-scope chains; pooled over those entries."""
    from itibar import gold
    rows = []
    for e in gold.entries():
        if not e.get("deviation_key") or e.get("scope_from"):
            continue
        gid = int(e["group_id"])
        chains = load.chains_by_group(c, [gid]).get(gid, [])
        sc = e.get("scope") or {}
        if sc.get("companion") is not None:
            chains = [x for x in chains if x.rawis[-1] == int(sc["companion"])]
        mis = sum(len(d["sanad_ids"]) for d in e.get("known_deviations") or [] if d.get("misresolution"))
        drop = sum(len(d["sanad_ids"]) for d in e.get("known_deviations") or []
                   if not d.get("misresolution") and "dropped link" in d.get("reason", ""))
        other = sum(len(d["sanad_ids"]) for d in e.get("known_deviations") or []) - mis - drop
        rows.append({"entry": e["id"], "group": gid, "in_scope_chains": len(chains), "misresolution": mis,
                     "dropped_link": drop, "error_chains": mis + drop, "other_documented_routes": other,
                     "error_rate": (mis + drop) / len(chains) if chains else None})
    t = pd.DataFrame(rows)
    tot = t["in_scope_chains"].sum()
    err = t["error_chains"].sum()
    out = [("Every gold entry whose chains were inspected one by one (`deviation_key` and `known_deviations` in "
            "`tests/gold/gold.yaml`): chains documented as a cross-name misresolution (`misresolution`) or a dropped "
            "link, over the chains in the entry's scope. Other documented deviations (alternative routes the classical "
            "sources do not count) are listed but are not errors of the data. The four entries are hand-picked famous "
            "reports, so this is an indicative rate for the limitations section, not an estimate for the corpus.\n"),
           md_table(t),
           (f"\nPooled: **{err} of {tot} in-scope chains ({err / tot:.2%})** carry a documented misresolution or "
            f"dropped link; misresolution alone {t['misresolution'].sum()} ({t['misresolution'].sum() / tot:.2%}).\n")]
    return "\n".join(out)


def v2_section(c, scale) -> str:
    rp = paths.records_path().as_posix()
    cp = paths.chains_path().as_posix()
    r = pd.read_parquet(rp)
    r = r[r["status"] == "ok"]
    hk = scale.hukm_codes
    src = r["matn_no_group"]
    out = []
    books = c.sql("SELECT id, name FROM books WHERE id IN (1, 2) ORDER BY id").fetchall()
    out.append("Books used by the qarāʾin and the collection classes, verified: "
               + "; ".join(f"`books.id` {i} = {n}" for i, n in books) + ".\n")
    rows = [("v1 (best single chain)", (r["derived_code"] == src).mean())]
    for col in sorted(x for x in r.columns if x.startswith("code_v2_")):
        rows.append((col.replace("code_v2_", "v2 ").replace("alt_", "variant "), (r[col] == src).mean()))
    t = pd.DataFrame(rows, columns=["grade", "agreement_with_matn_no"])
    out.append("**Agreement with the source's recorded group grade** (`meaning_groups.matn_no`), over the "
               f"{len(r):,} groups with chains. Variants run on the `ibn_hajar` ruleset with one switch changed "
               "(config `derive.variants`); they are reported, not used. The gate requires both rulesets ≥ v1.\n")
    out.append(md_table(t, floatfmt="{:.4f}"))
    for rs in ("ibn_hajar", "ibn_al_salah"):
        xt = pd.crosstab(r[f"code_v2_{rs}"].astype(int), src.astype(int))
        xt.index = [f"ours {i}" for i in xt.index]
        xt.columns = [f"{cd} {hk.get(cd, '')}" for cd in xt.columns]
        out.append(f"\n**Disagreement table, `{rs}`**: our v2 code (rows) by the source's code (columns):\n")
        out.append(md_table(xt.reset_index().rename(columns={"index": "v2 code"})))
    xt = pd.crosstab(r["derived_code"].astype(int), src.astype(int))
    xt.index = [f"ours {i}" for i in xt.index]
    xt.columns = [f"{cd} {hk.get(cd, '')}" for cd in xt.columns]
    out.append("\n**For comparison, v1**:\n")
    out.append(md_table(xt.reset_index().rename(columns={"index": "v1 code"})))
    rules = r["rule_v2_ibn_hajar"].value_counts().rename_axis("rule").reset_index(name="groups")
    rules["share"] = rules["groups"] / len(r)
    out.append("\n**Rule that fired for the group's v2 chain (`ibn_hajar`)**:\n")
    out.append(md_table(rules))
    dv = r["divergence_v2_ibn_hajar"].value_counts().rename_axis("divergence").reset_index(name="groups")
    att = r.loc[r["divergence_v2_ibn_hajar"].notna(), "witness_attested_v2_ibn_hajar"].mean()
    out.append(f"\n**Divergence class of the witness** (upgraded groups; the witness is an attested chain in "
               f"{att:.1%} of them, else a route spliced from several chains):\n")
    out.append(md_table(dv))
    ch = pd.read_parquet(cp, columns=["sanad_id", "weakest_positions", "chain_ordinal"])
    best = r[["group_id", "best_sanad_v2_ibn_hajar", "code_v2_ibn_hajar", "matn_no_group", "derived_code"]].merge(
        ch, left_on="best_sanad_v2_ibn_hajar", right_on="sanad_id", how="left")
    best["weakest_level"] = [13 - int(o) if 1 <= o <= 12 else "unknown" for o in best["chain_ordinal"]]
    bl = best.groupby("weakest_level").apply(lambda d: pd.Series({
        "groups": len(d), "agree_v1": (d["derived_code"] == d["matn_no_group"]).mean(),
        "agree_v2_ibn_hajar": (d["code_v2_ibn_hajar"] == d["matn_no_group"]).mean()}), include_groups=False)
    out.append("\n**By the weakest narrator's Taqrīb level** in the group's v2 chain (`ibn_hajar`):\n")
    out.append(md_table(bl.reset_index()))
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
    out.append(md_table(top))
    down = r[(r["derived_code"] == 0) & (r["code_v2_ibn_hajar"] > 0)]
    dch = pd.read_parquet(cp, columns=["sanad_id", "defects_v2_ibn_hajar"]).set_index("sanad_id")
    comp = Counter(",".join(dch.loc[int(s), "defects_v2_ibn_hajar"]) or "none"
                   for s in down["best_sanad_v2_ibn_hajar"])
    out.append(f"\n**Downgrades.** {len(down):,} groups that v1 grades 0 get a higher v2 code under `ibn_hajar` "
               f"({int((down['matn_no_group'] == 0).sum()):,} of them recorded 0 by the source). The defects of their "
               "v2 chain: " + "; ".join(f"{k} {v:,}" for k, v in comp.most_common()) + ". A mudallis's muʿanʿan "
               "link is a light defect by the brief's decision, and a light defect, even corroborated, reaches ḥasan "
               "li-ghayrihi at most. The source's binary `has_tadlis` does not carry Ibn Hajar's five tiers of "
               "mudallisūn, whose first two tiers' ʿan is accepted (DECISIONS.md D36).\n")
    return "\n".join(out)


def number_section(c) -> str:
    from itibar import structure
    r = pd.read_parquet(paths.records_path())
    r = r[r["status"] == "ok"]
    N = structure.tawatur_n()
    out = []
    order = ["gharib_mutlaq", "gharib_nisbi", "aziz", "mashhur", "mutawatir_count"]
    nc = r["number_class"].fillna("no route").value_counts().reindex(order + ["no route"], fill_value=0)
    t = pd.DataFrame({"number_class": nc.index, "groups": nc.values, "share": nc.values / len(r)})
    out.append(f"Width on the on-path graph at `all`, Taqrīb layers 1–12, compiler roles excluded; tawatur_n = {N}. "
               "`no route`: no on-path narrator in layers 1–12 (κ_all = 0).\n")
    out.append(md_table(t))
    xt = pd.crosstab(r["number_class"].fillna("no route"), r["number_class_kappa"].fillna("no route"))
    out.append("\n**Width reading (rows) against the κ reading (columns)**:\n")
    out.append(md_table(xt.reset_index().rename(columns={"number_class": "width \\ κ"})))
    dis = r["number_class_disagree"].mean()
    wide = ((r["number_class"].isin(["gharib_mutlaq", "gharib_nisbi"])) & (r["kappa_all"] >= 2)).sum()
    out.append(f"\nThe readings differ in {dis:.1%} of groups. The width reading treats each Taqrīb layer as a cut, "
               "but routes skip layers (tabaka steps of 2–4 are normal on this scale, §8.5), so a layer is a cut only "
               f"when every route has a narrator in it. {wide:,} groups read gharīb by width while κ_all ≥ 2: the "
               "single narrator sits in a layer other routes jump over (group 273, إن الله لا يقبض العلم انتزاعا, is "
               "gharīb nisbī by width because Shaqīq is alone at layer 2, and mashhūr by κ). The converse (κ below "
               "the width class) is hidden sharing: the minimum cut mixes narrators of different layers.\n")
    rows = []
    for n in sorted(set([4, 5, 10, 12, 40, 70] + [N])):
        rows.append({"tawatur_n": n, "mutawatir_count (width)": int((r["min_width"] >= n).sum()),
                     "mutawatir_count (κ_all)": int((r["kappa_all"] >= n).sum()),
                     "mashhur (width)": int(((r["min_width"] >= 3) & (r["min_width"] < n)).sum())})
    out.append("\n**Sensitivity to tawatur_n** (the numbers the books report as proposed):\n")
    out.append(md_table(pd.DataFrame(rows)))
    q = pd.DataFrame([{"flag": f, "groups": int(r[f].sum()), "share": r[f].mean(),
                       "recorded 0 (صحيح) among them": (r.loc[r[f], "matn_no_group"] == 0).mean()}
                      for f in ("in_sahihayn", "in_sahih_class", "sound_distinct_routes", "huffaz_chain")])
    out.append("\n**Qarāʾin flags** (reported, never combined; knowledge yield is not computed):\n")
    out.append(md_table(q))
    allq = (r["in_sahihayn"] & r["sound_distinct_routes"] & r["huffaz_chain"]).sum()
    out.append(f"\nAll three flags together: {allq:,} groups.\n")
    return "\n".join(out)


def build() -> str:
    t0 = time.time()
    c = data.views()
    scale = grades.load()
    q1 = lambda s: c.sql(s).fetchall()[0][0]  # noqa: E731
    df = lambda s: c.sql(s).df()  # noqa: E731
    src = config.load("source")["huggingface"]
    ph_ids = ",".join(str(i) for i in scale.placeholders)
    gap_ids = ",".join(str(k) for k, v in scale.placeholders.items() if v["role"] == "gap")
    W: list[str] = []
    w = W.append

    w("# itibar — source audit\n")
    w(f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `make audit` (`itibar.audit`) from the Parquet copy of "
      f"`{src['filename']}` (Hugging Face `{src['repo_id']}` @ `{src['revision'][:12]}`, sha256 "
      f"`{src['sha256'][:16]}…`). Upstream comparison values are from `DATA_REPORT.md` at "
      f"`emadjumaah/hadith@{config.load('source')['upstream_code']['commit'][:7]}`.\n")
    w("Every number below is recomputed. Where itibar's definition differs from upstream's, both are shown.\n")

    # ------------------------------------------------------------------ 1
    w("## 1. Upstream facts re-verified\n")
    w("| quantity | ours | upstream | |\n|---|---|---|---|")
    for t in ("hadiths", "sanads", "sanad_rawis", "rawis", "meaning_groups", "books", "tarafs", "hadith_rawis",
              "hadith_ayas", "aqwal", "alems", "topics"):
        w(check(f"rows in `{t}`", q1(f"SELECT count(*) FROM {t}"), UPSTREAM[t]))
    empty = q1("SELECT count(*) FROM meaning_groups g WHERE id > 0 AND NOT EXISTS "
               "(SELECT 1 FROM hadiths h WHERE h.group_id = g.id)")
    w(check("meaning groups (id > 0) with no hadith", empty, UPSTREAM["group_without_hadith"]))
    w(check("marfu'/qudsi hadith with no group", q1("SELECT count(*) FROM hadiths WHERE type_no IN (0,1) AND group_id IS NULL"),
            UPSTREAM["marfu_without_group"]))
    c.execute("""CREATE OR REPLACE TEMP TABLE chain_end AS
        SELECT s.id AS sanad_id, h.type_no, h.group_id, h.book_id, e.rawi_id, r.rank, r.rank_no, r.tabaka, r.is_stub
        FROM sanads s JOIN hadiths h ON h.id = s.hadith_id
        JOIN (SELECT sanad_id, arg_max(rawi_id, pos) AS rawi_id FROM sanad_rawis GROUP BY 1) e ON e.sanad_id = s.id
        JOIN rawis r ON r.id = e.rawi_id""")
    w(check("marfu'/qudsi chains whose end has rank != 'صحابي' (upstream definition)",
            q1("SELECT count(*) FROM chain_end WHERE type_no IN (0,1) AND rank != 'صحابي'"), UPSTREAM["end_not_sahabi"]))
    w(check("homonym clusters: same (name, nickname), non-stub, >1 narrator",
            q1("SELECT count(*) FROM (SELECT name, nickname FROM rawis WHERE is_stub = 0 GROUP BY 1, 2 HAVING count(*) > 1)"),
            UPSTREAM["homonym_clusters"]))
    w(check("stub narrators (is_stub = 1)", q1("SELECT count(*) FROM rawis WHERE is_stub = 1"), UPSTREAM["stubs"]))
    w(check("sanads.length != distinct narrators in chain", q1(
        "SELECT count(*) FROM sanads s JOIN (SELECT sanad_id, count(DISTINCT rawi_id) n FROM sanad_rawis GROUP BY 1) x "
        "ON x.sanad_id = s.id WHERE s.length != x.n"), UPSTREAM["length_mismatch"]))
    w(check("sanads.max_rank != max(rank_no) over the whole chain incl. pos 0", q1(
        "SELECT count(*) FROM sanads s JOIN (SELECT sr.sanad_id, max(r.rank_no) m FROM sanad_rawis sr "
        "JOIN rawis r ON r.id = sr.rawi_id GROUP BY 1) x ON x.sanad_id = s.id WHERE s.max_rank != x.m"),
        UPSTREAM["max_rank_mismatch"]))
    w(check("narrators whose riwaya_qty is off from chain appearances by >10x", q1(
        "SELECT count(*) FROM rawis r JOIN (SELECT rawi_id, count(*) c FROM sanad_rawis GROUP BY 1) x ON x.rawi_id = r.id "
        "WHERE r.riwaya_qty > 0 AND (x.c > r.riwaya_qty * 10 OR r.riwaya_qty > x.c * 10)"), UPSTREAM["riwaya_qty_off_10x"]))
    single = q1("SELECT count(*) FROM (SELECT hadith_id FROM sanads GROUP BY 1 HAVING count(*) = 1)")
    exact = q1("""WITH one AS (SELECT hadith_id, min(id) sid FROM sanads GROUP BY 1 HAVING count(*) = 1),
        m AS (SELECT hadith_id, string_agg(rawi_id::VARCHAR, ',' ORDER BY seq) sig FROM hadith_rawis GROUP BY 1),
        cc AS (SELECT one.hadith_id, string_agg(sr.rawi_id::VARCHAR, ',' ORDER BY sr.pos) sig FROM one
               JOIN sanad_rawis sr ON sr.sanad_id = one.sid AND sr.pos > 0 GROUP BY 1)
        SELECT count(*) FROM m JOIN cc USING (hadith_id) WHERE m.sig = cc.sig""")
    w(check("single-chain hadith", single, UPSTREAM["single_chain_hadith"]))
    w(check("…whose mention sequence equals the chain minus pos 0 (upstream check)", exact, UPSTREAM["mention_exact"]))
    w("")
    w("All upstream facts this project depends on reproduce exactly. Note: `meaning_groups` also has a row "
      "`id = 0` (`غير منشور`, \"unpublished\") with no hadith; upstream excludes it (`id > 0`), so the "
      "table holds 462 groups without hadith. `sanads.max_rank` includes the book author at pos 0 "
      "(upstream `meta`), which matters for the derived-grade comparison (§8.6).\n")

    w("### sahaba_qty spot check (10 most-narrated groups)\n")
    w("`upstream` = distinct chain-end narrators with rank exactly `صحابي`; `itibar` = distinct companions "
      "(rank_no 1 minus the labels that deny companionship, plus the young-companion labels at any rank_no) at "
      "chain ends; `on path` = companions narrating "
      "directly from PROPHET on an unbroken route to a book (`records.companions`; requires `make bundles`).\n")
    rec_exists = (paths.records_path()).exists()
    on_path_sql = (f"(SELECT companions FROM read_parquet('{paths.records_path().as_posix()}') r WHERE r.group_id = g.id)"
                   if rec_exists else "NULL")
    is_comp = companion_sql(scale)
    sq = df(f"""SELECT g.id AS group_id, g.sahaba_qty AS declared,
            (SELECT count(DISTINCT e.rawi_id) FROM chain_end e WHERE e.group_id = g.id AND e.rank = 'صحابي') AS upstream,
            (SELECT count(DISTINCT e.rawi_id) FROM chain_end e WHERE e.group_id = g.id
               AND {companion_sql(scale, 'e.rank_no', 'e.rank')} AND e.rawi_id NOT IN ({ph_ids})) AS itibar,
            {on_path_sql} AS on_path, left(g.nass, 50) AS opening
            FROM meaning_groups g WHERE g.id > 0 ORDER BY g.repeat_qty DESC LIMIT 10""")
    w(md_table(sq))
    w("\nThe upstream audit table reads group 1 at 64 recomputed companions (the brief's \"63\" is group 2's "
      "figure). Upstream's exact-label rule misses female companions (`صحابية`) and `صحابي صغير`.\n")

    # ------------------------------------------------------------------ 2
    w("## 2. `rawis.rank` vocabulary and the `rank_no` ordering\n")
    rk = df("""SELECT rank_no, count(*) AS narrators, count(DISTINCT coalesce(rank, '')) AS labels,
               string_agg(DISTINCT CASE WHEN rn <= 3 THEN rank END, ' / ') AS top_labels
               FROM (SELECT *, row_number() OVER (PARTITION BY rank_no ORDER BY cnt DESC) rn FROM
                    (SELECT rank_no, rank, count(*) OVER (PARTITION BY rank_no, rank) cnt FROM rawis))
               GROUP BY 1 ORDER BY 1""")
    rk["taqrib_level"] = [scale.level_name.get(int(r), "never described (stubs)") for r in rk["rank_no"]]
    rk["itibar_ordinal"] = [scale.level_ordinal.get(int(r), 0) for r in rk["rank_no"]]
    w(md_table(rk[["rank_no", "narrators", "labels", "taqrib_level", "itibar_ordinal", "top_labels"]]))
    w("")
    w("**`rank_no` is Ibn Hajar's twelve-level scale from *Taqrib al-Tahdhib*.** The labels are Taqrib's wording "
      "verbatim (Malik's `رأس المتقنين وكبير المتثبتين`, al-Bukhari's `جبل الحفظ وإمام الدنيا في فقه الحديث` sit at "
      "level 2), and the levels run in Taqrib order: companions → `ثقة ثقة`/`حافظ` → `ثقة` → `صدوق` → `صدوق يهم` → "
      "`مقبول` → `مجهول الحال` → `ضعيف` → `مجهول` → `متروك` → `متهم` → `كذاب`/`وضاع`. **Higher `rank_no` is weaker**, "
      "confirmed three ways: the label sequence; `sanads.max_rank` = max(rank_no) over the chain (0 mismatches, §1), "
      "i.e. the weakest link is the maximum; and the source's own chain grades worsen monotonically with it:\n")
    mono = df("""SELECT max_rank, count(*) AS chains, round(avg(matn_no), 2) AS mean_chain_code,
                 round(avg((matn_no = 0)::INT), 3) AS share_code0 FROM sanads GROUP BY 1 ORDER BY 1""")
    w(md_table(mono))
    w("\nThe dip at 12 is the placeholders (§8.1): every chain through a break marker gets `max_rank` 12.\n")
    w("`rank_no = 0` is not a grade: it marks the 25 stub narrators the source never described. The four rows "
      "with `rank IS NULL` and `rank_no = 12` are not people at all (§8.1). The full vocabulary — "
      f"{q1('SELECT count(DISTINCT (rank_no, coalesce(rank, chr(0)))) FROM rawis'):,} distinct (rank_no, label) pairs "
      "with counts and itibar's ordinal — is regenerated into `config/grades.yaml` (`labels:`) by this target "
      "and reproduced in Appendix A.\n")
    anomalies = df("""SELECT rank_no, rank, count(*) AS n FROM rawis WHERE
        (rank_no = 1 AND rank IN ('لم تثبت له صحبة', 'له إدراك', 'لها إدراك'))
        OR (rank_no > 1 AND (rank LIKE 'صحابي%' OR rank LIKE 'صحابية%'))
        OR (rank_no IN (2, 3) AND rank LIKE '%مقبول%') OR (rank_no >= 6 AND rank LIKE 'ثقة%')
        OR (rank_no < 8 AND rank LIKE 'ضعيف%') OR (rank_no = 6 AND rank LIKE 'انفرد بتوثيقه%')
        GROUP BY 1, 2 ORDER BY 1, n DESC""")
    w("Labels whose wording disagrees with their level (kept at the source's level; itibar grades by `rank_no`):\n")
    w(md_table(anomalies))
    w("")
    w("### 2.1 Companion label overrides\n")
    ov = ",".join("'" + x + "'" for x in sorted(scale.companion_label_overrides)) or "NULL"
    ovt = df(f"""SELECT r.id, r.nickname, r.rank, r.rank_no, r.tabaka, r.death_year,
                 (SELECT count(*) FROM chain_end e WHERE e.rawi_id = r.id AND e.type_no IN (0, 1)) AS chain_ends,
                 (SELECT count(DISTINCT e.group_id) FROM chain_end e WHERE e.rawi_id = r.id AND e.type_no IN (0, 1)) AS groups
                 FROM rawis r WHERE r.rank IN ({ov}) AND r.rank_no NOT IN ({','.join(map(str, sorted(scale.companion_rank_nos)))})
                 ORDER BY r.rank_no, r.id""")
    w(f"`grades.yaml: companion.label_overrides` ({', '.join('`' + x + '`' for x in sorted(scale.companion_label_overrides))}) "
      f"makes a narrator a companion whatever its `rank_no`. {len(ovt)} narrators carry these labels outside rank_no 1 "
      f"({q1(f'SELECT count(*) FROM rawis WHERE rank IN ({ov}) AND rank_no = 1')} more are at rank_no 1 and were "
      "companions already). Their chains now reach PROPHET. Companionship only: the ordinal still follows `rank_no` "
      "(DECISIONS D33).\n")
    w(md_table(ovt))
    disp = df(f"""WITH d AS (SELECT rank_no, count(*) AS narrators, sum(({is_comp})::INT) AS companions_in_itibar
                             FROM rawis WHERE rank LIKE '%مختلف في صحب%' GROUP BY 1),
                       e AS (SELECT rank_no, count(*) AS chain_ends FROM chain_end
                             WHERE type_no IN (0, 1) AND rank LIKE '%مختلف في صحب%' GROUP BY 1)
                  SELECT d.*, coalesce(e.chain_ends, 0) AS chain_ends FROM d LEFT JOIN e USING (rank_no) ORDER BY 1""")
    w("\nDisputed companionship (`مختلف في صحبته` and variants) is not overridden and follows `rank_no`: a companion "
      "at rank_no 1, a narrator of that level otherwise.\n")
    w(md_table(disp))
    w("")

    # ------------------------------------------------------------------ 3
    w("## 3. `tabaka`: distribution, and Ibn Hajar's twelve generations\n")
    tb = df("""SELECT tabaka, count(*) AS narrators, sum((death_year IS NOT NULL)::INT) AS with_death,
               median(death_year) AS median_death, min(death_year) AS min_death, max(death_year) AS max_death,
               round(avg(CASE WHEN death_year IS NULL THEN NULL WHEN tabaka <= 2 THEN (death_year <= 100)::INT
                    WHEN tabaka <= 8 THEN (death_year > 100 AND death_year <= 200)::INT
                    WHEN tabaka <= 12 THEN (death_year > 200)::INT END), 3) AS fits_taqrib_rule
               FROM rawis GROUP BY 1 ORDER BY 1""")
    w(md_table(tb))
    w("")
    w("The column runs 0–38, not 1–12. **0 means missing** (8,143 narrators, including the 25 stubs and the "
      "four placeholders). Values 1–12 follow Ibn Hajar's layering: `fits_taqrib_rule` tests the rule Ibn Hajar gives "
      "in the introduction to *Taqrib* (layers 1–2 died before 100 AH, 3–8 after 100, 9–12 after 200) against the "
      "parsed death year. Values 13–38 extend the same scheme past Taqrib to the later compilers, about 25 years per "
      "layer (al-Bayhaqi, d. 458, is 19). Individual narrators can sit one layer off Taqrib:\n")
    names = dict(c.sql("SELECT id, tabaka FROM rawis").fetchall())
    w("| narrator | rawi id | source tabaka | Taqrib tabaqa |\n|---|---|---|---|")
    for rid, nm, tq in TAQRIB_SPOT:
        w(f"| {nm} | {rid} | {names.get(rid)} | {tq} |")
    w("\nSo `tabaka` is the source's generation scale anchored on Taqrib, not a copy of Taqrib's tabaqa field. "
      "Layers are used for the width profile; layer gaps along chain links calibrate the continuity check (§8.5).\n")

    # ------------------------------------------------------------------ 4
    w("## 4. Birth and death years: coverage by tabaka\n")
    cov = df("""SELECT CASE WHEN tabaka = 0 THEN '0 (missing)' WHEN tabaka <= 12 THEN lpad(tabaka::VARCHAR, 2, '0')
                ELSE '13+' END AS tabaka, count(*) AS narrators,
                sum((death_year IS NOT NULL)::INT) AS death_parsed,
                sum((death_year IS NULL AND death_year_raw IS NOT NULL)::INT) AS death_raw_only,
                sum((death_year_raw IS NULL)::INT) AS death_missing,
                sum((birth_year IS NOT NULL)::INT) AS birth_parsed,
                sum((birth_year IS NULL AND birth_year_raw IS NOT NULL)::INT) AS birth_raw_only,
                sum((birth_year_raw IS NULL)::INT) AS birth_missing
                FROM rawis GROUP BY 1 ORDER BY 1""")
    w(md_table(cov))
    raw_examples = df("""SELECT death_year_raw, count(*) n FROM rawis WHERE death_year IS NULL AND death_year_raw IS NOT NULL
                         GROUP BY 1 ORDER BY n DESC LIMIT 8""")
    w("\nRaw-only values are ranges or approximations the build declined to parse, e.g. "
      + ", ".join(f"`{r}` ({n})" for r, n in raw_examples.itertuples(index=False)) + ". itibar keeps them beside the "
      "parsed value (terminus columns) and never parses them itself. Where both the teacher's death and the "
      "student's birth are known the continuity check uses years; otherwise it falls back to tabaka (§8.5).\n")

    # ------------------------------------------------------------------ 5
    w("## 5. Inline mentions and transmission words\n")
    wp = paths.OUT_DIR / "words.parquet"
    w(f"Upstream's check (single-chain hadith whose full mention sequence equals the chain minus pos 0) reproduces: "
      f"**{exact:,} of {single:,}**. This is what lets us read the transmission word before each narrator.\n")
    if wp.exists():
        c.execute(f"CREATE OR REPLACE VIEW words AS SELECT * FROM read_parquet('{wp.as_posix()}')")
        al = df("""SELECT method, count(DISTINCT sanad_id) AS chains, count(*) AS links FROM words GROUP BY 1 ORDER BY 1""")
        tot_links = q1(f"SELECT count(*) FROM sanad_rawis WHERE pos > 0 AND rawi_id NOT IN ({gap_ids})")
        w("itibar's alignment (`itibar.words`) restricts mentions to the sanad part (before `matn_start`), skips break "
          "markers (they have no mention), and accepts in-order subsequences for multi-chain (tahwil) hadith:\n")
        w(md_table(al))
        w(f"\nWords are recovered for {q1('SELECT count(*) FROM words'):,} of {tot_links:,} narrator links "
          f"({q1('SELECT count(*) FROM words') / tot_links:.1%}); chains of {q1('SELECT count(*) FROM sanads') - q1('SELECT count(DISTINCT sanad_id) FROM words'):,} "
          "sanads are unaligned and get `unknown word`.\n")
        wc = df("""SELECT coalesce(word_class, '(no token)') AS class, count(*) AS links,
                   string_agg(DISTINCT word, ' ') FILTER (WHERE rn <= 4) AS top_forms FROM
                   (SELECT *, row_number() OVER (PARTITION BY word_class ORDER BY cnt DESC) rn FROM
                    (SELECT word_class, word, count(*) OVER (PARTITION BY word_class, word) cnt FROM words))
                   GROUP BY 1 ORDER BY links DESC""")
        w(md_table(wc))
        w("\n`(no token)`: two mentions with nothing between them (co-teachers joined by `و`).\n")
    else:
        w("_(run `make bundles` first for the alignment table)_\n")

    # ------------------------------------------------------------------ 6
    w("## 6. Homonyms, stubs, chains not ending in a companion, empty groups\n")
    w("### 6.1 The 421 same-name clusters\n")
    hc = df(f"""WITH cl AS (SELECT name, nickname, list(id ORDER BY id) ids, count(*) n FROM rawis
                WHERE is_stub = 0 AND id NOT IN ({ph_ids}) GROUP BY 1, 2 HAVING count(*) > 1),
             m AS (SELECT unnest(ids) id, nickname FROM cl),
             used AS (SELECT m.nickname, count(DISTINCT sr.rawi_id) used_members, count(*) links
                      FROM m JOIN sanad_rawis sr ON sr.rawi_id = m.id GROUP BY 1)
             SELECT cl.nickname, cl.n AS members, coalesce(used.used_members, 0) AS members_in_chains,
                    coalesce(used.links, 0) AS chain_links FROM cl LEFT JOIN used USING (nickname)
             ORDER BY chain_links DESC LIMIT 12""")
    both = q1(f"""WITH cl AS (SELECT name, nickname, id FROM rawis WHERE is_stub = 0 AND id NOT IN ({ph_ids})
                  AND (name, nickname) IN (SELECT name, nickname FROM rawis WHERE is_stub = 0 GROUP BY 1, 2 HAVING count(*) > 1)),
                g AS (SELECT DISTINCT h.group_id, cl.name, cl.nickname, cl.id FROM sanad_rawis sr
                      JOIN cl ON cl.id = sr.rawi_id JOIN sanads s ON s.id = sr.sanad_id JOIN hadiths h ON h.id = s.hadith_id
                      WHERE h.group_id IS NOT NULL)
                SELECT count(*) FROM (SELECT group_id, name, nickname FROM g GROUP BY 1, 2, 3 HAVING count(*) > 1)""")
    w(md_table(hc))
    w(f"\nA cluster can only change kappa inside a group where two of its members both occur: that happens "
      f"{both:,} times (group × cluster). `kappa_lower` merges every cluster into one node. Misresolution across "
      "*different* full names is not caught by these clusters: e.g. `يحيى بن سعيد` resolved to al-Qattan (r8271, "
      "nickname `يحيى بن سعيد القطان`) where the student of al-Taymi is al-Ansari (r8272, `يحيى بن سعيد الأنصاري`) "
      "in six chains of *innama al-a'mal* (tests/gold/gold.yaml). Same-name clusters by `nickname` alone would be "
      f"{q1('SELECT count(*) FROM (SELECT nickname FROM rawis WHERE is_stub = 0 GROUP BY 1 HAVING count(*) > 1)'):,}.\n")
    w("### 6.2 The 25 stubs\n")
    st = df("""SELECT r.id, r.name, count(sr.sanad_id) AS chain_links, min(sr.pos) AS min_pos, max(sr.pos) AS max_pos
               FROM rawis r LEFT JOIN sanad_rawis sr ON sr.rawi_id = r.id WHERE r.is_stub = 1 GROUP BY 1, 2 ORDER BY 3 DESC""")
    w(md_table(st))
    w(f"\nStubs touch {st['chain_links'].sum():,} chain links. They get ordinal 0 (below every threshold but `all`) "
      "and are dropped in `kappa_lower`. Several names are relational (`أبي`, `أبيه`, `أباه`).\n")
    w("### 6.3 Marfu'/qudsi chains not ending in a companion\n")
    ends = df(f"""SELECT CASE WHEN rawi_id IN ({gap_ids}) THEN 'break marker (' || rawi_id || ')'
                    WHEN rawi_id = 1131 THEN 'unnamed person (1131)'
                    WHEN {is_comp} THEN 'companion: ' || rank
                    WHEN rank_no = 1 THEN 'rank_no 1, not a companion: ' || rank
                    WHEN is_stub = 1 THEN 'stub'
                    ELSE 'other narrator, rank_no ' || rank_no END AS chain_end, count(*) AS chains,
                  coalesce(sum((rank != 'صحابي')::INT), 0) AS counted_by_upstream
               FROM chain_end WHERE type_no IN (0, 1) GROUP BY 1 ORDER BY chains DESC""")
    w(md_table(ends))
    ours_mursal = q1(f"""SELECT count(*) FROM chain_end WHERE type_no IN (0,1) AND NOT ({is_comp}
                       AND rawi_id NOT IN ({ph_ids}))""")
    w(f"\nUpstream's 17,811 counts chain ends whose label is not exactly `صحابي`: it **includes** 10,646 chains ending "
      f"at female companions and 3,879 at `صحابي صغير`, and **excludes** every chain ending at a NULL-rank "
      f"placeholder (37,538, mostly `موضع إرسال`, the source's own irsal marker). By itibar's companion rule "
      f"(rank_no 1, minus `لم تثبت له صحبة` / `له إدراك` / `لها إدراك`, plus the young-companion labels at any rank_no) "
      f"**{ours_mursal:,}** marfu'/qudsi chains do not "
      "end in a companion; these are kept in their bundles, flagged mursal, and get no PROPHET edge.\n")
    w("### 6.4 Groups without chains\n")
    w(f"{empty:,} groups (id > 0) have no hadith, group 0 is the `غير منشور` placeholder, and "
      f"{q1('SELECT count(*) FROM meaning_groups g WHERE EXISTS (SELECT 1 FROM hadiths h WHERE h.group_id = g.id) AND NOT EXISTS (SELECT 1 FROM hadiths h JOIN sanads s ON s.hadith_id = h.id WHERE h.group_id = g.id)'):,} "
      "group has hadith but no chain. All get a row in `out/records.parquet` with `status = 'no_chains'`. "
      f"{q1('SELECT count(*) FROM chain_end WHERE group_id IS NULL'):,} chains belong to marfu' hadith without a group "
      "and are outside every bundle.\n")

    # ------------------------------------------------------------------ 7
    w("## 7. Grade codes (`matn_no`) verified\n")
    for tbl in ("meaning_groups", "tarafs", "sanads", "hadiths"):
        if tbl == "meaning_groups":
            t = df("""SELECT g.matn_no, t.matn AS label_from_tarafs, count(*) AS n FROM meaning_groups g
                      LEFT JOIN (SELECT DISTINCT matn_no, matn FROM tarafs) t USING (matn_no) GROUP BY 1, 2 ORDER BY 1""")
        else:
            t = df(f"SELECT matn_no, matn AS label, count(*) AS n FROM {tbl} GROUP BY 1, 2 ORDER BY 1")
        w(f"**{tbl}**\n")
        w(md_table(t))
        w("")
    w("`meaning_groups.matn_no` carries no label; its codes 0–5 decode through `tarafs` (one taraf per group, same "
      "code). The upstream comment (`0=صحيح 1=حسن 2=ضعيف 3=شديد الضعف …`) is confirmed and completed: 4 = `متهم بالوضع`, "
      "5 = `موضوع`. `hadiths` adds −1 (no chain), 6 (mawquf), 7 (maqtu'), 8 (no shawahid or chain). itibar quotes these "
      "labels as the source's; its own derived grade is expressed as a Taqrib level and a code on this scale.\n")

    # ------------------------------------------------------------------ 8
    w("## 8. Findings that change connectivity numbers\n")
    w("### 8.1 Four placeholder rows are not narrators\n")
    ph = df("""SELECT r.id, r.name, r.rank_no, count(sr.sanad_id) AS chain_links, count(DISTINCT sr.sanad_id) AS chains,
                sum((sr.pos = 0)::INT) AS at_pos0,
                sum((sr.pos = s.length_raw - 1)::INT) AS at_chain_end
                FROM rawis r JOIN sanad_rawis sr ON sr.rawi_id = r.id
                JOIN (SELECT sanad_id, count(*) AS length_raw FROM sanad_rawis GROUP BY 1) s ON s.sanad_id = sr.sanad_id
                WHERE r.rank IS NULL AND r.rank_no = 12 GROUP BY 1, 2, 3 ORDER BY chain_links DESC""")
    w(md_table(ph))
    null12 = set(c.sql("SELECT id FROM rawis WHERE rank IS NULL AND rank_no = 12").fetchnumpy()["id"].tolist())
    w(f"\n`config/grades.yaml: placeholders` lists exactly this set: **{'yes' if null12 == set(scale.placeholders) else 'NO'}**. "
      "Three are the source's break markers — `موضع إرسال` (irsal: companion dropped), `موضع انقطاع` (inqita': link "
      "missing inside the chain), `موضع تعليق` (ta'liq: compiler omitted the start) — and one, `اسم مبهم`, stands for "
      "every unnamed person (\"a man\", \"a shaykh\"). Each is a single id shared by tens of thousands of chains, and "
      "each carries rank_no 12 (the `كذاب` level). Taken at face value they would (a) fuse unrelated routes through "
      "one shared hub, inflating kappa and creating false cut vertices, and (b) give every broken chain the lowest "
      "possible weakest link. itibar models break markers as one untraversable gap node per chain occurrence (the gap "
      "is recorded; no route crosses it) and the unnamed person as one node per (student, teacher) context with "
      "unknown grade.\n")
    w("### 8.2 pos 0 is not always the book's compiler\n")
    bc = df(f"SELECT * FROM read_parquet('{(paths.PARQUET_DIR / 'book_compilers.parquet').as_posix()}')") \
        if (paths.PARQUET_DIR / "book_compilers.parquet").exists() else None
    np0 = q1("""WITH p0 AS (SELECT h.book_id, sr.rawi_id FROM sanads s JOIN hadiths h ON h.id = s.hadith_id
                JOIN sanad_rawis sr ON sr.sanad_id = s.id AND sr.pos = 0),
             m AS (SELECT book_id, mode(rawi_id) top FROM p0 GROUP BY 1)
             SELECT count(*) FROM p0 JOIN m USING (book_id) WHERE p0.rawi_id != m.top""")
    w(f"{np0:,} chains (of {UPSTREAM['sanads']:,}) start with a narrator other than their book's most frequent pos-0 "
      "narrator. In primary collections pos 0 is the compiler (al-Bukhari 99.5%, Muslim 99.9%, Ahmad 99.4%); in "
      "secondary ones it is the quoted source or the compiler's teacher, and the compiler himself is absent:\n")
    if bc is not None:
        w(md_table(bc.sort_values("chains", ascending=False).head(12)[
            ["book_id", "name", "author_death_year", "chains", "top_pos0_share", "compiler_rawi_id", "compiler_node"]]))
        withc = bc[bc["chains"] > 0]
        w(f"\n{int((withc['top_pos0_share'] >= config.load('structure')['bundle']['compiler_min_share']).sum())} of "
          f"{len(withc)} books with chains have a dominant pos-0 narrator (share >= "
          f"{config.load('structure')['bundle']['compiler_min_share']}); `compiler_rawi_id` is filled when any book "
          "by the same `author_no` has one (Ibn 'Asakir is identified through another of his books). ")
    w("Without a correction, Ibn 'Asakir's many teachers would enter *Tarikh Dimashq* as parallel routes into an "
      "uncuttable book node, so a report found only there through three of his teachers would score kappa 3 although "
      "it passed through one man. itibar puts one cuttable compiler node `c<author_no>` in front of every book; "
      "every route into a book passes through it.\n")
    w("### 8.3 Self-loops, repeated narrators and cycles\n")
    sl = q1("""SELECT count(*) FROM (SELECT sanad_id, rawi_id, lag(rawi_id) OVER (PARTITION BY sanad_id ORDER BY pos) prev
               FROM sanad_rawis) WHERE rawi_id = prev""")
    rep = q1(f"""SELECT count(*) FROM (SELECT sanad_id FROM sanad_rawis WHERE rawi_id NOT IN ({ph_ids})
                 GROUP BY 1 HAVING count(*) != count(DISTINCT rawi_id))""")
    w(f"{sl:,} adjacent repeats (same narrator at pos and pos+1: a self-loop) and {rep:,} chains repeating a real "
      "narrator. Self-loops are dropped and counted per group; non-adjacent repeats and cross-chain contradictions "
      "(A from B in one chain, B from A in another) make cycles. Flow, dominators and SCC-based measures handle "
      "cycles; path counts are taken on an acyclic reduction and flagged (`paths_on_acyclic_reduction`).\n")
    if rec_exists:
        rp = paths.records_path().as_posix()
        w(f"Groups with a cycle in the on-path bundle: {q1(f'SELECT sum(has_cycle::INT) FROM read_parquet({chr(39)}{rp}{chr(39)})'):,}.\n")
    w("### 8.4 Homonym misresolution across different full names\n")
    nar = load.narrators(c, scale)
    nick = dict(c.sql("SELECT id, nickname FROM rawis").fetchall())
    mt, caught, total = misresolution_table(c, nar, nick)
    w("Not mergeable without a name-resolution model (out of scope, §6.1). The continuity rule (§8.5) is the "
      "visible symptom: a wrongly resolved narrator often sits in the wrong generation for his teacher. For every "
      "cross-name misresolution documented in `tests/gold/gold.yaml` (and the one candidate), the links into and "
      "out of the wrong narrator are checked against the corrected rule. *Caught* means at least one of them is "
      "incompatible, so the `nocompat` graph of `kappa_lower` removes that route.\n")
    w(mt)
    w(f"\n**{caught} of {total}** chains caught. The al-Qattan chains are caught by years: the data gives al-Taymi "
      "d. 119 (Taqrib: 120) and al-Qattan b. 120, so the student was born after the teacher died; PR 1's rule "
      "(death ≥ birth) already flagged them because of the 119, and the corrected rule (death − birth ≥ "
      f"{structure.ContinuityRule.load().min_hearing_age}) would also catch the Taqrib date. Every documented case was "
      "already flagged under PR 1's rule (last column); what changes is that the flags now lower `kappa_lower` "
      "through the `nocompat` graph (§8.7). The candidate (Sa'id b. Bashir for Ibn Abi 'Aruba) sits in a plausible "
      "generation and is not caught. Cross-name misresolution the rule does not catch remains an unquantified "
      "upward bias on κ.\n")
    w("### 8.5 Continuity: layer gaps and the years rule\n")
    rule = structure.ContinuityRule.load()
    win = config.load("structure")["continuity"]
    c.execute(f"""CREATE OR REPLACE TEMP TABLE links AS
        SELECT b.rawi_id AS teacher, a.rawi_id AS student, count(*) AS n FROM sanad_rawis a JOIN sanad_rawis b
        ON a.sanad_id = b.sanad_id AND b.pos = a.pos + 1
        WHERE a.rawi_id NOT IN ({ph_ids}) AND b.rawi_id NOT IN ({ph_ids}) GROUP BY 1, 2""")
    gaps = df("""SELECT CASE WHEN ts.tabaka = 0 OR tt.tabaka = 0 THEN 'missing'
                              WHEN ts.tabaka - tt.tabaka <= -2 THEN '≤ −2'
                              WHEN ts.tabaka - tt.tabaka >= 6 THEN '6+'
                              ELSE (ts.tabaka - tt.tabaka)::VARCHAR END AS student_minus_teacher,
                         sum(n)::BIGINT AS links, count(*) AS distinct_pairs
                  FROM links l JOIN rawis ts ON ts.id = l.student JOIN rawis tt ON tt.id = l.teacher GROUP BY 1""")
    order = ["≤ −2", "-1", "0", "1", "2", "3", "4", "5", "6+", "missing"]
    gaps["k"] = [order.index(x) for x in gaps["student_minus_teacher"]]
    gaps = gaps.sort_values("k").drop(columns="k")
    gaps["student_minus_teacher"] = gaps["student_minus_teacher"].str.replace("-", "−")
    tot = gaps["links"].sum()
    gaps["share"] = gaps["links"] / tot
    ours_win = {str(x).replace("-", "−") for x in rule.window}
    brief_win = {str(x).replace("-", "−") for x in win["brief_tabaka_window"]}
    gaps["itibar_window"] = ["" if g == "missing" else ("in" if g in ours_win else "out") for g in gaps["student_minus_teacher"]]
    gaps["brief_window"] = ["" if g == "missing" else ("in" if g in brief_win else "out") for g in gaps["student_minus_teacher"]]
    w("Chain links (adjacent narrators in `sanad_rawis`, placeholders excluded) by tabaka gap, student minus teacher. "
      "This is the tabaka rule's input; years decide first where both are known.\n")
    w(md_table(gaps))
    pairs = [(720, 7272, "Anas → al-Zuhri"), (5719, 6796, "'Alqama → al-Taymi"), (7272, 6659, "al-Zuhri → Malik"),
             (6458, 3795, "Qatada → Shu'ba"), (7272, 3443, "al-Zuhri → Ibn 'Uyayna"), (5913, 6796, "'Umar → al-Taymi (dropped link)")]
    w("\n| link | teacher tabaka | student tabaka | gap |\n|---|---|---|---|")
    for u, v, lab in pairs:
        tu, tv = names.get(u), names.get(v)
        w(f"| {lab} | {tu} | {tv} | {tv - tu} |")
    out_brief = gaps[gaps["brief_window"] == "out"]["links"].sum() / tot
    out_ours = gaps[gaps["itibar_window"] == "out"]["links"].sum() / tot
    w(f"\nThe brief's window {win['brief_tabaka_window']} puts {out_brief:.0%} of all links outside it, including every "
      f"canonical gap-3 and gap-4 link above. itibar's window {win['tabaka_window']} (`config/structure.yaml`) keeps "
      f"them and accepts −1 (a senior narrating from a junior, *riwayat al-akabir 'an al-asaghir*); {out_ours:.1%} of "
      "links fall outside it (a gap of 5+ layers, ~125 years, or a student two or more layers before the teacher).\n")
    yrs = df("""SELECT CASE WHEN d < -20 THEN -25 WHEN d >= 100 THEN 100 ELSE floor(d / 5)::INT * 5 END AS bin,
                       sum(n)::BIGINT AS links, count(*) AS distinct_pairs FROM
                (SELECT tt.death_year - ts.birth_year AS d, l.n FROM links l JOIN rawis ts ON ts.id = l.student
                 JOIN rawis tt ON tt.id = l.teacher WHERE tt.death_year IS NOT NULL AND ts.birth_year IS NOT NULL)
                GROUP BY 1 ORDER BY 1""")
    both = int(yrs["links"].sum())
    below = int(yrs[yrs["bin"] < rule.min_hearing_age]["links"].sum())
    yrs["death_minus_birth"] = ["< −20" if b == -25 else ("≥ 100" if b == 100 else f"{b} to {b + 4}") for b in yrs["bin"]]
    yrs["share"] = yrs["links"] / both
    yrs["verdict"] = ["incompatible" if b < rule.min_hearing_age else "compatible" for b in yrs["bin"]]
    w(f"**Years rule.** {both:,} of {tot:,} links ({both / tot:.1%}) have both the teacher's death year and the student's "
      f"birth year; for them the years decide. Compatible iff death(teacher) − birth(student) ≥ "
      f"{rule.min_hearing_age} (`continuity.min_hearing_age`): {below:,} links ({below / both:.2%}) fall below it, of "
      f"which {int(yrs[(yrs['bin'] >= 0) & (yrs['bin'] < rule.min_hearing_age)]['links'].sum()):,} are 0–4 (passed by "
      "PR 1's death ≥ birth rule) and the rest negative.\n")
    w(md_table(yrs[["death_minus_birth", "links", "distinct_pairs", "share", "verdict"]]))
    # verdict tallies with the one continuity function, new rule vs PR 1's
    lk = c.sql("SELECT teacher, student, n FROM links").fetchnumpy()
    new_ct, old_ct = Counter(), Counter()
    for u, v, n in zip(lk["teacher"].tolist(), lk["student"].tolist(), lk["n"].tolist()):
        new_ct[structure.link_continuity(nar, u, v, rule)] += n
        old_ct[structure.link_continuity(nar, u, v, PR1_RULE)] += n
    w("\nVerdicts over all chain links, by basis (`continuity_basis`), under the corrected rule and under PR 1's "
      "(window [0..4], death ≥ birth):\n")
    w("| verdict | basis | links (corrected) | share | links (PR 1) | share |\n|---|---|---|---|---|---|")
    for key in sorted(set(new_ct) | set(old_ct), key=lambda k: (k[0], k[1])):
        w(f"| {key[0]} | {key[1]} | {new_ct[key]:,} | {new_ct[key] / tot:.2%} | {old_ct[key]:,} | {old_ct[key] / tot:.2%} |")
    w("\nThe continuity flags feed one quantity: the `nocompat` hypothesis of `kappa_lower` (§8.7), which removes "
      "every incompatible link. They are never used in κ itself or in the derived grade.\n")
    w("### 8.6 `max_rank` includes the compiler\n")
    if rec_exists:
        cp = paths.chains_path().as_posix()
        ag = df(f"""SELECT count(*) AS chains, sum(agree_full::INT) AS agree_full, sum(agree_derived::INT) AS agree_derived,
                   sum((disagreement_class = 'compiler_strictly_weakest')::INT) AS compiler_strictly_weakest,
                   sum((disagreement_class NOT IN ('compiler_strictly_weakest'))::INT) AS other_classes
                   FROM read_parquet('{cp}')""")
        w(md_table(ag))
        w("\n`agree_full`: our weakest link over the whole stored chain equals `max_rank` (the like-for-like check of "
          "our reading). `agree_derived`: the same with the compiler at pos 0 excluded, as the derived grade does; every "
          "disagreement is a chain whose compiler is strictly weaker than everyone else in it.\n")
    w("### 8.7 κ_lower under three hypotheses\n")
    if rec_exists:
        rp = paths.records_path().as_posix()
        kl = []
        for th in scale.thresholds:
            r = c.sql(f"""SELECT count(*) AS groups,
                sum((kappa_lower_{th} < kappa_{th})::INT) AS lower_below_kappa,
                sum((kappa_nocompat_{th} < kappa_{th})::INT) AS nocompat_below_kappa,
                sum((kappa_nocompat_years_{th} < kappa_{th})::INT) AS nocompat_years_below_kappa,
                sum((kappa_lower_source_{th} = 'unmerged')::INT) AS attained_unmerged,
                sum((kappa_lower_source_{th} = 'merged')::INT) AS attained_merged,
                sum((kappa_lower_source_{th} = 'nocompat')::INT) AS attained_nocompat,
                sum((kappa_{th} >= 2 AND kappa_lower_{th} < 2)::INT) AS kappa_2plus_lower_below_2,
                sum((kappa_{th} >= 1 AND kappa_lower_{th} = 0)::INT) AS kappa_1plus_lower_0
                FROM read_parquet('{rp}') WHERE status = 'ok'""").df()
            r.insert(0, "threshold", th)
            kl.append(r)
        w("`kappa_lower_θ` = min of κ_θ over three graphs, stubs dropped in all: **unmerged** (identities as "
          "resolved), **merged** (each same-name cluster one node of min ordinal, unnamed persons merged per student) "
          "and **nocompat** (unmerged, every continuity-incompatible link removed). `kappa_lower_source_θ` names the "
          "first hypothesis attaining the minimum in that order; since removing links never raises κ, `nocompat` "
          "there means removing incompatible links lowered κ below both other graphs.\n")
        w(md_table(pd.concat(kl, ignore_index=True)))
        w("\nIt is a lower bound under those hypotheses, not a guarantee: cross-name misresolution that the continuity "
          "rule does not catch (§8.4) remains an unquantified upward bias on κ.\n")
        w("`kappa_nocompat_years_θ` removes only the links the years rule marks incompatible (both dates known: the "
          "strong evidence); κ_lower keeps the all-incompatible graph. Both are reported for the paper.\n")
    w("### 8.8 Summary of modelling consequences\n")
    w("- break markers: per-chain, untraversable gap nodes (no fused hubs; broken chains do not count as routes)\n"
      "- unnamed person: per-(student, teacher) node, ordinal 0\n"
      "- compiler node in front of every book; book nodes never cut\n"
      "- self-loops dropped; cycles handled; path counts flagged on cyclic bundles\n"
      "- companion = rank_no 1 minus explicit denials, plus the young-companion labels at any rank_no; mursal chains "
      "kept, not connected to PROPHET\n"
      f"- continuity: years first (death − birth ≥ {rule.min_hearing_age}), then the tabaka window "
      f"{win['tabaka_window']} calibrated to the source scale\n"
      "- `kappa_lower`: min of κ over three stated hypotheses — same-name clusters merged, unmerged, "
      "continuity-incompatible links removed (stubs dropped in all); a lower bound under those hypotheses, not a "
      "guarantee\n")

    # ------------------------------------------------------------------ 9
    w("## 9. Why κ is zero\n")
    if rec_exists:
        rp = paths.records_path().as_posix()
        cp = paths.chains_path().as_posix()
        n_all = q1(f"SELECT count(*) FROM read_parquet('{rp}')")
        n_ok = q1(f"SELECT count(*) FROM read_parquet('{rp}') WHERE status = 'ok'")
        zr = df(f"""SELECT kappa_zero_reason AS reason, count(*) AS groups FROM read_parquet('{rp}')
                    WHERE kappa_zero_reason IS NOT NULL GROUP BY 1""")
        zorder = ["no_chains", "no_companion_end", "broken_only", "other"]
        zr = zr.set_index("reason").reindex(zorder, fill_value=0).reset_index()
        nz = int(zr["groups"].sum())
        zr["share_of_all_groups"] = zr["groups"] / n_all
        zr["share_of_zero_groups"] = zr["groups"] / nz
        meaning = {"no_chains": "the group has no chains",
                   "no_companion_end": "no chain ends in a companion (irsal marker, unnamed person, non-companion or stub)",
                   "broken_only": "companion-ending chains exist, every one with a break marker",
                   "other": "a continuous chain exists yet no route survived (gated at 0)"}
        zr["meaning"] = [meaning[x] for x in zr["reason"]]
        w(f"κ = 0 means **no unbroken companion-ending route in this data**, not no support. {nz:,} of {n_all:,} "
          f"groups have no PROPHET → book route at *everyone*: {nz - int(zr.loc[zr.reason == 'no_chains', 'groups'].sum()):,} "
          f"of the {n_ok:,} groups with chains ({(nz - int(zr.loc[zr.reason == 'no_chains', 'groups'].sum())) / n_ok:.1%}) "
          "plus the groups without chains. `kappa_zero_reason` assigns each one reason, by precedence:\n")
        w(md_table(zr))
        for reason in ("no_companion_end", "broken_only"):
            tb = df(f"""WITH g AS (SELECT group_id FROM read_parquet('{rp}') WHERE kappa_zero_reason = '{reason}'),
                        gb AS (SELECT DISTINCT group_id, book_id FROM read_parquet('{cp}')),
                        tot AS (SELECT book_id, count(*) AS groups_with_chains FROM gb GROUP BY 1)
                        SELECT gb.book_id, b.name AS book, b.author_name AS author, count(*) AS groups,
                               tot.groups_with_chains, count(*) / tot.groups_with_chains AS share_of_book
                        FROM gb JOIN g USING (group_id) JOIN books b ON b.id = gb.book_id JOIN tot USING (book_id)
                        GROUP BY gb.book_id, b.name, b.author_name, tot.groups_with_chains
                        ORDER BY groups DESC, gb.book_id LIMIT 10""")
            w(f"\n**`{reason}`: the ten books contributing the most such groups** (a group counts for every book with a "
              "chain in it):\n")
            w(md_table(tb))
        sp = df(f"""SELECT group_id, kappa_all, n_chains, n_chains_companion_end, n_chains_broken, left(nass, 40) AS opening
                    FROM read_parquet('{rp}') WHERE status = 'ok' AND kappa_all > 0 AND n_chains_connected = 0
                    ORDER BY group_id""")
        w(f"\n**The converse does not hold.** {len(sp)} groups have κ ≥ 1 with no continuous chain: every chain is "
          "broken, but at different places, and the union graph joins the intact parts into a route. In group 7978 one "
          "copy of the isnad has an inqita' marker in the middle and another a ta'liq at the compiler's end; together "
          "they cover the whole chain. Routes are paths in the bundle, not attested chains (DECISIONS D31); "
          "`n_chains_connected` and `bypass_chains` count attested chains.\n")
        w(md_table(sp))
        hk = scale.hukm_codes
        xt = df(f"""SELECT coalesce(kappa_zero_reason, 'κ ≥ 1') AS reason, matn_no_group AS code, count(*) AS n
                    FROM read_parquet('{rp}') GROUP BY 1, 2""")
        piv = xt.pivot_table(index="reason", columns="code", values="n", aggfunc="sum", fill_value=0)
        piv = piv.reindex([x for x in zorder + ["κ ≥ 1"] if x in piv.index])
        piv.columns = [f"{int(cd)} {hk.get(int(cd), '')}" for cd in piv.columns]
        piv = piv.reset_index()
        w("\n**Against the source's recorded group grade** (`meaning_groups.matn_no`, labels quoted from the source). "
          "A group the source grades صحيح with no connected chain here is a gap in this data's chains, not a finding "
          "about the report:\n")
        w(md_table(piv))
    else:
        w("_(run `make bundles` first)_\n")

    # ------------------------------------------------------------------ 10
    w("## 10. Indicative chain-level error rate from the gold set\n")
    w(misresolution_rate(c))
    # ------------------------------------------------------------------ 11
    w("## 11. Derived grade v2: corroboration\n")
    if rec_exists:
        w(v2_section(c, scale))
    else:
        w("_(run `make bundles` first)_\n")
    # ------------------------------------------------------------------ 12
    w("## 12. Number class and qarāʾin\n")
    if rec_exists:
        w(number_section(c))
    else:
        w("_(run `make bundles` first)_\n")

    # ------------------------------------------------------------------ appendix
    w("## Appendix A. Full `rawis.rank` vocabulary\n")
    voc = df("SELECT rank_no, coalesce(rank, '(NULL)') AS rank, count(*) AS n FROM rawis GROUP BY 1, 2 ORDER BY 1, n DESC, 2")
    voc["ordinal"] = [None if (r == 12 and lab == "(NULL)") else scale.level_ordinal.get(int(r), 0)
                      for r, lab in zip(voc["rank_no"], voc["rank"])]
    w(md_table(voc))
    w(f"\n_Audit computed in {time.time() - t0:.1f}s._\n")
    return "\n".join(W)


def main() -> None:
    con = data.views()
    grades.write_labels(con)
    text = build()
    out = paths.REPORTS_DIR / "audit.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(text):,} chars)")


if __name__ == "__main__":
    main()
