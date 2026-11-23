"""The source's recorded grade, decoded (PR 7 §1–2).

`sanads.hukum` is a sentence filled by a program from the source's narrator table, and `sanads.matn_no` its code:
«إسناده متصل ، رجاله ثقات», «إسناده حسن رجاله ثقات عدا X وهو L», «إسناد ضعيف فيه X وهو L», «إسناد ضعيف لأن
به موضع إرسال …». This module parses every sentence into its template family and slots, states the template as a
v1 ruleset (`source_template`, config/structure.yaml: derive.source_template) and reproduces the recorded chain
code chain by chain; then states how the hadith grade and the group grade follow from the chain codes.

  chain_code(rawis, nar, scale)   the template's code for one chain (also used by the pipeline on itibar's chains)
  parse(hukum)                    template family and slots of one sentence
  decode()                        out/source_template.parquet: one row per chain with the parse, the template code,
                                  the recorded code and, where they differ, the residual class
  report()                        reports/source_grade.md (+ reports/source_templates.csv, every skeleton)

  python -m itibar.source_template [decode|report|all]

The template code (decoded, reports/source_grade.md):
  level      max rawis.rank_no over every position (the compiler at pos 0 included); an undescribed narrator
             (rank_no 0) reads «مجهول الحال», level 7; the unnamed person is not graded
  code       grades.yaml code_source of that level: 1-3 -> 0, 4-6 -> 1, 7-9 -> 2, 10 -> 3, 11 -> 4, 12 -> 5
  breaks     n = inqita' markers + ta'liq markers + 1 if (an irsal marker, or an unnamed person with an inqita' or
             ta'liq marker in the chain); n = 1 -> code >= 2, n >= 2 -> code >= 3
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

from itibar import config, data, grades, lists, paths

SEP = " ، "
GRADE = {0: "صحيح", 1: "حسن", 2: "ضعيف", 3: "شديد الضعف", 4: "متهم بالوضع", 5: "موضوع"}
GAP_IDS = {30000: "inqita", 30001: "taliq", 30002: "irsal"}
MUBHAM_ID = 1131


def cfg() -> dict:
    return (config.load("structure").get("derive") or {}).get("source_template") or {}


def out_path() -> Path:
    return paths.OUT_DIR / "source_template.parquet"


# ---------------------------------------------------------------- the template code

@dataclass
class TemplateCode:
    code: int
    level: int | None             # the weakest graded level (rank_no), None if no graded narrator
    level_code: int               # code of that level before the break rule
    n_breaks: int
    breaks: tuple[str, ...]       # break kinds counted (irsal, inqita, taliq; "unnamed_as_irsal")
    weakest_positions: tuple[int, ...]


def chain_code(rawis, rank_no, is_stub, scale: grades.GradeScale | None = None, c: dict | None = None,
               skip=()) -> TemplateCode:
    """The source template's code for one chain. `rank_no` and `is_stub` are indexable by rawi id
    (load.Narrators arrays or dicts); `skip` lists positions left ungraded (a counterfactual: the residue's
    book_role tag grades the chain without its book-role positions)."""
    c = c if c is not None else cfg()
    scale = scale or grades.load()
    codes = str(c.get("codes", "source"))
    stub_level = int(c.get("stub_level", 7))
    allpos = str(c.get("positions", "all")) == "all"
    unnamed_rule = str(c.get("unnamed", "ignored_unless_break"))
    brk_codes = {int(k): int(v) for k, v in (c.get("breaks") or {1: 2, 2: 3}).items()}
    nq = nt = nr = 0
    mub = False
    lv_at: dict[int, int] = {}
    for p, rid in enumerate(rawis):
        rid = int(rid)
        k = GAP_IDS.get(rid)
        if k == "inqita":
            nq += 1
        elif k == "taliq":
            nt += 1
        elif k == "irsal":
            nr += 1
        elif rid == MUBHAM_ID:
            mub = True
        elif (allpos or p > 0) and p not in skip:
            rn = int(rank_no[rid])
            if rn <= 0 or int(is_stub[rid]):
                rn = stub_level
            lv_at[p] = rn
    level = max(lv_at.values()) if lv_at else None
    level_code = scale.code_of_level(level, codes) if level is not None else 0
    kinds = ["inqita"] * nq + ["taliq"] * nt
    if nr:
        kinds.append("irsal")
    elif mub and (nq or nt) and unnamed_rule == "ignored_unless_break":
        kinds.append("unnamed_as_irsal")
    elif mub and unnamed_rule == "irsal":
        kinds.append("unnamed_as_irsal")
    n = len(kinds)
    code = level_code
    if n:
        floor = brk_codes.get(min(n, max(brk_codes)), 2)
        code = max(code, floor)
    weakest = tuple(p for p, v in lv_at.items() if v == level) if level is not None else ()
    return TemplateCode(code=int(code), level=level, level_code=int(level_code), n_breaks=n, breaks=tuple(kinds),
                        weakest_positions=weakest)


def group_code(codes: list[tuple[int, int]]) -> tuple[int | None, int | None]:
    """(code, sanad_id) of the group's template grade: the lowest chain code, ties by lowest sanad id."""
    if not codes:
        return None, None
    code, sid = min(codes)
    return int(code), int(sid)


# ---------------------------------------------------------------- parsing the sentence

@lru_cache(maxsize=1)
def labels() -> tuple[str, ...]:
    con = data.views()
    labs = {r[0].strip() for r in con.sql("SELECT DISTINCT rank FROM rawis WHERE rank IS NOT NULL").fetchall()}
    return tuple(sorted((x for x in labs if x), key=len, reverse=True))


def normalize_hukum(h: str | None) -> str:
    return re.sub(r"\s*[،,]\s*", SEP, (h or "").strip()).strip()


@dataclass
class Parsed:
    text: str
    opening: str | None = None
    thiqat: str | None = None                 # thiqat | thiqat_saduq («رجاله ثقات وصدوقيين»)
    named: list[tuple[str, str | None]] = field(default_factory=list)      # (name, verdict word)
    muttaham: list[tuple[str, str | None]] = field(default_factory=list)   # «متهم بالوضع وهو X [وهو L]»
    breaks: list[str] = field(default_factory=list)
    between: list[str] = field(default_factory=list)                        # «موضع انقطاع بين X وY» (raw)
    rijal: str | None = None                  # الشيخين | البخاري | مسلم
    rijal_exc: list[tuple[str, str]] = field(default_factory=list)          # (names, how: تعليقًا | مقرونًا)
    hand: list[str] = field(default_factory=list)                            # clauses outside the template
    unparsed: list[str] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return [n for n, _ in self.named + self.muttaham if n and not n.startswith("<")]

    @property
    def ok(self) -> bool:
        return not self.unparsed and self.opening is not None


OPENINGS = [
    ("sahih", r"^إسناده متصل ، رجاله ثقات"),
    ("sahih_truncated", r"^إسناده متصل ، و$"),
    ("hasan_mutabaat", r"^إسناده حسن في المتابعات والشواهد"),
    ("hasan", r"^إسناده حسن"),
    ("hasan_plain", r"^إسناد حسن"),
    ("daif_yuhsan", r"^إسناده ضعيف ويحسن إذا توبع"),
    ("daif_ihi", r"^إسناده ضعيف"),
    ("daif", r"^إسناد ضعيف"),
    ("shadid", r"^إسناد شديد الضعف"),
    ("mawdu", r"^إسناد موضوع"),
    ("mudal", r"^إسناد معضل"),
    ("muttaham", r"^إسناد(?= فيه (?:متهم|متهمان|متهمون) بالوضع)"),
    ("wadda", r"^إسناد(?= فيه راويان وضاعان)"),
    ("fihi", r"^إسناد(?= فيه )"),
]
OPENING_CODE = {"sahih": 0, "sahih_truncated": 0, "hasan_mutabaat": 1, "hasan": 1, "hasan_plain": 1,
                "daif_yuhsan": 2, "daif_ihi": 2, "daif": 2, "shadid": 3, "mawdu": None, "mudal": None,
                "muttaham": 4, "wadda": 5, "fihi": 5}
HAND = [
    ("unnamed_companion_clause", "وجهالة الصحابي لا تضر"),
    ("shart_clause", "على شرط"),
    ("tadlis_clause", "متهم بالتدليس"),
    ("saqt_clause", "سقط"),
    ("rijal_bukhari_ma_ada", "رجاله رجال بخاري"),
]


def _match_label(after: str) -> str:
    for lab in labels():
        if after.startswith(lab) and (len(after) == len(lab) or after[len(lab):].startswith(SEP)):
            return lab
    j = after.find(SEP)
    return after if j < 0 else after[:j]


def split_items(text: str) -> list[tuple[str, str | None]]:
    """«X وهو L ، وY وهو L2 ، وZ» -> [(X, L), (Y, L2), (Z, None)]; the verdict word is matched against the
    rawis.rank vocabulary (labels can contain « ، »)."""
    items: list[tuple[str, str | None]] = []
    rest = text.strip()
    while rest:
        i = rest.find(" وهو ")
        j = rest.find(SEP + "و")
        if i < 0 or 0 <= j < i:
            if j < 0:
                items.append((rest.strip(), None))
                break
            items.append((rest[:j].strip(), None))
            rest = rest[j + len(SEP) + 1:]
            continue
        name, after = rest[:i].strip(), rest[i + 5:]
        lab = _match_label(after)
        items.append((name, lab))
        rest = after[len(lab):]
        if rest.startswith(SEP):
            rest = rest[len(SEP):]
            if rest.startswith("و"):
                rest = rest[1:]
            else:
                items.append(("<?>" + rest, None))
                break
        elif rest:
            items.append(("<?>" + rest, None))
            break
    return items


def _muttaham_items(body: str) -> list[tuple[str, str | None]]:
    out = []
    for n, lab in split_items(body):
        out.append((n, lab))
    return out


def parse(h: str | None) -> Parsed:
    t = normalize_hukum(h)
    P = Parsed(text=t)
    for clause_kind, needle in HAND:
        if needle in t:
            P.hand.append(clause_kind)
    rest = None
    for k, pat in OPENINGS:
        m = re.match(pat, t)
        if m:
            P.opening, rest = k, t[m.end():]
            break
    if P.opening is None:
        P.unparsed.append(t)
        return P
    rest = rest.strip()
    while rest:
        rest = rest.lstrip(" ،").strip()
        if not rest:
            break
        if rest == "و":
            P.unparsed.append("<trailing و>")
            break
        m = re.match(r"^(?:و ?)?(?:باقي )?(?:و)?رجاله ثقات( وصدوقيين)?(?: عدا (.*?))?(?= ، رجاله رجال| ، و?رجاله رجال|$)",
                     rest)
        if m and re.match(r"^(?:رجاله ثقات|و ?باقي|ورجاله ثقات)", rest):
            P.thiqat = "thiqat_saduq" if m.group(1) else "thiqat"
            if m.group(2):
                P.named += split_items(m.group(2))
            rest = rest[m.end():]
            continue
        m = re.match(r"^و?رجاله رجال (الشيخين|البخاري|مسلم|بخاري)(?: (?:ما)?عدا ?(.*))?$", rest)
        if m:
            P.rijal = "البخاري" if m.group(1) == "بخاري" else m.group(1)
            exc = (m.group(2) or "").strip()
            pat = r"^(.*?) روى (?:له|لهما|لهم) البخاري (تعليقًا|مقرونًا بغير\w*)(?: و(.*))?$"
            mm = re.match(pat, exc) if exc else None
            while mm:
                P.rijal_exc.append((mm.group(1).strip(), "taliq" if mm.group(2).startswith("تعليق") else "maqrun"))
                mm = re.match(pat, mm.group(3)) if mm.group(3) else None
            if m.group(2) is not None and not P.rijal_exc:
                P.rijal_exc.append((exc or "<empty>", "?"))
            rest = ""
            continue
        m = re.match(r"^و?(?:لأن به|لوجود) (.*?)(?= ، |$)", rest)
        if m:
            for part in re.split(r" و(?=موضع|اسم|سقط)", m.group(1)):
                mm = re.match(r"^موضع انقطاع بين (.+)$", part)
                if mm:
                    P.breaks.append("inqita")
                    P.between.append(mm.group(1))
                elif part.startswith("موضع إرسال"):
                    P.breaks.append("irsal")
                elif part.startswith("موضع تعليق"):
                    P.breaks.append("taliq")
                elif part.startswith("موضع انقطاع"):
                    P.breaks.append("inqita")
                elif "سقط" in part:
                    P.breaks.append("saqt")
                else:
                    P.unparsed.append(part)
            rest = rest[m.end():]
            continue
        m = re.match(r"^وفي الإسناد (.+?) متهم بالتدليس", rest)
        if m:
            P.named.append((m.group(1).strip(), "متهم بالتدليس"))
            rest = rest[m.end():]
            continue
        m = re.match(r"^(?:و)?فيه ?(.*)$", rest)
        if m:
            body = m.group(1)
            mm = re.match(r"^(?:و)?(?:متهم|متهمان|متهمون) بالوضع (?:وهو|وهما|وهم) (.*)$", body) \
                or re.match(r"^راويان وضاعان هما (.*)$", body)
            if mm:
                P.muttaham += _muttaham_items(mm.group(1))
                rest = ""
                continue
            mm = re.match(r"^راو مجهول يروي (?:عن )?(.*)$", body)
            if mm:
                P.named.append(("<majhul>", "مجهول"))
                if mm.group(1):
                    P.named.append((mm.group(1).strip(), None))
                rest = ""
                continue
            k = body.find(" ، رجاله رجال ")
            if k < 0:
                k = body.find(" ، ورجاله رجال ")
            if k >= 0:
                P.named += split_items(body[:k])
                rest = body[k:]
                continue
            k = body.find(" ، ومتهم")
            if k >= 0:
                P.named += split_items(body[:k])
                rest = "فيه " + body[k + 4:]
                continue
            if body:
                P.named += split_items(body)
            else:
                P.named.append(("<empty>", None))
            rest = ""
            continue
        m = re.match(r"^(?:و)?(?:متهم|متهمان|متهمون) بالوضع (?:وهو|وهما|وهم) (.*)$", rest)
        if m:
            P.muttaham += _muttaham_items(m.group(1))
            rest = ""
            continue
        if any(needle in rest for _, needle in HAND):
            rest = ""
            continue
        P.unparsed.append(rest)
        rest = ""
    if any(n.startswith("<?>") for n, _ in P.named + P.muttaham):
        P.unparsed.append("list")
    return P


def skeleton(P: Parsed) -> str:
    """The sentence with every parsed name -> {N} and verdict word -> {L}; a list of k items is written once
    with ×k."""
    t = P.text
    subs = sorted({n for n, _ in P.named + P.muttaham if n and not n.startswith("<")}
                  | {n for n, _ in P.rijal_exc if n and not n.startswith("<")}, key=len, reverse=True)
    for n in subs:
        t = t.replace(n, "{N}")
    for b in P.between:
        t = t.replace(b, "{N} و{N}") if b not in subs else t
    labs = sorted({lab for _, lab in P.named + P.muttaham if lab}, key=len, reverse=True)
    for lab in labs:
        t = re.sub(r"(?<=وهو )" + re.escape(lab) + r"(?=$| ،)", "{L}", t)
    t = re.sub(r"\{N\} و\{N\}(?= روى لهما)", "{N}×2", t)

    def collapse(m):
        k = m.group(0).count("{N}")
        return "{N} وهو {L} ×%d" % k
    t = re.sub(r"\{N\} وهو \{L\}(?: ، و\{N\} وهو \{L\})+", collapse, t)
    return t


def family(P: Parsed) -> str:
    """The skeleton with list lengths dropped: the template family."""
    return re.sub(r" ×\d+", "", skeleton(P)).replace("{N}×2", "{N}")


# ---------------------------------------------------------------- decoding the corpus

def _chains(con) -> pd.DataFrame:
    return con.sql(
        """SELECT s.id AS sanad_id, s.hadith_id, h.group_id, h.book_id, s.matn_no, s.hukum, s.max_rank,
                  h.matn_no AS hadith_matn_no, list(sr.rawi_id ORDER BY sr.pos) AS chain
           FROM sanads s JOIN hadiths h ON h.id = s.hadith_id JOIN sanad_rawis sr ON sr.sanad_id = s.id
           GROUP BY ALL ORDER BY s.id"""
    ).df()


def decode(write: bool = True) -> pd.DataFrame:
    con = data.views()
    from itibar import load
    scale = grades.load()
    nar = load.narrators(con, scale)
    r = con.sql("SELECT id, nickname, coalesce(rank, '') AS rank, is_bukhari, is_muslim FROM rawis").df()
    nick = dict(zip(r["id"], r["nickname"]))
    rank_lab = dict(zip(r["id"], r["rank"]))
    is_b = dict(zip(r["id"], r["is_bukhari"]))
    is_m = dict(zip(r["id"], r["is_muslim"]))
    ch = _chains(con)
    parsed = {h: parse(h) for h in ch["hukum"].unique()}
    c = cfg()
    rows = []
    hadith_nicks: dict[int, set] = defaultdict(set)
    for hid, chain in zip(ch["hadith_id"], ch["chain"]):
        hadith_nicks[int(hid)].update(nick.get(int(x)) for x in chain)
    for t in ch.itertuples(index=False):
        chain = [int(x) for x in t.chain]
        tc = chain_code(chain, nar.rank_no, nar.is_stub, scale, c)
        P = parsed[t.hukum]
        pos_of: dict[str, list[int]] = defaultdict(list)
        for p, x in enumerate(chain):
            pos_of[nick.get(x)].append(p)
        named = P.names
        named_pos = [pos_of.get(n, []) for n in named]
        in_chain = [bool(ps) for ps in named_pos]
        lab_ok = []
        for (n, lab) in P.named + P.muttaham:
            if not n or n.startswith("<") or lab is None:
                continue
            ps = pos_of.get(n)
            if ps:
                lab_ok.append(lab.strip() in {rank_lab.get(chain[p], "").strip() for p in ps})
        flat_named = sorted({p for ps in named_pos for p in ps})
        real = [x for x in chain if x not in GAP_IDS and x != MUBHAM_ID]
        graded = real[1:] if len(real) > 1 else real
        rows.append({
            "sanad_id": int(t.sanad_id), "hadith_id": int(t.hadith_id),
            "group_id": None if pd.isna(t.group_id) else int(t.group_id), "book_id": int(t.book_id),
            "matn_no": int(t.matn_no), "hadith_matn_no": int(t.hadith_matn_no),
            "opening": P.opening, "family": family(P), "skeleton": skeleton(P), "parsed": P.ok,
            "hand": list(P.hand), "breaks_text": list(P.breaks), "rijal": P.rijal,
            "rijal_exc": [f"{n}|{how}" for n, how in P.rijal_exc],
            "n_named": len(named), "n_named_in_chain": sum(in_chain),
            "named_positions": flat_named,
            "named_not_in_chain": [n for n, ok in zip(named, in_chain) if not ok],
            "named_in_hadith": all(n in hadith_nicks[int(t.hadith_id)] for n in named),
            "labels_checked": len(lab_ok), "labels_match": sum(lab_ok),
            "template_code": tc.code, "template_level": tc.level, "template_level_code": tc.level_code,
            "template_breaks": list(tc.breaks), "template_weakest": list(tc.weakest_positions),
            "named_among_template_weakest": (bool(flat_named) and set(flat_named) <= set(tc.weakest_positions)
                                             if flat_named else None),
            "opening_code": OPENING_CODE.get(P.opening),
            "all_bukhari_muslim": all(is_b.get(x) and is_m.get(x) for x in graded),
            "all_bukhari": all(is_b.get(x) for x in graded), "all_muslim": all(is_m.get(x) for x in graded),
            "chain_len": len(chain),
        })
    df = pd.DataFrame(rows)
    df["hit"] = df["template_code"] == df["matn_no"]
    nch = df.groupby("hadith_id")["sanad_id"].transform("size")
    df["hadith_n_chains"] = nch
    key_t = df.groupby("hadith_id")["template_code"].apply(lambda s: tuple(sorted(s)))
    key_r = df.groupby("hadith_id")["matn_no"].apply(lambda s: tuple(sorted(s)))
    df["hadith_multiset_match"] = df["hadith_id"].map((key_t == key_r).to_dict())
    df["residual"] = [residual_class(row) for row in df.itertuples(index=False)]
    # itibar's weakest positions (out/chains.parquet, v1: book-role positions excluded)
    if paths.chains_path().exists():
        w = pd.read_parquet(paths.chains_path(), columns=["sanad_id", "weakest_positions", "book_role_positions"])
        wm = dict(zip(w["sanad_id"], w["weakest_positions"]))
        df["itibar_weakest"] = [list(wm[s]) if s in wm and wm[s] is not None else [] for s in df["sanad_id"]]
        df["named_among_itibar_weakest"] = [(set(np) <= set(iw) if len(np) else None)
                                            for np, iw in zip(df["named_positions"], df["itibar_weakest"])]
    if write:
        out_path().parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path(), index=False)
    return df


def residual_class(r) -> str | None:
    """Why the template code differs from the recorded chain code (None when it does not). In order:"""
    if r.hit:
        return None
    if r.hadith_n_chains > 1 and r.hadith_multiset_match:
        # the hukums of this hadith are the template's codes of its chains, attached to other chains
        return "misattached_named" if (r.n_named and r.named_not_in_chain and r.named_in_hadith) else "misattached"
    if not r.parsed or r.hand or r.opening in ("mudal",):
        return "outside_template"
    if r.labels_checked and r.labels_match < r.labels_checked:
        return "label_changed"
    if r.n_named and r.named_not_in_chain:
        return "named_elsewhere" if r.named_in_hadith else "named_not_in_hadith"
    if (r.skeleton or "").endswith("، وفيه"):
        return "empty_list"
    if r.opening == "daif_yuhsan" and r.template_level == 6:
        return "maqbul_as_yuhsan"
    if r.opening == "daif_ihi":
        return "unnamed_as_weakness"
    oc = r.opening_code
    if oc is not None and oc != r.template_code and oc == r.matn_no:
        return "sentence_describes_another_chain"
    if oc is not None and oc == r.template_code:
        return "code_set_apart_from_sentence"
    return "other"


# ---------------------------------------------------------------- report

def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        cells = []
        for v in r:
            if isinstance(v, float):
                cells.append("" if pd.isna(v) else (f"{v:.2%}" if 0 <= v <= 1 and not float(v).is_integer()
                                                    else f"{v:,.0f}"))
            elif isinstance(v, (int,)) and not isinstance(v, bool):
                cells.append(f"{v:,}")
            else:
                cells.append("" if v is None else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _pct(a, b) -> str:
    return f"{a / b:.2%}" if b else "—"


def group_rule(con=None) -> pd.DataFrame:
    """One row per group with chains: the recorded group grade beside the recorded chain codes."""
    con = con or data.views()
    return con.sql(
        """WITH c AS (SELECT h.group_id g, min(s.matn_no) best, max(s.matn_no) worst, count(*) n,
                             mode(s.matn_no) modal, count(DISTINCT h.id) n_hadith
                      FROM sanads s JOIN hadiths h ON h.id = s.hadith_id WHERE h.group_id IS NOT NULL GROUP BY 1),
                hh AS (SELECT group_id g, min(matn_no) FILTER (WHERE matn_no BETWEEN 0 AND 5) hbest
                       FROM hadiths WHERE group_id IS NOT NULL GROUP BY 1)
           SELECT mg.id AS group_id, mg.matn_no AS group_code, c.best, c.worst, c.modal, c.n AS n_chains, c.n_hadith,
                  hh.hbest AS hadith_best
           FROM meaning_groups mg JOIN c ON c.g = mg.id LEFT JOIN hh ON hh.g = mg.id ORDER BY 1"""
    ).df()


def report(df: pd.DataFrame | None = None) -> Path:
    con = data.views()
    df = df if df is not None else pd.read_parquet(out_path())
    n = len(df)
    L: list[str] = []
    w = L.append
    w("# What the recorded grade is: the source's grade, decoded\n")
    w("Generated by `make source-template` (`itibar.source_template`) from `sanads.hukum`, `sanads.matn_no`, "
      "`hadiths.matn_no` and `meaning_groups.matn_no`, all chains of the corpus. The decoded template is the v1 "
      "ruleset `source_template` (`config/structure.yaml: derive.source_template`); the pipeline applies it to "
      "every chain (`out/chains.parquet: code_source_template`) and group (`out/records.parquet`). Nothing "
      "here is fitted to itibar's own grades.\n")
    # ---- 1. the sentences
    w("## 1. The sentences: template families\n")
    fam = df.groupby("family").agg(chains=("sanad_id", "size"), distinct=("skeleton", "nunique")).reset_index()
    codes = df.pivot_table(index="family", columns="matn_no", values="sanad_id", aggfunc="size", fill_value=0)
    fam = fam.join(codes, on="family").sort_values("chains", ascending=False)
    n_dist = df["skeleton"].nunique()
    w(f"`sanads.hukum` holds {df['skeleton'].size:,} sentences, "
      f"{con.sql('SELECT count(DISTINCT hukum) FROM sanads').fetchall()[0][0]:,} distinct strings. Each is parsed into "
      "an opening (the code phrase), the narrators it names with the verdict word given for each («فيه X وهو L», "
      "«عدا X وهو L», «متهم بالوضع وهو X»), the break markers («لأن به موضع إرسال / تعليق / انقطاع بين X وY»), "
      "the «رجاله رجال الشيخين / البخاري / مسلم» clause and its exceptions («روى له البخاري تعليقًا / مقرونًا "
      f"بغيره»). Replacing the names by {{N}} and the verdict words by {{L}} leaves {n_dist:,} skeletons "
      f"(`reports/source_templates.csv`, every one with its count and code distribution) in {len(fam):,} families "
      f"(list lengths dropped). {int(df['parsed'].sum()):,} sentences ({_pct(int(df['parsed'].sum()), n)}) parse "
      "completely; the rest are listed in §1.2.\n")
    top = fam.head(60).copy()
    top.columns = [str(c) if not isinstance(c, (int,)) else f"code {c}" for c in top.columns]
    w("### 1.1 The 60 most frequent families, with the recorded chain code (`sanads.matn_no`)\n")
    w(_md(top.rename(columns={"family": "family ({N} name, {L} verdict word)"})) + "\n")
    w("Every family's code is fixed by its opening: «إسناده متصل ، رجاله ثقات» 0; «إسناده حسن …», «إسناد حسن», "
      "«إسناده حسن في المتابعات والشواهد …» 1; «إسناده ضعيف ويحسن إذا توبع …», «إسناد ضعيف …» 2; "
      "«إسناد شديد الضعف …» 3; «إسناد فيه متهم بالوضع …» 4; «إسناد فيه X وهو كذاب» 5. «إسناد موضوع لأن به …» "
      "(the opening says موضوع) carries 4 or 5, the code of its worst narrator.\n")
    oc = df[df["opening_code"].notna()]
    w(f"Opening phrase and recorded code agree on {_pct(int((oc['opening_code'] == oc['matn_no']).sum()), len(oc))} "
      f"of the {len(oc):,} chains whose opening fixes a code.\n")
    bad = df[~df["parsed"]]
    w("### 1.2 Sentences outside the template grammar\n")
    hand = Counter(h for hs in df["hand"] for h in hs)
    w(f"{len(bad):,} sentences do not parse completely. Hand-written clauses (another hand than the template): "
      + ", ".join(f"`{k}` {v:,}" for k, v in hand.most_common()) + ". Examples:\n")
    for t in bad.drop_duplicates("skeleton").head(12).itertuples(index=False):
        hk = con.sql(f"SELECT hukum FROM sanads WHERE id = {t.sanad_id}").fetchall()[0][0]
        w(f"- sanad {t.sanad_id} (code {t.matn_no}): «{hk.strip()}»")
    w("")
    # ---- 2. the verdict word
    w("## 2. What the template reads\n")
    lc, lm = int(df["labels_checked"].sum()), int(df["labels_match"].sum())
    w(f"**The verdict word is `rawis.rank`.** Of the {lc:,} named narrators found in their chain, the word after "
      f"«وهو» equals that narrator's `rawis.rank` label in {lm:,} ({_pct(lm, lc)}); the source does not re-grade "
      "narrators in the sentence. The mismatches are labels edited after the sentence was written:\n")
    mm = _label_mismatches(con, df)
    w(_md(mm.head(15)) + "\n")
    # weakest: on chains whose sentence is attached to them (template code = record)
    nn = df[df["hit"] & df["named_among_template_weakest"].notna()]
    cover = df[df["hit"] & df["named_positions"].map(len).gt(0)]
    covers = [set(tw) <= set(np) for tw, np in zip(cover["template_weakest"], cover["named_positions"])]
    w(f"**The narrators the sentence names include the template's weakest.** On the {len(cover):,} chains whose "
      f"sentence names narrators of the chain and whose recorded code the template reproduces, every position at the "
      f"chain's weakest level is named in {_pct(sum(covers), len(cover))}; every narrator named is at the weakest "
      f"level in {_pct(int(nn['named_among_template_weakest'].sum()), len(nn))} — the «عدا» lists name every "
      "narrator below the base wording («رجاله ثقات عدا X وهو صدوق ، وY وهو مقبول»), not only the weakest.")
    if "named_among_itibar_weakest" in df:
        hit_named = df[df["hit"] & df["named_positions"].map(len).gt(0)]
        ov = [bool(set(np) & set(iw)) for np, iw in zip(hit_named["named_positions"], hit_named["itibar_weakest"])] \
            if "itibar_weakest" in hit_named else []
        if ov:
            w(f" A narrator the sentence names is among itibar's v1 weakest positions (book-role positions excluded) "
              f"in {_pct(sum(ov), len(ov))} of them; the rest are chains whose weakest narrator is the compiler at "
              "pos 0, whom the template grades and itibar's v1 does not, or whose weakest itibar position is the "
              "unnamed person, whom the template does not grade.")
    w("\n")
    w(_level_table(df))
    w(_reads_table(df, con))
    # ---- 3. reproduction
    w("## 3. The template as a v1 ruleset (`source_template`) and its reproduction\n")
    w("```\n" + "\n".join(x[2:] if x.startswith("  ") else x for x in
                        __doc__.split("The template code (decoded, reports/source_grade.md):", 1)[1].strip("\n").splitlines())
      + "\n```\n")
    hit = int(df["hit"].sum())
    one = df[df["hadith_n_chains"] == 1]
    multi = df[df["hadith_n_chains"] > 1]
    msok = int(df["hadith_multiset_match"].sum())
    w(f"**Chain by chain**, the template code equals `sanads.matn_no` for {hit:,} of {n:,} chains "
      f"(**{_pct(hit, n)}**). In hadith with one chain: {int(one['hit'].sum()):,} of {len(one):,} "
      f"(**{_pct(int(one['hit'].sum()), len(one))}**); in hadith with several: {int(multi['hit'].sum()):,} of "
      f"{len(multi):,} ({_pct(int(multi['hit'].sum()), len(multi))}).\n")
    w("**In hadith with several chains the sentences are attached to the wrong chains.** Compared as a multiset "
      "over the hadith's chains, the template codes equal the recorded codes in "
      f"{msok:,} chains' hadith ({_pct(msok, n)} of all chains). Where they match as a multiset and not chain by "
      "chain, the recorded sentence often names a narrator who is in another chain of the same hadith and not in "
      "this one. The pairing is close to random:\n")
    w(_permutation_table(df))
    w("So `sanads.matn_no` and `sanads.hukum` describe a chain of the hadith, not necessarily the chain on their "
      "row. Codes read per hadith (the hadith grade, below) or per group are unaffected (a minimum does not "
      "depend on the pairing); anything read per chain — the residue's former `chain_choice` among them — is.\n")
    res = df[~df["hit"]]["residual"].value_counts()
    w("### 3.1 Every chain the template misses, by class\n")
    w(_md(pd.DataFrame({"class": res.index, "chains": res.values, "share of misses": res.values / max(len(df) - hit, 1)})))
    w("")
    w(_residual_notes())
    for k in res.index:
        sm = df[df["residual"] == k].sample(min(3, int(res[k])), random_state=7)
        w(f"**`{k}`** ({int(res[k]):,}):\n")
        for t in sm.itertuples(index=False):
            w(_print_chain(con, t))
        w("")
    # ---- 4. the hadith and the group
    w("## 4. The hadith grade and the group grade\n")
    w(_hadith_rule(con, df))
    w(_group_rule(con))
    out = paths.REPORTS_DIR / "source_grade.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sk = df.groupby(["family", "skeleton"]).agg(chains=("sanad_id", "size")).reset_index()
    sk = sk.join(df.pivot_table(index="skeleton", columns="matn_no", values="sanad_id", aggfunc="size",
                                fill_value=0).add_prefix("code_"), on="skeleton")
    sk.sort_values("chains", ascending=False).to_csv(paths.REPORTS_DIR / "source_templates.csv", index=False)
    return out


def _label_mismatches(con, df) -> pd.DataFrame:
    r = con.sql("SELECT id, nickname, coalesce(rank, '') AS rank, rank_no FROM rawis").df()
    by_nick = defaultdict(list)
    for i, nk, rk, rn in zip(r["id"], r["nickname"], r["rank"], r["rank_no"]):
        by_nick[nk].append((rk, rn))
    cnt: Counter = Counter()
    sub = df[df["labels_checked"] > df["labels_match"]]
    hk = dict(con.sql("SELECT id, hukum FROM sanads").fetchall())
    for sid in sub["sanad_id"]:
        P = parse(hk[sid])
        for nme, lab in P.named + P.muttaham:
            if lab and nme in by_nick:
                cur = {x for x, _ in by_nick[nme]}
                if lab.strip() not in {c.strip() for c in cur}:
                    cnt[(lab, by_nick[nme][0][0], int(by_nick[nme][0][1]))] += 1
    return pd.DataFrame([{"word in the sentence": a, "rawis.rank now": b, "rank_no": c, "chains": v}
                         for (a, b, c), v in cnt.most_common()])


def _level_table(df) -> str:
    one = df[(df["hadith_n_chains"] == 1) & (df["template_breaks"].map(len) == 0)]
    t = one.pivot_table(index="template_level", columns="matn_no", values="sanad_id", aggfunc="size", fill_value=0)
    t.index = [f"level {int(i)}" for i in t.index]
    t.columns = [f"code {c}" for c in t.columns]
    t = t.reset_index().rename(columns={"index": "weakest level (all positions, stub = 7, unnamed ignored)"})
    return ("**Level → code.** Chains of single-chain hadith without a break marker, by the weakest level over every "
            "position against the recorded code: levels 1–3 → 0, 4–6 → 1, 7–9 → 2, 10 → 3, 11 → 4, 12 → 5 "
            "(`grades.yaml: code_source`). Ibn Hajar's maqbūl (6) and the ṣadūq with a qualifier (5) are coded "
            "ḥasan; itibar's classical map codes them 2 («مقبول حيث يتابع، وإلا فلين الحديث», D20).\n\n"
            + _md(t) + "\n")


def _reads_table(df, con) -> str:
    one = df[df["hadith_n_chains"] == 1]
    L = []
    # the compiler at pos 0
    ch = pd.read_parquet(paths.chains_path(), columns=["sanad_id", "disagreement_class"]) if paths.chains_path().exists() else None
    if ch is not None:
        cw = set(ch.loc[ch["disagreement_class"].isin(["compiler_strictly_weakest", "book_role_strictly_weakest"]),
                        "sanad_id"])
        x = one[one["sanad_id"].isin(cw)]
        L.append(f"- **The compiler at pos 0 is graded.** In the {len(x):,} single-chain hadith whose book-role position "
                 f"(the compiler at pos 0, or a book transmitter) is strictly the weakest narrator, the template code, "
                 f"which grades him, reproduces the record in {_pct(int(x['hit'].sum()), len(x))}; graded without him "
                 "(itibar's v1 reading) the template would miss most of them. `sanads.max_rank` includes pos 0 for the "
                 "same reason (D21).")
    st = one[one["template_breaks"].map(len) == 0]
    L.append("- **Breaks.** One break marker raises the code to at least 2, two or more to at least 3 "
             "(«إسناد ضعيف لأن به موضع تعليق وموضع إرسال» is coded 3). The unnamed person (`اسم مبهم`) is not "
             "graded: a chain whose only weakness is an unnamed person is coded by its other narrators "
             "(«إسناده متصل ، رجاله ثقات» over «عن رجل»). With an inqiṭāʿ or taʿlīq marker in the chain he is read "
             "as one more «موضع إرسال» (counted once with an irsal marker).")
    L.append("- **Undescribed narrators** (rank_no 0, the stubs) read «مجهول الحال» (level 7): «… عدا عبد المؤمن "
             "وهو مجهول الحال».")
    L.append("- **The companion slot** is read by rank_no like any position: a companion is level 1; «مختلف في صحبته», "
             "«لم تثبت له صحبة» take the level the source gives them.")
    L.append("- **Tadlīs** enters only as the verdict word: «صدوق إلا أنه يدلس», «صدوق مدلس» are level-4 labels and the "
             "chain is coded 1 whatever the transmission word; there is no tadlīs rule (a handful of hand-written "
             "sentences add «وفي الإسناد X متهم بالتدليس»).")
    rj = df[df["rijal"].notna() & (df["hadith_n_chains"] == 1)]
    allbm = df[(df["hadith_n_chains"] == 1) & df["parsed"]]
    if len(rj):
        sh = allbm[allbm["opening"].isin(["sahih", "hasan", "hasan_plain", "hasan_mutabaat", "daif", "shadid"])]
        fit = {k: int(((sh["rijal"] == k) == sh[col]).mean() * 10000) / 100
               for k, col in (("الشيخين", "all_bukhari_muslim"),)}
        L.append(f"- **«رجاله رجال الشيخين / البخاري / مسلم»** ({len(rj):,} single-chain sentences): the clause tracks "
                 f"`rawis.is_bukhari` / `is_muslim` over the chain below pos 0 (the clause «رجال الشيخين» present iff "
                 f"every such narrator is both: {fit['الشيخين']:.2f}% of single-chain sentences with an opening that "
                 "can carry it). Its exceptions «روى له البخاري تعليقًا» and «روى له البخاري مقرونًا بغيره» read "
                 "information the dump does not carry: `is_bukhari` is 1 for a narrator al-Bukhārī cites only "
                 "muʿallaq (Ḥammād b. Salama, Abū Dāwūd al-Ṭayālisī are 1 and 1).")
    return "\n".join(L) + "\n"


def _permutation_table(df) -> str:
    import itertools
    rows = []
    for k in (2, 3):
        sub = df[df["hadith_n_chains"] == k].sort_values(["hadith_id", "sanad_id"])
        cnt: Counter = Counter()
        for hid, x in sub.groupby("hadith_id"):
            p, m = list(x["template_code"]), list(x["matn_no"])
            if len(set(p)) < k:
                continue
            perms = [q for q in itertools.permutations(range(k)) if [p[i] for i in q] == m]
            cnt["identity" if perms == [tuple(range(k))] else ("one other pairing" if len(perms) == 1 else
                                                                "none" if not perms else "several")] += 1
        tot = sum(cnt.values())
        rows.append({"chains in the hadith": k, "hadith whose chains' template codes all differ": tot,
                     "recorded codes in sanad order": cnt["identity"], "another pairing": cnt["one other pairing"],
                     "no pairing": cnt["none"], "expected by chance in sanad order": tot / (2 if k == 2 else 6)})
    return _md(pd.DataFrame(rows)) + "\n"


def _residual_notes() -> str:
    return ("- `misattached` / `misattached_named`: the hadith's recorded codes are its chains' template codes, "
            "attached to other chains (with `_named`: the sentence names a narrator found in another chain of the "
            "hadith and not in this one).\n"
            "- `label_changed`: a named narrator is in the chain but his `rawis.rank` label is no longer the word "
            "the sentence gives (the narrator table was edited after the sentence was written).\n"
            "- `named_elsewhere` / `named_not_in_hadith`: the sentence names a narrator who is not in this chain "
            "(and the hadith's codes do not match as a multiset): the chain was re-resolved after grading.\n"
            "- `empty_list`: «… لأن به موضع إرسال ، وفيه» with nothing after «وفيه»: the generator printed no narrator "
            "and kept code 2 whatever the narrators' levels.\n"
            "- `maqbul_as_yuhsan`: a level-6 chain under «إسناده ضعيف ويحسن إذا توبع» (code 2) — a second wording "
            "for the maqbūl, without the narrator list, used beside «إسناده حسن في المتابعات والشواهد».\n"
            "- `unnamed_as_weakness`: «إسناده ضعيف ، …» over an unnamed person in mid-chain (code 2): a wording "
            "that grades the unnamed person, which the main template does not.\n"
            "- `outside_template`: a sentence outside the grammar or with a hand-written clause (§1.2).\n"
            "- `sentence_describes_another_chain`: the code phrase agrees with the record but not with the stored "
            "chain (the sentence omits a break marker or a narrator the chain has, or names a level it does not).\n"
            "- `code_set_apart_from_sentence`: the sentence agrees with the template, the recorded code does not "
            "(«إسناد ضعيف لأن به موضع إرسال ، وباقي رجاله ثقات» recorded 0): the code was edited apart from it.\n"
            "- `other`: the rest.\n")


def _print_chain(con, t) -> str:
    rows = con.sql(f"""SELECT sr.pos, r.id, r.nickname, r.rank_no, coalesce(r.rank, '') FROM sanad_rawis sr
                       JOIN rawis r ON r.id = sr.rawi_id WHERE sr.sanad_id = {int(t.sanad_id)} ORDER BY sr.pos""").fetchall()
    hk = con.sql(f"SELECT hukum FROM sanads WHERE id = {int(t.sanad_id)}").fetchall()[0][0].strip()
    chain = " ← ".join(f"{nk} ({rn})" for _, _, nk, rn, _ in rows)
    return (f"- sanad {int(t.sanad_id)} (hadith {int(t.hadith_id)}, book {int(t.book_id)}, {int(t.hadith_n_chains)} "
            f"chain(s)): recorded {int(t.matn_no)}, template {int(t.template_code)}. «{hk}»\n  chain (pos 0 first, "
            f"rank_no): {chain}")


def _hadith_rule(con, df) -> str:
    h = con.sql("""SELECT h.id, h.matn_no, min(s.matn_no) best, max(s.matn_no) worst, count(*) n
                   FROM hadiths h JOIN sanads s ON s.hadith_id = h.id GROUP BY 1, 2""").df()
    eq = int((h["matn_no"] == h["best"]).sum())
    worse = h[h["matn_no"] > h["best"]]
    better = h[h["matn_no"] < h["best"]]
    t = pd.crosstab(worse["matn_no"], worse["best"])
    t.index = [f"hadith {i}" for i in t.index]
    t.columns = [f"best chain {c}" for c in t.columns]
    return (f"**The hadith grade is its best chain's.** `hadiths.matn_no` equals the lowest `sanads.matn_no` of the "
            f"hadith's chains for {eq:,} of {len(h):,} hadith with chains ({_pct(eq, len(h))}); it is never better "
            f"({len(better):,}); it is worse for {len(worse):,} ({_pct(len(worse), len(h))}), all of them a hadith "
            "coded 3–5 over a best chain of 2–4:\n\n" + _md(t.reset_index().rename(columns={"index": ""})) + "\n")


def _group_rule(con) -> str:
    g = group_rule(con)
    n = len(g)
    eq = g["group_code"] == g["best"]
    within = (g["group_code"] >= g["best"]) & (g["group_code"] <= g["worst"])
    better = g["group_code"] < g["best"]
    worse = g["group_code"] > g["best"]
    outside = ~within
    L = [f"**The group grade is its best chain's, with editors' exceptions.** Over the {n:,} groups with chains, "
         f"`meaning_groups.matn_no` equals the lowest recorded chain code of the group in {int(eq.sum()):,} "
         f"(**{_pct(int(eq.sum()), n)}**), lies within the chains' range in {_pct(int(within.sum()), n)}; it equals "
         f"the best hadith grade in {_pct(int((g['group_code'] == g['hadith_best']).sum()), n)}, the modal chain code "
         f"in {_pct(int((g['group_code'] == g['modal']).sum()), n)}. There is no corroboration across chains: a "
         "group of ḍaʿīf chains is never coded ḥasan by the count of its chains. The exceptions:\n"]
    t = pd.crosstab(g["group_code"], g["best"])
    t.index = [f"group {i}" for i in t.index]
    t.columns = [f"best chain {c}" for c in t.columns]
    L.append(_md(t.reset_index().rename(columns={"index": ""})) + "\n")
    L.append(f"- **worse than its best chain**: {int(worse.sum()):,} groups ({_pct(int(worse.sum()), n)}); "
             f"{int((worse & (g['group_code'] >= 3)).sum()):,} of them coded 3–5 — the editors placed the report "
             "below every chain it has (a verdict on the text, or on a narrator beyond the label).")
    L.append(f"- **better than its best chain**: {int(better.sum()):,} ({_pct(int(better.sum()), n)}) — something "
             "beyond the chains raised it.")
    L.append(f"- **outside the chains' range**: {int(outside.sum()):,} (better than the best, or worse than the "
             "worst chain).\n")
    # samples
    for title, mask in (("worse than its best chain", worse), ("better than its best chain", better)):
        sub = g[mask].sample(min(4, int(mask.sum())), random_state=11)
        L.append(f"Sample, *{title}*:\n")
        for r in sub.itertuples(index=False):
            hs = con.sql(f"""SELECT h.id, h.book_id, b.name, h.matn_no, h.takhrij, substr(h.nass, coalesce(h.matn_start, 0) + 1, 160)
                             FROM hadiths h JOIN books b ON b.id = h.book_id
                             WHERE h.group_id = {int(r.group_id)} ORDER BY h.matn_no, h.id LIMIT 3""").fetchall()
            L.append(f"- group {int(r.group_id)}: recorded {int(r.group_code)} {GRADE[int(r.group_code)]}, best chain "
                     f"{int(r.best)}, worst {int(r.worst)}, {int(r.n_chains)} chains in {int(r.n_hadith)} hadith")
            for hid, bid, bname, hm, tk, txt in hs:
                L.append(f"  - hadith {hid} ({bname}, book {bid}), hadith code {hm}, takhrij {tk}: "
                         f"«{(txt or '').strip()}…»")
        L.append("")
    L.append("`takhrij` (`hadiths.takhrij`, `sanads.takhrij`) is an identifier shared by the parallel narrations of "
             "one takhrīj, without text in the dump; no field of the dump says why an exception was made.\n")
    return "\n".join(L)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("decode", "all"):
        df = decode()
        print(f"decoded {len(df):,} chains, template reproduces {df['hit'].mean():.4%}")
    if cmd in ("report", "all"):
        print(report())


if __name__ == "__main__":
    main()
