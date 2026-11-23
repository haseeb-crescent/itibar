"""Page builders and adapters for the written corpus reports."""
from __future__ import annotations

import gzip
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup

from itibar import paths
from itibar.cli import ZERO_REASONS
from itibar.site.data import receipts
from itibar.site.graph import graph_data


REPOSITORY = "https://github.com/haseeb-crescent/itibar"
THRESHOLDS = {
    "all": ("Everyone", "All narrator levels"),
    "above_matruk": ("Above matrūk", "Levels 1–9"),
    "saduq_up": ("Ṣadūq and above", "Levels 1–4"),
    "thiqa_up": ("Thiqa and above", "Levels 1–3"),
}
RULESETS = {"ibn_hajar": "Ibn Ḥajar", "ibn_al_salah": "Ibn al-Ṣalāḥ"}
NUMBER_CLASSES = {
    "gharib_mutlaq": "Gharīb muṭlaq", "gharib_nisbi": "Gharīb nisbī",
    "aziz": "ʿAzīz", "mashhur": "Mashhūr", "mutawatir_count": "Mutawātir by count",
}
DIVERGENCE = {
    "mutabaa_tamma": "Mutābaʿa tāmma", "mutabaa_qasira": "Mutābaʿa qāṣira",
    "shahid": "Shāhid", "wasl": "Waṣl",
}
FIGURES = [
    ("fig1_kappa", "Independent routes by narrator threshold",
     "Survival curves and the share of reports by κ, from everyone to thiqa and above.",
     ["fig1_kappa_survival", "fig1_kappa_share"]),
    ("fig2_width_by_tabaka", "Width by generation",
     "The number of on-route narrators per Taqrīb layer in the Ṣaḥīḥayn and in other collections.",
     ["fig2_width_by_tabaka"]),
    ("fig3_lists_bins", "The classical mutawātir lists",
     "Matches to the lists of al-Kattānī and al-Suyūṭī, binned by their narrator-threshold results.",
     ["fig3_lists_bins"]),
    ("fig4_cl_death_years", "When the common links died",
     "Death-year distributions of common links by collection class.", ["fig4_cl_death_years"]),
    ("fig5_chapter_census", "Transmission across the topic tree",
     "Number class, single routes, and corroboration by chapter.", ["fig5_chapter_census"]),
    ("fig6_residue", "Where the derived and recorded grades differ",
     "The disagreements by mechanical cause and direction.", ["fig6_residue"]),
]
ROUTE_LISTS = {"common": "Common link", "cut": "Cut vertex", "routes": "On a route"}
ROUTE_TEASER = 8
ROUTE_PAGE = 75
TAG_INDENT = re.compile(r"(?m)^[ \t]+(?=<)")


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    path.write_bytes(gzip.compress(content, compresslevel=6, mtime=0) if path.suffix == ".gz" else content)


def death_date(year, original=None):
    if original and str(original) != str(year):
        return f"{year} AH · {original}" if year is not None and year > 0 else str(original)
    return f"{year} AH" if year is not None and year > 0 else "Year unrecorded"


def show_arabic(value):
    return isinstance(value, str) and bool(re.search(r"[\u0600-\u06ff]", value))


def clean_url(value):
    if value and urlsplit(value).scheme in ("https", "http"):
        return value
    return ""


def markdown(text, origin, root):
    renderer = MarkdownIt("commonmark", {"html": False}).enable("table")

    def heading_open(renderer, tokens, i, options, env):
        title = tokens[i + 1].content
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        tokens[i].attrSet("id", slug)
        return renderer.renderToken(tokens, i, options, env)

    def direction(renderer, tokens, i, options, env):
        tokens[i].attrSet("dir", "auto")
        return renderer.renderToken(tokens, i, options, env)

    def link_open(renderer, tokens, i, options, env):
        token = tokens[i]
        href = token.attrGet("href")
        if href and not href.startswith(("#", "https://", "http://", "mailto:")):
            path, _, fragment = href.partition("#")
            special = {"DATA_LICENSE.md": "downloads/", "reports/gold.md": "gold/",
                       "reports/residue.md": "residue/"}
            token.attrSet("href", (root + special[path] if path in special else f"{REPOSITORY}/blob/main/{origin / path}")
                          + (f"#{fragment}" if fragment else ""))
        return renderer.renderToken(tokens, i, options, env)

    renderer.add_render_rule("heading_open", heading_open)
    renderer.add_render_rule("blockquote_open", direction)
    renderer.add_render_rule("td_open", direction)
    renderer.add_render_rule("link_open", link_open)
    return Markup(renderer.render(text))


class Pages:
    def __init__(self, dist: Path):
        self.dist = dist
        self.templates = Environment(
            loader=FileSystemLoader(Path(__file__).parent / "templates"),
            autoescape=select_autoescape(), trim_blocks=True, lstrip_blocks=True,
        )
        self.templates.globals.update(repo=REPOSITORY, arabic=show_arabic, number=lambda n: f"{n:,}",
                                      clean_url=clean_url, death_date=death_date, thresholds=THRESHOLDS)

    def page(self, route, template, title, **context):
        folder = self.dist / route
        root = "../" * len(PurePosixPath(route).parts) or "./"
        folder.mkdir(parents=True, exist_ok=True)
        page = self.templates.get_template(template).render(root=root, title=title, **context)
        (folder / "index.html").write_text(TAG_INDENT.sub("", page), encoding="utf-8")
        return folder

    def report(self, corpus, row, nodes, edges, references, representative, chains, route_narrators):
        gid = row["group_id"]
        books = defaultdict(list)
        for ref in references:
            books[ref["book_id"]].append(ref["no_inbook"])
        on_path = row["status"] == "ok"
        cuts, links = [], []
        for field, prefix, dest in (("cut_vertices", "cut", cuts), ("common_links", "cl", links)):
            for node, year, raw in zip(row.get(field) or (), row.get(f"{prefix}_death_year") or (),
                                      row.get(f"{prefix}_death_year_raw") or (), strict=True):
                rid = int(node[1:]) if node.startswith("r") else None
                dest.append({"name": corpus.node(node), "rid": rid if rid in route_narrators else None,
                             "date": death_date(year, raw)})

        steps = receipts(row, representative)
        rs = []
        if on_path:
            by_sanad = {chain["sanad_id"]: chain for chain in chains}
            for key, label in RULESETS.items():
                sid = row[f"best_sanad_v2_{key}"]
                witnesses = next((s["data"].get("witnesses", []) for s in steps[key] if s["check"] == "witnesses"), [])
                rs.append({
                    "key": key, "label": label, "code": row[f"code_v2_{key}"], "rule": row[f"rule_v2_{key}"],
                    "sanad": sid, "defects": by_sanad[sid][f"defects_v2_{key}"],
                    "witnesses": [{**w, "label": DIVERGENCE.get(w["divergence"], w["divergence"])} for w in witnesses],
                })
        opening = row["opening"] or f"Report {gid}"
        folder = self.page(f"reports/{gid}", "report.html", opening, report=row, opening=opening,
                           representative=representative, references=[(corpus.books[k], v) for k, v in books.items()],
                           representative_book=corpus.books.get(representative.get("book_id")),
                           chain_books=[corpus.books[k] for k in sorted({chain["book_id"] for chain in chains})],
                           grades=corpus.scale.hukm_codes, rulesets=rs, cut=cuts, common=links,
                           number_class=NUMBER_CLASSES.get(row.get("number_class"), "Unassigned"),
                           reason=ZERO_REASONS.get(row.get("kappa_zero_reason")),
                           gold_cases=corpus.gold[gid], verdicts=corpus.verdicts.get(gid, []))
        if on_path:
            save_json(folder / "graph.json.gz", graph_data(corpus, row, nodes, edges, route_narrators, steps))
            save_json(folder / "receipts.json.gz", steps)
            save_json(folder / "chains.json.gz", chain_data(corpus, chains, route_narrators))

    def narrator(self, corpus, rid, membership, census, catalog):
        person = corpus.people[rid]
        role_lists = {"common": [r["group_id"] for r in membership if r["common_link"]],
                      "cut": [r["group_id"] for r in membership if r["cut_vertex"]],
                      "routes": [r["group_id"] for r in membership]}
        role_counts = {"common": census.get("groups_common_link", len(role_lists["common"])),
                       "cut": census.get("groups_cut_all_roles", len(role_lists["cut"])),
                       "routes": census.get("groups_on_route", len(role_lists["routes"]))}
        if role_counts != {key: len(gids) for key, gids in role_lists.items()}:
            raise ValueError(f"Narrator {rid}: census counts and route flags disagree")
        name = corpus.name(rid)
        tier = corpus.tiers.get(rid)
        rulings = []
        for ruling in corpus.rulings[rid]:
            citation = re.search(r"\]\((https?://[^)]+)\)", ruling.get("citation", ""))
            rulings.append({**ruling, "link": citation[1] if citation else ""})
        more = {key: (len(gids) - ROUTE_TEASER + ROUTE_PAGE - 1) // ROUTE_PAGE
                for key, gids in role_lists.items() if len(gids) > ROUTE_TEASER}
        folder = self.page(f"narrators/{rid}", "narrator.html", name, person=person, name=name, tier=tier,
                           tier_source=corpus.mudallis_sources.get(tier), rulings=rulings,
                           roles=ROUTE_LISTS, role_counts=role_counts, teaser=ROUTE_TEASER,
                           catalog=catalog, lists=role_lists, more=more)
        for key, gids in role_lists.items():
            for i, start in enumerate(range(ROUTE_TEASER, len(gids), ROUTE_PAGE), 1):
                save_json(folder / "reports" / f"{key}-{i}.json.gz",
                          [[gid, catalog[gid]["opening"]] for gid in gids[start:start + ROUTE_PAGE]])

    def corpus_pages(self, corpus, catalog, reports_dir, figures_dir, downloadable):
        example = next((c for c in corpus.cases if c["id"] == "innama-al-amal" and c["group_id"] in catalog), None)
        self.page("", "home.html", "The hadith transmission atlas", example=example,
                  total=len(catalog), chained=sum(r["status"] == "ok" for r in catalog.values()))
        self.page("search", "search.html", "Search the corpus")
        readme = (paths.ROOT / "README.md").read_text(encoding="utf-8")
        definitions = readme[readme.index("## Data and provenance"):readme.index("## Outputs")]
        self.page("method", "prose.html", "Method",
                  content=markdown(definitions, PurePosixPath("."), "../"))
        self.page("residue", "prose.html", "The residue",
                  content=markdown((reports_dir / "residue.md").read_text(encoding="utf-8").split("\n", 1)[1],
                                   PurePosixPath("reports"), "../"))
        self.page("gold", "gold.html", "The gold set", entries=[c for c in corpus.cases if c["group_id"] in catalog])
        self.page("figures", "figures.html", "Corpus figures", figures=FIGURES)
        self.page("downloads", "downloads.html", "Downloads", files=downloadable, figures=FIGURES)
        for stem, _, _, csvs in FIGURES:
            for name in [f"{stem}.svg", f"{stem}.png", *(f"{csv}.csv" for csv in csvs)]:
                shutil.copy2(figures_dir / name, self.dist / "downloads" / name)
        for name in ("DATA_LICENSE.md", "LICENSE"):
            shutil.copy2(paths.ROOT / name, self.dist / "downloads" / name)


def chain_data(corpus, chains, route_narrators):
    """Compact display rows in the source's book-to-companion order."""
    people, words, grade_labels = {}, {None: 0}, {None: 0}
    rows = []
    for chain in chains:
        links = []
        for i, person in enumerate(chain["people"] or []):
            rid, word = person["rawi"], person["word"]
            display_id = (0 if chain["unnamed_companion"] and i == len(chain["people"]) - 1 else rid)
            if display_id not in people:
                people[display_id] = ["رجل من أصحاب النبي ﷺ" if display_id == 0 else corpus.name(rid),
                                      int(display_id in route_narrators)]
            links.extend((display_id, words.setdefault(word, len(words))))
        grade = chain["recorded_grade"] or corpus.scale.hukm_codes.get(chain["matn_no"])
        rows.append([chain["sanad_id"], chain["book_id"], chain["no_inbook"],
                     grade_labels.setdefault(grade, len(grade_labels)), links])
    return {"people": people, "words": list(words), "grades": list(grade_labels), "rows": rows}
