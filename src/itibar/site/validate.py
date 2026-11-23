"""Check the publish tree, including local file and fragment links."""
from __future__ import annotations

import gzip
import json
import os
import posixpath
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

SITE_LIMIT = 1_000_000_000
HTML_LIMIT = 192 * 1024
GRAPH_LIMIT = 192 * 1024
REPORT_LIMIT = 256 * 1024


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = set()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value and name == "id":
                self.anchors.add(value)
            elif value and name in ("href", "src", "action"):
                self.links.add(value)


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
    reports = {name: size + files[posixpath.join(posixpath.dirname(name), "graph.json.gz")]
               for name, size in html.items()
               if name.startswith("reports/") and posixpath.join(posixpath.dirname(name), "graph.json.gz") in graph}
    total = sum(files.values())
    problems = []
    if total > SITE_LIMIT:
        problems.append(f"Publish tree is {total:,} bytes, above {SITE_LIMIT:,}")
    for pages, limit in ((html, HTML_LIMIT), (graph, GRAPH_LIMIT), (reports, REPORT_LIMIT)):
        problems.extend(f"{name} is {size:,} bytes, above {limit:,}" for name, size in pages.items() if size > limit)
    must_exist = ("index.html", "search/index.html", "method/index.html", "figures/index.html",
                  "gold/index.html", "residue/index.html", "downloads/index.html")
    problems.extend(f"Missing page {path}" for path in must_exist if path not in files)

    @lru_cache(maxsize=512)
    def chain_ids(path):
        return {str(row[0]) for row in json.loads(gzip.decompress((dest / path).read_bytes()))["rows"]}

    anchors, fragments = {}, []
    for name in html:
        parser = PageLinks()
        parser.feed((dest / name).read_text(encoding="utf-8"))
        anchors[name] = parser.anchors
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
        if name.startswith("narrators/") and name.endswith(".json.gz"):
            for gid, _ in json.loads(gzip.decompress((dest / name).read_bytes())):
                if f"reports/{gid}/index.html" not in html:
                    problems.append(f"{name} → report {gid} (missing page)")
    for name in graph:
        for asset in ("chains.json.gz", "receipts.json.gz"):
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
