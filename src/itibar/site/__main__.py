"""Generate site/dist from existing itibar outputs, or check a generated tree."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from itibar import paths
from itibar.site.data import Corpus
from itibar.site.pages import Pages
from itibar.site.search import SearchIndex
from itibar.site.validate import check

ASSETS = paths.ROOT / "site" / "assets"
DIST = ASSETS.parent / "dist"
# Intermediate inputs of the shāhid overlap, rebuilt by `make matn`; not published (DECISIONS D105).
INTERMEDIATE = ("matn_tokens", "matn_vocab")
DOWNLOADS = {
    "records": "Group-level results and receipts",
    "chains": "Recorded chains, chain codes and comparisons",
    "narrators": "Narrator-level census",
    "narrator_links": "Teacher-student pairs, counted in reports and chains",
    "nodes": "Bundle nodes and on-route flags",
    "edges": "Bundle edges, chain occurrences and words",
    "words": "Aligned transmission words by chain position",
    "matn_tokens": "Normalized matn token IDs by hadith",
    "matn_vocab": "The token vocabulary and IDF",
    "unnamed_tops": "Unnamed people at the companion end of chains",
    "verdicts": "Critics’ remarks and bundle comparisons",
}


def recompress(con, select, target):
    """The published Parquet: the same rows and columns, zstd at level 19 (D105)."""
    con.execute(f"COPY ({select}) TO '{target.as_posix()}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19)")


def downloads(corpus, dest):
    dest.mkdir()
    files = {}
    for out in sorted(corpus.out.glob("*.parquet")):
        if out.stem in ("nodes", "edges") or out.stem in INTERMEDIATE:
            continue
        target = dest / out.name
        recompress(corpus.con, f"SELECT * FROM read_parquet('{out.as_posix()}')", target)
        files[out.stem] = target
    for kind in ("nodes", "edges"):
        target = dest / f"{kind}.parquet"
        columns = "* EXCLUDE (bucket)" if "bucket" in corpus.con.table(kind).columns else "*"
        recompress(corpus.con, f"SELECT {columns} FROM {kind}", target)
        files[kind] = target
    ordered = [key for key in DOWNLOADS if key in files] + sorted(files.keys() - DOWNLOADS.keys())
    return [(files[key].name, f"{files[key].stat().st_size / 1_000_000:.2f} MB",
             DOWNLOADS.get(key, "Pipeline output")) for key in ordered]


def search_record(row, references, topics):
    """The result card: report id, English title, Arabic opening, major collections, lines, grade, class, topics."""
    from itibar.site.view import MAJOR
    books = {ref["book_id"] for ref in references}
    grade = row["rule_v2_ibn_hajar"] if row["rule_v2_ibn_hajar"] in RULES else (
        f"code{row['code_v2_ibn_hajar']}" if row["code_v2_ibn_hajar"] is not None else None)
    opening = row["opening"] or ""
    return [row["group_id"], row["title_en"], opening[:OPENING_CHARS] + ("…" if len(opening) > OPENING_CHARS else ""),
            [b for b in MAJOR if b in books], row["kappa_all"], row["kappa_thiqa_up"], grade, row["number_class"],
            topics, len(books), row["companions"]]


from itibar.site.view import SHORT_BOOK  # noqa: E402

RULES = ("sahih_li_dhatihi", "sahih_li_ghayrihi", "hasan_li_dhatihi", "hasan_li_ghayrihi", "daif")
OPENING_CHARS = 180


def search_books(corpus):
    out = {}
    for book_id, book in corpus.books.items():
        en, title, ar, author = corpus.book(book_id)
        out[book_id] = {**book, "english": [x for x in (en, title, author) if x], "title": title or en}
    return out


def search_meta(corpus):
    from itibar.site import vocab
    grades = {rule: vocab.grade_rule(rule) for rule in RULES}
    grades.update({f"code{c}": vocab.grade_code(c) for c in range(6)})
    return {"grades": {k: [v["term"], v["arabic"], v["gloss"], v["family"]] for k, v in grades.items()},
            "classes": {k: [v["term"], v["gloss"]] for k, v in vocab.glossary()["number_classes"].items()},
            "topics": [[t["id"], (corpus.en("topic", t["id"], t["name"]) or {}).get("en"), t["name"]] for t in corpus.topic_roots()],
            "books": dict(SHORT_BOOK)}


def build(dest=DIST, *, source=paths.PARQUET_DIR, out=paths.OUT_DIR,
          reports=paths.REPORTS_DIR, figures=paths.FIGURES_DIR, groups=None):
    dest = dest.resolve()
    if dest.exists() and any(dest.iterdir()) and not (dest / ".nojekyll").is_file():
        raise ValueError(f"{dest} contains files and is not an itibar build directory")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".site-build-", dir=dest.parent) as tmp:
        staging = Path(tmp) / "publish"
        staging.mkdir()
        shutil.copytree(ASSETS, staging / "assets")
        (staging / ".nojekyll").touch()
        corpus = Corpus(source, out, reports, groups)
        try:
            catalog = corpus.catalog()
            if not catalog or (groups and set(groups) - catalog.keys()):
                raise ValueError("The requested groups are missing from records.parquet")
            routes = corpus.routes()
            census = corpus.census() if groups is None else {}
            for case in corpus.cases:
                case["companion_page"] = case.get("scope", {}).get("companion") in routes
            pages, search = Pages(staging), SearchIndex()
            pages.shared(corpus)
            ranks = {gid: n for n, gid in enumerate(sorted(catalog, key=lambda g: (-(catalog[g]["n_chains"] or 0), g)))}
            topics = corpus.top_topics()
            variants = corpus.variant_openings()
            for lo in sorted({gid // 1000 * 1000 for gid in catalog}):
                for row, nodes, edges, references, representative, chains in corpus.batch(lo, lo + 999):
                    pages.report(corpus, row, nodes, edges, references, representative, chains, routes)
                    gid = row["group_id"]
                    human = corpus.human.get(gid) or {}
                    text = corpus.en("text", f"{gid}:{representative.get('hadith_id')}", representative.get("content"))
                    search.report(ranks[gid], gid, search_record(catalog[gid], references, topics.get(gid, [])), references,
                                  opening=row["opening"], variants=variants.get(gid, ()), text=representative.get("content"),
                                  english=[catalog[gid]["title_mt"] or "", human.get("title") or ""],
                                  english_body=[(text or {}).get("en", ""), human.get("text") or ""])
            order = sorted(routes, key=lambda r: (-len(routes[r]), r))
            for n, rid in enumerate(order):
                membership = routes[rid]
                pages.narrator(corpus, rid, membership, census.get(rid, {}), catalog, routes)
                person = corpus.people[rid]
                en, short, ar = corpus.person(rid)
                search.narrator(n, rid, [rid, short or en, ar, person.get("death_year"),
                                         sum(1 for m in membership if m["common_link"]), len(membership)],
                                (person["nickname"], person["name"]), (en or "", short or ""))
            search.write(staging / "search" / "index", search_books(corpus), search_meta(corpus))
            pages.browse(corpus, catalog, ranks, topics, census)
            pages.corpus_pages(corpus, catalog, reports, figures, downloads(corpus, staging / "downloads"))
        finally:
            corpus.con.close()

        if dest.exists():
            dest.rename(Path(tmp) / "previous")
        try:
            staging.rename(dest)
        except OSError:
            previous = Path(tmp) / "previous"
            if previous.exists():
                previous.rename(dest)
            raise
    return {"reports": len(catalog), "narrators": len(routes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DIST, help="directory for the static site")
    parser.add_argument("--groups", type=int, nargs="+", help="only build the selected reports for browser checks")
    parser.add_argument("--check", action="store_true", help="check links and size budgets in a built site")
    args = parser.parse_args()
    summary = check(args.dest) if args.check else build(args.dest, groups=args.groups)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
