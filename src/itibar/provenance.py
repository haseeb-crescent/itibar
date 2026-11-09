"""Whose verdicts are the narrator labels? (audit section 11.7)

A deterministic sample of 40 narrators of al-Bukhari or Muslim (rawis.is_bukhari or
is_muslim: every such narrator has an entry in Ibn Hajar's Taqrib al-Tahdhib), 20 of
them labelled «صدوق حسن الحديث» in the source and 20 drawn from the other labels of
levels 2-9, is looked up in Shamela's Taqrib al-Tahdhib (book 8609, ed. Muhammad
'Awwama) and in Tahrir Taqrib al-Tahdhib (book 127715, Bashshar 'Awwad Ma'ruf and
Shu'ayb al-Arna'ut, 1997), which reprints each Taqrib entry and adds its own verdict
after «بل:» where it disagrees.

  fetch   query both books for each sampled narrator -> lists/source/taqrib_sample.jsonl
  report  the entry lines, the source's label beside Ibn Hajar's and Tahrir's verdicts,
          and the counts -> the audit (section 11.7)

The comparison is mechanical (does the source's label occur in Ibn Hajar's entry, in
Tahrir's «بل:» revision?) and every row is printed for the reader to check."""

from __future__ import annotations

import json
import random
import re
import sys
import time

from itibar import data, lists

TAQRIB, TAHRIR = 8609, 127715
OUT = lists.SOURCE_DIR / "taqrib_sample.jsonl"
SEED = 20261109
FORMULA = "صدوق حسن الحديث"


def sample(con=None, n_formula: int = 20, n_other: int = 20, seed: int = SEED) -> list[dict]:
    con = con or data.views()
    rows = con.sql("""SELECT id, name, nickname, rank_no, rank, death_year, tabaka FROM rawis
                      WHERE (is_bukhari = 1 OR is_muslim = 1) AND rank_no BETWEEN 2 AND 9 AND is_stub = 0
                      ORDER BY id""").fetchall()
    form = [r for r in rows if (r[4] or "").strip() == FORMULA]
    other = [r for r in rows if (r[4] or "").strip() != FORMULA]
    rng = random.Random(seed)
    pick = rng.sample(form, min(n_formula, len(form))) + rng.sample(other, min(n_other, len(other)))
    return [{"rawi_id": r[0], "name": r[1], "nickname": r[2], "rank_no": r[3], "label": r[4], "death_year": r[5],
             "tabaka": r[6], "stratum": "formula" if (r[4] or "").strip() == FORMULA else "other"} for r in pick]


def _norm(t: str) -> str:
    """lists.normalize, «ابن» as «بن», and the article dropped from every word (the source
    writes «حسن بن مدرك» where the Taqrib prints «الحسن ابن مدرك»)."""
    out = []
    for w in lists.normalize(t).split():
        w = "بن" if w == "ابن" else w
        out.append(w[2:] if w.startswith("ال") and len(w) > 3 else w)
    return " ".join(out)


def _call(name: str, args: dict) -> dict:
    d = lists._rpc("tools/call", {"name": name, "arguments": args})
    res = d.get("result") or {}
    if res.get("structuredContent"):
        return res["structuredContent"]
    try:
        return json.loads("".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"))
    except ValueError:
        return {}


def _entry(text: str, name: str) -> tuple[str | None, str | None, int]:
    """The numbered entry line that names the longest prefix (at least three words: ism,
    ibn, father) of `name`, normalized; with Tahrir's «بل:» lines that follow it."""
    words = _norm(name).split()
    # at least through the father's name: "عبد الله بن المبارك", not "عبد الله بن"
    first_ibn = next((i for i, w in enumerate(words) if w == "بن"), len(words))
    min_k = min(len(words), first_ibn + 2 + (1 if first_ibn + 1 < len(words) and words[first_ibn + 1] in
                                            ("عبد", "ابي", "ابو") else 0))
    lines = text.split("\n")
    best = (None, None, 0)
    for i, line in enumerate(lines):
        m = re.match(r"\s*([٠-٩]+)\s*-\s*(.*)", line)
        if not m:
            continue
        body = _norm(m.group(2))
        k = 0
        for j in range(max(3, min_k), len(words) + 1):
            if words[j - 1] == "بن":          # a prefix ending on "بن" has not named the next father
                continue
            if body.startswith(" ".join(words[:j])):
                k = j
        if k > best[2]:
            follow = []
            for nxt in lines[i + 1:i + 3]:
                if nxt.strip().startswith("•"):
                    follow.append(nxt.strip())
                else:
                    break
            best = ("\n".join([line.strip()] + follow), m.group(1), k)
    return best


def fetch(out=OUT) -> int:
    lists._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                              "clientInfo": {"name": "itibar", "version": "0.3"}})
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for s in sample():
            rec = dict(s)
            for book, tag in ((TAQRIB, "taqrib"), (TAHRIR, "tahrir")):
                best = (None, None, 0, None, None)
                nick = s["nickname"] or ""
                for q in (" ".join(s["name"].split()[:5]), " ".join(s["name"].split()[:4]), nick,
                          " ".join(s["name"].split()[:3]), "ال" + " ".join(s["name"].split()[:3])):
                    r = _call("shamela_find_scoped", {"query": q, "book_ids": [book], "limit": 5, "difficulty": "easy"})
                    for src in (r.get("evidence") or {}).get("sources") or []:
                        line, num, k = _entry(src.get("text", ""), s["name"])
                        if k > best[2]:
                            best = (line, num, k, src.get("citation", {}).get("markdown"), src.get("page_id"))
                    if best[2] >= 3:
                        break
                    time.sleep(1.0)
                line, num, k, hit, page = best
                rec[f"{tag}_line"], rec[f"{tag}_number"], rec[f"{tag}_citation"], rec[f"{tag}_page"] = line, num, hit, page
                rec[f"{tag}_prefix_words"] = k
                time.sleep(1.0)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def load(path=OUT) -> list[dict]:
    return [json.loads(x) for x in open(path, encoding="utf-8")]


def _verdict(line: str | None, name: str) -> str | None:
    """The verdict words of a Taqrib-style entry: after the name and its nisbas, before
    «من ال...» (the tabaqa); in Tahrir the colon separates them."""
    if not line:
        return None
    first = line.split("\n")[0]
    t = re.sub(r"^\s*[٠-٩]+\s*-\s*", "", first)
    if ":" in t:
        t = t.split(":", 1)[1]
    m = re.search(r"(?:،\s*)?من\s+(?:كبار\s+|صغار\s+)?(?:ال)?(?:أولى|اولى|ثانية|ثالثة|رابعة|خامسة|سادسة|سابعة|ثامنة|تاسعة|"
                  r"عاشرة|حادية عشرة|ثانية عشرة)", t)
    return t[:m.start()].strip(" ،.") if m else t.strip()


_TABAQA = {"الاولي": 1, "الثانيه": 2, "الثالثه": 3, "الرابعه": 4, "الخامسه": 5, "السادسه": 6, "السابعه": 7,
           "الثامنه": 8, "التاسعه": 9, "العاشره": 10, "الحاديه عشره": 11, "الثانيه عشره": 12}


def _tabaqa(line: str | None) -> int | None:
    """Ibn Hajar's tabaqa as printed in the entry («من السادسة», «من كبار التاسعة»)."""
    if not line:
        return None
    t = lists.normalize(line.split("\n")[0])
    m = re.search(r"من (?:كبار |صغار |اوساط )?(الحاديه عشره|الثانيه عشره|الاولي|الثانيه|الثالثه|الرابعه|الخامسه|"
                  r"السادسه|السابعه|الثامنه|التاسعه|العاشره)", t)
    return _TABAQA.get(m.group(1)) if m else None


def _same_person(line: str | None, tabaka: int | None, name: str = "") -> bool:
    """False for a namesake: the entry's tabaqa is more than one layer from the narrator's
    tabaka in the data (whose layers run up to one off the Taqrib's, D10) and the entry
    does not also agree on the grandfather."""
    if not line:
        return False
    t = _tabaqa(line)
    if t is None or not tabaka or abs(int(tabaka) - t) <= 1:
        return True
    body = _norm(re.sub(r"^\s*[٠-٩]+\s*-\s*", "", line.split("\n")[0])).split()
    words = _norm(name).split()
    k = 0
    while k < min(len(body), len(words)) and body[k] == words[k]:
        k += 1
    while k and words[k - 1] == "بن":
        k -= 1
    return words[:k].count("بن") >= 2


def compare(rows: list[dict]) -> list[dict]:
    """Per sampled narrator: Ibn Hajar's verdict, Tahrir's «بل:» revision, and the
    comparisons with the source's label. An entry whose tabaqa is more than one layer from
    the narrator's tabaka, without agreeing on the grandfather, is a namesake and counts as
    not found; a Tahrir entry cut by a page break (no verdict on the
    page) leaves Tahrir unread."""
    out = []
    for r in rows:
        r = dict(r)
        for tag in ("taqrib", "tahrir"):
            if r.get(f"{tag}_line") and not _same_person(r[f"{tag}_line"], r.get("tabaka"), r["name"]):
                r[f"{tag}_line"] = None
                r[f"{tag}_namesake"] = True
        if r.get("tahrir_line") and ":" not in r["tahrir_line"].split("\n")[0]:
            r["tahrir_cut"] = True
        lab = _norm(r["label"] or "")
        ih = _verdict(r.get("taqrib_line"), r["name"])
        tline = r.get("tahrir_line") or ""
        bal = next((x for x in tline.split("\n") if re.match(r"^•\s*بل\s*:", x)), None)
        th = re.sub(r"^•\s*بل\s*:\s*", "", bal).split("،")[0].split(".")[0].strip() if bal else None
        ih_n = _norm(ih or "")
        found = bool(r.get("taqrib_line")) and bool(r.get("tahrir_line")) and not r.get("tahrir_cut")
        eq_ih = bool(lab) and (lab in ih_n or (bool(ih_n) and ih_n in lab))
        eq_th = bool(lab) and bool(th) and lab in _norm(th)
        out.append({**r, "ibn_hajar": ih, "tahrir_revision": th,
                    "label_in_ibn_hajar": bool(lab) and lab in ih_n,
                    "ibn_hajar_in_label": bool(ih_n) and ih_n in lab,
                    "label_in_tahrir": eq_th, "found": found,
                    "reading": (None if not found else "Tahrir's revision" if eq_th
                                else "Ibn Hajar's wording" if eq_ih and not th
                                else "formula over Ibn Hajar's verdict" if lab == _norm(FORMULA) and not th
                                else "neither")})
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "fetch":
        print(f"{fetch()} narrators -> {OUT}")
