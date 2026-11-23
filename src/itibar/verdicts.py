"""The critics' own verdicts, extracted from the hadith texts (PR 7 §4).

The authors of the collections close many reports with a remark: al-Tirmidhī's «هذا حديث حسن صحيح» and «وفي
الباب عن فلان وفلان», al-Ṭabarānī's «لم يرو هذا الحديث عن X إلا Y، تفرد به Z», al-Bazzār's «لا نعلمه يروى عن
رسول الله إلا من هذا الوجه», al-Ḥākim's «صحيح على شرط الشيخين ولم يخرجاه», Abū Nuʿaym's «غريب من حديث X تفرد
به Y», al-Bayhaqī's «رواه البخاري في الصحيح عن X». Each is a per-report claim about what itibar computes. This
module reads every hadith text of the commenting books (lists.normalize: diacritics and tatweel stripped, letters
unified), matches the formula families the survey found (`survey()`, reports/verdicts.md §1), and writes one row
per claim to out/verdicts.parquet:

  book_id, critic, hadith_id, group_id, page_no   where the claim is
  span, span_start, span_end                       the quoted span, a substring of hadiths.nass (gated)
  claim_type                                       verdict | tafarrud | gharib | wafi_al_bab | shart | sahih_attribution
                                                   | comparison | bukhari_view | hearing | khata
  family                                           the formula (e.g. tabarani_lam_yarwi)
  grade, scope, clause                             the slots of a verdict / shart claim
  x_text, y_text, z_text, names                   the name slots as written (normalized)
  x_id, y_id, z_id, ...                           resolved among the narrators of the hadith's own chain(s)
                                                   (conditional.find_names, as PR 6 resolved conditions); P = the
                                                   Prophet; *_reason when a slot is unresolved
  sanad_ids                                        the chains of the hadith the claim attaches to

  python -m itibar.verdicts [survey|extract]
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from itibar import conditional, data, lists, paths

# ---------------------------------------------------------------- books and critics

CRITIC_BOOKS: dict[int, str] = {
    3: "al-Tirmidhi", 66: "al-Tabarani", 65: "al-Tabarani", 67: "al-Tabarani", 45: "al-Tabarani", 386: "al-Tabarani",
    35: "al-Bazzar", 36: "al-Bazzar", 59: "al-Bazzar (Kashf al-Astar)", 20: "al-Daraqutni",
    22: "al-Bayhaqi", 195: "al-Bayhaqi", 24: "al-Bayhaqi", 269: "al-Bayhaqi", 21: "al-Bayhaqi",
    267: "Abu Nuaym", 297: "Abu Nuaym", 14: "Abu Nuaym", 296: "Abu Nuaym",
    301: "al-Khatib", 155: "al-Khatib", 160: "al-Khatib", 158: "al-Khatib",
    12: "al-Hakim", 4: "Abu Dawud", 17: "al-Nasai", 5: "al-Nasai", 10: "Ibn Khuzayma", 11: "Ibn Hibban",
}
SURVEY_BOOKS = sorted(CRITIC_BOOKS) + [303, 9, 62, 1, 2, 6, 7, 13, 230, 229, 236, 226, 15]


def out_path() -> Path:
    return paths.OUT_DIR / "verdicts.parquet"


# ---------------------------------------------------------------- normalization with offsets

_DIAC = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")
_MAP = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}


def norm_map(text: str) -> tuple[str, list[int]]:
    """lists.normalize (version 1) with, for every output character, its index in `text` (the start of the
    source character). Spaces collapse onto the first source position of the run."""
    out: list[str] = []
    pos: list[int] = []
    space = True
    for i, ch in enumerate(text or ""):
        if _DIAC.match(ch) or ch == "ـ":
            continue
        ch = _MAP.get(ch, ch)
        if "ء" <= ch <= "ي" and ch != "ـ":
            out.append(ch)
            pos.append(i)
            space = False
        else:
            if not space:
                out.append(" ")
                pos.append(i)
                space = True
    while out and out[-1] == " ":
        out.pop()
        pos.pop()
    return "".join(out), pos


def source_span(text: str, pos: list[int], a: int, b: int) -> tuple[int, int, str]:
    """The source slice [start, end) covering normalized characters [a, b): from the source index of a to just
    after the last source character of b-1 (its trailing diacritics included)."""
    start = pos[a]
    j = pos[b - 1] + 1
    while j < len(text) and (_DIAC.match(text[j]) or text[j] == "ـ"):
        j += 1
    return start, j, text[start:j]


# ---------------------------------------------------------------- formulas

# a name: up to 7 tokens, none of them a formula word
_STOP = (r"(?:الا|تفرد|تفردبه|ولا|ولم|لم|حدثنا|ثنا|نا|اخبرنا|قال|وقال|ورواه|رواه|وهو|وهذا|هذا|وكان|كان|وقد|قد|من|"
         r"بهذا|عن|غير|وغيره|وغير|فيما|فذكر|وذكر|وروي|روي|ويروي|يروي|والحديث|الحديث|واسناده|اسناده|وفيه|"
         r"والصحيح|والصواب|وانما|انما|مرسلا|موقوفا|مرفوعا|متصلا|وحده|جميعا|ورواية|وهم|وهما|ايضا|نحوه|مثله)")
NAME = r"[^ ]+(?: (?!" + _STOP + r"(?: |$))[^ ]+){0,6}"


def N(g: str) -> str:
    return f"(?P<{g}>{NAME})"


@dataclass
class Family:
    key: str
    books: tuple[int, ...] | None           # None: any commenting book
    claim_type: str
    pattern: re.Pattern
    slots: dict = field(default_factory=dict)  # fixed slot values


def _f(key, books, ctype, pat, **slots) -> Family:
    return Family(key, books, ctype, re.compile(pat), slots)


TAB = (66, 65, 67, 45, 386, 301)
BAZ = (35, 36, 59)
TIR = (3,)
GRADE_WORDS = r"(?P<grade>حسن صحيح غريب|صحيح حسن غريب|حسن صحيح|صحيح حسن|حسن غريب|صحيح غريب|غريب حسن|غريب صحيح|حسن|صحيح|غريب)"

FAMILIES: list[Family] = [
    # ---- al-Tabarani (and al-Khatib relaying him: «قال سليمان لم يروه عن …»)
    _f("tabarani_lam_yarwi", TAB, "tafarrud",
       r"لم (?:يرو|يرفع|يصل|يسند|يجود) (?:هذا الحديث|هذين الحديثين|هذه الاحاديث|هذا) عن " + N("x") + r" الا " + N("y")),
    _f("tabarani_lam_yarwihi", TAB, "tafarrud", r"لم يروه عن " + N("x") + r" الا " + N("y")),
    _f("tabarani_la_yurwa_isnad", TAB, "tafarrud",
       r"لا يروي (?:هذا الحديث |هذان الحديثان |هذه الاحاديث )?عن " + N("x") + r" الا بهذا الاسناد"),
    _f("tafarrud_bihi", None, "tafarrud", r"(?<![^ ])(?:تفرد به|تفرد بروايته|تفرد بروايه هذا الحديث|تفرد بهذا الحديث)"
                                          r"(?: عنه)? " + N("z")),
    _f("wala_anhu_illa", TAB + BAZ, "tafarrud", r"ولا (?:عنه|رواه عنه) الا " + N("y")),
    # ---- al-Bazzar (and Kashf al-Astar «قال البزار …»)
    _f("bazzar_la_nalamuhu_wajh", BAZ, "tafarrud",
       r"لا نعلمه (?:يروي )?(?:عن " + N("x") + r" )?(?:بهذا اللفظ )?الا (?:من هذا الوجه|بهذا الاسناد|من هذا الوجه بهذا الاسناد)"),
    _f("bazzar_la_nalam_rawahu", BAZ, "tafarrud",
       r"لا نعلم (?:احدا )?(?:رواه|يرويه|حدث به) عن " + N("x") + r" (?:الا|غير) " + N("y")),
    _f("bazzar_min_hadith", BAZ, "tafarrud", r"لا نعلمه (?:يروي )?(?:عن " + N("x") + r" )?الا من حديث " + N("y")),
    # ---- al-Tirmidhi
    _f("tirmidhi_verdict", TIR, "verdict",
       r"(?<![^ ])(?:هذا |وهذا )?حديث " + GRADE_WORDS + r"(?: (?P<scope>من هذا الوجه|من حديث " + N("x") + r"|لا نعرفه))?"),
    _f("tirmidhi_la_narifuhu_wajh", TIR, "tafarrud", r"لا نعرفه (?:مرفوعا )?الا من هذا الوجه"),
    _f("tirmidhi_la_narifuhu_hadith", TIR, "tafarrud", r"لا نعرفه (?:مرفوعا |بهذا الاسناد )?الا من حديث " + N("y")),
    _f("wafi_al_bab", TIR, "wafi_al_bab", r"وفي الباب عن (?P<names>[^ ]+(?: (?!(?:قال|هذا|وهذا|حديث|وحديث|حدثنا|اخبرنا|"
                                         r"وروي|وقد|والعمل|ابو|عيسي)(?: |$))[^ ]+){0,40})"),
    _f("tirmidhi_isnad_laysa_qaim", TIR, "verdict", r"ليس اسناده بذاك القايم", grade="laysa_isnaduhu_qaim"),
    _f("tirmidhi_laysa_muttasil", TIR, "verdict", r"(?:ليس اسناده بمتصل|اسناده ليس بمتصل)", grade="laysa_muttasil"),
    _f("tirmidhi_asahh", TIR, "comparison", r"(?:وهذا|هذا) اصح من (?:حديث )?" + N("x")),
    _f("tirmidhi_bukhari", TIR, "bukhari_view", r"سالت محمدا(?: يعني البخاري| بن اسماعيل)? عن (?P<rest>(?:[^ ]+ ){0,25}[^ ]+)"),
    # ---- verdict words of others
    _f("hakim_shart", (12,), "shart",
       r"صحيح (?:الاسناد )?علي شرط (?P<clause>الشيخين|مسلم|البخاري)(?: (?P<lam>ولم يخرجاه|ولم يخرجه))?"),
    _f("hakim_sahih_isnad", (12,), "verdict", r"(?<![^ ])(?:هذا )?حديث صحيح الاسناد(?: ولم يخرجاه)?", grade="sahih_isnad"),
    _f("hakim_sahih_lam", (12,), "verdict", r"(?<![^ ])هذا حديث صحيح ولم يخرجاه", grade="sahih"),
    _f("isnad_grade", (20, 22, 195, 24, 21, 4, 17, 5, 10), "verdict",
       r"(?<![^ ])(?:هذا )?اسناد (?P<grade>صحيح|حسن|ضعيف|متصل|مرسل|ثابت)"),
    _f("kulluhum_thiqat", (20,), "verdict", r"(?<![^ ])كلهم ثقات", grade="kulluhum_thiqat"),
    _f("mursal", (20, 22, 195, 24, 21, 4, 17, 3, 12), "verdict", r"(?<![^ ])(?:هذا|وهذا) (?:حديث )?مرسل", grade="mursal"),
    _f("munkar", (4, 17, 5, 20, 22, 3), "verdict", r"(?<![^ ])(?:هذا|وهذا) (?:حديث )?منكر", grade="munkar"),
    _f("khata", (17, 5, 20, 4, 22), "khata", r"(?<![^ ])(?:هذا|وهذا) (?:الحديث )?(?:خطا|غلط)"),
    _f("laysa_bilqawi", (17, 5, 4, 20, 22, 10), "verdict", r"(?P<x0>(?:[^ ]+ ){0,4}[^ ]+) ليس بالقوي", grade="laysa_bilqawi"),
    _f("in_sahha", (10,), "verdict", r"ان صح الخبر", grade="in_sahha"),
    _f("abu_nuaym_gharib", (267, 297, 14, 296, 301, 20, 22, 195), "gharib",
       r"(?:حديث )?غريب (?:من حديث|من روايه) " + N("x") + r"(?: (?:تفرد به|لم يروه عنه الا|تفرد به عنه) " + N("y") + r")?"),
    _f("lam_naktubhu", (267, 297, 14, 296), "tafarrud", r"لم نكتبه الا من (?:حديث " + N("y") + r"|هذا الوجه)"),
    _f("mashhur_min_hadith", (267, 297, 14, 296), "verdict", r"مشهور من حديث " + N("x"), grade="mashhur"),
    _f("sahih_muttafaq", (267, 297, 14, 296), "verdict", r"(?<![^ ])(?:هذا حديث )?صحيح (?P<g2>متفق عليه|ثابت)", grade="sahih"),
    # ---- al-Bayhaqi's takhrij: «رواه البخاري في الصحيح عن X» / «أخرجه مسلم في الصحيح من حديث X»
    _f("sahih_attribution", (22, 195, 24, 269, 21), "sahih_attribution",
       r"(?:رواه|اخرجه|ورواه|واخرجه) (?P<who>البخاري|مسلم|البخاري ومسلم) في الصحيح (?:عن|من حديث|من وجه اخر عن) " + N("x")),
    # ---- hearing statements
    _f("lam_yasma", (4, 17, 3, 11, 10, 20, 22), "hearing", r"لم يسمع " + N("x") + r" من " + N("y")),
]


def critic(book_id: int) -> str:
    return CRITIC_BOOKS.get(int(book_id), f"book {book_id}")


# ---------------------------------------------------------------- survey

def survey(books=None, top: int = 30, con=None) -> pd.DataFrame:
    """Per book: the most frequent 3-5 token n-grams in the text after matn_end (lists.normalize); one row per
    (book, n-gram) with its count of hadith."""
    con = con or data.views()
    books = books or SURVEY_BOOKS
    rows = []
    for b in books:
        cnt: Counter = Counter()
        tot = 0
        for nass, me in con.sql(f"SELECT nass, matn_end FROM hadiths WHERE book_id = {int(b)}").fetchall():
            if not nass or me is None:
                continue
            toks = lists.normalize(nass[me:]).split()
            if not toks:
                continue
            tot += 1
            seen = set()
            for n in (3, 4, 5):
                for i in range(len(toks) - n + 1):
                    g = " ".join(toks[i:i + n])
                    if g not in seen:
                        seen.add(g)
                        cnt[g] += 1
        for g, k in cnt.most_common(top):
            rows.append({"book_id": int(b), "ngram": g, "hadith": k, "with_tail": tot})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- resolution

class Resolver:
    """Names in a claim resolved among the narrators of the hadith's own chain(s), as conditional.find_names
    resolves a ruling's names among a narrator's adjacent narrators."""

    def __init__(self, con):
        r = con.sql("SELECT id, name, nickname, rank_no FROM rawis").df()
        self.name = dict(zip(r["id"], r["name"]))
        self.nick = dict(zip(r["id"], r["nickname"]))
        self.rank = dict(zip(r["id"], r["rank_no"]))
        self._cand: dict[tuple, list] = {}

    def cands(self, ids_links: tuple[tuple[int, int], ...]) -> list:
        c = self._cand.get(ids_links)
        if c is None:
            c = [conditional._cand(int(i), int(k), self.name.get(i), self.nick.get(i)) for i, k in ids_links]
            self._cand[ids_links] = c
        return c

    def resolve(self, text: str | None, ids_links: tuple[tuple[int, int], ...]) -> tuple[str | None, str | None]:
        """(id or 'P', None) or (None, reason)."""
        if not text:
            return None, "empty"
        t = text.strip()
        if re.fullmatch(r"(?:رسول الله|النبي|نبي الله)(?: .*)?", t):
            return "P", None
        found, amb, left = conditional.find_names(t, self.cands(ids_links), 0.95)
        if len(found) == 1:
            return f"r{next(iter(found))}", None
        if len(found) > 1:
            # the first name in the span (a name followed by more words: «سفيان عن …» never reaches here)
            return None, "several:" + ",".join(f"r{x}" for x in sorted(found))
        if amb:
            return None, "ambiguous:" + amb[0]
        return None, "not_in_chain"


# ---------------------------------------------------------------- extraction

def _hadith_chains(con, book_ids) -> dict[int, list[tuple[int, list[int]]]]:
    rows = con.sql(f"""SELECT s.hadith_id, s.id, list(sr.rawi_id ORDER BY sr.pos) FROM sanads s
                       JOIN hadiths h ON h.id = s.hadith_id JOIN sanad_rawis sr ON sr.sanad_id = s.id
                       WHERE h.book_id IN ({",".join(str(int(b)) for b in book_ids)}) GROUP BY ALL""").fetchall()
    out: dict[int, list] = defaultdict(list)
    for hid, sid, ch in rows:
        out[int(hid)].append((int(sid), [int(x) for x in ch]))
    return out


def extract(con=None, books=None, write: bool = True, hadith_ids=None) -> pd.DataFrame:
    con = con or data.views()
    books = sorted(books or CRITIC_BOOKS)
    only = "" if hadith_ids is None else f" AND id IN ({','.join(str(int(h)) for h in hadith_ids)})"
    chains = _hadith_chains(con, books)
    R = Resolver(con)
    rows = []
    hs = con.sql(f"""SELECT id, book_id, group_id, page_no, nass, matn_start, matn_end FROM hadiths
                     WHERE book_id IN ({",".join(str(int(b)) for b in books)}){only} ORDER BY id""").fetchall()
    for hid, bid, gid, page, nass, ms, me in hs:
        if not nass:
            continue
        norm, pos = norm_map(nass)
        if not norm:
            continue
        # search from the start of the matn (the remark follows it; matn_end is approximate)
        start_n = 0
        if ms is not None:
            start_n = next((k for k, p in enumerate(pos) if p >= int(ms)), len(norm))
        tail_n = None
        if me is not None:
            tail_n = next((k for k, p in enumerate(pos) if p >= int(me)), len(norm))
        hay = norm[start_n:]
        chs = chains.get(int(hid), [])
        links = Counter(x for _, ch in chs for x in ch)
        ids_links = tuple(sorted((x, k) for x, k in links.items() if x not in (30000, 30001, 30002, 1131)))
        taken: list[tuple[int, int]] = []
        for F in FAMILIES:
            if F.books is not None and int(bid) not in F.books:
                continue
            for m in F.pattern.finditer(hay):
                a, b = m.start() + start_n, m.end() + start_n
                if any(a < tb and ta < b and F.claim_type == tt for ta, tb, tt in taken):
                    continue            # one claim per span and type (e.g. tafarrud_bihi inside a Tabarani formula)
                taken.append((a, b, F.claim_type))
                s0, s1, span = source_span(nass, pos, a, b)
                g = m.groupdict()
                row = {"book_id": int(bid), "critic": critic(bid), "hadith_id": int(hid),
                       "group_id": None if gid is None else int(gid), "page_no": page,
                       "span": span, "span_start": s0, "span_end": s1, "in_tail": tail_n is not None and a >= tail_n - 2,
                       "claim_type": F.claim_type, "family": F.key, "grade": g.get("grade") or F.slots.get("grade"),
                       "scope": g.get("scope"), "clause": g.get("clause") or g.get("who") or g.get("g2"),
                       "x_text": g.get("x") or g.get("x0"), "y_text": g.get("y"), "z_text": g.get("z"),
                       "names": None, "sanad_ids": [s for s, _ in chs]}
                if F.key == "tirmidhi_verdict" and row["scope"] and row["scope"].startswith("من حديث"):
                    row["scope"] = "min_hadith"
                elif row["scope"] == "من هذا الوجه":
                    row["scope"] = "min_hadha_al_wajh"
                elif row["scope"] == "لا نعرفه":
                    row["scope"] = None
                if F.key == "wafi_al_bab":
                    row["names"] = split_names(g["names"])
                for k in ("x", "y", "z"):
                    rid, why = R.resolve(row[f"{k}_text"], ids_links) if row[f"{k}_text"] else (None, None)
                    row[f"{k}_id"], row[f"{k}_reason"] = rid, why
                # «إلا Y1 وY2»: the other names of the Y slot (critics.py keeps those directly below X)
                row["y_alt_ids"] = []
                if row["y_text"]:
                    parts = split_names(row["y_text"])
                    if len(parts) > 1:
                        if row["y_id"] is None:
                            rid, why = R.resolve(parts[0], ids_links)
                            if rid:
                                row["y_id"], row["y_reason"] = rid, None
                        for part in parts[1:]:
                            rid, _ = R.resolve(part, ids_links)
                            if rid and rid != row["y_id"] and rid not in row["y_alt_ids"]:
                                row["y_alt_ids"].append(rid)
                rows.append(row)
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values(["hadith_id", "span_start", "claim_type"]).reset_index(drop=True)
        df.insert(0, "claim_id", range(1, len(df) + 1))
        # the columns the site's critics panel reads (src/itibar/site/data.py): the quote, where it is, and the
        # result of scoring it (critics.score fills `result`; until then the claim is not scored)
        bn = dict(con.sql("SELECT id, name FROM books").fetchall())
        df["quote"] = df["span"]
        df["citation"] = [f"{bn.get(b, b)}, p. {p}, hadith {h}" for b, p, h in
                          zip(df["book_id"], df["page_no"], df["hadith_id"])]
        df["url"] = None
        df["result"] = "not scored"
    if write:
        out_path().parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path(), index=False)
    return df


# names in a «وفي الباب» list: split on the conjunction, keeping companion names that begin with «و»
_W_NAMES = ("وايل", "واثله", "وابصه", "وهب", "وحشي", "وراد", "وهبان", "وردان", "واقد", "وقاص")


_NAME_JOIN = ("بن", "ابي", "ابو", "ام", "عبد", "بنت", "ابن")


def split_names(s: str | None) -> list[str]:
    """«علي وابن عمر وسعد بن ابي وقاص» -> [علي, ابن عمر, سعد بن ابي وقاص]: a token «وX» starts a new name unless it
    follows a name part that needs a continuation («بن», «ابي» …) or X is a companion name that begins with «و»."""
    if not s:
        return []
    out: list[list[str]] = []
    for t in s.split():
        if out and out[-1][-1] in _NAME_JOIN:
            out[-1].append(t)
        elif t.startswith("و") and len(t) > 2 and out:
            out.append([t[1:]] if not any(t.startswith(w) for w in _W_NAMES) or t[1:].startswith(_W_NAMES)
                       else [t])
        elif not out:
            out.append([t])
        else:
            out[-1].append(t)
    return [" ".join(x) for x in out if x]


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "extract"
    if cmd == "survey":
        df = survey()
        df.to_csv(paths.REPORTS_DIR / "verdicts_survey.csv", index=False)
        print(len(df))
    elif cmd == "extract":
        df = extract()
        print(f"{len(df):,} claims", df["claim_type"].value_counts().to_dict())


if __name__ == "__main__":
    main()
