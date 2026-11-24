"""HadeethEnc's human English translations, fetched once and joined to the meaning groups.

HadeethEnc (https://hadeethenc.com) permits republishing its translations unmodified, with the
publisher and source named and the version stated (its "Terms and Policies"; DECISIONS D101).
`fetch` walks the public API v1 politely and writes `translations/source/hadeethenc_en.jsonl`
(committed, so `match` needs no network). `match` normalizes each item's Arabic text with
`lists.normalize` and joins it to the group whose recorded texts share the most idf weight with it
(`out/matn_tokens.parquet`, `out/matn_vocab.parquet`), keeping only clear matches, and writes
`translations/hadeethenc.parquet`. The site shows a matched item's English verbatim, attributed,
beside the Arabic; nothing computed reads it.
"""
from __future__ import annotations

import argparse
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

from itibar import lists, paths

API = "https://hadeethenc.com/api/v1"
SOURCE = paths.ROOT / "translations" / "source" / "hadeethenc_en.jsonl"
OUTPUT = paths.ROOT / "translations" / "hadeethenc.parquet"
AGENT = "itibar-research-client (+https://github.com/haseeb-crescent/itibar)"
KEEP = ("id", "title", "hadeeth", "hadeeth_intro", "attribution", "hadeeth_ar", "hadeeth_intro_ar", "categories")
# A match needs this share of the item's idf mass in one group, and a margin over the runner-up.
MIN_SHARE = 0.6
MIN_MARGIN = 0.15


def _get(path, params, pause):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(8):
        time.sleep(pause * (2 ** attempt if attempt else 1))
        try:
            request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504):
                raise
            print(f"  {error.code} on {url}; backing off", file=sys.stderr)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
            print(f"  {getattr(error, 'reason', error)} on {url}; backing off", file=sys.stderr)
    raise RuntimeError(f"Giving up on {url}")


def fetch(dest=SOURCE, pause=1.5):
    """Every English item reachable from the category list, one request per item (resumable)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if dest.is_file():
        for line in dest.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            done[item["id"]] = item
    categories = _get("categories/list/", {"language": "en"}, pause)
    ids = set()
    for category in categories:
        page, last = 1, 1
        while page <= last:
            listing = _get("hadeeths/list/", {"language": "en", "category_id": category["id"],
                                              "page": page, "per_page": 100}, pause)
            ids.update(str(item["id"]) for item in listing["data"])
            last = int(listing["meta"]["last_page"])
            page += 1
    print(f"{len(ids)} English items listed; {len(ids - done.keys())} to fetch", file=sys.stderr)
    retrieved = date.today().isoformat()
    with dest.open("a", encoding="utf-8") as out:
        for n, hid in enumerate(sorted(ids - done.keys(), key=int), 1):
            item = _get("hadeeths/one/", {"language": "en", "id": hid}, pause)
            kept = {key: item.get(key) for key in KEEP}
            kept["id"] = str(kept["id"])
            kept["retrieved"] = retrieved
            out.write(json.dumps(kept, ensure_ascii=False, sort_keys=True) + "\n")
            out.flush()
            if n % 100 == 0:
                print(f"  {n} fetched", file=sys.stderr)
    _sort(dest)


def _sort(dest):
    items = {}
    for line in dest.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        items[item["id"]] = item
    dest.write_text("".join(json.dumps(items[k], ensure_ascii=False, sort_keys=True) + "\n"
                            for k in sorted(items, key=int)), encoding="utf-8")


def read(source=SOURCE):
    if not source.is_file():
        return []
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]


def strip_intro(arabic, intro):
    """The Arabic matn: HadeethEnc puts the companion's introduction before the Prophet's words."""
    text = arabic or ""
    if intro and text.startswith(intro):
        text = text[len(intro):]
    return text


def match(items, hadith_tokens, idf, hadith_group, min_share=MIN_SHARE, min_margin=MIN_MARGIN):
    """Join items to groups by idf-weighted token overlap with any recorded text of the group.

    items: dicts with id and hadeeth_ar (and hadeeth_intro_ar); hadith_tokens: hadith id -> set of
    normalized tokens; idf: token -> weight; hadith_group: hadith id -> group id. Returns
    {item id: (group id, share, runner-up share)} for clear matches only.
    """
    postings = defaultdict(set)
    for hid, tokens in hadith_tokens.items():
        for token in tokens:
            postings[token].add(hid)
    out = {}
    for item in items:
        tokens = set(lists.tokens(strip_intro(item.get("hadeeth_ar"), item.get("hadeeth_intro_ar"))))
        tokens = {t for t in tokens if t in idf}
        mass = sum(idf[t] for t in tokens)
        if not tokens or mass <= 0:
            continue
        by_group = defaultdict(float)
        candidates = set()
        for token in sorted(tokens, key=lambda t: -idf[t])[:12]:
            candidates |= postings.get(token, set())
        for hid in candidates:
            share = sum(idf[t] for t in tokens & hadith_tokens[hid]) / mass
            gid = hadith_group[hid]
            by_group[gid] = max(by_group[gid], share)
        if not by_group:
            continue
        ranked = sorted(by_group.items(), key=lambda kv: (-kv[1], kv[0]))
        gid, share = ranked[0]
        runner = ranked[1][1] if len(ranked) > 1 else 0.0
        if share >= min_share and share - runner >= min_margin:
            out[item["id"]] = (gid, round(share, 4), round(runner, 4))
    return out


def build(source=SOURCE, output=OUTPUT):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    items = read(source)
    if not items:
        print(f"{source} is missing or empty; run make hadeethenc-fetch", file=sys.stderr)
        return {}
    con = duckdb.connect()
    con.execute(f"CREATE VIEW hadiths AS SELECT * FROM read_parquet('{paths.PARQUET_DIR / 'hadiths.parquet'}')")
    rows = con.execute("SELECT id, group_id, nass, matn_start, matn_end FROM hadiths WHERE group_id IS NOT NULL").fetchall()
    from itibar.matn import _matn
    hadith_tokens, hadith_group, df = {}, {}, defaultdict(int)
    for hid, gid, nass, start, end in rows:
        tokens = set(lists.tokens(_matn(nass, start, end)))
        hadith_tokens[hid], hadith_group[hid] = tokens, gid
        for token in tokens:
            df[token] += 1
    import math
    total = len(hadith_tokens)
    idf = {t: math.log(total / n) for t, n in df.items()}
    matches = match(items, hadith_tokens, idf, hadith_group)
    by_id = {item["id"]: item for item in items}
    best = {}
    for hid, (gid, share, runner) in matches.items():
        # One human translation per group: the closest match, then the lowest HadeethEnc id.
        if gid not in best or (share, -int(hid)) > (best[gid][1], -int(best[gid][0])):
            best[gid] = (hid, share, runner)
    table = pa.table({
        "group_id": pa.array(sorted(best), pa.int64()),
        "hadeethenc_id": [best[g][0] for g in sorted(best)],
        "title": [by_id[best[g][0]]["title"] for g in sorted(best)],
        "text": [by_id[best[g][0]]["hadeeth"] for g in sorted(best)],
        "attribution": [by_id[best[g][0]].get("attribution") for g in sorted(best)],
        "url": [f"https://hadeethenc.com/en/browse/hadith/{best[g][0]}" for g in sorted(best)],
        "retrieved": [by_id[best[g][0]].get("retrieved") for g in sorted(best)],
        "share": [best[g][1] for g in sorted(best)],
        "runner_up": [best[g][2] for g in sorted(best)],
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output, compression="zstd")
    summary = {"items": len(items), "matched": len(matches), "groups": len(best)}
    print(json.dumps(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "build"))
    args = parser.parse_args()
    fetch() if args.command == "fetch" else build()


if __name__ == "__main__":
    main()
