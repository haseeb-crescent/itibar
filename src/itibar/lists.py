"""`make lists`: the classical mutawatir lists, digitized, matched to meaning
groups and binned.

  fetch   re-download al-Kattani's Nazm al-Mutanathir (Shamela book 7016) page by
          page from Shamela's public read-only MCP server into lists/source/
  parse   lists/source/*.jsonl -> lists/kattani.yaml, lists/suyuti.yaml
  match   deterministic token-overlap match of every entry to meaning groups ->
          lists/candidates.csv (top 5 per entry) and lists/confirmed.csv (auto rows
          rewritten; human rows kept exactly as the user left them)
  report  join confirmed groups, pooled bundles and bins -> reports/lists.md,
          figures/fig3_lists_bins.{png,svg,csv}

al-Suyuti's al-Azhar al-Mutanathira is not in Shamela's catalogue or usul.ai.
al-Kattani states in his introduction that he included every hadith of al-Azhar
and marked each with "أورده في الأزهار من حديث فلان", listing the companions
al-Suyuti counted and dropping al-Suyuti's source citations. lists/suyuti.yaml is
reconstructed from those markers and says so in every entry (DECISIONS.md D45).

No embeddings and no model: normalization is a versioned function, scores are
token-set overlap and an opening-phrase test, and nothing is confirmed beyond the
documented auto rule.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

from itibar import config, data, paths

LISTS_DIR = paths.ROOT / "lists"
SOURCE_DIR = LISTS_DIR / "source"
KATTANI_BOOK = 7016
KATTANI_SOURCE = SOURCE_DIR / f"kattani_{KATTANI_BOOK}.jsonl"
SHAMELA_MCP = "https://mcp.shamela.ws"

# ---------------------------------------------------------------- normalization

NORMALIZE_VERSION = 1
_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_NON_ARABIC = re.compile(r"[^ء-ي\s]")


def normalize(text: str | None) -> str:
    """Version 1: strip diacritics, Quranic marks and tatweel; alif variants -> ا,
    alif maqsura -> ي, ta marbuta -> ه, hamza on waw/ya -> و/ي; drop everything
    that is not an Arabic letter; collapse whitespace."""
    if not text:
        return ""
    t = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    t = t.replace("ﷺ", " ")
    t = t.translate(_LETTERS)
    t = _NON_ARABIC.sub(" ", t)
    return " ".join(t.split())


def tokens(text: str | None) -> list[str]:
    return normalize(text).split()


# ---------------------------------------------------------------- fetch

def _rpc(method: str, params: dict) -> dict:
    import urllib.request
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(SHAMELA_MCP, data=body, headers={
                "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                "User-Agent": "itibar/0.2 (research; github.com/haseeb-crescent/itibar)"})
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read().decode("utf-8")
            if raw.startswith(("event:", "data:")):
                raw = "\n".join(line[5:] for line in raw.splitlines() if line.startswith("data:"))
            return json.loads(raw)
        except Exception as e:  # network retries
            if attempt == 7:
                raise
            time.sleep(min(180, 5 * 2 ** attempt if "429" in str(e) else 2 + 3 * attempt))
    raise RuntimeError("unreachable")


def _open(book: int, page: int, field: str = "body") -> dict:
    d = _rpc("tools/call", {"name": "shamela_open",
                            "arguments": {"book_id": book, "page_id": page, "max_chars": 16000, "field": field}})
    res = d["result"]
    if res.get("structuredContent"):
        return res["structuredContent"]
    return json.loads("".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"))


def fetch(book: int = KATTANI_BOOK, out: Path = KATTANI_SOURCE) -> int:
    """Walk the book from page 1, one JSON line per page (text, footnotes, citation)."""
    _rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                        "clientInfo": {"name": "itibar", "version": "0.2"}})
    out.parent.mkdir(parents=True, exist_ok=True)
    n, page = 0, 1
    with open(out, "w", encoding="utf-8") as f:
        while page:
            r = _open(book, page)
            fn = _open(book, page, "footnotes")
            f.write(json.dumps({"page_id": page, "citation": (r.get("citation") or {}).get("markdown"),
                                "title": None, "text": r.get("text", ""), "footnotes": fn.get("text", ""),
                                "headings": None}, ensure_ascii=False) + "\n")
            n += 1
            page = (r.get("navigation") or {}).get("next_page_id")
            time.sleep(1.5)
    return n


# ---------------------------------------------------------------- parse

_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ENTRY = re.compile(r"(?:^|\n)\s*([٠-٩]{1,3})\s*[-–ـ]\s*")
_PAGE = re.compile(r"<<P(\d+)>>")
_CHAPTER = re.compile(r"\n\s*\(((?:كتاب|باب|أبواب)[^)\n]{1,80})\)\s*\.?")
_MARKER = re.compile(r"أورد(?:ه|ها)?\s+(?:في\s+الأزهار|فيها)(?:\s+في\s+(?:كتاب|باب)\s+\S+)?(?:\s+أيضا[ًا]?)?\s*(?:من\s+حديث|عن)?")
_NUM = re.compile(r"\(([٠-٩]{1,3})\)")
_COUNT_END = re.compile(r"(نفسا|نفساً|أنفس|نفوس|صحابيا|صحابياً)\s*\.?")
_SOURCES = ["البخاري", "مسلم", "الشيخان", "أحمد", "أبو داود", "الترمذي", "النسائي", "ابن ماجه", "الدارمي",
            "الطبراني", "الحاكم", "البيهقي", "ابن حبان", "ابن خزيمة", "الدارقطني", "أبو يعلى", "البزار",
            "ابن أبي شيبة", "عبد الرزاق", "الطحاوي", "ابن عساكر", "أبو نعيم", "الخطيب", "ابن عبد البر", "ابن منده",
            "الزيلعي", "المنذري", "العراقي", "ابن حجر", "السخاوي", "المناوي", "الهيثمي", "ابن الجوزي", "ابن الصلاح",
            "النووي", "السيوطي", "ابن كثير", "ابن تيمية", "الذهبي", "الضياء", "ابن عدي", "العقيلي", "سعيد بن منصور"]
_UNITS = {"واحد": 1, "أحد": 1, "احد": 1, "اثنا": 2, "اثني": 2, "اثنين": 2, "اثنان": 2, "ثلاث": 3, "ثلاثة": 3,
          "أربع": 4, "أربعة": 4, "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6, "سبع": 7, "سبعة": 7, "ثمان": 8,
          "ثماني": 8, "ثمانية": 8, "تسع": 9, "تسعة": 9}
_TENS = {"عشرين": 20, "عشرون": 20, "ثلاثين": 30, "ثلاثون": 30, "أربعين": 40, "أربعون": 40, "خمسين": 50,
         "خمسون": 50, "ستين": 60, "ستون": 60, "سبعين": 70, "سبعون": 70, "ثمانين": 80, "ثمانون": 80,
         "تسعين": 90, "تسعون": 90}


def _ar_int(s: str) -> int:
    return int("".join(str(_AR_DIGITS.index(ch)) for ch in s))


def count_words(phrase: str) -> int | None:
    """Arabic number words before نفسا/أنفس: 'خمسة عشر' 15, 'اثني عشر' 12, 'عشرة' 10,
    'ثلاثة وعشرين' 23, 'تسعة' 9. 'نيف' (an unspecified few) returns None."""
    w = [x.strip("ًٌٍَُِّْ") for x in phrase.replace("و", " و ").split()]
    w = [x for x in w if x and x != "و"]
    if not w or "نيف" in w or "نيفا" in w:
        return None
    if len(w) >= 2 and w[-1] in ("عشر", "عشرة") and w[-2] in _UNITS:
        return 10 + _UNITS[w[-2]]
    if w[-1] in _TENS:
        return _TENS[w[-1]] + (_UNITS.get(w[-2], 0) if len(w) >= 2 else 0)
    if w[-1] in ("عشر", "عشرة"):
        return 10
    if w[-1] in _UNITS:
        return _UNITS[w[-1]]
    return None


def _names(segment: str) -> list[str]:
    """Names in a numbered list '(١) فلان (٢) وفلان ...'. Handles a number misplaced
    after the first word ('رافع (١) بن خديج (٢) ومحمود ...')."""
    parts = _NUM.split(segment)
    pre, rest = parts[0].strip(), parts[1:]
    segs = [rest[i + 1] for i in range(0, len(rest) - 1, 2)]
    if pre and segs and segs[0].strip().startswith(("بن ", "ابن ")):
        segs[0] = pre + " " + segs[0].strip()
    out = []
    for s in segs:
        s = _COUNT_END.split(s)[0]
        s = re.split(r"[.،؛]|\s(?:ذكر|رواه|ورواه|أخرجه|وفي|قال|وقال|كلاهما|وقد|وممن|ثم|وهو|عند|في)\s", " " + s + " ")[0]
        s = re.sub(r"^\s*و(?=\S)", "", s.strip())
        words = s.split()
        # drop a trailing count phrase ("خمسة عشر")
        while words and (words[-1] in _UNITS or words[-1] in _TENS or words[-1] in ("عشر", "عشرة", "اثني")):
            words.pop()
        if words:
            out.append(" ".join(words[:8]))
    return out


def _page_label(citation: str | None) -> str | None:
    if not citation:
        return None
    m = re.search(r"\(([^()]*)\)\]", citation)
    return m.group(1) if m else None


def parse_kattani(path: Path = KATTANI_SOURCE) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    cit = {r["page_id"]: r["citation"] for r in rows}
    full = "".join(f"\n<<P{r['page_id']}>>\n" + r["text"] for r in rows)
    starts = list(_ENTRY.finditer(full))
    chapters = [(m.start(), m.group(1).strip()) for m in _CHAPTER.finditer(full)]
    entries = []
    prev = 0
    seen: Counter = Counter()
    for i, m in enumerate(starts):
        n = _ar_int(m.group(1))
        if n < prev:                      # a stray numeral line inside an entry
            continue
        prev = n
        seen[n] += 1
        key = str(n) if seen[n] == 1 else f"{n}{'abcdefgh'[seen[n] - 1]}"
        end = starts[i + 1].start() if i + 1 < len(starts) else full.find("خاتمة", m.end())
        if end < 0:
            end = len(full)
        body = full[m.end():end]
        before = full[:m.start()]
        pages = [int(x) for x in _PAGE.findall(before)][-1:] + [int(x) for x in _PAGE.findall(body)]
        page0 = pages[0]
        chap = next((c for pos, c in reversed(chapters) if pos < m.start()), None)
        clean = _PAGE.sub(" ", body)
        if clean.lstrip().startswith("("):
            j = clean.index("(")
            depth, k = 0, j
            while k < len(clean):
                if clean[k] == "(":
                    depth += 1
                elif clean[k] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            wording = " ".join(clean[j + 1:k].split())
            rest = clean[k + 1:]
            after = " ".join(rest.split()).lstrip(" .-")
            kind = "wording"
            if len(rest.strip()) < 160 and "تقدم" in rest[:160]:
                kind = "cross_reference"
            elif wording.startswith("أحاديث") or re.search(r"أوردها\s+(?:في\s+الأزهار|فيها)", after[:400]):
                kind = "topic"
        else:
            first = re.split(r"[.\n]", clean.strip(), maxsplit=1)[0]
            wording = " ".join(first.split())[:300]
            kind = "topic"
            rest = clean
        nums = [_ar_int(x) for x in _NUM.findall(rest)]
        names = _names(rest[: _COUNT_END.search(rest).end()] if _COUNT_END.search(rest) else rest)
        mk = _MARKER.search(rest)
        suy = None
        if mk:
            seg = rest[mk.end():]
            q = seg.find("(قلت)")
            ce = _COUNT_END.search(seg)
            cut = min(x for x in (q if q >= 0 else len(seg), ce.end() if ce else len(seg), len(seg)))
            seg = seg[:cut]
            snums = [_ar_int(x) for x in _NUM.findall(seg)]
            stated = None
            if ce and ce.end() <= cut + 1:
                tail = seg[max(0, ce.start() - 40):ce.start()]
                tail = _NUM.split(tail)[-1]
                stated = count_words(" ".join(tail.split()[-3:]))
            suy = {"companions": _names(seg), "numbered": max(snums) if snums else 0, "stated_count": stated}
        found_sources = []
        for s in _SOURCES:
            if re.search(r"(?<![ء-ي])" + re.escape(s) + r"(?![ء-ي])", rest):
                found_sources.append(s)
        entries.append({
            "index": key, "number": n, "kind": kind, "wording": wording, "chapter": chap,
            "page_id": page0, "page_label": _page_label(cit.get(page0)),
            "url": f"https://shamela.ws/book/{KATTANI_BOOK}/{page0}",
            "pages": sorted(set(pages)),
            "in_azhar": suy is not None,
            "companions_numbered": max(nums) if nums else 0,
            "companions": names if not mk else (suy["companions"] if suy else []),
            "kattani_companions_added": max(0, (max(nums) if nums else 0) - (suy["numbered"] if suy else 0)),
            "suyuti": suy,
            "sources_named": found_sources,
            "head": " ".join(clean.split())[:400],
        })
    return entries


def write_lists(entries: list[dict]) -> tuple[Path, Path]:
    LISTS_DIR.mkdir(parents=True, exist_ok=True)
    k_meta = {
        "work": "نظم المتناثر من الحديث المتواتر (Nazm al-Mutanathir min al-Hadith al-Mutawatir)",
        "author": "Muhammad b. Ja'far al-Kattani (d. 1345/1927)",
        "source": f"Shamela book {KATTANI_BOOK}, https://shamela.ws/book/{KATTANI_BOOK} (text of the Fez print "
                  "completed 19 Jumada II 1328, per its colophon on the last page)",
        "retrieved_via": "Shamela public read-only MCP server (https://mcp.shamela.ws), lists/source/",
        "normalize_version": NORMALIZE_VERSION,
        "fields": {
            "index": "al-Kattani's entry number as a string; a number the print repeats gets a letter (238b)",
            "number": "al-Kattani's printed number",
            "kind": "wording (a quoted text), topic (a subject heading) or cross_reference (points to an earlier entry)",
            "companions_numbered": "the highest number in his numbered list of narrators (his own count, al-Suyuti's included)",
            "companions": "the names in the first numbered list (al-Suyuti's, when the entry is in al-Azhar)",
            "in_azhar": "the entry carries al-Kattani's marker أورده في الأزهار / أورده فيها",
            "sources_named": "works and critics named in the entry text (a fixed vocabulary, in list order)",
            "page_id": "Shamela page id; page_label is the printed page",
        },
        "missing_numbers": [n for n in range(1, max(e["number"] for e in entries) + 1)
                            if n not in {e["number"] for e in entries}],
        "repeated_numbers": sorted({e["number"] for e in entries if not e["index"].isdigit()}),
    }
    kat = [{k: e[k] for k in ("index", "number", "kind", "wording", "chapter", "companions_numbered", "companions",
                              "in_azhar", "sources_named", "page_id", "page_label", "url", "pages")}
           for e in entries]
    kp = LISTS_DIR / "kattani.yaml"
    kp.write_text(yaml.safe_dump({"meta": k_meta, "entries": kat}, allow_unicode=True, sort_keys=False, width=200),
                  encoding="utf-8")
    suy = []
    for e in entries:
        if not e["in_azhar"]:
            continue
        s = e["suyuti"]
        suy.append({
            "index": str(len(suy) + 1), "kattani_index": e["index"], "kind": e["kind"], "wording": e["wording"],
            "companions_stated": s["stated_count"], "companions_numbered": s["numbered"],
            "companions": s["companions"], "cited_sources": None,
            "page_id": e["page_id"], "page_label": e["page_label"], "url": e["url"],
        })
    s_meta = {
        "work": "الأزهار المتناثرة في الأخبار المتواترة (al-Azhar al-Mutanathira fi al-Akhbar al-Mutawatira)",
        "author": "Jalal al-Din al-Suyuti (d. 911/1505)",
        "source": "SECONDARY. Reconstructed from al-Kattani, Nazm al-Mutanathir (Shamela book 7016): in his "
                  "introduction he states that he included every hadith of al-Azhar and marked it with "
                  "'أورده في الأزهار من حديث فلان', listing the companions al-Suyuti counted and dropping "
                  "al-Suyuti's source citations. The primary text is not in Shamela's catalogue or on usul.ai; "
                  "a scan of a printed edition can replace this file (see DECISIONS.md D45).",
        "criterion": "ما رواه من الصحابة عشرة فصاعدا (ten or more companions), per al-Suyuti",
        "fields": {
            "index": "order of appearance in al-Kattani; NOT al-Suyuti's own numbering (not transmitted)",
            "kattani_index": "al-Kattani's entry number",
            "companions_stated": "the count al-Suyuti gives ('خمسة عشر نفسا'), as al-Kattani reports it",
            "companions_numbered": "the length of al-Suyuti's numbered list as al-Kattani reports it",
            "cited_sources": "null: al-Kattani drops al-Suyuti's citations (مسقطا لما ذكره من المخرجين)",
        },
        "kattani_count_note": "al-Kattani: al-Suyuti states 100 entries at the end of al-Azhar; al-Kattani "
                              "counted 112 (Nazm al-Mutanathir, introduction).",
    }
    sp = LISTS_DIR / "suyuti.yaml"
    sp.write_text(yaml.safe_dump({"meta": s_meta, "entries": suy}, allow_unicode=True, sort_keys=False, width=200),
                  encoding="utf-8")
    return kp, sp


def load_list(name: str) -> list[dict]:
    return yaml.safe_load((LISTS_DIR / f"{name}.yaml").read_text(encoding="utf-8"))["entries"]


# ---------------------------------------------------------------- match

def _cfg() -> dict:
    return config.load("structure")["lists"]


def matn_table(con):
    """One row per hadith with a group: normalized matn tokens (deduplicated), and
    the group's own nass as a pseudo-matn (hadith_id = -group_id)."""
    import pyarrow as pa
    rows = con.sql("""SELECT id, group_id, nass, matn_start, matn_end FROM hadiths WHERE group_id IS NOT NULL""").fetchall()
    hid, gid, toks, text = [], [], [], []
    for h, g, nass, a, b in rows:
        m = nass[a:b] if (nass and a is not None and b is not None and b > a) else (nass or "")
        t = normalize(m)
        hid.append(h)
        gid.append(g)
        text.append(t)
    for g, nass in con.sql("SELECT id, nass FROM meaning_groups").fetchall():
        hid.append(-int(g))
        gid.append(int(g))
        text.append(normalize(nass))
    for t in text:
        toks.append(sorted(set(t.split())))
    return pa.table({"hadith_id": hid, "group_id": gid, "text": text, "toks": toks})


def match(entries_by_list: dict[str, list[dict]], con=None) -> list[dict]:
    """Top-k candidate groups per entry. Score = w_contain * containment
    + w_opening * opening + w_support * relative support, where
      containment  max over member matns (and the group nass) of the idf-weighted
                   share of the entry's tokens present in the matn
      opening      1 if the entry's first `opening_tokens` tokens occur contiguously
                   in the group nass or a member matn, else 0
      support      member matns with containment >= support_min, divided by the
                   largest such count among this entry's candidates."""
    con = con or data.views()
    cfg = _cfg()
    t0 = time.time()
    mt = matn_table(con)
    con.register("mt", mt)
    con.execute("CREATE OR REPLACE TEMP TABLE mtok AS SELECT hadith_id, group_id, unnest(toks) AS tok FROM mt")
    n_docs = con.sql("SELECT count(*) FROM mt").fetchall()[0][0]
    con.execute(f"""CREATE OR REPLACE TEMP TABLE idf AS
                    SELECT tok, ln({n_docs} / count(*)) + 1 AS w FROM mtok GROUP BY 1""")
    ent_rows = []
    keyed = []
    for lst, entries in entries_by_list.items():
        for e in entries:
            toks = sorted(set(tokens(e["wording"])))
            keyed.append((lst, e))
            for t in toks:
                ent_rows.append((f"{lst}:{e['index']}", t))
    import pyarrow as pa
    con.register("et", pa.table({"eid": [r[0] for r in ent_rows], "tok": [r[1] for r in ent_rows]}))
    con.execute("""CREATE OR REPLACE TEMP TABLE etw AS
                   SELECT et.eid, et.tok, coalesce(idf.w, ln(1000000) + 1) AS w FROM et LEFT JOIN idf USING (tok)""")
    con.execute("CREATE OR REPLACE TEMP TABLE etot AS SELECT eid, sum(w) AS tot FROM etw GROUP BY 1")
    smin = float(cfg["support_min"])
    k = int(cfg["candidates"])
    shortlist = int(cfg["shortlist"])
    con.execute("""CREATE OR REPLACE TEMP TABLE hit AS
        SELECT etw.eid, mtok.hadith_id, any_value(mtok.group_id) AS group_id, sum(etw.w) / any_value(etot.tot) AS c
        FROM etw JOIN mtok USING (tok) JOIN etot USING (eid)
        GROUP BY 1, 2""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE gsc AS
        SELECT eid, group_id, max(c) AS containment, count(*) FILTER (WHERE c >= {smin} AND hadith_id > 0) AS support
        FROM hit GROUP BY 1, 2""")
    top = con.sql(f"""SELECT * FROM (
            SELECT *, row_number() OVER (PARTITION BY eid ORDER BY containment DESC, support DESC, group_id) AS rk
            FROM gsc) WHERE rk <= {shortlist}""").fetchall()
    by_e: dict[str, list] = {}
    for eid, g, c, s, _ in top:
        by_e.setdefault(eid, []).append([int(g), float(c), int(s)])
    # opening phrase on the shortlist
    need = sorted({g for v in by_e.values() for g, _, _ in v})
    con.register("need", pa.table({"group_id": need}))
    texts: dict[int, list[str]] = {}
    for g, t in con.sql("SELECT group_id, text FROM mt WHERE group_id IN (SELECT group_id FROM need)").fetchall():
        texts.setdefault(int(g), []).append(" " + t + " ")
    wc, wo, ws = (float(cfg["weights"][x]) for x in ("containment", "opening", "support"))
    nop = int(cfg["opening_tokens"])
    out = []
    for lst, e in keyed:
        eid = f"{lst}:{e['index']}"
        seq = tokens(e["wording"])
        phrase = " " + " ".join(seq[:nop]) + " " if seq else None
        cands = by_e.get(eid, [])
        smax = max((s for _, _, s in cands), default=0) or 1
        scored = []
        for g, c, s in cands:
            op = 1.0 if phrase and any(phrase in t for t in texts.get(g, [])) else 0.0
            score = wc * c + wo * op + ws * (s / smax)
            scored.append((round(score, 4), g, round(c, 4), op, s))
        scored.sort(key=lambda x: (-x[0], -x[4], x[1]))
        for rank, (score, g, c, op, s) in enumerate(scored[:k], 1):
            out.append({"list": lst, "entry": e["index"], "kind": e["kind"], "rank": rank, "group_id": g,
                        "score": score, "containment": c, "opening": op, "support": s,
                        "wording": e["wording"][:120]})
        if not scored:
            out.append({"list": lst, "entry": e["index"], "kind": e["kind"], "rank": 0, "group_id": None,
                        "score": 0.0, "containment": 0.0, "opening": 0.0, "support": 0,
                        "wording": e["wording"][:120]})
    print(f"  matched {len(keyed)} entries in {time.time() - t0:.0f}s", file=sys.stderr)
    return out


CAND_FIELDS = ["list", "entry", "kind", "rank", "group_id", "score", "containment", "opening", "support", "wording"]
CONF_FIELDS = ["list", "entry", "group_id", "status", "confirmed_by", "score", "margin", "note"]


def entry_sort_key(e) -> tuple[int, str]:
    """'238b' -> (238, 'b'): al-Kattani's number, then the letter a repeated number gets."""
    m = re.match(r"(\d+)(\D*)", str(e))
    return (int(m.group(1)), m.group(2)) if m else (10**6, str(e))


def auto_rows(cands: list[dict]) -> list[dict]:
    """One row per entry: auto-confirmed (top score >= auto_min_score and margin to
    the second >= auto_min_margin, wording entries only) or needs_review."""
    cfg = _cfg()
    smin, mmin = float(cfg["auto_min_score"]), float(cfg["auto_min_margin"])
    by: dict[tuple, list[dict]] = {}
    for c in cands:
        by.setdefault((c["list"], c["entry"]), []).append(c)
    rows = []
    for (lst, idx), cs in sorted(by.items(), key=lambda kv: (kv[0][0], entry_sort_key(kv[0][1]))):
        cs = sorted([c for c in cs if c["group_id"] is not None], key=lambda c: c["rank"])
        top = cs[0] if cs else None
        second = cs[1]["score"] if len(cs) > 1 else 0.0
        margin = round(top["score"] - second, 4) if top else 0.0
        ntok = len(tokens(top["wording"])) if top else 0
        ok = (bool(top) and top["kind"] == "wording" and ntok >= int(cfg["auto_min_tokens"])
              and int(top["support"]) >= int(cfg["auto_min_support"]) and top["score"] >= smin and margin >= mmin)
        rows.append({"list": lst, "entry": idx, "group_id": top["group_id"] if (top and ok) else "",
                     "status": "auto" if ok else "needs_review", "confirmed_by": "auto" if ok else "",
                     "score": top["score"] if top else 0.0, "margin": margin,
                     "note": "" if ok else ("no candidate" if not top else f"{top['kind']} entry"
                                           if top["kind"] != "wording" else "wording too short for the auto rule"
                                           if ntok < int(cfg["auto_min_tokens"]) else "too few supporting matns"
                                           if int(top["support"]) < int(cfg["auto_min_support"]) else "below the auto rule")})
    return rows


def write_match(cands: list[dict]) -> tuple[Path, Path]:
    cp = LISTS_DIR / "candidates.csv"
    with open(cp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAND_FIELDS)
        w.writeheader()
        w.writerows(cands)
    conf = LISTS_DIR / "confirmed.csv"
    human: list[dict] = []
    if conf.exists():
        with open(conf, encoding="utf-8") as f:
            human = [r for r in csv.DictReader(f) if r.get("confirmed_by") == "human"]
    hk = {(r["list"], str(r["entry"])) for r in human}
    rows = [r for r in auto_rows(cands) if (r["list"], str(r["entry"])) not in hk] + human
    rows.sort(key=lambda r: (r["list"], entry_sort_key(r["entry"]), str(r["group_id"])))
    with open(conf, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CONF_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return cp, conf


def confirmed() -> dict[tuple[str, str], list[int]]:
    out: dict[tuple[str, str], list[int]] = {}
    conf = LISTS_DIR / "confirmed.csv"
    if not conf.exists():
        return out
    with open(conf, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("confirmed_by") in ("auto", "human") and r.get("group_id"):
                out.setdefault((r["list"], str(r["entry"])), []).append(int(r["group_id"]))
    return out


# ---------------------------------------------------------------- join and report

def join(con=None) -> list[dict]:
    import pandas as pd

    from itibar import load, pool
    con = con or data.views()
    corpus = load.corpus(con)
    rec = pd.read_parquet(paths.records_path()).set_index("group_id")
    N = int(config.load("structure")["number_class"]["tawatur_n"])
    conf = confirmed()
    review = {}
    with open(LISTS_DIR / "confirmed.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            review[(r["list"], str(r["entry"]))] = r["status"]
    all_g = sorted({g for v in conf.values() for g in v})
    by_group = load.chains_by_group(con, all_g) if all_g else {}
    rows = []
    suy_by_k = {str(e["kattani_index"]): e for e in load_list("suyuti")}
    for lst in ("kattani", "suyuti"):
        for e in load_list(lst):
            key_idx = str(e["index"])
            gids = conf.get((lst, key_idx), [])
            if lst == "suyuti" and not gids:
                gids = conf.get(("kattani", str(e["kattani_index"])), [])
            if lst == "suyuti":
                author = e.get("companions_stated") or e.get("companions_numbered")
            else:
                author = e.get("companions_numbered")
            suy_count = None
            if lst == "kattani" and e.get("in_azhar"):
                s_ent = suy_by_k.get(key_idx)
                suy_count = (s_ent.get("companions_stated") or s_ent.get("companions_numbered")) if s_ent else None
            row = {"list": lst, "entry": key_idx, "kind": e["kind"], "wording": e["wording"],
                   "author_count": author, "suyuti_count": suy_count, "groups": gids,
                   "review": review.get((lst, key_idx), "")}
            if not gids:
                row["bin"] = "unmatched"
                rows.append(row)
                continue
            ok = [g for g in gids if g in rec.index and rec.loc[g, "status"] == "ok"]
            best = max(ok, key=lambda g: (rec.loc[g, "kappa_all"], -g)) if ok else None
            P = pool.analyse(gids, con, corpus, label=f"{lst}:{key_idx}", by_group=by_group)
            row.update({
                "best_group": best,
                **{f"best_kappa_{th}": (int(rec.loc[best, f"kappa_{th}"]) if best is not None else None)
                   for th in corpus.scale.thresholds},
                "best_companions": int(rec.loc[best, "companions"]) if best is not None else None,
                "best_number_class": rec.loc[best, "number_class"] if best is not None else None,
                **{f"pool_kappa_{th}": P.get(f"kappa_{th}") for th in corpus.scale.thresholds},
                "pool_companions": P.get("companions"),
                "pool_number_class": P.get("number_class"),
            })
            single = row["best_kappa_all"] is not None and row["best_kappa_all"] >= N
            pooled = (P.get("kappa_all") or 0) >= N
            row["bin"] = "wording" if single else ("meaning_only" if pooled else "below_threshold_in_this_data")
            rows.append(row)
    return rows


BINS = ["wording", "meaning_only", "below_threshold_in_this_data", "unmatched"]


def report(rows: list[dict] | None = None) -> str:
    import pandas as pd
    rows = rows if rows is not None else join()
    df = pd.DataFrame(rows)
    N = int(config.load("structure")["number_class"]["tawatur_n"])
    cfg = _cfg()
    L = ["# The classical mutawātir lists against the corpus", "",
         "Generated by `make lists`. Entries: `lists/kattani.yaml` (al-Kattānī, *Naẓm al-Mutanāthir*, Shamela book",
         "7016) and `lists/suyuti.yaml` (al-Suyūṭī, *al-Azhār al-Mutanāthira*, reconstructed from al-Kattānī's",
         "\"أورده في الأزهار\" markers: secondary, see DECISIONS.md D45). Matches: `lists/candidates.csv`",
         f"(top {cfg["candidates"]} groups per entry) and `lists/confirmed.csv` (the mapping used here: `auto` rows",
         (f"pass the documented rule, score ≥ {cfg['auto_min_score']}, margin ≥ {cfg['auto_min_margin']}, ≥ "
          f"{cfg['auto_min_tokens']} tokens and ≥ {cfg['auto_min_support']} supporting matns; `human`"),
         "rows are filled by a reviewer, never by the pipeline).", "",
         f"Bins (tawatur_n = {N}, κ at the `all` threshold): **wording** — a single matched group has κ_all ≥ {N};",
         "**meaning_only** — only the pooled bundle of all matched groups does; **below_threshold_in_this_data** —",
         "matched, neither reaches it; **unmatched** — no confirmed group (auto rule not met and no human row yet).",
         "A pool mixes distinct reports: pooled κ measures tawātur in meaning at the granularity of the entry.", ""]
    L += ["## Bins", "", "| list | entries | " + " | ".join(BINS) + " | pending review |",
          "|---|---|" + "---|" * (len(BINS) + 1)]
    for lst in ("kattani", "suyuti"):
        d = df[df["list"] == lst]
        L.append(f"| {lst} | {len(d)} | " + " | ".join(str(int((d['bin'] == b).sum())) for b in BINS)
                 + f" | {int((d['review'] == 'needs_review').sum())} |")
    L += ["", "The auto rule confirms one group per entry, so a pool equals its single group until a reviewer adds",
          "groups; `meaning_only` can only arise from multi-group (human) mappings.", "",
          "## Entries with a confirmed group", "",
          "Author's count: al-Kattānī's numbered list (his own count, al-Suyūṭī's included) or, for `suyuti`, the count",
          "al-Suyūṭī states as al-Kattānī reports it; the al-Suyūṭī column repeats that count beside al-Kattānī's rows.",
          "Ours: companions narrating from the Prophet on an unbroken route to a book, and κ.", "",
          "| list | entry | wording | author's count | al-Suyūṭī | groups | best group | κ all (best) | κ thiqa+ (best) | companions (best) | κ all (pool) | κ thiqa+ (pool) | companions (pool) | bin |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    df["_k"] = df["entry"].map(entry_sort_key)
    m = df[df["bin"] != "unmatched"].sort_values(["list", "_k"])
    def f(v) -> str:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        return str(int(v)) if isinstance(v, (int, float)) else str(v)

    for r in m.itertuples(index=False):
        L.append(f"| {r.list} | {r.entry} | {str(r.wording)[:60]} | {f(r.author_count)} | {f(r.suyuti_count)} | "
                 f"{', '.join(map(str, r.groups))} | {f(r.best_group)} | {f(r.best_kappa_all)} | {f(r.best_kappa_thiqa_up)} | "
                 f"{f(r.best_companions)} | {f(r.pool_kappa_all)} | {f(r.pool_kappa_thiqa_up)} | {f(r.pool_companions)} | {r.bin} |")
    L += ["", "## Unmatched entries (pending review or no candidate)", "",
          "Top candidate per entry is in `lists/candidates.csv`.", "",
          "| list | entry | kind | wording | review |", "|---|---|---|---|---|"]
    u = df[df["bin"] == "unmatched"].sort_values(["list", "_k"])
    for r in u.itertuples(index=False):
        L.append(f"| {r.list} | {r.entry} | {r.kind} | {str(r.wording)[:80]} | {r.review} |")
    L.append("")
    out = paths.REPORTS_DIR / "lists.md"
    out.write_text("\n".join(L), encoding="utf-8")
    _fig3(df)
    return "\n".join(L)


def _fig3(df) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from itibar import figures as F
    counts = {lst: [int(((df["list"] == lst) & (df["bin"] == b)).sum()) for b in BINS] for lst in ("kattani", "suyuti")}
    out_dir = paths.FIGURES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    pd.DataFrame([{"list": k, **dict(zip(BINS, v))} for k, v in counts.items()]).to_csv(
        out_dir / "fig3_lists_bins.csv", index=False)
    labels = {"wording": "one group reaches\ntawatur_n", "meaning_only": "only the pool\nreaches it",
              "below_threshold_in_this_data": "matched, below\ntawatur_n", "unmatched": "no confirmed\ngroup"}
    colors = [F.BLUE[650], F.BLUE[450], F.BLUE[250], F.GRID]
    fig, ax = plt.subplots(figsize=(8.5, 2.9))
    names = {"kattani": "al-Kattānī, Naẓm al-Mutanāthir", "suyuti": "al-Suyūṭī, al-Azhār (via al-Kattānī)"}
    for yi, lst in enumerate(("kattani", "suyuti")):
        left = 0
        tot = sum(counts[lst]) or 1
        for b, c, v in zip(BINS, colors, counts[lst]):
            ax.barh(yi, v, left=left, color=c, edgecolor=F.SURFACE, linewidth=2, height=0.6)
            if v / tot > 0.06:
                ax.text(left + v / 2, yi, str(v), ha="center", va="center", fontsize=8,
                        color="#ffffff" if c in (F.BLUE[650], F.BLUE[450]) else F.INK)
            left += v
    ax.set_yticks([0, 1], [names["kattani"], names["suyuti"]])
    ax.invert_yaxis()
    ax.set_xlabel("entries")
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in colors], [labels[b] for b in BINS],
              ncol=4, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.32))
    ax.set_title(f"Classical mutawātir lists against the corpus (κ_all ≥ {config.load('structure')['number_class']['tawatur_n']})")
    fig.subplots_adjust(left=0.27, right=0.98, top=0.85, bottom=0.42)
    for ext in ("png", "svg"):
        fig.savefig(out_dir / f"fig3_lists_bins.{ext}", dpi=200)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="itibar.lists")
    ap.add_argument("step", choices=["fetch", "parse", "match", "report", "all"], nargs="?", default="all")
    a = ap.parse_args(argv)
    if a.step == "fetch":
        print(fetch(), "pages")
        return
    if a.step in ("parse", "all"):
        ents = parse_kattani()
        kp, sp = write_lists(ents)
        print(f"{len(ents)} al-Kattani entries ({sum(e['in_azhar'] for e in ents)} marked al-Azhar) -> {kp}, {sp}")
    if a.step in ("match", "all"):
        cands = match({"kattani": load_list("kattani"), "suyuti": load_list("suyuti")})
        cp, conf = write_match(cands)
        st = Counter(r["status"] for r in auto_rows(cands))
        print(f"candidates -> {cp}; confirmed -> {conf}: {dict(st)}")
    if a.step in ("report", "all"):
        report()
        print(f"-> {paths.REPORTS_DIR / 'lists.md'}")


if __name__ == "__main__":
    main()

