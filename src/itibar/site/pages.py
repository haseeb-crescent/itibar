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
from markupsafe import Markup, escape

from itibar import paths
from itibar.cli import ZERO_REASONS
from itibar.site.data import receipts
from itibar.site import story as storylib
from itibar.site import view, vocab
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
ROUTE_LISTS = {"common": "Where it begins to spread", "cut": "A bottleneck", "routes": "On a line to the books"}
ROUTE_TEASER = 3
BROWSE_TEASER = 30
NAMED_PEOPLE = 5
RULING_WORDS = {"from_shaykh": "Rated differently when narrating from a particular teacher",
                "region_of_shaykh": "Rated differently when narrating from the people of a particular region",
                "via_student": "Rated differently through particular students",
                "ikhtilat_before": "His memory failed late in life; these students heard him before",
                "ikhtilat_after": "His memory failed late in life; these students heard him after",
                "unobservable": "A condition the chains cannot show (for example, narrating from his book or from memory)"}
EFFECT_WORDS = {"none": "recorded; not applied, since no chain shows the condition",
                "defect:light": "on such links his narration counts as a light weakness",
                "level:3": "on such links he counts as trustworthy", "level:4": "on such links he counts as truthful"}
ROUTE_PAGE = 75
TAG_INDENT = re.compile(r"(?m)^[ \t]+(?=<)")


def split_title(text, longest=64):
    """A long English opening shown as a heading and its continuation: the first clause of at least three
    words becomes the heading; nothing is dropped."""
    if not text or len(text) <= longest:
        return text, ""
    for match in re.finditer(r"[;:,—]\s", text):
        head = text[:match.start()]
        if len(head.split()) >= 3 and len(head) <= longest + 16:
            return head, text[match.start() + 1:].strip()
    return text, ""


PRE = re.compile(r"(<pre\b.*?</pre>|<textarea\b.*?</textarea>)", re.S)
SPACES = re.compile(r"[ \t]*\n[ \t\n]*")
UNQUOTE = re.compile(r'(\s[a-z-]+)="([A-Za-z0-9_.:#/-]+)"')


def minify(page):
    """Smaller HTML with the same rendering: runs of blank lines and indentation collapsed to one newline,
    simple attribute values unquoted (an unquoted value may end in a slash: the HTML tokenizer keeps it in the
    value), <pre> left alone (DECISIONS D105)."""
    parts = PRE.split(page)
    for i in range(0, len(parts), 2):
        parts[i] = UNQUOTE.sub(r"\1=\2", SPACES.sub("\n", parts[i]))
    return "".join(parts)


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
        (folder / "index.html").write_text(minify(TAG_INDENT.sub("", page).replace(view.ROOT, root)), encoding="utf-8")
        return folder

    def report(self, corpus, row, nodes, edges, references, representative, chains, route_narrators):
        gid = row["group_id"]
        names = view.Names(corpus, route_narrators)
        steps = receipts(row, representative)
        cases = corpus.gold[gid]
        opening = row["opening"] or ""
        human = corpus.human.get(gid)
        machine_title = corpus.en("opening", gid, opening)
        title_en = (human or {}).get("title") or (machine_title or {}).get("en")
        text_key = f"{gid}:{representative.get('hadith_id')}"
        machine_text = corpus.en("text", text_key, representative.get("content")) if representative.get("content") else None
        story = payload = outline = why = None
        if row["status"] == "ok":
            story = storylib.build(row, nodes, edges, steps, list(corpus.scale.thresholds))
            if story is not None:
                payload, outline = view.story_payload(story, names, corpus, row, steps, cases)
            why = view.why_grade(row, {c["sanad_id"]: c for c in chains}, steps, names, corpus)
        glance = view.glance(row, names, story, cases, steps, why)
        representative_book = view.book_view(corpus, representative["book_id"]) if representative.get("book_id") else None
        title_head, title_rest = split_title(title_en)
        title = title_head or opening or f"Report {gid}"
        folder = self.page(
            f"reports/{gid}", "report.html", title, report=row, opening=opening, title_en=title_en,
            title_head=title_head, title_rest=title_rest, has_story=payload is not None,
            title_source="human" if human and human.get("title") else ("machine" if machine_title else None),
            human=human, machine_text=machine_text, representative=representative,
            representative_book=representative_book, head=view.header(corpus, row, references), glance=glance,
            outline=outline, why=why, groups=view.book_groups(corpus, references),
            spec=view.specialist(row, steps, names, cases) if row["status"] == "ok" else None,
            gold_cases=cases, critics=critics_view(corpus.verdicts.get(gid, []), names),
            thresholds=[(k, vocab.threshold(k)) for k in corpus.scale.thresholds],
            chain_books=sorted({c["book_id"] for c in chains}, key=lambda b: (b not in view.MAJOR, view.MAJOR.index(b) if b in view.MAJOR else b)),
            number_class=vocab.number_class(row.get("number_class")))
        if row["status"] == "ok":
            save_json(folder / "graph.json.gz", graph_data(corpus, row, nodes, edges, route_narrators, steps))
            save_json(folder / "record.json.gz", view.record_json(row))
            save_json(folder / "chains.json.gz", chain_data(corpus, chains, route_narrators, names))
            if payload is not None:
                save_json(folder / "story.json.gz", payload)

    def narrator(self, corpus, rid, membership, census, catalog, routes=None):
        person = corpus.people[rid]
        role_lists = {"common": [r["group_id"] for r in membership if r["common_link"]],
                      "cut": [r["group_id"] for r in membership if r["cut_vertex"]],
                      "routes": [r["group_id"] for r in membership]}
        role_counts = {"common": census.get("groups_common_link", len(role_lists["common"])),
                       "cut": census.get("groups_cut_all_roles", len(role_lists["cut"])),
                       "routes": census.get("groups_on_route", len(role_lists["routes"]))}
        if role_counts != {key: len(gids) for key, gids in role_lists.items()}:
            raise ValueError(f"Narrator {rid}: census counts and route flags disagree")
        for key in role_lists:   # the widest-spread reports first
            role_lists[key].sort(key=lambda g: (-(catalog[g]["n_chains"] or 0), g))
        en, short, ar = corpus.person(rid)
        tier = corpus.tiers.get(rid)
        rulings = []
        for ruling in corpus.rulings[rid]:
            citation = re.search(r"\]\((https?://[^)]+)\)", ruling.get("citation", ""))
            rulings.append({**ruling, "link": citation[1] if citation else "", "words": RULING_WORDS.get(ruling["kind"], ruling["kind"]),
                            "effect_words": EFFECT_WORDS.get(ruling["effect"], ruling["effect"])})
        more = {key: (len(gids) - ROUTE_TEASER + ROUTE_PAGE - 1) // ROUTE_PAGE
                for key, gids in role_lists.items() if len(gids) > ROUTE_TEASER}
        names = view.Names(corpus, routes or {})

        def linked(rows, key):
            return [{"html": names.html(f"r{row[key]}"), "reports": row["reports"]} for row in rows[:NAMED_PEOPLE]]

        sayings = [{"critic": corpus.critic(row["alem_id"]), "critic_ar": corpus.critics.get(row["alem_id"], {}).get("known"),
                    "text": row["qawl"]} for row in corpus.sayings(rid)]
        places = [corpus.place(p) or p for p in corpus.places(rid)]
        lived = [" ".join(p.split()) for p in re.split(r"[،,]", person.get("iqama") or "") if p.strip()]
        lived = [corpus.place(p) or p for p in lived]
        died_at = " ".join((person.get("death_place") or "").split())
        died_at = corpus.place(died_at) or died_at
        folder = self.page(
            f"narrators/{rid}", "narrator.html", short or en or ar, person=person, en=en, short=short, ar=ar,
            level=vocab.level(person.get("rank_no")), generation=vocab.generation(person.get("tabaka")),
            died=vocab.died(person.get("death_year"), person.get("death_year_raw")),
            born=person.get("birth_year"), lived=lived, died_at=died_at, places=places,
            tier=tier, tier_words=vocab.tadlis_tier(tier), tier_source=corpus.mudallis_sources.get(tier), rulings=rulings,
            roles=ROUTE_LISTS, role_counts=role_counts, teaser=ROUTE_TEASER, catalog=catalog, lists=role_lists, more=more,
            teachers=linked(corpus.teachers[rid], "teacher"), students=linked(corpus.students[rid], "student"),
            n_teachers=len(corpus.teachers[rid]), n_students=len(corpus.students[rid]), sayings=sayings)
        for key, gids in role_lists.items():
            for i, start in enumerate(range(ROUTE_TEASER, len(gids), ROUTE_PAGE), 1):
                save_json(folder / "reports" / f"{key}-{i}.json.gz",
                          [[gid, catalog[gid]["title_en"], None if catalog[gid]["title_en"] else (catalog[gid]["opening"] or "")[:90]]
                           for gid in gids[start:start + ROUTE_PAGE]])

    def browse(self, corpus, catalog, ranks, topics, census):
        """Browse by topic, by collection, by notable narrator, and the famous reports (DECISIONS D97)."""
        def card(gid):
            row = catalog[gid]
            grade = row["rule_v2_ibn_hajar"]
            terms = view.grade_terms(grade, row["code_v2_ibn_hajar"]) if grade else None
            return {"gid": gid, "title": row["title_en"], "opening": row["opening"], "k": row["kappa_all"],
                    "chains": row["n_chains"], "grade": terms[0] if terms else None,
                    "cls": (vocab.number_class(row["number_class"]) or {}).get("term")}

        def entries(gids):
            return [[g, catalog[g]["title_en"], (catalog[g]["opening"] or "")[:90], catalog[g]["kappa_all"],
                     (view.grade_terms(catalog[g]["rule_v2_ibn_hajar"], catalog[g]["code_v2_ibn_hajar"])[0]
                      if catalog[g]["rule_v2_ibn_hajar"] else None)] for g in gids]

        def paged(folder, gids):
            for i, start in enumerate(range(BROWSE_TEASER, len(gids), ROUTE_PAGE), 1):
                save_json(folder / "list" / f"{i}.json.gz", entries(gids[start:start + ROUTE_PAGE]))
            return (len(gids) - BROWSE_TEASER + ROUTE_PAGE - 1) // ROUTE_PAGE if len(gids) > BROWSE_TEASER else 0

        by_rank = lambda gids: sorted((g for g in gids if g in catalog), key=lambda g: ranks[g])
        tree = corpus.topic_tree()
        roots = []
        for node in tree:
            node["en"] = (corpus.en("topic", node["id"], node["name"]) or {}).get("en")
            if node["level"] == 1:
                node["children"] = []
                roots.append(node)
            elif roots:
                roots[-1]["children"].append(node)
        for node in tree:
            gids = by_rank(node["groups"])
            node["count"] = len(gids)
            if node["level"] == 2 and gids:
                folder = self.dist / "browse" / "topics" / str(node["id"])
                parent = next(r for r in roots if node in r["children"])
                pages = paged(folder, gids)
                self.page(f"browse/topics/{node['id']}", "browse_list.html", node["en"] or node["name"],
                          heading=node["en"], heading_ar=node["name"], kind="topic", parent=parent,
                          cards=[card(g) for g in gids[:BROWSE_TEASER]], total=len(gids), pages=pages)
        refs = corpus.book_reports()
        books = []
        for book_id, rows in sorted(refs.items()):
            rows = [r for r in rows if r[1] in catalog]
            if not rows:
                continue
            en, title, ar, author = corpus.book(book_id)
            info = {"id": book_id, "en": en, "title": title or view.SHORT_BOOK.get(book_id), "ar": ar, "author": author,
                    "count": len(rows), "tasnif": corpus.books[book_id]["tasnif_no"]}
            books.append(info)
            folder = self.dist / "browse" / "collections" / str(book_id)
            gids = [g for _, g in rows]
            pages = paged(folder, gids)
            numbers = {g: n for n, g in rows}
            self.page(f"browse/collections/{book_id}", "browse_list.html", info["title"] or ar, heading=info["title"],
                      heading_ar=ar, subtitle=info["en"], kind="collection",
                      cards=[{**card(g), "number": numbers[g]} for g in gids[:BROWSE_TEASER]], total=len(gids), pages=pages)
        groups = []
        for key, label, glossary_id, test in view.BOOK_GROUPS:
            members = [b for b in books if test(corpus.books[b["id"]]) and not any(b in g["books"] for g in groups)]
            if members:
                groups.append({"label": label, "term": glossary_id, "books": members})
        notable = sorted((r for r in census.values() if r.get("groups_common_link")), key=lambda r: (-r["groups_common_link"], r["rawi_id"]))[:60]
        names = view.Names(corpus, {r["rawi_id"]: True for r in notable})
        narrators = [{"html": names.html(f"r{r['rawi_id']}"), "cl": r["groups_common_link"], "died": vocab.died(r["death_year"]),
                      "level": vocab.level(r["taqrib_level"])} for r in notable]
        famous_ids = list(dict.fromkeys([c["group_id"] for c in corpus.cases if c["group_id"] in catalog]))
        widest = sorted((g for g in catalog if catalog[g]["companions"]), key=lambda g: (-catalog[g]["companions"], g))[:24]
        self.page("browse", "browse.html", "Browse", roots=roots, groups=groups, narrators=narrators,
                  famous=[card(g) for g in famous_ids], widest=[card(g) for g in widest])

    def shared(self, corpus):
        """Data every page's scripts read once: the glossary and the book titles."""
        g = vocab.glossary()
        save_json(self.dist / "assets" / "glossary.json", {
            "terms": {t["id"]: {"term": t["term"], "arabic": t.get("arabic"), "short": t["short"]} for t in g["terms"]},
            "levels": {n: {k: v[k] for k in ("name", "badge", "arabic", "meaning")} for n, v in g["levels"].items()},
            "generations": {n: {"name": v["name"]} for n, v in g["generations"].items()},
        })
        save_json(self.dist / "assets" / "books.json", {
            b: [title or en, ar] for b, (en, title, ar, _) in ((b, corpus.book(b)) for b in corpus.books)})
        self.page("glossary", "glossary.html", "Glossary", terms=g["terms"], levels=g["levels"],
                  generations=g["generations"], tiers=g["tadlis_tiers"])

    def corpus_pages(self, corpus, catalog, reports_dir, figures_dir, downloadable):
        example = next((c for c in corpus.cases if c["id"] == "innama-al-amal" and c["group_id"] in catalog), None)
        walk = None
        if example:
            row = catalog[example["group_id"]]
            names = view.Names(corpus, corpus.routes())
            line = (example.get("expect", {}).get("cut_vertices_eq") or {}).get("all") or []
            kept = re.search(r"\((\d+)\)", example["scoped"].get("scope chains (kept)", ""))
            walk = {"row": row, "line": [names.html(n) for n in line], "last": names.html(line[-1]) if line else None,
                    "kept": int(kept[1]) if kept else None,
                    "last_died": names.died(line[-1]) if line else None, "case": example,
                    "grade": view.grade_html(row["rule_v2_ibn_hajar"], row["code_v2_ibn_hajar"])}
        self.page("", "home.html", "How hadith reached the books", walk=walk,
                  total=len(catalog), chained=sum(r["status"] == "ok" for r in catalog.values()))
        self.page("search", "search.html", "Search")
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


WORD_GLOSS = {"haddathana": "told us", "akhbarana": "informed us", "anbaana": "informed us", "samitu": "heard",
              "qiraa": "read to", "an": "from", "anna": "that", "qala": "said", "kitaba": "wrote to", "tahwil": "switch"}


def chain_data(corpus, chains, route_narrators, names):
    """Compact display rows in the source's book-to-companion order, with English names and ratings."""
    from itibar.words import WORD_CLASSES
    people, words, grade_labels = {}, {None: 0}, {None: 0}
    rows = []
    for chain in chains:
        links = []
        for i, person in enumerate(chain["people"] or []):
            rid, word = person["rawi"], person["word"]
            display_id = (0 if chain["unnamed_companion"] and i == len(chain["people"]) - 1 else rid)
            if display_id not in people:
                if display_id == 0:
                    people[0] = ["an unnamed companion", "رجل من أصحاب النبي ﷺ", 0, 1]
                else:
                    p = names.person(f"r{rid}")
                    level = corpus.people.get(rid, {}).get("rank_no") or 0
                    if rid in corpus.scale.placeholders:
                        level = -1
                    people[display_id] = [p["short"] or p["en"] or "", p["ar"], int(rid in route_narrators), level]
            gloss = WORD_GLOSS.get(WORD_CLASSES.get(person.get("norm") or ""), "")
            links.extend((display_id, words.setdefault(word and f"{word}|{gloss}", len(words))))
        grade = chain["recorded_grade"] or corpus.scale.hukm_codes.get(chain["matn_no"])
        rows.append([chain["sanad_id"], chain["book_id"], chain["no_inbook"],
                     grade_labels.setdefault(grade, len(grade_labels)), links, chain.get("code_v2_ibn_hajar")])
    return {"people": people, "words": list(words), "grades": list(grade_labels), "rows": rows}


CRITICS = {"al-Tabarani": "al-Ṭabarānī", "al-Bayhaqi": "al-Bayhaqī", "al-Tirmidhi": "al-Tirmidhī", "al-Hakim": "al-Ḥākim",
           "Abu Nuaym": "Abū Nuʿaym", "al-Bazzar": "al-Bazzār", "al-Bazzar (Kashf al-Astar)": "al-Bazzār",
           "al-Khatib": "al-Khaṭīb", "al-Nasai": "al-Nasāʾī", "al-Daraqutni": "al-Dāraquṭnī", "Abu Dawud": "Abū Dāwūd",
           "Ibn Khuzayma": "Ibn Khuzayma", "Ibn Hibban": "Ibn Ḥibbān", "al-Bukhari": "al-Bukhārī"}
GRADE_WORDS = {"حسن": "ḥasan", "صحيح": "ṣaḥīḥ", "غريب": "gharīb", "ضعيف": "ḍaʿīf", "مرسل": "mursal", "منكر": "munkar",
               "مشهور": "mashhūr", "sahih_isnad": "ṣaḥīḥ al-isnād", "sahih": "ṣaḥīḥ", "mursal": "mursal", "mashhur": "mashhūr"}
COLLECTION = {"البخاري": "al-Bukhārī", "مسلم": "Muslim"}
CRITIC_SHOWN = 6


def critics_view(verdicts, names):
    """The critics' own remarks (PR 7's out/verdicts.parquet): an English summary by claim type, the Arabic
    quote and the citation; at most CRITIC_SHOWN per report, the rest counted. PR 7's scores stay in its report."""
    out = []
    for v in verdicts:
        summary = critic_summary(v, names)
        if summary and not any(o["summary"] == summary and o["quote"] == v.get("quote") for o in out):
            out.append({"summary": summary, "quote": v.get("quote"), "citation": v.get("citation"), "url": v.get("url")})
    return {"shown": out[:CRITIC_SHOWN], "more": max(0, len(out) - CRITIC_SHOWN)} if out else None


def critic_summary(v, names):
    critic = CRITICS.get(v.get("critic"), v.get("critic") or "A critic")
    kind = v.get("claim_type")
    grade = v.get("grade")
    words = " ".join(GRADE_WORDS.get(w, w) for w in str(grade).split()) if grade else None
    clause = COLLECTION.get((v.get("clause") or "").strip())

    def who(node, text):
        if node and str(node).startswith("r"):
            return str(names.html(node))
        return text or "one narrator"
    if kind == "verdict" and words:
        return Markup(f"{critic} grades it <i>{escape(words)}</i>.")
    if kind == "sahih_attribution":
        return Markup(f"{critic} says {clause or 'a Ṣaḥīḥ'} recorded it in the Ṣaḥīḥ.")
    if kind == "shart":
        return Markup(f"{critic} says its chain meets the conditions of {clause or 'the Ṣaḥīḥayn'}.")
    if kind == "tafarrud":
        y = who(v.get("y_id"), v.get("y_text"))
        x = v.get("x_id") and who(v.get("x_id"), v.get("x_text"))
        return Markup(f"{critic} says it is known only through {y}" + (f", from {x}" if x else "") + ".")
    if kind == "gharib":
        return Markup(f"{critic} calls it <i>gharīb</i> (carried by one narrator) through {who(v.get('x_id'), v.get('x_text'))}.")
    if kind == "wafi_al_bab":
        return Markup(f"{critic} names other companions’ reports on the same subject.")
    if kind == "khata":
        return Markup(f"{critic} says a narrator erred in it.")
    if kind == "hearing":
        return Markup(f"{critic} remarks on whether a narrator heard it from his teacher.")
    if kind == "bukhari_view":
        return Markup(f"{critic} reports al-Bukhārī’s view of it.")
    if kind == "comparison":
        return Markup(f"{critic} compares two versions of it.")
    return Markup(f"{critic} remarks on it.")
