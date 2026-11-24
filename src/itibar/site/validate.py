"""Check the publish tree, including local file and fragment links."""
from __future__ import annotations

import gzip
import json
import os
import posixpath
import re
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

SITE_LIMIT = 1_000_000_000
HTML_LIMIT = 192 * 1024
GRAPH_LIMIT = 192 * 1024
REPORT_LIMIT = 256 * 1024


READING_PAGES = ("reports/", "narrators/", "browse/")   # method, residue, figures, downloads document the data
REPORT_SECTIONS = ("glance", "tree", "grade", "books", "chains", "specialists")
REPORT_DATA = ("record.json.gz", "chains.json.gz", "graph.json.gz")   # story.json.gz where a route reaches the Prophet
# Internal identifiers the interface must never show (DECISIONS D100), and verdicts in the site's own voice.
INTERNAL = re.compile(r"sahih_li|hasan_li|_v2|\bv[12]\b|ordinal|hadith-kg scale|kappa_|mutabaa_|gharib_|mutawatir_count|"
                      r"\bdaif\b|not_repairable|\bnone recorded\b|@root/", re.I)
VERDICT = re.compile(r"\b(this|the) (hadith|report) is (weak|sound|authentic|fabricated|sahih|da.if)\b", re.I)


class PageLinks(HTMLParser):
    """Links and anchors, and the visible text outside code, pre and scripts (with where #specialists starts)."""

    def __init__(self):
        super().__init__()
        self.anchors = set()
        self.links = set()
        self.text = []
        self.skip = 0
        self.specialists_at = None

    def handle_starttag(self, tag, attrs):
        if tag in ("code", "pre", "script", "style", "title"):
            self.skip += 1
        for name, value in attrs:
            if value and name == "id":
                self.anchors.add(value)
                if value == "specialists" and self.specialists_at is None:
                    self.specialists_at = len(self.text)
            elif value and name in ("href", "src", "action"):
                self.links.add(value)

    def handle_endtag(self, tag):
        if tag in ("code", "pre", "script", "style", "title") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.text.append(data)


def page_text_problems(name, parser):
    """The interface's words: no internal identifiers, no verdict of the site's own, κ only for specialists."""
    problems = []
    text = " ".join(parser.text)
    for match in INTERNAL.finditer(text):
        problems.append(f"{name}: internal identifier in page text: {match.group(0)!r}")
    for match in VERDICT.finditer(text):
        problems.append(f"{name}: verdict in the site's own words: {match.group(0)!r}")
    if name.startswith("reports/"):
        before = " ".join(parser.text[:parser.specialists_at])
        if "κ" in before:
            problems.append(f"{name}: κ outside the specialists' section")
    return problems[:3]


def story_problems(name, story):
    problems = []
    n = len(story["items"])
    seen = [i for row in story["rows"] for i in row["i"]]
    if sorted(seen) != list(range(n)):
        problems.append(f"{name}: rows do not place every item exactly once")
    for a, b, *_ in story["links"]:
        if not (0 <= a < n and 0 <= b < n):
            problems.append(f"{name}: link to a missing item")
    for key, lines in story["lines"].items():
        if any(not (0 <= i < n) for line in lines for i in line):
            problems.append(f"{name}: line through a missing item ({key})")
    for item in story["items"]:
        if item.get("p") and item["p"] not in story["people"]:
            problems.append(f"{name}: item names an undescribed person {item['p']}")
    return problems[:3]


def check(dest):
    dest = dest.resolve()
    if not (dest / "index.html").is_file():
        raise ValueError(f"{dest}: no built site")
    files = {}
    for folder, _, names in os.walk(dest):
        for name in names:
            path = dest / folder / name
            files[path.relative_to(dest).as_posix()] = path.stat().st_size
    html = {name: size for name, size in files.items() if name.endswith(".html")}
    graph = {name: size for name, size in files.items() if name.endswith("/graph.json.gz")}
    # What a report page loads before any click: its HTML and the story view (the full graph loads on demand).
    reports = {name: size + files.get(posixpath.join(posixpath.dirname(name), "story.json.gz"), 0)
               for name, size in html.items() if name.startswith("reports/")}
    total = sum(files.values())
    problems = []
    if total > SITE_LIMIT:
        problems.append(f"Publish tree is {total:,} bytes, above {SITE_LIMIT:,}")
    for pages, limit in ((html, HTML_LIMIT), (graph, GRAPH_LIMIT), (reports, REPORT_LIMIT)):
        problems.extend(f"{name} is {size:,} bytes, above {limit:,}" for name, size in pages.items() if size > limit)
    must_exist = ("index.html", "search/index.html", "method/index.html", "figures/index.html",
                  "gold/index.html", "residue/index.html", "downloads/index.html", "glossary/index.html",
                  "browse/index.html", "assets/glossary.json", "assets/books.json")
    problems.extend(f"Missing page {path}" for path in must_exist if path not in files)

    @lru_cache(maxsize=512)
    def chain_ids(path):
        return {str(row[0]) for row in json.loads(gzip.decompress((dest / path).read_bytes()))["rows"]}

    anchors, fragments = {}, []
    for name in html:
        parser = PageLinks()
        parser.feed((dest / name).read_text(encoding="utf-8"))
        anchors[name] = parser.anchors
        if name.startswith(READING_PAGES) or name in ("index.html", "search/index.html", "glossary/index.html", "gold/index.html"):
            problems.extend(page_text_problems(name, parser))
        folder = posixpath.dirname(name)
        if name.startswith("reports/") and posixpath.join(folder, "graph.json.gz") in files:
            problems.extend(f"{name}: missing section #{section}" for section in REPORT_SECTIONS
                            if section not in parser.anchors)
            problems.extend(f"{name}: missing {data}" for data in REPORT_DATA
                            if posixpath.join(folder, data) not in files)
            story = posixpath.join(folder, "story.json.gz")
            if story in files:
                problems.extend(story_problems(story, json.loads(gzip.decompress((dest / story).read_bytes()))))
        for link in parser.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            path = unquote(url.path)
            target = name if not path else posixpath.normpath(posixpath.join(posixpath.dirname(name), path))
            if target not in files:
                target = posixpath.normpath(posixpath.join(target, "index.html"))
            if target not in files:
                problems.append(f"{name} → {link} (missing file)")
            elif url.fragment and target in html:
                fragments.append((name, target, unquote(url.fragment)))

    for name, target, fragment in fragments:
        if fragment in anchors[target]:
            continue
        if fragment.startswith("chain-"):
            chain_path = posixpath.join(posixpath.dirname(target), "chains.json.gz")
            if chain_path in files and fragment[6:] in chain_ids(chain_path):
                continue
        problems.append(f"{name} → {target}#{fragment} (missing anchor)")

    for name in files:
        if name.startswith(("narrators/", "browse/")) and name.endswith(".json.gz"):
            for gid, *_ in json.loads(gzip.decompress((dest / name).read_bytes())):
                if f"reports/{gid}/index.html" not in html:
                    problems.append(f"{name} → report {gid} (missing page)")
    for name in graph:
        for asset in ("chains.json.gz", "record.json.gz"):
            if posixpath.join(posixpath.dirname(name), asset) not in files:
                problems.append(f"{name} → {asset} (missing report data)")
    if problems:
        raise ValueError(f"{len(problems)} site check failures:\n" + "\n".join(problems[:24]))

    def largest(items):
        path, size = max(items.items(), key=lambda item: item[1], default=(None, 0))
        return {"path": path, "bytes": size}

    return {"published_bytes": total, "files": len(files), "html_pages": len(html),
            "largest_html": largest(html), "largest_graph": largest(graph), "largest_initial_report": largest(reports),
            "by_directory": {part: sum(size for name, size in files.items()
                                      if name.startswith(part + "/"))
                             for part in ("reports", "narrators", "search", "downloads", "assets")}}
