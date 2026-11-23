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
DOWNLOADS = {
    "records": "Group-level results and receipts",
    "chains": "Recorded chains, chain codes and comparisons",
    "narrators": "Narrator-level census",
    "nodes": "Bundle nodes and on-route flags",
    "edges": "Bundle edges, chain occurrences and words",
    "words": "Aligned transmission words by chain position",
    "matn_tokens": "Normalized matn token IDs by hadith",
    "matn_vocab": "The token vocabulary and IDF",
    "unnamed_tops": "Unnamed people at the companion end of chains",
    "verdicts": "Critics’ remarks and bundle comparisons",
}


def downloads(corpus, dest):
    dest.mkdir()
    files = {}
    for out in sorted(corpus.out.glob("*.parquet")):
        if out.stem in ("nodes", "edges"):
            continue
        target = dest / out.name
        shutil.copyfile(out, target)
        files[out.stem] = target
    for kind in ("nodes", "edges"):
        target = dest / f"{kind}.parquet"
        columns = "* EXCLUDE (bucket)" if "bucket" in corpus.con.table(kind).columns else "*"
        corpus.con.sql(f"SELECT {columns} FROM {kind}").write_parquet(str(target), compression="zstd")
        files[kind] = target
    ordered = [key for key in DOWNLOADS if key in files] + sorted(files.keys() - DOWNLOADS.keys())
    return [(files[key].name, f"{files[key].stat().st_size / 1_000_000:.2f} MB",
             DOWNLOADS.get(key, "Pipeline output")) for key in ordered]


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
            for lo in sorted({gid // 1000 * 1000 for gid in catalog}):
                for row, nodes, edges, references, representative, chains in corpus.batch(lo, lo + 999):
                    pages.report(corpus, row, nodes, edges, references, representative, chains, routes)
                    gid = row["group_id"]
                    search.report(gid, row["opening"], representative["content"], references)
            for rid, membership in routes.items():
                pages.narrator(corpus, rid, membership, census.get(rid, {}), catalog)
                person = corpus.people[rid]
                search.narrator(rid, person["nickname"], person["name"])
            search.write(staging / "search" / "index", corpus.books)
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
