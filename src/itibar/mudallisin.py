"""`make mudallisin`: Ibn Hajar's Tabaqat al-Mudallisin (Ta'rif Ahl al-Taqdis bi-Maratib
al-Mawsufin bi-l-Tadlis), digitized from Shamela book 1186 (ed. 'Asim al-Qaryuti, 1983),
and joined to rawis.

  fetch   re-download the book page by page into lists/source/mudallisin_1186.jsonl
  parse   -> lists/mudallisin.yaml: the 152 entries of Ibn Hajar's five tiers (number,
          tier, name as printed, his note, page); the editor's appendix of 22 further
          names (pages 58-66) is not Ibn Hajar's and is left out
  match   deterministic name matching to rawis -> lists/mudallisin_candidates.csv (top 5
          per entry with every score feature) and lists/mudallisin_confirmed.csv (auto
          rows rewritten; human rows kept exactly as the user left them)

The tiers, in Ibn Hajar's words (introduction, printed pp. 13-14):
  1  من لم يوصف بذلك الا نادرا
  2  من احتمل الائمة تدليسه وأخرجوا له في الصحيح لامامته وقلة تدليسه في جنب ما روى ...
     أو كان لا يدلس الا عن ثقة
  3  من أكثر من التدليس فلم يحتج الائمة من أحاديثهم الا بما صرحوا فيه بالسماع
  4  من اتفق على أنه لا يحتج بشئ من حديثهم الا بما صرحوا فيه بالسماع لكثرة تدليسهم
     على الضعفاء والمجاهيل
  5  من ضعف بأمر آخر سوى التدليس فحديثهم مردود ولو صرحوا بالسماع

No model: names are normalized with lists.normalize (v1) and scored by idf-weighted
token overlap; nothing is confirmed beyond the documented auto rule (README).
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from itibar import config, data, lists

BOOK = 1186
SOURCE = lists.SOURCE_DIR / f"mudallisin_{BOOK}.jsonl"
YAML_PATH = lists.LISTS_DIR / "mudallisin.yaml"
CAND_PATH = lists.LISTS_DIR / "mudallisin_candidates.csv"
CONF_PATH = lists.LISTS_DIR / "mudallisin_confirmed.csv"
FIRST_PAGE, LAST_PAGE = 14, 56          # Ibn Hajar's text; the editor's appendix starts at page 58
TIER_WORDS = {"الاولى": 1, "الأولى": 1, "الثانية": 2, "الثالثة": 3, "الرابعة": 4, "الخامسة": 5}
TIER_COUNTS = {1: 33, 2: 33, 3: 50, 4: 12, 5: 24}   # "وعدتهم ..." as printed at each tier's head
# Taqrib's sigla (introduction of the Taqrib, reproduced by the editor on printed p. 8)
SIGLA = set("خ خت بخ عخ ز ى ي م د مد صد خد قد ف ل كد ت تم س سى عس كن ق فق ع ٤ تمييز".split())
# printed before a name in three entries: "ح" and "ن" (sigla as printed), "مقرونا" (Muslim's
# coupled narration, entry 125), "الله تعالى" (a printing artefact at the head of entry 130)
LEAD_NOISE = {"ح", "ن", "مقرونا", "الله", "تعالى"}
_NAME_STOP = set("""أحد احد كان روى وصفه صاحب مشهور قال ذكر ذكره رأى مات يروي نزيل عن الفقيه المحدث محدث
حافظ ثقة صدوق ضعيف ضعفه ضعفوه أخرج اخرج له تابعي التابعي القاضي قاضي شيخ أشار اشار يقال وثقه اختلط مختلف معروف
المشهور الامام إمام امام وكان وهو في وقال سمع رمي متهم تكلموا مكثر المكثر صغير من الثقة اتهمه تركه بمثناه
موصوف بالمهلمة بمهملة بمعجمات أصله اصله أكثر اختلف فيه قي""".split())
_PARTICLES = {"بن", "ابن", "ابي", "ابو", "ام", "بنت", "عبد", "ال"}
_AR = "٠١٢٣٤٥٦٧٨٩"


def _ar_int(s: str) -> int:
    return int("".join(str(_AR.index(c)) for c in s))


def fetch() -> int:
    return lists.fetch(BOOK, SOURCE)


def parse(path: Path = SOURCE) -> list[dict]:
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    cit = {r["page_id"]: r["citation"] for r in rows}
    full = "".join(f"\n<<P{r['page_id']}>>\n" + r["text"] for r in rows if FIRST_PAGE <= r["page_id"] <= LAST_PAGE)
    heads = [(m.start(), TIER_WORDS[m.group(1)]) for m in re.finditer(r"المرتبة\s+(\S+)", full)
             if m.group(1) in TIER_WORDS]
    marks = list(re.finditer(r"\(([٠-٩]{1,3})\)\s*", full))
    out = []
    for i, m in enumerate(marks):
        n = _ar_int(m.group(1))
        if n == 0:                    # the edition's "(٠)" separators
            continue
        end = next((x.start() for x in marks[i + 1:] if _ar_int(x.group(1)) != 0), len(full))
        seg = full[m.end():end]
        pages = [int(p) for p in re.findall(r"<<P(\d+)>>", full[:m.start()])]
        page = pages[-1] if pages else FIRST_PAGE
        tier = max((t for s, t in heads if s < m.start()), default=None)
        text = re.sub(r"\s*<<P\d+>>\s*", " ", seg).strip()
        text = re.split(r"\s*المرتبة\s+(?:الثانية|الثالثة|الرابعة|الخامسة)", text)[0].strip()
        text = re.sub(r"\s*\(٠\)\s*", " ", text).strip()
        toks = text.split()
        sig = []
        while toks and (toks[0] in SIGLA or toks[0] in LEAD_NOISE or re.fullmatch(r"[٠-٩]+", toks[0])):
            sig.append(toks.pop(0))
        name = []
        for t in toks:
            if name and len(name) >= 2 and lists.normalize(t) in {lists.normalize(x) for x in _NAME_STOP}:
                break
            name.append(t)
            if len(name) >= 12:
                break
        label = lists._page_label(cit.get(page))
        out.append({"number": n, "tier": tier, "sigla": " ".join(sig), "name": " ".join(name),
                    "note": " ".join(toks), "page_id": page, "page_label": label,
                    "url": f"https://shamela.ws/book/{BOOK}/{page}"})
    return out


def write_yaml(entries: list[dict]) -> Path:
    counts = Counter(e["tier"] for e in entries)
    meta = {
        "work": "تعريف أهل التقديس بمراتب الموصوفين بالتدليس (Tabaqat al-Mudallisin)",
        "author": "Ibn Hajar al-'Asqalani (d. 852/1449)",
        "source": f"Shamela book {BOOK}, ed. 'Asim b. 'Abdallah al-Qaryuti (Amman: Maktabat al-Manar, 1403/1983), "
                  f"fetched page by page into lists/source/mudallisin_{BOOK}.jsonl; the editor numbers the 152 names "
                  "serially across the tiers. His appendix of 22 further names (pages 58-66) is not Ibn Hajar's and is "
                  "not included.",
        "tiers": {
            1: "من لم يوصف بذلك الا نادرا",
            2: "من احتمل الائمة تدليسه وأخرجوا له في الصحيح لامامته وقلة تدليسه في جنب ما روى كالثوري أو كان لا يدلس الا عن ثقة كإبن عيينة",
            3: "من أكثر من التدليس فلم يحتج الائمة من أحاديثهم الا بما صرحوا فيه بالسماع ومنهم من رد حديثهم مطلقا ومنهم من قبلهم كأبي الزبير المكي",
            4: "من اتفق على أنه لا يحتج بشئ من حديثهم الا بما صرحوا فيه بالسماع لكثرة تدليسهم على الضعفاء والمجاهيل كبقية بن الوليد",
            5: "من ضعف بأمر آخر سوى التدليس فحديثهم مردود ولو صرحوا بالسماع الا أن يوثق من كان ضعفه يسيرا كابن لهيعة",
        },
        "tiers_url": f"https://shamela.ws/book/{BOOK}/9 (tiers 1-3), https://shamela.ws/book/{BOOK}/10 (tiers 4-5)",
        "count_stated": "مائة واثنان وخمسون نفسا (152)",
        "count_parsed": len(entries),
        "per_tier_parsed": {int(k): int(v) for k, v in sorted(counts.items())},
        "per_tier_printed": TIER_COUNTS,
        "fields": {
            "number": "the editor's serial number",
            "tier": "Ibn Hajar's tier (المرتبة), 1-5",
            "sigla": "Taqrib sigla before the name, as printed (ع = the Six Books)",
            "name": "the name as printed, up to the first descriptive word (a heuristic cut; `note` keeps the whole entry)",
            "note": "the whole entry after the sigla, as printed",
        },
    }
    YAML_PATH.write_text(yaml.safe_dump({"meta": meta, "entries": entries}, allow_unicode=True, sort_keys=False,
                                        width=200), encoding="utf-8")
    return YAML_PATH


def load_entries() -> list[dict]:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))["entries"]


# ---------------------------------------------------------------- matching

def _cfg() -> dict:
    return config.load("structure")["mudallisin"]


def _bare(t: str) -> str:
    """The token without the article: the source writes «وليد بن مسلم» where Ibn Hajar
    prints «الوليد بن مسلم»."""
    return t[2:] if t.startswith("ال") and len(t) > 3 else t


def _toks(s: str | None) -> list[str]:
    return [_bare(t) for t in lists.tokens(s) if t not in _PARTICLES]


_COMPOUND = ("عبد", "ابو", "ابي", "ام")


def _units(tokens: list[str]) -> list[str]:
    """Name units: "عبد الملك", "أبو حرة" and "أبي زائدة" are one unit each; the article is
    dropped from every token."""
    t = [_bare(x) for x in tokens]
    out, i = [], 0
    while i < len(t):
        if t[i] in _COMPOUND and i + 1 < len(t) and t[i + 1] not in ("بن", "ابن"):
            out.append(t[i] + " " + t[i + 1])
            i += 2
        else:
            out.append(t[i])
            i += 1
    return out


def _ism_father(tokens: list[str]) -> tuple[str, ...]:
    """(ism, father) for "X بن Y" in name units ("عبد الملك بن عبد العزيز" ->
    ("عبد الملك", "عبد العزيز")), article-insensitive; (ism,) without a father."""
    u = _units(tokens)
    if len(u) >= 3 and u[1] in ("بن", "ابن"):
        return (u[0], u[2])
    return (u[0],) if u else ()


def candidates(entries: list[dict], con=None) -> list[dict]:
    """Top-k rawis per entry. Features (all in [0, 1]):
      name      idf-weighted share of the printed name's tokens (particles بن/أبي/... dropped)
                present in the narrator's full name or nickname
      nickname  idf-weighted share of the narrator's nickname tokens present in the first
                `head_tokens` tokens of the entry
      sequence  1 if the printed name agrees with the narrator's full name or nickname on ism
                and father ("X بن Y", "X بن أبي Z"; article-insensitive); for a printed name
                without a father ("حميد الطويل"), on the ism and a second printed token found
                in the nickname
      tadlis    the source's has_tadlis flag
      prolific  min(1, log10(1 + riwaya_qty) / 4): Ibn Hajar's mudallisun are, with few
                exceptions, prolific transmitters; it separates namesakes of equal name score
    score = sum of weights * features (config mudallisin.weights)."""
    con = con or data.views()
    cfg = _cfg()
    w = cfg["weights"]
    rw = con.sql("""SELECT id, name, nickname, has_tadlis, death_year, tabaka, rank_no, coalesce(riwaya_qty, 0)
                    FROM rawis WHERE is_stub = 0 AND rank IS NOT NULL""").fetchall()
    df: Counter = Counter()
    info = {}
    for rid, name, nick, tad, dy, tab, rn, rq in rw:
        full = set(_toks(name)) | set(_toks(nick))
        prol = min(1.0, math.log10(1 + int(rq)) / 4)
        info[rid] = (name, nick, int(tad or 0), dy, tab, rn, full, _toks(nick),
                     {_ism_father(lists.tokens(name)), _ism_father(lists.tokens(nick))}, prol,
                     {_bare(x) for x in lists.tokens(nick)})
        df.update(full)
    N = len(rw)
    idf = {t: math.log(N / n) + 1 for t, n in df.items()}
    inv: dict[str, list[int]] = defaultdict(list)
    for rid, v in info.items():
        for t in v[6]:
            inv[t].append(rid)
    head_n = int(cfg["head_tokens"])
    k = int(cfg["candidates"])
    out = []
    for e in entries:
        nt = _toks(e["name"])
        head = set(_toks(" ".join(e["note"].split()[:head_n])))
        pt = lists.tokens(e["name"])
        pif = _ism_father(pt)
        has_father = len(pif) == 2
        pu = _units(pt)
        pool = set()
        for t in set(nt):
            if idf.get(t, 0) >= float(cfg["min_idf"]):
                pool.update(inv.get(t, ()))
        tot_n = sum(idf.get(t, math.log(N) + 1) for t in set(nt)) or 1.0
        scored = []
        for rid in pool:
            name, nick, tad, dy, tab, rn, full, nk, fn, prol, nkall = info[rid]
            f_name = sum(idf.get(t, 0) for t in set(nt) if t in full) / tot_n
            tot_k = sum(idf.get(t, 0) for t in set(nk)) or 1.0
            f_nick = sum(idf.get(t, 0) for t in set(nk) if t in head) / tot_k
            if has_father:
                f_seq = 1.0 if pif in fn else 0.0
            else:
                f_seq = 1.0 if pu and any(x[:1] == pif for x in fn) and len(pu) > 1 and all(
                    w in nkall for w in pu[1].split()) else 0.0
            s = (w["name"] * f_name + w["nickname"] * f_nick + w["sequence"] * f_seq + w["tadlis"] * tad
                 + w["prolific"] * prol)
            scored.append((round(s, 4), rid, round(f_name, 4), round(f_nick, 4), f_seq, tad))
        scored.sort(key=lambda x: (-x[0], x[1]))
        for rank, (s, rid, fa, fb, fc, tad) in enumerate(scored[:k], 1):
            name, nick, _, dy, tab, rn = info[rid][:6]
            out.append({"number": e["number"], "tier": e["tier"], "printed": e["name"], "rank": rank, "rawi_id": rid,
                        "nickname": nick, "full_name": name, "death_year": dy, "tabaka": tab, "taqrib_level": rn,
                        "has_tadlis": tad, "score": s, "f_name": fa, "f_nickname": fb, "f_sequence": fc})
        if not scored:
            out.append({"number": e["number"], "tier": e["tier"], "printed": e["name"], "rank": 0, "rawi_id": None,
                        "nickname": None, "full_name": None, "death_year": None, "tabaka": None, "taqrib_level": None,
                        "has_tadlis": None, "score": 0.0, "f_name": 0.0, "f_nickname": 0.0, "f_sequence": 0.0})
    return out


CAND_FIELDS = ["number", "tier", "printed", "rank", "rawi_id", "nickname", "full_name", "death_year", "tabaka",
               "taqrib_level", "has_tadlis", "score", "f_name", "f_nickname", "f_sequence"]
CONF_FIELDS = ["number", "tier", "printed", "rawi_id", "nickname", "status", "confirmed_by", "score", "margin", "note"]


def auto_rows(cands: list[dict]) -> list[dict]:
    """One row per entry. `auto` when the top candidate's printed name and the narrator's
    name agree on ism and father (f_sequence = 1) and either
      (a) score >= auto_min_score and margin to the second >= auto_min_margin, or
      (b) the source independently flags him (has_tadlis = 1), score >= flag_min_score,
          margin >= flag_min_margin, and no other candidate in the top five with the same
          ism and father is flagged (two flagged namesakes are left to the reviewer);
    otherwise `needs_review` with the reason."""
    cfg = _cfg()
    smin, mmin = float(cfg["auto_min_score"]), float(cfg["auto_min_margin"])
    fmin, fmar = float(cfg["flag_min_score"]), float(cfg["flag_min_margin"])
    by: dict[int, list[dict]] = defaultdict(list)
    for c in cands:
        by[int(c["number"])].append(c)
    rows = []
    for n in sorted(by):
        cs = sorted([c for c in by[n] if c["rawi_id"] is not None], key=lambda c: c["rank"])
        top = cs[0] if cs else None
        second = cs[1]["score"] if len(cs) > 1 else 0.0
        margin = round(top["score"] - second, 4) if top else 0.0
        seq = bool(top) and float(top["f_sequence"]) == 1.0
        rule_a = seq and top["score"] >= smin and margin >= mmin
        rival = any(int(c["has_tadlis"] or 0) == 1 and float(c["f_sequence"]) == 1.0 for c in cs[1:])
        rule_b = (seq and int(top["has_tadlis"] or 0) == 1 and top["score"] >= fmin and margin >= fmar
                  and not rival)
        ok = rule_a or rule_b
        note = "" if rule_a else "auto (b): the source's has_tadlis flag agrees" if rule_b else (
            "no candidate" if not top else "ism and father differ" if not seq
            else "a namesake is also flagged has_tadlis" if int(top["has_tadlis"] or 0) == 1 and rival
            else "below auto_min_score" if top["score"] < smin else "margin below auto_min_margin")
        rows.append({"number": n, "tier": by[n][0]["tier"], "printed": by[n][0]["printed"],
                     "rawi_id": top["rawi_id"] if (top and ok) else "", "nickname": top["nickname"] if (top and ok) else "",
                     "status": "auto" if ok else "needs_review", "confirmed_by": "auto" if ok else "",
                     "score": top["score"] if top else 0.0, "margin": margin, "note": note})
    return rows


def write_match(cands: list[dict]) -> tuple[Path, Path]:
    with open(CAND_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAND_FIELDS)
        w.writeheader()
        w.writerows(cands)
    human: list[dict] = []
    if CONF_PATH.exists():
        with open(CONF_PATH, encoding="utf-8") as f:
            human = [r for r in csv.DictReader(f) if r.get("confirmed_by") == "human"]
    hk = {int(r["number"]) for r in human}
    rows = [r for r in auto_rows(cands) if int(r["number"]) not in hk] + human
    rows.sort(key=lambda r: (int(r["number"]), str(r["rawi_id"])))
    with open(CONF_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CONF_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return CAND_PATH, CONF_PATH


def confirmed_tiers(path: Path | None = None) -> dict[int, int]:
    """rawi id -> Ibn Hajar's tier, from the confirmed rows (auto and human). A human row
    with an empty rawi_id records that the entry has no narrator in the data. If two
    entries resolve to one rawi id, the stricter (higher) tier is kept."""
    path = path or CONF_PATH
    out: dict[int, int] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("status") not in ("auto", "human") and r.get("confirmed_by") not in ("auto", "human"):
                continue
            if not r.get("rawi_id"):
                continue
            rid, t = int(r["rawi_id"]), int(r["tier"])
            out[rid] = max(out.get(rid, 0), t)
    return out


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "fetch":
        print(f"{fetch()} pages -> {SOURCE}")
        return
    if cmd in ("parse", "all"):
        ents = parse()
        print(f"{len(ents)} entries -> {write_yaml(ents)}")
    if cmd in ("match", "all"):
        c = candidates(load_entries())
        cp, fp = write_match(c)
        rows = list(csv.DictReader(open(fp, encoding="utf-8")))
        print(f"candidates -> {cp}; confirmed -> {fp}: " + ", ".join(
            f"{k} {v}" for k, v in Counter(r["status"] for r in rows).items()))


if __name__ == "__main__":
    main()
