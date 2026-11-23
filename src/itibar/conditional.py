"""`make conditional`: conditional narrator rulings (PR 6 §2, derive version 4).

A narrator's standing can be conditional on the link, not the man: weak from one teacher
(Simāk from ʿIkrima), sound only from the people of his own land (Ismāʿīl b. ʿAyyāsh), sound
only through some students (Ibn Lahīʿa through the ʿAbādila), sound before his memory failed
(the mukhtaliṭūn). The rulings are built from the books, never from the disagreement table:

  seed      the narrators to look up: the fourteen narrators of PR 5's residue table (audit
            §11.9), every narrator whose rawis.rank label carries a condition («إلا في»,
            «روايته عن», «حديثه عن», «اختلط», «تغير», «بأخرة», «أهل بلده», «خلط», «في غير»),
            every narrator the source flags has_ikhtilat, the narrators the brief names, every
            entry of al-Kawākib al-Nayyirāt and Ibn Rajab's sections matched to rawis
  fetch     their Taqrīb (Shamela 8609) and Taḥrīr al-Taqrīb (127715) entries ->
            lists/source/conditional_taqrib.jsonl; al-Kawākib al-Nayyirāt (309) ->
            lists/source/kawakib_309.jsonl; Ibn Rajab's Sharḥ ʿIlal al-Tirmidhī (9552), the
            section on trustworthy narrators weakened in some times, places or teachers ->
            lists/source/ibn_rajab_9552.jsonl
  build     rulings proposed from those texts, names of teachers and students matched to the
            narrators actually adjacent to him in the chains (sanad_rawis) ->
            lists/conditional_candidates.csv (every proposal with its match evidence),
            lists/conditional_confirmed.csv (auto rows rewritten; human rows kept exactly as the
            user left them), lists/conditional.yaml (the rows in force: auto and human)

Kinds and effects (README, D71-D74):
  from_shaykh        weak or sound from named teachers only            condition: teacher ids
  region_of_shaykh   sound from the people of his land only             condition: a region tag
  via_student        sound only through named students                  condition: student ids
  ikhtilat_before    heard before his memory failed                     condition: student ids
  ikhtilat_after     heard after (and, unknown: after, anyone not listed before)
  unobservable       a condition the chain cannot show (book vs memory, place of hearing,
                     after his books burned): recorded, applied nowhere
  effect             level:N (the link takes Taqrīb level N) | defect:light | accepted (the link
                     takes level min(base, 4): no defect where the base label would give one)

Auto-confirmed only when the Taqrīb or Taḥrīr entry of the narrator himself states the
condition in words and every id in the row matched uniquely among his adjacent narrators;
everything else is needs_review. The pipeline never writes a human row.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from itibar import config, data, lists, paths

TAQRIB, TAHRIR, KAWAKIB, IBN_RAJAB, ALAI, IGHTIBAT = 8609, 127715, 309, 9552, 25846, 130
SRC_TAQRIB = lists.SOURCE_DIR / "conditional_taqrib.jsonl"
SRC_KAWAKIB = lists.SOURCE_DIR / f"kawakib_{KAWAKIB}.jsonl"
SRC_RAJAB = lists.SOURCE_DIR / f"ibn_rajab_{IBN_RAJAB}.jsonl"
SRC_ALAI = lists.SOURCE_DIR / f"alai_{ALAI}.jsonl"
SRC_IGHTIBAT = lists.SOURCE_DIR / f"ightibat_{IGHTIBAT}.jsonl"
RAJAB_PAGES = (673, 755)        # «القسم الثاني»: trustworthy narrators weakened in some times, places or teachers
CAND_PATH = lists.LISTS_DIR / "conditional_candidates.csv"
CONF_PATH = lists.LISTS_DIR / "conditional_confirmed.csv"
YAML_PATH = lists.LISTS_DIR / "conditional.yaml"
KINDS = ("from_shaykh", "region_of_shaykh", "via_student", "ikhtilat_before", "ikhtilat_after", "unobservable")
BOOK_TITLES = {TAQRIB: "تقريب التهذيب", TAHRIR: "تحرير تقريب التهذيب", KAWAKIB: "الكواكب النيرات",
               IBN_RAJAB: "شرح علل الترمذي", ALAI: "المختلطين للعلائي", IGHTIBAT: "الاغتباط بمن رمي من الرواة بالاختلاط"}

# PR 5's residue table (audit §11.9, "narrators most often weakest in the disagreeing groups"),
# the unnamed person (1131) left out: the seed for where to look, never evidence for a ruling.
RESIDUE_SEED = (6811, 5033, 1239, 1919, 6155, 3638, 2288, 31544, 7270, 6638, 5770, 870, 1050, 5223)
# Narrators the brief names (resolved by name in rawis; checked by hand against their Taqrīb entries).
BRIEF_SEED = {3431: "سفيان بن حسين", 7633: "معمر بن راشد", 2119: "جرير بن حازم", 2492: "حماد بن سلمة",
              3044: "زهير بن معاوية", 5629: "عطاء بن السائب", 3281: "سعيد بن أبي عروبة",
              4533: "عبد الرزاق بن همام", 1239: "الحسن بن أبي الحسن البصري", 5223: "عبد الملك بن عبد العزيز بن جريج",
              6155: "عمرو بن عبد الله بن عبيد", 5033: "عبد الله بن لهيعة", 1050: "إسماعيل بن عياش", 3638: "سماك بن حرب"}
LABEL_PATTERN = "إلا في|روايته عن|حديثه عن|اختلط|تغير|بأخرة|بآخره|بآخرة|أهل بلده|خلط|في غير"


def cfg() -> dict:
    return config.load("structure")["derive"].get("conditional_rules") or {}


# ---------------------------------------------------------------- seed

def seed(con=None) -> list[dict]:
    """Seed narrators with why each is looked up (several reasons per narrator possible)."""
    con = con or data.views()
    why: dict[int, set[str]] = defaultdict(set)
    for rid in RESIDUE_SEED:
        why[rid].add("residue_table")
    for rid in BRIEF_SEED:
        why[rid].add("brief")
    for (rid,) in con.sql(f"""SELECT id FROM rawis WHERE is_stub = 0 AND rank IS NOT NULL
                              AND regexp_matches(rank, '{LABEL_PATTERN}')""").fetchall():
        why[int(rid)].add("label")
    for (rid,) in con.sql("SELECT id FROM rawis WHERE has_ikhtilat = 1 AND is_stub = 0").fetchall():
        why[int(rid)].add("has_ikhtilat")
    for tag, ents in (("kawakib", kawakib_entries_matched(con)), ("alai", alai_matched(con)),
                      ("ightibat", ightibat_matched(con)), ("ibn_rajab", ibn_rajab_matched(con))):
        for e in ents:
            if e.get("rawi_id") and e.get("match_status") == "auto":
                why[int(e["rawi_id"])].add(tag)
    info = {r[0]: r for r in con.sql(
        "SELECT id, name, nickname, rank_no, rank, death_year, tabaka FROM rawis").fetchall()}
    out = []
    for rid in sorted(why):
        r = info.get(rid)
        if r is None:
            continue
        out.append({"rawi_id": rid, "name": r[1], "nickname": r[2], "rank_no": r[3], "label": r[4],
                    "death_year": r[5], "tabaka": r[6], "why": sorted(why[rid])})
    return out


# ---------------------------------------------------------------- fetch: Taqrib / Tahrir entries

def _queries(s: dict) -> list[str]:
    nm = (s["name"] or "").split()
    nick = s.get("nickname") or ""
    qs = [" ".join(nm[:5]), " ".join(nm[:4]), nick, " ".join(nm[:3]), "ال" + " ".join(nm[:3])]
    if s["rawi_id"] in BRIEF_SEED:
        qs.insert(0, BRIEF_SEED[s["rawi_id"]])
    out = []
    for q in qs:
        q = q.strip()
        if q and q not in out and len(q.split()) >= 2:
            out.append(q)
    return out


_VOWEL_NOTE = re.compile(r"^(?:ب(?:فتح|كسر|ضم|سكون|تشديد|تخفيف|التحتانيه|المهمله|المعجمه|الموحده|النون|الزاي|الراء|"
                         r"الياء|المثلثه|المثناه|القاف|الفاء|الجيم|الحاء|الخاء|العين|الغين|الشين|السين|الصاد|الضاد|"
                         r"الطاء|الظاء|الذال|الدال|الكاف|اللام|الميم|الهاء|الواو)|اوله|ثانيه|ثالثه|اخره|الميم|وتخفيف|وتشديد|"
                         r"وفتح|وكسر|وضم|وسكون|مصغر|مصغرا|مكبر|المهمله|المعجمه|الموحده|التحتانيه|مفتوحه|مكسوره|مضمومه|"
                         r"ساكنه|بعدها|ثم|و?قيل|ويقال|مهمله|معجمه|موحده|تحتانيه|خفيفه|ثقيله|مشدده|اوله|وبالفاء|وبالقاف)$")


def entry_line(text: str, name: str) -> tuple[str | None, str | None, int]:
    """provenance._entry, tolerant of the vowelling notes the Taqrīb prints inside a name («سماك بكسر
    أوله وتخفيف الميم ابن حرب»): those words are dropped from the line before the prefix is read."""
    from itibar import provenance
    best = provenance._entry(text, name)
    lines = text.split("\n")
    words = provenance._norm(name).split()
    for i, line in enumerate(lines):
        m = re.match(r"\s*([٠-٩]+)\s*-\s*(.*)", line)
        if not m:
            continue
        raw = [w for w in lists.normalize(m.group(2)).split()[:24] if not _VOWEL_NOTE.match(w)]
        body = provenance._norm(" ".join(raw)).split()
        k = 0
        while k < min(len(words), len(body)) and body[k] == words[k]:
            k += 1
        while k and words[k - 1] == "بن":
            k -= 1
        if k >= 3 and k > best[2]:
            best = ("\n".join([line.strip()] + _continuation(lines, i)), m.group(1), k)
    if best[0]:
        # provenance._entry keeps only the «•» lines after the entry; Tahrir's lists run on in plain
        # paragraphs («أما اختلاطه فنحن ذاكرون هنا من روى عنه قبل الاختلاط وهم: …»)
        for i, line in enumerate(lines):
            if line.strip() == best[0].split("\n")[0]:
                best = ("\n".join([line.strip()] + _continuation(lines, i)), best[1], best[2])
                break
    return best


def _continuation(lines: list[str], i: int, n: int = 10) -> list[str]:
    """The lines after entry line i up to the next numbered entry (Tahrir's «بل:», comments, lists)."""
    out = []
    for x in lines[i + 1:i + 1 + n]:
        if re.match(r"\s*[٠-٩]+\s*-", x):
            break
        if x.strip():
            out.append(x.strip())
    return out


def refresh_tahrir(path: Path = SRC_TAQRIB) -> int:
    """Re-read each accepted Tahrir entry from its page with the continuation lines (the first fetch kept
    only the «•» lines)."""
    recs = [json.loads(x) for x in open(path, encoding="utf-8")]
    con = data.views()
    nas = dict(con.sql("SELECT id, nasab FROM rawis WHERE nasab IS NOT NULL").fetchall())
    lists._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "itibar", "version": "0.5"}})
    n = 0
    for r in recs:
        s = {**r, "nasab": nas.get(r["rawi_id"])}
        if not (r.get("tahrir_page") and entry_ok(r.get("tahrir_line"), s, int(r.get("tahrir_prefix_words") or 0))):
            continue
        page = lists._open(TAHRIR, int(r["tahrir_page"]))
        text = page.get("text", "")
        first = r["tahrir_line"].split("\n")[0]
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == first.strip():
                r["tahrir_line"] = "\n".join([line.strip()] + _continuation(lines, i))
                n += 1
                break
        time.sleep(1.0)
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return n


def fetch_taqrib(out: Path = SRC_TAQRIB, only_missing: bool = True, refetch: set[int] | str | None = None) -> int:
    """Taqrīb and Taḥrīr entry lines for every seed narrator (provenance.py's search and entry
    reader). Resumable: narrators already in the file are kept when only_missing, except those in
    `refetch`. A narrator the brief names is also matched under the name the books print
    (BRIEF_SEED: «سعيد بن أبي عروبة» for the data's «سعيد بن مهران»)."""
    from itibar import provenance
    lists._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "itibar", "version": "0.5"}})
    have = {}
    if only_missing and out.exists():
        have = {json.loads(x)["rawi_id"]: x for x in open(out, encoding="utf-8")}
    seeds = seed()
    if refetch == "unidentified":            # seeds with no entry passing the identity check in either book
        con = data.views()
        nas = dict(con.sql("SELECT id, nasab FROM rawis WHERE nasab IS NOT NULL").fetchall())
        refetch = set()
        for s in seeds:
            r = json.loads(have[s["rawi_id"]]) if s["rawi_id"] in have else {}
            ss = {**s, "nasab": nas.get(s["rawi_id"])}
            if not (entry_ok(r.get("taqrib_line"), ss, int(r.get("taqrib_prefix_words") or 0))
                    or entry_ok(r.get("tahrir_line"), ss, int(r.get("tahrir_prefix_words") or 0))):
                refetch.add(s["rawi_id"])
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for s in seeds:
            if s["rawi_id"] in have and s["rawi_id"] not in (refetch or ()):
                f.write(have[s["rawi_id"]] if have[s["rawi_id"]].endswith("\n") else have[s["rawi_id"]] + "\n")
                continue
            rec = dict(s)
            late = int(s.get("tabaka") or 0) > 12      # after the Taqrib's twelve layers: no entry to find
            for book, tag in ((TAQRIB, "taqrib"), (TAHRIR, "tahrir")):
                best = (None, None, 0, None, None)
                for q in ([] if late else _queries(s)):
                    r = provenance._call("shamela_find_scoped", {"query": q, "book_ids": [book], "limit": 5,
                                                                 "difficulty": "easy"})
                    for src in (r.get("evidence") or {}).get("sources") or []:
                        for nm in [s["name"]] + ([BRIEF_SEED[s["rawi_id"]]] if s["rawi_id"] in BRIEF_SEED else []):
                            line, num, k = entry_line(src.get("text", ""), nm)
                            if k > best[2] and provenance._same_person(line, s.get("tabaka"), nm):
                                best = (line, num, k, src.get("citation", {}).get("markdown"), src.get("page_id"))
                    time.sleep(1.0)
                    if best[2] >= 3:
                        break
                line, num, k, cit, page = best
                rec[f"{tag}_line"], rec[f"{tag}_number"], rec[f"{tag}_citation"] = line, num, cit
                rec[f"{tag}_page"], rec[f"{tag}_prefix_words"] = page, k
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
    return n


def load_taqrib(path: Path = SRC_TAQRIB) -> dict[int, dict]:
    if not path.exists():
        return {}
    return {r["rawi_id"]: r for r in (json.loads(x) for x in open(path, encoding="utf-8"))}


def fetch_pages(book: int, first: int, last: int, out: Path) -> int:
    """Pages first..last of a Shamela book, one JSON line per page (body text and citation; the modern
    editors' footnotes are not kept: nothing here reads them)."""
    lists._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "itibar", "version": "0.5"}})
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for page in range(first, last + 1):
            r = lists._open(book, page)
            f.write(json.dumps({"page_id": page, "citation": (r.get("citation") or {}).get("markdown"),
                                "text": r.get("text", "")}, ensure_ascii=False) + "\n")
            n += 1
            time.sleep(1.2)
    return n


def trim_sources() -> None:
    """Keep in lists/source/ only what the pipeline reads: the body text of the pages (no editors'
    footnotes), and of al-Kawakib only Ibn al-Kayyal's own pages (the editor's appendices are not read)."""
    for path, last in ((SRC_KAWAKIB, KAWAKIB_LAST_PAGE), (SRC_ALAI, 10 ** 6), (SRC_IGHTIBAT, 10 ** 6), (SRC_RAJAB, 10 ** 6)):
        if not path.exists():
            continue
        rows = [json.loads(x) for x in open(path, encoding="utf-8")]
        rows = [{"page_id": r["page_id"], "citation": r.get("citation"), "text": r.get("text", "")}
                for r in rows if r["page_id"] <= last]
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- al-Kawakib al-Nayyirat

def kawakib_pages(path: Path = SRC_KAWAKIB) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in open(path, encoding="utf-8")]


KAWAKIB_LAST_PAGE = 423     # Ibn al-Kayyal's 70 entries; page 424 opens the editor's appendices («الملحق الأول»)


def kawakib_entries(path: Path = SRC_KAWAKIB) -> list[dict]:
    """Entries of al-Kawākib al-Nayyirāt (Ibn al-Kayyāl's own 70; the editor's two appendices of
    narrators the author did not list are left out, as the editor's appendix of the mudallisin
    book is, D57): the numbered heads («١ - …») with their text up to the next head; the page of
    the head."""
    pages = [p for p in kawakib_pages(path) if p["page_id"] <= KAWAKIB_LAST_PAGE]
    if not pages:
        return []
    full = "".join(f"\n<<P{p['page_id']}>>\n" + (p.get("text") or "") for p in pages)
    heads = list(re.finditer(r"(?:^|\n)\s*([٠-٩]{1,3})\s*[-–ـ]\s*", full))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(full)
        seg = full[m.end():end]
        pg = re.findall(r"<<P(\d+)>>", full[:m.start()])
        text = re.sub(r"\s*<<P\d+>>\s*", " ", seg).strip()
        out.append({"number": lists._ar_int(m.group(1)) if hasattr(lists, "_ar_int") else m.group(1),
                    "page_id": int(pg[-1]) if pg else pages[0]["page_id"], "text": text,
                    "head": " ".join(text.split()[:12])})
    return out


def numbered_entries(path: Path, first: int = 1, last: int = 10 ** 6) -> list[dict]:
    """Numbered entries («N - name …», an optional «[rumuz]» after the dash) of a fetched book."""
    if not path.exists():
        return []
    pages = [json.loads(x) for x in open(path, encoding="utf-8")]
    pages = [p for p in pages if first <= p["page_id"] <= last]
    full = "".join(f"\n<<P{p['page_id']}>>\n" + (p.get("text") or "") for p in pages)
    heads = list(re.finditer(r"(?:^|\n)\s*([٠-٩]{1,3})\s*[-–ـ]\s*(?:\[[^\]]{0,30}\])?\s*", full))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(full)
        pg = re.findall(r"<<P(\d+)>>", full[:m.start()])
        text = re.sub(r"\s*<<P\d+>>\s*", " ", full[m.end():end]).strip()
        out.append({"number": lists._ar_int(m.group(1)), "page_id": int(pg[-1]) if pg else pages[0]["page_id"],
                    "text": text, "head": " ".join(text.split()[:12])})
    return out


def alai_entries() -> list[dict]:
    """al-ʿAlāʾī's 46 entries with the category he assigns («فهو من القسم الأول» …): 1 = the
    confusion did him no harm, 2 = weak before it, 3 = sound before, to be told apart."""
    out = []
    for e in numbered_entries(SRC_ALAI, 2, 119):
        cats = re.findall(r"القسم\s+(الأول|الاول|الثاني|الثالث)", e["text"])
        e["category"] = {"الأول": 1, "الاول": 1, "الثاني": 2, "الثالث": 3}[cats[-1]] if cats else None
        out.append(e)
    return out


def ightibat_entries() -> list[dict]:
    return numbered_entries(SRC_IGHTIBAT, 3, 128)


# Ibn Rajab, Sharh 'Ilal al-Tirmidhi, «القسم الثاني» (pages 673-755): the narrators of its three
# parts, as printed (read from lists/source/ibn_rajab_9552.jsonl): (name, page, part)
IBN_RAJAB_NAMES = [
    ("عطاء بن السائب", 674, "time"), ("حصين بن عبد الرحمن", 679, "time"), ("سعيد بن إياس الجريري", 682, "time"),
    ("سعيد بن أبي عروبة", 683, "time"), ("الفضل بن دكين", 684, "time"), ("ابن أبي عدي", 685, "time"),
    ("عبد الرحمن بن عبد الله المسعودي", 687, "time"), ("عبد الوهاب بن عبد المجيد الثقفي", 689, "time"),
    ("سفيان بن عيينة", 689, "time"), ("صالح بن نبهان مولى التوأمة", 689, "time"), ("أبان بن صمعة", 690, "time"),
    ("محمد بن الفضل السدوسي", 690, "time"), ("أبو قلابة الرقاشي", 691, "time"), ("عبد الرزاق بن همام", 692, "time"),
    ("أبو حمزة السكري", 694, "time"), ("علي بن مسهر", 695, "time"), ("عبد العزيز بن محمد الدراوردي", 697, "time"),
    ("همام بن يحيى العوذي", 698, "time"), ("شريك بن عبد الله النخعي", 699, "time"), ("حماد بن أبي سليمان", 701, "time"),
    ("حفص بن غياث", 702, "time"), ("شبيب بن سعيد الحبطي", 703, "time"), ("إبراهيم بن سعد الزهري", 703, "time"),
    ("أبو داود الطيالسي", 704, "time"), ("يونس بن يزيد الأيلي", 705, "time"), ("عبد الصمد بن حسان", 705, "time"),
    ("معمر بن راشد", 706, "place"), ("هشام بن عروة", 708, "place"), ("عبد الرحمن بن أبي الزناد", 708, "place"),
    ("يزيد بن هارون", 709, "place"), ("عبيد الله بن عمر العمري", 711, "place"), ("الوليد بن مسلم الدمشقي", 711, "place"),
    ("إسماعيل بن عياش", 712, "place"), ("بقية بن الوليد", 713, "place"), ("فرج بن فضالة", 714, "place"),
    ("خالد بن مخلد القطواني", 714, "place"), ("زهير بن محمد الخراساني", 716, "place"),
    ("محمد بن عبد الرحمن بن أبي ذئب", 718, "place"), ("أيوب بن عتبة اليمامي", 719, "place"),
    ("حماد بن سلمة", 720, "shaykh"), ("جرير بن حازم", 723, "shaykh"), ("محمد بن عجلان", 726, "shaykh"),
    ("عاصم بن بهدلة", 727, "shaykh"), ("هشام بن حسان", 727, "shaykh"), ("سليمان التيمي", 727, "shaykh"),
    ("جعفر بن برقان", 729, "shaykh"), ("معقل بن عبيد الله الجزري", 732, "shaykh"), ("المغيرة بن مسلم", 733, "shaykh"),
    ("عكرمة بن عمار", 734, "shaykh"), ("سماك بن حرب", 735, "shaykh"), ("عمرو بن أبي عمرو", 736, "shaykh"),
    ("داود بن الحصين", 737, "shaykh"), ("الأوزاعي", 738, "shaykh"), ("منصور بن المعتمر", 740, "shaykh"),
    ("حماد بن زيد", 740, "shaykh"), ("حبيب بن أبي ثابت", 740, "shaykh"), ("عبد الكريم بن مالك الجزري", 742, "shaykh"),
    ("مطر بن طهمان الوراق", 744, "shaykh"), ("أبو معشر نجيح السندي", 744, "shaykh"), ("عمر بن إبراهيم البصري", 745, "shaykh"),
    ("عبد المجيد بن عبد العزيز بن أبي رواد", 746, "shaykh"), ("هشام بن سليمان المخزومي", 746, "shaykh"),
    ("ورقاء بن عمر اليشكري", 746, "shaykh"), ("عبد الرزاق بن عمر الدمشقي", 747, "shaykh"),
    ("إسحاق بن راشد الجزري", 748, "shaykh"), ("قبيصة بن عقبة", 750, "shaykh"), ("يعلى بن عبيد", 751, "shaykh"),
    ("محمد بن خازم أبو معاوية الضرير", 751, "shaykh"), ("محمد بن كثير الصنعاني", 751, "shaykh"),
    ("زيد بن الحباب العكلي", 752, "shaykh"), ("سلمة الأحمر", 752, "shaykh"), ("يونس بن أبي إسحاق", 752, "shaykh"),
]


def _entry_name(e: dict, n_name: int = 8) -> str:
    """The narrator's name at the head of an entry: up to the first colon or full stop within the
    first twelve words (al-ʿAlāʾī writes «سعيد بن أبي عروبة: من أصحاب قتادة …»), else n_name words."""
    head = " ".join(e["text"].split()[:12])
    m = re.search(r"[:.،(]", head)
    name = head[:m.start()] if m and len(head[:m.start()].split()) >= 2 else " ".join(e["text"].split()[:n_name])
    return re.sub(r"\s+", " ", name).strip()


def _match_entries(ents: list[dict], con, n_name: int = 8) -> list[dict]:
    """Narrator of each entry matched to rawis with the mudallisin matcher (idf name tokens, ism +
    father agreeing). auto: its rule (a) — score >= auto_min_score and margin >= auto_min_margin —
    or, the counterpart of its rule (b) for these books, the source's own has_ikhtilat flag on the
    candidate and on no namesake among the five, with score >= flag_min_score and margin >= flag_min_margin."""
    from itibar import mudallisin
    if not ents:
        return []
    cfg_m = mudallisin._cfg()
    proto = [{"number": i, "tier": 0, "name": _entry_name(e, n_name), "note": e["text"][:400]} for i, e in enumerate(ents)]
    cands = mudallisin.candidates(proto, con)
    flag = {int(r[0]) for r in con.sql("SELECT id FROM rawis WHERE has_ikhtilat = 1").fetchall()}
    by: dict[int, list[dict]] = defaultdict(list)
    for c in cands:
        if c["rawi_id"] is not None:
            by[int(c["number"])].append(c)
    out = []
    for i, e in enumerate(ents):
        cs = sorted(by.get(i, []), key=lambda c: c["rank"])
        top = cs[0] if cs else None
        margin = (top["score"] - cs[1]["score"]) if len(cs) > 1 else (top["score"] if top else 0)
        seq = bool(top) and float(top["f_sequence"]) == 1.0
        rule_a = seq and top["score"] >= float(cfg_m["auto_min_score"]) and margin >= float(cfg_m["auto_min_margin"])
        rival = any(int(c["rawi_id"]) in flag and float(c["f_sequence"]) == 1.0 for c in cs[1:])
        rule_b = (seq and int(top["rawi_id"]) in flag and not rival and top["score"] >= float(cfg_m["flag_min_score"]) - 0.15
                  and margin >= float(cfg_m["flag_min_margin"]))
        ok = rule_a or rule_b
        out.append({**e, "name": _entry_name(e, n_name), "rawi_id": int(top["rawi_id"]) if ok else None,
                    "match_status": "auto" if ok else "needs_review", "match_score": top["score"] if top else None,
                    "match_rule": "a" if rule_a else ("b_has_ikhtilat" if rule_b else None)})
    return out


def alai_matched(con=None) -> list[dict]:
    return _match_entries(alai_entries(), con or data.views())


def ightibat_matched(con=None) -> list[dict]:
    return _match_entries(ightibat_entries(), con or data.views())


def ibn_rajab_matched(con=None) -> list[dict]:
    ents = [{"number": i, "page_id": pg, "text": nm, "head": nm, "part": part}
            for i, (nm, pg, part) in enumerate(IBN_RAJAB_NAMES)]
    return _match_entries(ents, con or data.views())


def kawakib_entries_matched(con=None) -> list[dict]:
    """Each Kawākib entry's narrator matched to rawis (_match_entries; unmatched: rawi_id None)."""
    return _match_entries(kawakib_entries(), con or data.views())


# ---------------------------------------------------------------- adjacency (candidates for condition names)

def adjacency(rids: list[int], con=None) -> tuple[dict[int, Counter], dict[int, Counter]]:
    """Per narrator: Counter of his teachers (next position up) and of his students (next
    position down) over every chain, with link counts."""
    con = con or data.views()
    con.execute("CREATE OR REPLACE TEMP TABLE _cr AS SELECT unnest(?::BIGINT[]) AS rid", [sorted(set(rids))])
    teach: dict[int, Counter] = defaultdict(Counter)
    stud: dict[int, Counter] = defaultdict(Counter)
    for a, b, n in con.sql("""SELECT x.rawi_id, t.rawi_id, count(*) FROM sanad_rawis x
                              JOIN sanad_rawis t ON t.sanad_id = x.sanad_id AND t.pos = x.pos + 1
                              WHERE x.rawi_id IN (SELECT rid FROM _cr) GROUP BY 1, 2""").fetchall():
        teach[int(a)][int(b)] = int(n)
    for a, b, n in con.sql("""SELECT x.rawi_id, s.rawi_id, count(*) FROM sanad_rawis x
                              JOIN sanad_rawis s ON s.sanad_id = x.sanad_id AND s.pos = x.pos - 1
                              WHERE x.rawi_id IN (SELECT rid FROM _cr) GROUP BY 1, 2""").fetchall():
        stud[int(a)][int(b)] = int(n)
    return teach, stud


# ---------------------------------------------------------------- the rulings in force

@dataclass(frozen=True)
class Ruling:
    rule_id: str
    rawi_id: int
    kind: str
    condition: str                    # as printed (names), or the unobservable condition's tag
    ids: frozenset[int]               # teachers (from_shaykh), students (via_student, ikhtilat_*)
    region: str | None                # region tag (region_of_shaykh)
    effect: str                       # level:N | defect:light | accepted | none
    observable: bool
    source: str                       # book and page
    quote: str
    status: str                       # auto | human

    @property
    def level(self) -> int | None:
        return int(self.effect.split(":")[1]) if self.effect.startswith("level:") else None


def load_rulings(path: Path | None = None) -> dict[int, list[Ruling]]:
    """rawi id -> rulings in force (auto and human rows of lists/conditional_confirmed.csv)."""
    path = path or CONF_PATH
    out: dict[int, list[Ruling]] = defaultdict(list)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("status") not in ("auto", "human"):
                continue
            ids = frozenset(int(x) for x in (r.get("condition_ids") or "").split() if x.strip().isdigit())
            out[int(r["rawi_id"])].append(Ruling(
                rule_id=r["rule_id"], rawi_id=int(r["rawi_id"]), kind=r["kind"], condition=r.get("condition") or "",
                ids=ids,
                region=(r.get("region") or None), effect=r["effect"] or "none",
                observable=str(r.get("observable", "true")).lower() != "false",
                source=f"{r.get('source_book', '')} {r.get('citation', '')}".strip(), quote=r.get("quote") or "",
                status=r["status"]))
    return dict(out)


def regions(con=None) -> dict[int, frozenset[str]]:
    """rawi id -> region tags, from the nisba tokens of rawis.nasab and the places of rawis.iqama
    against derive.conditional_rules.regions (rawis has no region column as such)."""
    con = con or data.views()
    reg = cfg().get("regions") or {}
    if not reg:
        return {}
    table = {tag: ({lists.normalize(x) for x in (v.get("nisba") or [])},
                   {lists.normalize(x) for x in (v.get("places") or [])}) for tag, v in reg.items()}
    out = {}
    for rid, nasab, iqama in con.sql("SELECT id, nasab, iqama FROM rawis WHERE nasab IS NOT NULL OR iqama IS NOT NULL"
                                     ).fetchall():
        nt = {lists.normalize(x) for x in re.split(r"[،,]", nasab or "") if x.strip()}
        it = {lists.normalize(x) for x in re.split(r"[،,]", iqama or "") if x.strip()}
        tags = frozenset(tag for tag, (ns, ps) in table.items() if (nt & ns) or (it & ps))
        if tags:
            out[int(rid)] = tags
    return out


# ---------------------------------------------------------------- reading the entries

_ART = re.compile(r"^ال(?=..)")
_PARTS = {"بن", "ابن", "بنت"}


def _n(t: str | None) -> str:
    """lists.normalize, «ابن» as «بن», the article dropped from every word."""
    out = []
    for w in lists.normalize(t or "").split():
        w = "بن" if w == "ابن" else w
        out.append(_ART.sub("", w) if len(w) > 3 else w)
    return " ".join(out)


def entry_ok(line: str | None, s: dict, k: int) -> bool:
    """Identity check on a fetched entry line (provenance's prefix reader can land on a namesake):
    at least four words of the data's name in order, or three with a nisba of his nickname or
    nasab in the entry, or three with the source's own label inside the entry's verdict."""
    if not line:
        return False
    if k >= 4:
        return True
    if k < 3:
        return False
    body = set(_n(line.split("\n")[0]).split())
    nis = set(_n(s.get("nickname")).split()[1:]) | set(_n((s.get("nasab") or "").replace("،", " ")).split())
    nis -= set(_n(s.get("name")).split()) | _PARTS
    if nis & body:
        return True
    lab = _n(s.get("label"))
    return bool(lab) and len(lab.split()) >= 2 and lab in _n(line)


def verdict_texts(rec: dict) -> list[tuple[int, str, str, str, str | None]]:
    """(book, head verdict, whole entry text, the line as printed, citation) for the Taqrīb entry and the
    Taḥrīr entry. The head verdict is what precedes the tabaqa («صدوق»); the whole text runs on past it
    (Ibn Lahīʿa's «من السابعة خلط بعد احتراق كتبه ورواية ابن المبارك …») and, for Taḥrīr, includes its
    «بل:» revision and comments."""
    from itibar import provenance
    out = []
    for book, tag in ((TAQRIB, "taqrib"), (TAHRIR, "tahrir")):
        line = rec.get(f"{tag}_line")
        if not rec.get(f"{tag}_ok"):
            continue
        head = provenance._verdict(line, rec["name"]) or ""
        first = re.sub(r"^\s*[٠-٩]+\s*-\s*", "", line.split("\n")[0])
        if ":" in first and book == TAHRIR:
            first = first.split(":", 1)[1]
        rest = "\n".join(line.split("\n")[1:])
        out.append((book, head, (first + "\n" + rest).strip(), line, rec.get(f"{tag}_citation")))
    return out


# verdict head formulas -> Taqrib level (longest first); a qualifier after the head is the
# ruling's business, not the head's
HEADS = [("ثقة ثبت", 2), ("ثقة حافظ", 2), ("ثقة متقن", 2), ("ثقة ثقة", 2), ("ثقة امام", 2), ("حافظ ثقة", 2),
         ("ثقة حجة", 2), ("ثقة", 3), ("صدوق سيء الحفظ", 5), ("صدوق يهم", 5), ("صدوق له اوهام", 5),
         ("صدوق يخطي", 5), ("صدوق كثير الخطا", 5), ("صدوق ربما وهم", 5), ("صدوق ربما اخطا", 5),
         ("صدوق في حفظه شيء", 5), ("صدوق يغرب", 5), ("صدوق", 4), ("لا باس به", 4), ("مقبول", 6),
         ("مستور", 7), ("مجهول الحال", 7), ("ضعيف", 8), ("لين الحديث", 8), ("مجهول", 9), ("متروك", 10)]


def head_level(verdict: str) -> int | None:
    """The Taqrib level of the verdict's head formula: the earliest formula found (the longest at a tie)."""
    t = " " + lists.normalize(verdict) + " "
    best = None
    for h0, lv in HEADS:
        h = lists.normalize(h0)
        i = t.find(" " + h + " ")
        if i >= 0 and (best is None or i < best[0] or (i == best[0] and len(h) > best[2])):
            best = (i, lv, len(h))
    return best[1] if best else None


# condition phrases (normalized text). X: the names, up to the effect word.
_EFFECT_WEAK = r"(?:(?:فهي|فهو|ففيها|ففيه|فيها|فيه) )?(?:مضطربه|ضعيفه|ضعيف|ضعف|فيها لين|ففيها لين|ففيه لين|فيه لين|لين|شيء|شيا|شييا|مناكير|منكره|فيه مقال|بأخره|باخره)"
_X = r"((?:(?!\b(?:من|مات|وكان|وهو|وقد|قال|ثقه|صدوق)\b)[^،.:]){2,60}?)"
PATTERNS = [
    # from_shaykh, weak: «إلا في روايته عن X ففيها لين», «روايته عن X خاصة مضطربة», «في حديثه عن X ضعف»
    ("from_shaykh", "defect:light", re.compile(r"الا (?:في|ان في|ان) (?:روايته|حديثه|سماعه) عن " + _X + r"(?: خاصه)?(?: ف| )?" + _EFFECT_WEAK)),
    ("from_shaykh", "defect:light", re.compile(r"(?:روايته|حديثه|سماعه) عن " + _X + r"(?: خاصه)? " + _EFFECT_WEAK)),
    ("from_shaykh", "defect:light", re.compile(r"الا في (?:روايته|حديثه) عن " + _X + r"(?=$| ف| و|،)")),
    ("from_shaykh", "defect:light", re.compile(r"ضعيف في (?:حديث|روايته عن|حديثه عن) " + _X + r"(?=$|،| و)")),
    ("from_shaykh", "defect:light", re.compile(r"(?:ثقه|صدوق) في غير " + _X + r"(?=$|،| و| باتفاقهم)")),
    ("from_shaykh", "defect:light", re.compile(r"تكلم(?:وا)? في (?:روايته|حديثه) عن " + _X + r"(?=$|،| و| ل)")),
    ("from_shaykh", "accepted", re.compile(r"(?:من )?اثبت الناس في " + _X + r"(?=$|،| و)")),
    # region: «صدوق في روايته عن أهل بلده مخلط في غيرهم» (Taḥrīr prints «في رواته من أهل بلده»)
    ("region_of_shaykh", "head", re.compile(r"في (?:روايته|رواته|حديثه) (?:عن|من) (اهل بلده|الشاميين|اهل الشام)")),
    # via_student: «ورواية ابن المبارك وابن وهب عنه أعدل من غيرهما»
    ("via_student", "head", re.compile(r"(?:روايه|وروايه|سماع|وسماع) " + _X + r" (?:عنه|منه) (?:اعدل|اصح|اقوي|صحيحه|صحيح|مستقيمه|جيده|قديم)")),
    # Tahrir: «وحديثه صحيح إذا روى عنه العبادلة: ابن المبارك، وابن وهب …» (the names after the colon)
    ("via_student", "sahih", re.compile(r"(?:حديثه )?صحيح اذا روي عنه (?:العبادله )?" + r"((?:(?!\b(?:فانهم|فانه|وقد|لانهم)\b).){2,120}?)(?= فانهم| فانه| وقد|$)")),
]
# Tahrir disputing what Ibn Hajar wrote (the labels follow Tahrir, audit §11.7): rows read from the
# Taqrib that Tahrir's comment disputes wait for review
DISPUTE = re.compile(r"(?:فيه نظر|ليس بجيد|لا معنى لذكره|لكان احسن|لم يختلط|من المبالغه|لم يثبت)")
IKHTILAT = re.compile(r"(?<!لم )(?<!ما )\b[وف]?(?:اختلط|اختلاطه|خلط|تغير|تغيره)\b")
IKHTILAT_MINOR = re.compile(r"(?:لم يفحش|قليلا|يسيرا|بيسير|يسير|لم يضر|فلم يحدث|ولم يحدث|ما حدث)")
UNOBSERVABLE = [
    ("book_vs_memory", re.compile(r"(?:من حفظه|من كتابه|كتابه صحيح|كتبه صحيحه|اذا حدث من حفظ)")),
    ("books_burned", re.compile(r"(?:احتراق كتبه|احترقت كتبه|احتراق منزله)")),
    # a hearing or narrating in a place («فيما حدث به بالبصرة», «من سمع منه ببغداد», «لما قدم بغداد»), not a
    # residence («قاضي بواسط») nor al-Hasan's «حدثوا وخطبوا بالبصرة» (his wording, a tadlis matter)
    ("place_of_hearing", re.compile(r"(?:حدث به|حدث|سمع منه|سمعوا منه|سماعه) (?:ب|في )?(?:بغداد|البصره|مصر|الكوفه|اليمن|"
                                    r"مكه|الشام|واسط)|(?:حدث به|سمع منه|سمعوا منه) ب(?:بغداد|البصره|مصر|الكوفه|اليمن|مكه|"
                                    r"الشام|واسط)|لما قدم")),
    ("material_inserted", re.compile(r"(?:ادخل عليه|يتلقن|تلقن|لقن)")),
]


_STOPW = {"بن", "عن", "في", "و", "من", "ابي", "ابو", "ام", "عنه", "منه", "خاصه", "غير", "اهل", "بلده", "عبادله",
          "اذا", "روي", "صحيح"}


def _toks(text: str) -> list[list[str]]:
    """Normalized tokens, each with its alternatives (a leading conjunction «و» removed)."""
    out = []
    for w in _n(text).split():
        alts = [w]
        if w.startswith("و") and len(w) > 3:
            a = w[1:]
            alts.append("بن" if a == "ابن" else (_ART.sub("", a) if len(a) > 3 else a))
        out.append(alts)
    return out


@dataclass
class Cand:
    rid: int
    links: int
    ism: str
    father: str | None
    kunya: str | None
    extra: list[str]                 # nisba / laqab tokens of the nickname
    alt_father: str | None = None    # the nickname's father when it differs («إسماعيل بن علية» for «بن إبراهيم»)


def _cand(rid: int, links: int, name: str | None, nick: str | None) -> Cand:
    nt = _n(nick).split()
    mt = _n(name).split()
    def ism_of(t):
        if len(t) >= 2 and t[0] in ("عبد", "ابو", "ابي", "ام"):
            return " ".join(t[:2]), t[2:]
        return (t[0], t[1:]) if t else ("", [])
    ism, rest = ism_of(mt or nt)
    father = rest[1] if len(rest) >= 2 and rest[0] == "بن" else None
    if father in ("عبد", "ابي", "ابو") and len(rest) >= 3:
        father = rest[1] + " " + rest[2]
    kunya = None
    if nt and nt[0] in ("ابو", "ابي", "ام") and len(nt) >= 2:
        kunya = "ابو " + nt[1] if nt[0] != "ام" else "ام " + nt[1]
    nism, nrest = ism_of(nt)
    nfather = nrest[1] if len(nrest) >= 2 and nrest[0] == "بن" else None
    alt = nfather if (nfather and nism == ism and nfather != father) else None
    extra = [w for w in nrest if w not in _PARTS and w != father and w != alt
             and (father is None or w not in father.split())]
    if nism and nism != ism and nism.split()[0] not in ("ابو", "ام"):
        extra.append(nism)            # the nickname's ism when the data name has another (rare)
    return Cand(rid=rid, links=links, ism=ism, father=father, kunya=kunya, extra=extra, alt_father=alt)


def find_names(text: str, cands: list[Cand], dominance: float) -> tuple[dict[int, str], list[str], list[str]]:
    """Narrators of `cands` named in `text`: ism + father («هشام بن عروة»), «ابن» + father
    («ابن المبارك»), a kunya («أبي إسحاق»), a distinctive nisba or laqab («الثوري», «الأعمش»), or an
    ism alone when no other candidate bears it («شعبة»). Returns (rid -> how matched, ambiguous
    spans, name tokens left unmatched). A span several candidates fit resolves to one only when it
    carries at least `dominance` of their links with the narrator."""
    toks = _toks(text)
    flat = [t[-1] if len(t) > 1 else t[0] for t in toks]
    raw = lists.normalize(text).split()
    raw = raw if len(raw) == len(toks) else flat
    n = len(toks)

    def at(i: int, seq: list[str]) -> bool:
        if i + len(seq) > n:
            return False
        return all(seq[j] in toks[i + j] or (seq[j] in ("ابو", "ابي") and toks[i + j][0] in ("ابو", "ابي"))
                   for j in range(len(seq)))

    ism_count = Counter(c.ism for c in cands)
    extra_count = Counter(w for c in cands for w in set(c.extra))
    hits: dict[int, list[tuple[Cand, str, int]]] = defaultdict(list)    # token index -> (cand, how, length)
    for c in cands:
        pats = []
        for fa in [x for x in (c.father, c.alt_father) if x]:
            pats.append(("ism_father", c.ism.split() + ["بن"] + fa.split()))
            pats.append(("ibn_father", ["بن"] + fa.split()))
        if c.kunya:
            pats.append(("kunya", c.kunya.split()))
        # a nisba or a lone ism several adjacent narrators share still proposes them all; the span then
        # resolves by dominance (find_names below) or stays ambiguous
        for w in c.extra:
            if len(w) > 3 and w not in _STOPW:
                pats.append(("nisba", [w]))
        if len(c.ism.split()) == 1 and len(c.ism) > 2 and c.ism not in _STOPW:
            pats.append(("ism", [c.ism]))
        for how, seq in pats:
            for i in range(n):
                if how in ("ism", "nisba") and i > 0 and flat[i - 1] in ("بن", "ابو", "ابي", "ام", "عبد"):
                    continue                  # «ابن وهب»: a father's name, not a man called Wahb
                if how == "nisba" and i > 1 and flat[i - 2] == "بن":
                    continue                  # «ابن يزيد المقرئ»: the nisba describes that «ابن يزيد»
                if how in ("ism", "kunya") and i + len(seq) < n and flat[i + len(seq)] == "بن":
                    continue                  # «أحمد بن شبويه» names his father: only ism + father can match it
                if at(i, seq):
                    # «بن X» counts alone only as «ابن X»; inside «Y بن X» it belongs to the longer pattern
                    if how == "ibn_father" and i > 0 and raw[i] not in ("ابن", "وابن"):
                        continue
                    hits[i].append((c, how, len(seq)))
    covered: set[int] = set()
    found: dict[int, str] = {}
    ambiguous: list[str] = []
    for i in sorted(hits):
        if i in covered:
            continue
        L = max(h[2] for h in hits[i])
        best = [h for h in hits[i] if h[2] == L]
        byc = {h[0].rid: h for h in best}
        if len(byc) == 1:
            c, how, _ = best[0]
            found[c.rid] = how
        else:
            # «سفيان الثوري»: the ism fits two Sufyans, the nisba that follows names one of them
            nxt = [h for h in hits.get(i + L, []) if h[0].rid in byc]
            nxt_ids = {h[0].rid for h in nxt}
            tot = sum(h[0].links for h in byc.values()) or 1
            top = max(byc.values(), key=lambda h: (h[0].links, -h[0].rid))
            if len(nxt_ids) == 1:
                rid = next(iter(nxt_ids))
                found[rid] = byc[rid][1] + "+" + nxt[0][1]
                L += max(h[2] for h in nxt)
            elif top[0].links / tot >= dominance:
                found[top[0].rid] = top[1] + "_dominant"
            else:
                ambiguous.append(" ".join(flat[i:i + L]) + " -> " + " ".join(f"r{r}" for r in sorted(byc)))
        covered.update(range(i, i + L))
    own = set()
    byrid = {c.rid: c for c in cands}
    for r in found:
        c = byrid[r]
        own |= (set(c.ism.split()) | set((c.father or "").split()) | set((c.alt_father or "").split())
                | set((c.kunya or "").split()) | set(c.extra))
    left = [flat[i] for i in range(n) if i not in covered and flat[i] not in _STOPW and len(flat[i]) > 2
            and flat[i] not in own]
    return found, ambiguous, left


# ---------------------------------------------------------------- proposals

BEFORE_TRIG = re.compile(r"(?:قبل (?:الاختلاط|اختلاطه|ان يختلط|التغير|تغيره|ان يتغير|احتراق كتبه|الاحتراق|ان تحترق)|"
                         r"في الصحه|قديما|صحيح السماع|سماعه صحيح|سماعهم صحيح|قبل تغيره|قبل الهزيمه|قبل ذهاب بصره)")
AFTER_TRIG = re.compile(r"(?:بعد (?:الاختلاط|اختلاطه|ان اختلط|التغير|تغيره|ان تغير|احتراق كتبه|الاحتراق)|"
                        r"في (?:الاختلاط|اختلاطه|التغير|حال اختلاطه)|بعد الهزيمه)")


_LETTERS_KEEP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_TRIG_B = (r"(?:قبل (?:الاختلاط|اختلاطه|ان يختلط|التغير|تغيره|ان يتغير|احتراق كتبه|الاحتراق|ان تحترق كتبه)|"
           r"في الصحه|قديما)")
# «حديثا», «بأخرة» mean late only in «ممن سمع منه …» (elsewhere «حديثا» is «a hadith»)
_TRIG_A = (r"(?:بعد (?:الاختلاط|اختلاطه|ان اختلط|ما اختلط|التغير|تغيره|احتراق كتبه|الاحتراق)|بعدما اختلط|"
           r"في (?:الاختلاط|اختلاطه|التغير|حال اختلاطه)|حديثا|باخره|اخيرا|في اخر عمره)")
_VERB = r"(?:سمع|روي|كتب|اخذ|حدث|سمعا|سمعوا|رووا)"
_STOP_L = (r"(?=\.|\(|؛|\n| قاله | قال | وقال | وممن | ممن | فممن | ومن | واما | اما | لكن | وذكر | وروي | روي | "
           r"واثبتهم | وارواهم | فسماعه | فحديثه | عن | وليس | ليس | فلا | لانهم | لانه | وكان |$)")
_NAMES = r"(?P<names>(?!فسماعه|فحديثه|فهو|فليس|فلا|فانه|فان)[^.؛\n]{2,700}?)"
LIST_PATTERNS = [
    # trigger first: «وممن سمع منه قبل الاختلاط: A، وB …», «من روى عنه قبل الاختلاط وهم: …»
    ("before", re.compile(r"(?:ممن|من|فممن) " + _VERB + r" (?:منه|عنه) " + _TRIG_B + r"(?: وهم)?\s*:?\s*" + _NAMES + _STOP_L)),
    ("after", re.compile(r"(?:ممن|من|فممن) " + _VERB + r" (?:منه|عنه) " + _TRIG_A + r"(?: وهم)?\s*:?\s*" + _NAMES + _STOP_L)),
    # names first: «وشعبة وسفيان ممن سمع منه قديما», «وجرير وخالد … ممن سمع منه حديثا»
    ("before", re.compile(r"(?P<names>(?:[^\s.؛:]+ ){0,7}[^\s.؛:]+) (?:ممن|فممن) " + _VERB + r" (?:منه|عنه) " + _TRIG_B)),
    ("after", re.compile(r"(?P<names>(?:[^\s.؛:]+ ){0,7}[^\s.؛:]+) (?:ممن|فممن) " + _VERB + r" (?:منه|عنه) " + _TRIG_A)),
    ("before", re.compile(r"(?:سماع|وسماع) (?P<names>[^.،:]{2,60}?) منه (?:صحيح|قديم|قبل)")),
    ("before", re.compile(r"(?P<names>(?:[^\s.؛:]+ ){0,4}[^\s.؛:]+) (?:صحيح السماع منه|سمع منه قبل (?:ان يختلط|اختلاطه|الاختلاط))")),
    ("after", re.compile(r"(?P<names>(?:[^\s.؛:]+ ){0,4}[^\s.؛:]+) (?:سمع منه بعد (?:الاختلاط|اختلاطه)|سمع منه في الاختلاط)")),
]


def _n_keep(text: str) -> str:
    """Diacritics and tatweel stripped and letters unified as lists.normalize does, punctuation kept."""
    t = re.sub("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]", "", text or "").replace("ـ", "")
    return re.sub(r"[ \t]+", " ", t.translate(_LETTERS_KEEP))


def ikhtilat_lists(text: str, students: list[Cand], dominance: float
                   ) -> tuple[set[int], set[int], list[str], list[tuple[int, str]]]:
    """Students the text places before or after the change, read only from explicit list phrases
    (LIST_PATTERNS: «وممن سمع منه قبل الاختلاط: …», «من روى عنه قبل الاختلاط وهم: …», «وممن سمع منه في
    الاختلاط …», «سماع X منه صحيح», «X صحيح السماع منه»); the names in each list are resolved among his
    adjacent students. A student placed on both sides is left out. Returns (before, after, ambiguous,
    [(rid, side)])."""
    t = _n_keep(text)
    ev, amb = [], []
    for k, (side, pat) in enumerate(LIST_PATTERNS):
        for m in pat.finditer(t):
            if k < 2 and re.match(r"\s*(?:ممن|فممن) ", t[m.end():]):
                continue                 # «… قديما A ممن سمع منه حديثا»: A belongs to the clause after it
            found, am, _ = find_names(m.group("names"), students, dominance)
            amb.extend(f"{side}: {x}" for x in am)
            ev.extend((r, side) for r in found)
    sides: dict[int, set[str]] = defaultdict(set)
    for rid, side in ev:
        sides[rid].add(side)
    before = {r for r, ss in sides.items() if ss == {"before"}}
    after = {r for r, ss in sides.items() if ss == {"after"}}
    amb += [f"both sides: r{r}" for r, ss in sides.items() if len(ss) > 1]
    return before, after, amb, ev


def propose(con=None) -> list[dict]:
    """Every proposed ruling row (before the confirmed file's human rows are merged)."""
    con = con or data.views()
    c = cfg()
    dominance = float(c.get("dominance", 0.95))
    recs = load_taqrib()
    seeds = {s["rawi_id"]: s for s in seed(con)}
    nas = dict(con.sql("SELECT id, nasab FROM rawis WHERE nasab IS NOT NULL").fetchall())
    teach, stud = adjacency(list(seeds), con)
    names = {r[0]: (r[1], r[2]) for r in con.sql("SELECT id, name, nickname FROM rawis").fetchall()}
    kaw: dict[int, list[dict]] = defaultdict(list)
    igh: dict[int, list[dict]] = defaultdict(list)
    ala: dict[int, list[dict]] = defaultdict(list)
    for dst, ents in ((kaw, kawakib_entries_matched(con)), (igh, ightibat_matched(con)), (ala, alai_matched(con))):
        for e in ents:
            if e.get("rawi_id") and e.get("match_status") == "auto":
                dst[int(e["rawi_id"])].append(e)
    reg = regions(con)
    alai = {int(e["rawi_id"]): e["category"] for e in alai_matched(con)
            if e.get("rawi_id") and e.get("match_status") == "auto" and e.get("category")}
    rows: list[dict] = []

    def cands(counter: Counter, me: int) -> list[Cand]:
        return [_cand(r, n, *names.get(r, (None, None))) for r, n in counter.items()
                if r in names and r not in (1131, 30000, 30001, 30002, me)]

    for rid, s in sorted(seeds.items()):
        rec = recs.get(rid, {})
        s = {**s, "nasab": nas.get(rid)}
        for tag in ("taqrib", "tahrir"):
            rec[f"{tag}_ok"] = entry_ok(rec.get(f"{tag}_line"), s, int(rec.get(f"{tag}_prefix_words") or 0))
        base = int(s["rank_no"] or 0)
        texts = verdict_texts({**rec, "name": s["name"]}) if rec else []
        T, S = cands(teach.get(rid, Counter()), rid), cands(stud.get(rid, Counter()), rid)
        common = {"rawi_id": rid, "narrator": s["nickname"], "base_level": base, "label": s["label"],
                  "seed": " ".join(s["why"])}
        seen: set[tuple] = set()
        ikh = None                                   # (book, verdict, line, citation, minor)
        for book, head, verdict, line, cit in texts:
            t = _n(verdict)
            clauses = [_n(c) for c in re.split(r"[،.:؛\n]", verdict) if _n(c)]
            spans: list[tuple[int, int, int]] = []          # (clause, start, end) already read
            for kind, eff, pat in PATTERNS:
              for ci, cl in enumerate(clauses if eff != "sahih" else [t]):
                for m in pat.finditer(cl):
                    if any(c0 == ci and not (m.end() <= a or m.start() >= b) for c0, a, b in spans):
                        continue
                    spans.append((ci, m.start(), m.end()))
                    x = m.group(1).strip()
                    if kind == "region_of_shaykh":
                        hl = head_level(head[:head.find("في")] if "في" in head else head)
                        tags = sorted(reg.get(rid, ()))
                        key = (kind, tuple(tags))
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append({**common, "kind": kind, "condition": x, "condition_ids": "",
                                     "region": " ".join(tags), "effect": f"level:{hl}" if hl else "none",
                                     "observable": True, "source_book": BOOK_TITLES[book], "citation": cit,
                                     "quote": line.split("\n")[0] if book == TAQRIB else line,
                                     "match": "region of the narrator himself: " + (" ".join(tags) or "none found"),
                                     "auto_ok": bool(tags and hl), "why_review": "" if (tags and hl) else
                                     "no region tag for the narrator or no verdict level"})
                        continue
                    pool = T if kind == "from_shaykh" else S
                    found, amb, left = find_names(x, pool, dominance)
                    if kind == "via_student":
                        hl = 3 if eff == "sahih" else head_level(head)
                        effect = f"level:{hl}" if hl and hl < base else ("accepted" if hl else "none")
                    else:
                        effect = eff
                    key = (kind, tuple(sorted(found)), effect)
                    if key in seen:
                        continue
                    seen.add(key)
                    ok = bool(found) and not amb and not left
                    rows.append({**common, "from_revision": eff == "sahih", "kind": kind, "condition": x,
                                 "condition_ids": " ".join(str(r) for r in sorted(found)), "region": "",
                                 "effect": effect, "observable": True, "source_book": BOOK_TITLES[book],
                                 "citation": cit, "quote": line.split("\n")[0] if book == TAQRIB else line,
                                 "match": "; ".join(f"r{r} ({how})" for r, how in sorted(found.items()))
                                 + (f"; ambiguous: {', '.join(amb)}" if amb else "")
                                 + (f"; unmatched: {' '.join(left)}" if left else ""),
                                 "auto_ok": ok, "why_review": "" if ok else
                                 ("no name matched" if not found else "ambiguous name" if amb else "a name unmatched")})
            m = IKHTILAT.search(t)
            if m and ikh is None:
                tail = t[m.start():m.start() + 40]
                ikh = (book, head, line, cit, bool(IKHTILAT_MINOR.search(tail)), verdict)
            for tag, pat in UNOBSERVABLE:
                mm = pat.search(t)
                if mm and ("unobservable", tag) not in seen:
                    seen.add(("unobservable", tag))
                    rows.append({**common, "kind": "unobservable", "condition": tag, "condition_ids": "",
                                 "region": "", "effect": "none", "observable": False,
                                 "source_book": BOOK_TITLES[book], "citation": cit,
                                 "quote": line.split("\n")[0] if book == TAQRIB else line,
                                 "match": t[max(0, mm.start() - 30):mm.end() + 30], "auto_ok": True,
                                 "why_review": ""})
        # a ruling read from Tahrir's «بل:» revision supersedes Ibn Hajar's of the same kind (the labels follow
        # Tahrir, audit §11.7)
        mine = [x for x in rows if x["rawi_id"] == rid]
        rev_kinds = {x["kind"] for x in mine if x.get("from_revision") and x["auto_ok"]}
        for x in mine:
            if x["kind"] in rev_kinds and not x.get("from_revision"):
                x["auto_ok"] = False
                x["why_review"] = (x["why_review"] + "; " if x["why_review"] else "") + "superseded by Tahrir's revision"
        # Tahrir disputing Ibn Hajar's condition: those rows wait for review
        tl = rec.get("tahrir_line") if rec.get("tahrir_ok") else None
        comment = _n(" ".join(x for x in (tl or "").split("\n")[1:] if x.strip().startswith("•"))) if tl else ""
        dm = DISPUTE.search(comment) if comment else None
        tq_line = _n(rec.get("taqrib_line") or "") if rec.get("taqrib_ok") else ""
        if dm:
            for row in rows:
                if row["rawi_id"] != rid or row["kind"] in ("ikhtilat_before", "ikhtilat_after", "unknown"):
                    continue
                toks = [w for w in _n(row["condition"]).split() if len(w) > 2 and w not in _STOPW]
                if toks and any(w in comment for w in toks) and any(w in tq_line for w in toks):
                    row["auto_ok"] = False
                    row["why_review"] = (row["why_review"] + "; " if row["why_review"] else "") + \
                        f"Tahrir disputes it («{comment[max(0, dm.start() - 40):dm.end() + 20].strip()}»)"
        ikh_disputed = bool(dm) and bool(re.search(r"اختلط|اختلاط", comment))
        # the criterion given as a date or a place («وضابط ذلك من سمع منه قبل المئتين», «من سمع منه ببغداد فبعد
        # الاختلاط»): the chain cannot place the link, so student lists do not decide it
        entry_text = _n(" ".join(v for _, _, v, _, _ in texts))
        ikh_criterion = re.search(r"ضابط|قبل (?:ال)?(?:مييتين|ماييتين|مايتين|ميتين)|قبل سنه|بعد سنه|من سمع منه ب(?:بغداد|البصره|مكه|الكوفه|مصر|واسط)",
                                  entry_text)
        alai_cat = alai.get(rid)
        # ikhtilat: stated in the narrator's own entry; student lists from it and from al-Kawakib
        if ikh is not None or "has_ikhtilat" in s["why"] or kaw.get(rid) or igh.get(rid) or ala.get(rid):
            srcs = []
            for book, head, verdict, line, cit in texts:
                srcs.append((book, verdict, line, cit))
            for book, ents in ((KAWAKIB, kaw), (IGHTIBAT, igh), (ALAI, ala)):
                for e in ents.get(rid, []):
                    srcs.append((book, e["text"], e["text"][:1500],
                                 f"[{BOOK_TITLES[book]}](https://shamela.ws/book/{book}/{e['page_id']})"))
            # the narrator's own entry places students first; the ikhtilat books add only students it
            # does not place (al-Kawakib's «وقال عبدة … إنه سمع منه في الاختلاط» does not undo Tahrir's list)
            tiers = {"entry": (set(), set()), "books": (set(), set())}
            amb, quotes = [], []
            for book, text, line, cit in srcs:
                b, a, am, _ = ikhtilat_lists(text, S, dominance)
                tb, ta = tiers["entry" if book in (TAQRIB, TAHRIR) else "books"]
                tb |= b
                ta |= a
                amb += am
                if b or a:
                    quotes.append((book, line, cit))
            (eb, ea), (kb, ka) = tiers["entry"], tiers["books"]
            both = (eb & ea) | ((kb & ka) - eb - ea)
            before = (eb | (kb - ea)) - both
            after = (ea | (ka - eb)) - both
            stated = ikh is not None and not ikh[4]
            # the level before the change: Tahrir's «بل:» revision when it gives one (the labels follow
            # Tahrir), else the Taqrib head without the qualifier
            bal = next((x for x in (tl or "").split("\n") if re.match(r"^\s*•\s*بل\s*:", x)), None)
            hl = head_level(bal.split(":", 1)[1].split("،")[0]) if bal else None
            if hl is None and ikh:
                hl = head_level(re.split(r"(?:اختلط|خلط|تغير|،)", ikh[1])[0])
            src_book, src_line, src_cit = (quotes[0] if quotes else ((ikh[0], ikh[2], ikh[3]) if ikh else (None, None, None)))
            why = []
            if ikh is None:
                why.append("no ikhtilat in the Taqrib/Tahrir entry" + ("" if texts else " (no entry identified)"))
            elif ikh[4]:
                why.append("minor change («قليلا», «لم يفحش», «فلم يحدث» …)")
            if not before:
                # with unknown: after, no documented early student would put every student after the change,
                # which the sources do not do (al-ʿAlāʾī on ʿAbd al-Razzāq: «وبالجملة فهو حجة على الإطلاق»)
                why.append("no student documented as hearing before" + ("" if after else "; no student list found"))
            if ikh_disputed:
                why.append("Tahrir disputes the ikhtilat")
            if ikh_criterion:
                why.append(f"the criterion is a date or a place («{entry_text[max(0, ikh_criterion.start() - 20):ikh_criterion.end() + 30].strip()}»)")
            if alai_cat == 1:
                why.append("al-Alai: first category (the confusion did him no harm)")
            if both:
                why.append("a student on both sides")
            ok = stated and bool(before) and not ikh_disputed and alai_cat != 1 and not ikh_criterion
            stated_q = (ikh[2].split("\n")[0] if ikh and ikh[0] == TAQRIB else ikh[2]) if ikh else ""
            for side, ids, effect in (("ikhtilat_before", before, f"level:{hl}" if hl and hl < base else "none"),
                                      ("ikhtilat_after", after, "defect:light")):
                rows.append({**common, "kind": side, "condition": "heard " + side.split("_")[1],
                             "condition_ids": " ".join(str(r) for r in sorted(ids)), "region": "",
                             "effect": effect, "observable": True,
                             "source_book": BOOK_TITLES.get(src_book, "") if src_book else "",
                             "citation": src_cit, "quote": (src_line or "")[:900],
                             "stated_in_entry": stated_q,
                             "match": " ".join(f"r{r}" for r in sorted(ids))
                             + (f"; ambiguous: {', '.join(amb[:6])}" if amb else ""),
                             "auto_ok": ok, "why_review": "; ".join(why)})
        elif "label" in s["why"] and not any(r["rawi_id"] == rid for r in rows):
            rows.append({**common, "kind": "unknown", "condition": s["label"], "condition_ids": "", "region": "",
                         "effect": "none", "observable": True, "source_book": "", "citation": "", "quote": "",
                         "match": "", "auto_ok": False,
                         "why_review": "the label carries a condition; " + ("no Taqrib/Tahrir entry identified"
                                                                           if not texts else "no pattern read it")})
    for i, r in enumerate(rows):
        r.setdefault("stated_in_entry", "")
    return rows


CAND_FIELDS = ["rule_id", "rawi_id", "narrator", "base_level", "label", "seed", "kind", "condition", "condition_ids",
               "region", "effect", "observable", "source_book", "citation", "quote", "stated_in_entry", "match",
               "auto_ok", "why_review"]
CONF_FIELDS = ["rule_id", "rawi_id", "narrator", "kind", "condition", "condition_ids", "region", "effect", "observable",
               "source_book", "citation", "quote", "status", "confirmed_by", "note"]


def _rule_ids(rows: list[dict]) -> None:
    n: Counter = Counter()
    for r in rows:
        n[(r["rawi_id"], r["kind"])] += 1
        r["rule_id"] = f"{r['rawi_id']}:{r['kind']}:{n[(r['rawi_id'], r['kind'])]}"


def write(rows: list[dict]) -> tuple[Path, Path, Path]:
    _rule_ids(rows)
    with open(CAND_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAND_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    human: list[dict] = []
    if CONF_PATH.exists():
        with open(CONF_PATH, encoding="utf-8") as f:
            human = [r for r in csv.DictReader(f) if r.get("confirmed_by") == "human"]
    hk = {r["rule_id"] for r in human}
    conf = []
    for r in rows:
        if r["rule_id"] in hk:
            continue
        conf.append({k: r.get(k, "") for k in CONF_FIELDS} | {
            "status": "auto" if r["auto_ok"] else "needs_review", "confirmed_by": "auto" if r["auto_ok"] else "",
            "note": r["why_review"]})
    conf += human
    conf.sort(key=lambda r: (int(r["rawi_id"]), r["rule_id"]))
    with open(CONF_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CONF_FIELDS)
        w.writeheader()
        w.writerows(conf)
    inforce = [r for r in conf if r["status"] in ("auto", "human")]
    meta = {
        "what": "conditional narrator rulings in force (auto and human rows of lists/conditional_confirmed.csv); "
                "generated by `make conditional`, do not edit by hand",
        "sources": {BOOK_TITLES[b]: f"https://shamela.ws/book/{b}" for b in BOOK_TITLES},
        "kinds": {k: v for k, v in zip(KINDS, (
            "weak or sound from the named teachers (condition_ids)",
            "sound from the people of his land: teachers carrying the region tag",
            "sound only through the named students (condition_ids)",
            "heard before his memory failed: the named students; a link in a chain of the Sahihayn is before",
            "heard after; with unknown: after, any student not listed before",
            "a condition the chain cannot show; applied nowhere"))},
        "effects": {"level:N": "the link takes Taqrib level N", "defect:light": "a light defect at the position",
                    "accepted": "the link takes level min(base, 4)", "none": "documented, no effect"},
        "count": len(inforce), "by_kind": dict(Counter(r["kind"] for r in inforce)),
    }
    YAML_PATH.write_text(yaml.safe_dump({"meta": meta, "rulings": inforce}, allow_unicode=True, sort_keys=False,
                                        width=200), encoding="utf-8")
    return CAND_PATH, CONF_PATH, YAML_PATH


def build() -> dict:
    rows = propose()
    write(rows)
    conf = list(csv.DictReader(open(CONF_PATH, encoding="utf-8")))
    return {"proposals": len(rows), "by_status": dict(Counter(r["status"] for r in conf)),
            "auto_by_kind": dict(Counter(r["kind"] for r in conf if r["status"] == "auto"))}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "fetch-taqrib":
        print(f"{fetch_taqrib()} narrators fetched -> {SRC_TAQRIB}")
    elif cmd == "fetch-kawakib":
        print(f"{fetch_pages(KAWAKIB, 1, KAWAKIB_LAST_PAGE, SRC_KAWAKIB)} pages -> {SRC_KAWAKIB}")
    elif cmd == "fetch-books":
        print(fetch_pages(ALAI, 1, 121, SRC_ALAI), fetch_pages(IGHTIBAT, 1, 129, SRC_IGHTIBAT),
              fetch_pages(IBN_RAJAB, *RAJAB_PAGES, SRC_RAJAB))
    elif cmd == "trim":
        trim_sources()
    elif cmd == "refresh-tahrir":
        print(f"{refresh_tahrir()} Tahrir entries re-read with their continuation lines")
    elif cmd == "build":
        print(build())
    elif cmd == "seed":
        s = seed()
        print(len(s), Counter(w for x in s for w in x["why"]))


