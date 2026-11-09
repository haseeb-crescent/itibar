"""`make narrators`: the narrator-level census (out/narrators.parquet) and the
common-link report (reports/common_links.md, figures/fig4_cl_death_years.*).

Per narrator, over every meaning group's bundle: groups on path; groups where he
is a cut vertex at `all` and at `thiqa_up`; groups where he is a common link;
groups where he lies on a route that bypasses the group's common links; and, for
a mudallis, the share of his incoming links (as the student) that are mu'an'an.
Collection classes for the distributions: groups with a chain in al-Bukhari or
Muslim (in_sahihayn), with a chain in a tasnif_no = 1 book (in_sahih_class), all.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from itibar import config, data, paths

SANITY = {"al-Zuhri": 7272, "Qatada": 6458, "al-A'mash": 3629, "Shu'ba": 3795, "Malik": 6659}


def build(con=None) -> pd.DataFrame:
    con = con or data.views()
    nodes = (paths.bundles_dir() / "nodes").as_posix()
    edges = (paths.bundles_dir() / "edges").as_posix()
    rec = paths.records_path().as_posix()
    d = duckdb.connect()
    d.execute(f"CREATE VIEW n AS SELECT * FROM read_parquet('{nodes}/**/*.parquet', hive_partitioning = true)")
    d.execute(f"CREATE VIEW e AS SELECT * FROM read_parquet('{edges}/**/*.parquet', hive_partitioning = true)")
    d.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{rec}')")
    rawis = con.sql("SELECT id, name, nickname, death_year, birth_year, tabaka, rank_no, has_tadlis, is_stub FROM rawis").df()
    d.register("rawis", rawis)
    q = """
    WITH nn AS (SELECT group_id, node, rawi_id, on_path, cut_vertex, common_link, in_bypass, pcl_k2, compiler_role FROM n
                WHERE kind = 'narrator'),
         thq AS (SELECT group_id, unnest(cut_vertices_thiqa_up) AS node FROM r WHERE status = 'ok'),
         agg AS (SELECT rawi_id,
                        count(DISTINCT group_id) FILTER (WHERE on_path) AS groups_on_path,
                        count(DISTINCT group_id) FILTER (WHERE cut_vertex) AS groups_cut_all,
                        count(DISTINCT group_id) FILTER (WHERE common_link) AS groups_common_link,
                        count(DISTINCT group_id) FILTER (WHERE pcl_k2) AS groups_pcl_k2,
                        count(DISTINCT group_id) FILTER (WHERE on_path AND compiler_role) AS groups_compiler_role,
                        count(DISTINCT group_id) FILTER (WHERE in_bypass) AS groups_in_bypass,
                        count(DISTINCT group_id) AS groups_in_bundle
                 FROM nn GROUP BY 1),
         cth AS (SELECT CAST(substr(node, 2) AS BIGINT) AS rawi_id, count(DISTINCT group_id) AS groups_cut_thiqa_up
                 FROM thq WHERE node LIKE 'r%' GROUP BY 1),
         inc AS (SELECT CAST(substr(v, 2) AS BIGINT) AS rawi_id,
                        count(*) AS incoming_links,
                        count(*) FILTER (WHERE muanan_mudallis = 'yes') AS incoming_muanan,
                        count(*) FILTER (WHERE muanan_mudallis IN ('yes', 'no')) AS incoming_word_known
                 FROM e WHERE v LIKE 'r%' AND u LIKE 'r%' GROUP BY 1)
    SELECT a.rawi_id, w.name, w.nickname, w.death_year, w.birth_year, w.tabaka, w.rank_no AS taqrib_level,
           w.has_tadlis::BOOLEAN AS mudallis, w.is_stub::BOOLEAN AS stub,
           a.groups_in_bundle, a.groups_on_path, a.groups_cut_all, coalesce(c.groups_cut_thiqa_up, 0) AS groups_cut_thiqa_up,
           a.groups_common_link, a.groups_pcl_k2, a.groups_in_bypass, a.groups_compiler_role,
           coalesce(i.incoming_links, 0) AS incoming_links, coalesce(i.incoming_muanan, 0) AS incoming_muanan,
           coalesce(i.incoming_word_known, 0) AS incoming_word_known,
           CASE WHEN w.has_tadlis = 1 AND coalesce(i.incoming_word_known, 0) > 0
                THEN i.incoming_muanan / i.incoming_word_known END AS muanan_share
    FROM agg a LEFT JOIN rawis w ON w.id = a.rawi_id LEFT JOIN cth c USING (rawi_id) LEFT JOIN inc i USING (rawi_id)
    ORDER BY a.groups_common_link DESC, a.groups_on_path DESC, a.rawi_id"""
    df = d.sql(q).df()
    out = paths.OUT_DIR / "narrators.parquet"
    df.to_parquet(out, index=False)
    return df


def cl_above(rawi_ids: list[int], con=None) -> pd.DataFrame:
    """For each narrator: in groups where he is a partial common link (k = 2) but not
    a common link, which common links sit above him (one row per (narrator, CL))."""
    con = con or data.views()
    nodes = (paths.bundles_dir() / "nodes").as_posix()
    d = duckdb.connect()
    d.execute(f"CREATE VIEW n AS SELECT * FROM read_parquet('{nodes}/**/*.parquet', hive_partitioning = true)")
    d.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{paths.records_path().as_posix()}')")
    ids = ",".join(str(int(x)) for x in rawi_ids)
    df = d.sql(f"""WITH p AS (SELECT group_id, rawi_id FROM n WHERE kind = 'narrator' AND pcl_k2 AND NOT common_link
                                AND rawi_id IN ({ids})),
                        c AS (SELECT group_id, unnest(common_links) AS cl FROM r WHERE status = 'ok')
                   SELECT p.rawi_id, c.cl, count(DISTINCT p.group_id) AS groups
                   FROM p JOIN c USING (group_id) GROUP BY 1, 2 ORDER BY 1, 3 DESC""").df()
    names = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
    df["cl_name"] = [names.get(int(x[1:])) if str(x).startswith("r") else x for x in df["cl"]]
    return df


def cl_pairs(con=None) -> pd.DataFrame:
    """One row per (group, common link) with the group's collection class."""
    con = con or data.views()
    r = pd.read_parquet(paths.records_path(), columns=["group_id", "status", "common_links", "in_sahihayn",
                                                       "in_sahih_class"])
    r = r[r["status"] == "ok"].explode("common_links").dropna(subset=["common_links"])
    r = r[r["common_links"].str.startswith("r")]
    r["rawi_id"] = r["common_links"].str[1:].astype(int)
    rawis = con.sql("SELECT id AS rawi_id, death_year, tabaka, rank_no FROM rawis").df()
    return r.merge(rawis, on="rawi_id", how="left")


def report(df: pd.DataFrame | None = None, con=None) -> str:
    con = con or data.views()
    df = df if df is not None else pd.read_parquet(paths.OUT_DIR / "narrators.parquet")
    pairs = cl_pairs(con)
    comp = {int(x) for x in config.load("grades")["companion"]["rank_no"]}
    L = ["# The common-link census", "",
         "Generated by `make narrators` from the bundles. A common link is a partial common link (k = 2 qualifying",
         "branches, README) with no partial common link above it; a group can have several. `out/narrators.parquet`",
         "holds one row per narrator. Collection classes: **Ṣaḥīḥayn** = groups with a chain in al-Bukhārī or",
         "Muslim; **ṣaḥīḥ class** = groups with a chain in a `books.tasnif_no = 1` book; **all** = every group.", ""]
    n_groups = int(pd.read_parquet(paths.records_path(), columns=["status"]).eq("ok").sum().iloc[0])
    L.append(f"- groups with chains: {n_groups:,}; (group, common link) pairs: {len(pairs):,}; "
             f"narrators who are a common link somewhere: {int((df['groups_common_link'] > 0).sum()):,}")
    cls_comp = pairs["rank_no"].isin(comp).mean() if len(pairs) else 0
    L.append(f"- share of common-link pairs at the companion level (Taqrīb level 1): {cls_comp:.1%}")
    L.append("")

    def top(d: pd.DataFrame, n: int = 30) -> list[str]:
        rows = ["| # | narrator | d. | tabaka | level | groups as common link | on path | cut (all) | cut (thiqa+) | in a bypass |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(d.head(n).itertuples(index=False), 1):
            dy = "" if pd.isna(r.death_year) else int(r.death_year)
            rows.append(f"| {i} | {r.nickname} (r{r.rawi_id}) | {dy} | {r.tabaka} | {r.taqrib_level} | "
                        f"{r.groups_common_link:,} | {r.groups_on_path:,} | {r.groups_cut_all:,} | "
                        f"{r.groups_cut_thiqa_up:,} | {r.groups_in_bypass:,} |")
        return rows

    d_all = df.sort_values(["groups_common_link", "groups_on_path"], ascending=False)
    L += ["## Top 30 common links", ""] + top(d_all) + [""]
    d_nc = d_all[~d_all["taqrib_level"].isin(comp)]
    L += ["## Top 30 common links below the companion layer", "",
          "Companions are common links whenever several students carry a report from them; the Western",
          "common-link debate concerns the generations after them, so this table drops Taqrīb level 1.", ""]
    L += top(d_nc) + [""]
    # sanity check
    L += ["## Sanity check", "",
          "The brief expects al-Zuhrī, Qatāda, al-Aʿmash, Shuʿba and Mālik near the top.", "",
          "| narrator | rawi id | rank among all common links | rank below the companion layer | groups as common link | groups as partial common link (k=2) | groups on path |",
          "|---|---|---|---|---|---|---|"]
    rank_all = {int(r): i for i, r in enumerate(d_all["rawi_id"], 1)}
    rank_nc = {int(r): i for i, r in enumerate(d_nc["rawi_id"], 1)}
    for nm, rid in SANITY.items():
        row = df[df["rawi_id"] == rid]
        if row.empty:
            L.append(f"| {nm} | r{rid} | — | — | 0 | 0 | 0 |")
            continue
        r = row.iloc[0]
        L.append(f"| {nm} ({r['nickname']}) | r{rid} | {rank_all.get(rid)} | {rank_nc.get(rid)} | "
                 f"{int(r['groups_common_link']):,} | {int(r['groups_pcl_k2']):,} | {int(r['groups_on_path']):,} |")
    L.append("")
    above = cl_above(list(SANITY.values()), con)
    L += ["Why the ranks fall where they do: a common link is the *uppermost* partial common link on its routes,",
          "so a narrator who branches widely loses the label wherever someone above him also branches. For each",
          "narrator, the groups where he is a partial common link but not a common link, and the common links",
          "above him there (top 4):", ""]
    for nm, rid in SANITY.items():
        a = above[above["rawi_id"] == rid].head(4)
        tot = int(df.loc[df["rawi_id"] == rid, "groups_pcl_k2"].sum() - df.loc[df["rawi_id"] == rid, "groups_common_link"].sum())
        L.append(f"- {nm}: {tot:,} such groups; above him: "
                 + "; ".join(f"{r.cl_name} ({r.cl}) {r.groups:,}" for r in a.itertuples(index=False)))
    L.append("")
    mrow = df[df["rawi_id"] == SANITY["Malik"]]
    if not mrow.empty:
        m = mrow.iloc[0]
        L += [(f"Mālik is the exception: he is a partial common link in only {int(m['groups_pcl_k2']):,} of his "
               f"{int(m['groups_on_path']):,} on-path groups, because in {int(m['groups_compiler_role']):,} of them "
               "his node is also"),
              "the compiler of the *Muwaṭṭaʾ* (his own book sits in the group), and D14 makes a narrator acting as a",
              "compiler a terminal: never a single strand, never a partial common link. The same holds for other",
              ("compiler-narrators (ʿAbd al-Razzāq: compiler role in "
               f"{int(df.loc[df['rawi_id'] == 4533, 'groups_compiler_role'].sum()):,} of "
               f"{int(df.loc[df['rawi_id'] == 4533, 'groups_on_path'].sum()):,} groups). Counting a compiler's narrator-role"),
              "branches is the alternative recorded in DECISIONS.md D51; it would change partial common links across",
              "the corpus and is left for a later structure version.", ""]
    # distributions
    L += ["## Death years and tabaka of common links, by collection class", "",
          "Counted over (group, common link) pairs; death years AH as recorded in `rawis.death_year`.", ""]
    classes = {"Ṣaḥīḥayn": pairs[pairs["in_sahihayn"]], "ṣaḥīḥ class": pairs[pairs["in_sahih_class"]], "all": pairs}
    bins = list(range(0, 401, 25))
    L += ["| death year AH | " + " | ".join(classes) + " |", "|---|" + "---|" * len(classes)]
    for lo in bins[:-1]:
        hi = lo + 25
        L.append(f"| {lo}–{hi - 1} | " + " | ".join(
            f"{((c['death_year'] >= lo) & (c['death_year'] < hi)).sum():,} ({((c['death_year'] >= lo) & (c['death_year'] < hi)).mean():.1%})"
            for c in classes.values()) + " |")
    L.append("| unknown | " + " | ".join(f"{c['death_year'].isna().sum():,} ({c['death_year'].isna().mean():.1%})"
                                       for c in classes.values()) + " |")
    L.append("")
    L.append("| median death year (known) | " + " | ".join(
        f"{c['death_year'].dropna().median():.0f}" for c in classes.values()) + " |")
    L.append("|---|" + "---|" * len(classes))
    L.append("| share dying 100–199 AH | " + " | ".join(
        f"{((c['death_year'] >= 100) & (c['death_year'] < 200)).sum() / max(1, c['death_year'].notna().sum()):.1%}"
        for c in classes.values()) + " |")
    L.append("")
    L += ["| tabaka | " + " | ".join(classes) + " |", "|---|" + "---|" * len(classes)]
    for t in sorted(int(x) for x in pairs["tabaka"].dropna().unique()):
        L.append(f"| {t} | " + " | ".join(f"{(c['tabaka'] == t).sum():,} ({(c['tabaka'] == t).mean():.1%})"
                                         for c in classes.values()) + " |")
    L.append("")
    mud = df[df["mudallis"] & (df["incoming_word_known"] > 0)].sort_values("groups_on_path", ascending=False)
    L += ["## Mudallisūn: share of incoming links that are muʿanʿan", "",
          "For narrators the source flags with tadlīs (`rawis.has_tadlis`): of his links as the student whose",
          "transmission word was recovered, the share using ʿan / anna / qāla (config `continuity.muanan_words`).", "",
          "| narrator | d. | groups on path | incoming links (word known) | muʿanʿan | share |", "|---|---|---|---|---|---|"]
    for r in mud.head(20).itertuples(index=False):
        dy = "" if pd.isna(r.death_year) else int(r.death_year)
        L.append(f"| {r.nickname} (r{r.rawi_id}) | {dy} | {r.groups_on_path:,} | {r.incoming_word_known:,} | "
                 f"{r.incoming_muanan:,} | {r.muanan_share:.1%} |")
    L.append("")
    text = "\n".join(L)
    (paths.REPORTS_DIR / "common_links.md").write_text(text, encoding="utf-8")
    _fig4(classes)
    return text


def _fig4(classes: dict[str, pd.DataFrame]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    from itibar import figures as F
    edges = np.arange(0, 401, 10)
    mids = edges[:-1] + 5
    rows = []
    fig, ax = plt.subplots(figsize=(9, 3.8))
    colors = [F.BLUE[700], F.BLUE[450], F.BLUE[250]]
    for (name, c), col in zip(classes.items(), colors):
        dy = c["death_year"].dropna().to_numpy()
        h, _ = np.histogram(dy, bins=edges)
        share = h / max(1, h.sum())
        ax.plot(mids, share, color=col, lw=2, drawstyle="steps-mid", label=f"{name} (n = {len(dy):,})")
        rows += [{"class": name, "death_year_from": int(a), "death_year_to": int(a) + 9, "pairs": int(n),
                  "share": float(s)} for a, n, s in zip(edges[:-1], h, share)]
    ax.axvspan(100, 200, color=F.GRID, alpha=0.5, lw=0)
    ax.text(150, ax.get_ylim()[1] * 0.95, "2nd century AH", ha="center", va="top", fontsize=8, color=F.INK2)
    ax.set_xlim(0, 400)
    ax.set_xlabel("death year of the common link (AH, 10-year bins)")
    ax.set_ylabel("share of (group, common link) pairs")
    ax.grid(True, axis="y", color=F.GRID, lw=0.6)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("When common links died, by collection class")
    fig.text(0.01, 0.01, "Common link: partial common link (k = 2) with none above it. Companions included. "
             "Source: hadith-kg (CC-BY-4.0), itibar bundles.", fontsize=7, color=F.MUTED)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.9, bottom=0.2)
    out = paths.FIGURES_DIR
    for ext in ("png", "svg"):
        fig.savefig(out / f"fig4_cl_death_years.{ext}", dpi=200)
    plt.close(fig)
    pd.DataFrame(rows).to_csv(out / "fig4_cl_death_years.csv", index=False)


def main() -> None:
    df = build()
    report(df)
    print(f"{len(df):,} narrators -> {paths.OUT_DIR / 'narrators.parquet'}; report -> {paths.REPORTS_DIR / 'common_links.md'}")


if __name__ == "__main__":
    main()
