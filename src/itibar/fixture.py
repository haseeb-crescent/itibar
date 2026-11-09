"""`make fixture`: a sampled, committable copy of the Parquet tables so CI never
needs the 1.6 GB source. Contains the gold-set groups, the sibling groups of the
gold entries that assert a cross-group shahid (`classical_claim_holds_with_siblings`),
the ten most-narrated groups (the companion-band gate), a seeded random sample, and
a few groups without chains. Narrators are every narrator in the sampled chains plus
all members of their same-name clusters (so kappa_lower is reproduced exactly);
topics are the sampled groups' leaves and their ancestors. matn_idf.parquet carries
the full corpus's idf for the sampled matns, so shahid overlaps equal the full run's.
Other groups' sibling witnesses are not in the fixture, so on those groups v2 can
differ from the full run where a cross-group witness decided it (README)."""

from __future__ import annotations

import shutil

import pyarrow.parquet as pq

from itibar import config, data, gold, paths

N_RANDOM = 300
SEED = 20261108


def build(out_dir=None) -> dict:
    out_dir = out_dir or (paths.FIXTURE_DIR / "parquet")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    con = data.views()
    gold_ids = gold.gold_group_ids()
    from itibar import siblings
    want = sorted({int(e["group_id"]) for e in gold.entries() if "classical_claim_holds_with_siblings" in e})
    sib = siblings.sibling_groups(con, want)
    sib_ids = sorted({s for g in want for s in sib.get(g, ())})
    top = [r[0] for r in con.sql("SELECT id FROM meaning_groups WHERE id > 0 ORDER BY repeat_qty DESC LIMIT 10").fetchall()]
    rnd = [r[0] for r in con.sql(
        f"""SELECT id FROM meaning_groups WHERE id IN (SELECT DISTINCT group_id FROM hadiths WHERE group_id IS NOT NULL)
            AND id NOT IN ({','.join(map(str, gold_ids + top))}) ORDER BY hash(id + {SEED}) LIMIT {N_RANDOM}""").fetchall()]
    rnd = [g for g in rnd if g not in sib_ids]
    empty = [r[0] for r in con.sql(
        "SELECT id FROM meaning_groups g WHERE NOT EXISTS (SELECT 1 FROM hadiths h WHERE h.group_id = g.id) ORDER BY id LIMIT 3"
    ).fetchall()]
    groups = sorted(set(gold_ids + sib_ids + top + rnd + empty))
    con.execute("CREATE TEMP TABLE fx_groups AS SELECT unnest(?::BIGINT[]) AS id", [groups])
    con.execute("CREATE TEMP TABLE fx_hadiths AS SELECT id FROM hadiths WHERE group_id IN (SELECT id FROM fx_groups)")
    con.execute("CREATE TEMP TABLE fx_sanads AS SELECT id FROM sanads WHERE hadith_id IN (SELECT id FROM fx_hadiths)")
    con.execute("""CREATE TEMP TABLE fx_rawis AS
        WITH used AS (SELECT DISTINCT rawi_id AS id FROM sanad_rawis WHERE sanad_id IN (SELECT id FROM fx_sanads)
                      UNION SELECT DISTINCT rawi_id FROM hadith_rawis WHERE hadith_id IN (SELECT id FROM fx_hadiths)
                            AND rawi_id IS NOT NULL),
             names AS (SELECT DISTINCT r.name, r.nickname FROM rawis r JOIN used USING (id) WHERE r.is_stub = 0)
        SELECT id FROM used UNION
        SELECT r.id FROM rawis r JOIN names n ON n.name = r.name AND n.nickname = r.nickname WHERE r.is_stub = 0""")
    queries = {
        "meta": "SELECT * FROM meta",
        "books": "SELECT * FROM books",
        "book_compilers": "SELECT * FROM book_compilers",
        "meaning_groups": "SELECT * FROM meaning_groups WHERE id IN (SELECT id FROM fx_groups)",
        "tarafs": "SELECT * FROM tarafs WHERE group_id IN (SELECT id FROM fx_groups)",
        "hadiths": "SELECT * FROM hadiths WHERE id IN (SELECT id FROM fx_hadiths)",
        "hadith_rawis": "SELECT * FROM hadith_rawis WHERE hadith_id IN (SELECT id FROM fx_hadiths)",
        "sanads": "SELECT * FROM sanads WHERE id IN (SELECT id FROM fx_sanads)",
        "sanad_rawis": "SELECT * FROM sanad_rawis WHERE sanad_id IN (SELECT id FROM fx_sanads)",
        "rawis": "SELECT * FROM rawis WHERE id IN (SELECT id FROM fx_rawis)",
        # the topic leaves of the sampled groups and every ancestor (nested set), for pools and the census
        "topics": """SELECT DISTINCT t.* FROM topics t JOIN topics leaf
                     ON leaf.group_id IN (SELECT id FROM fx_groups) AND leaf.tree_id = t.tree_id
                     AND t.lft <= leaf.lft AND t.rgt >= leaf.rgt""",
    }
    sizes = {}
    for name, sql in queries.items():
        t = con.sql(sql + " ORDER BY ALL" if name not in ("meta",) else sql).to_arrow_table()
        p = out_dir / f"{name}.parquet"
        pq.write_table(t, p, compression="zstd", compression_level=19)
        sizes[name] = (t.num_rows, p.stat().st_size)
    from itibar import matn
    hids = [r[0] for r in con.sql("SELECT id FROM fx_hadiths").fetchall()]
    n_idf = matn.write_fixture_idf(hids, out_dir)
    sizes["matn_idf"] = (n_idf, (out_dir / "matn_idf.parquet").stat().st_size)
    total = sum(s for _, s in sizes.values())
    (out_dir / "README.md").write_text(
        "Sampled fixture of hadith-kg.db (CC-BY-4.0, emadjumaah/hadith-kg @ "
        f"{config.load('source')['huggingface']['revision'][:12]}), generated by `make fixture`.\n"
        f"{len(groups)} meaning groups: {len(gold_ids)} gold, {len(sib_ids)} siblings of gold groups with a cross-group "
        f"shahid, 10 most-narrated, {len(rnd)} random (seed {SEED}), {len(empty)} without hadith; matn_idf.parquet: the "
        "full corpus's idf for the sampled matns. Do not edit by hand.\n", encoding="utf-8")
    return {"groups": len(groups), "bytes": total, "tables": sizes}


def main() -> None:
    r = build()
    for k, (n, b) in r["tables"].items():
        print(f"  {k:16s} {n:>9,} rows {b / 1e6:6.2f} MB")
    print(f"{r['groups']} groups, {r['bytes'] / 1e6:.1f} MB total")


if __name__ == "__main__":
    main()
