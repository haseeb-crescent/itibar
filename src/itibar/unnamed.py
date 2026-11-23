"""The unnamed person at the top of a chain: who the text says he is (structure version 5).

A chain whose top narrator is the unnamed-person placeholder (rawis 1131, «اسم مبهم») was read
as mursal in PR 4-5 (D36). The tradition distinguishes «عن رجل من أصحاب النبي ﷺ» — an unnamed
companion, whose anonymity does not harm — from a bare «عن رجل» / «عن شيخ», who may be a
Successor. This module recovers the words the text uses for him and classifies them.

Mention text. hadith_rawis gives [start, end) offsets of each narrator mention in hadiths.nass.
A chain is aligned with its hadith's sanad-part mentions as in words.py (exact for a single-chain
hadith, in-order subsequence otherwise); the top position's mention is then known. Its span is
often only the noun («رَجُلٍ»), the designation following it («مِنْ أَصْحَابِ النَّبِيِّ ﷺ»), so
the designation is the mention plus the text after it up to the next mention, a delimiter
(، : ؛ .) or a transmission word (قال، أن، عن …), at most `tail_chars` characters. Where the chain
does not align, the last unnamed-person mention of the hadith's sanad part is used
(`sanad_fallback_mention`); with none, the last `tail_chars` characters of the sanad part
(`sanad_fallback_text`); `method` records which.

Classes (config/structure.yaml: unnamed_companion.phrases), by precedence:
  companion       a designation of the Prophet's community («من أصحاب النبي», «صحب النبي» …)
  ansar_muhajir   «من الأنصار», «من المهاجرين» (accepted by default; variant ansar_muhajir: mursal)
  none            bare «رجل», «شيخ», tribal and regional designations, «بعض أصحابنا», kinship
  unclassified    no phrase of the list matched (treated as none; tabulated for the reviewer)

  build   -> out/unnamed_tops.parquet (sanad_id, hadith_id, mention, designation, method, cls, phrase)
"""

from __future__ import annotations

import re
import sys
import time
from collections import Counter

import pyarrow as pa
import pyarrow.parquet as pq

from itibar import config, data, grades, lists, paths, words

MUBHAM_ID = 1131
CLASSES = ("companion", "ansar_muhajir", "none")
_DELIM = re.compile(r"[،,:؛;.\n]")
_STOP = {"قال", "قالت", "يقول", "تقول", "أن", "أنه", "أنها", "عن", "حدثه", "حدثهم", "حدثني", "حدثنا", "أخبره",
         "أخبرني", "أخبرنا", "ح", "فقال", "وقال", "ثنا", "نا", "أنبأنا"}
_STOP_N = {lists.normalize(w) for w in _STOP}


def cfg() -> dict:
    return config.load("structure").get("unnamed_companion") or {}


def designation(text: str, start: int, end: int, limit: int, tail_chars: int) -> str:
    """The mention text plus its tail: up to `limit` (next mention or matn start), the first
    delimiter or transmission word, and at most `tail_chars` characters."""
    tail = text[end:min(limit, end + tail_chars)]
    m = _DELIM.search(tail)
    if m:
        tail = tail[:m.start()]
    out = []
    for tok in tail.split():
        if lists.normalize(tok) in _STOP_N:
            break
        out.append(tok)
    return (text[start:end] + " " + " ".join(out)).strip()


def phrases() -> list[tuple[str, str, str]]:
    """(normalized phrase, class, phrase as written), longest first within each class, classes
    in precedence order companion, ansar_muhajir, none."""
    p = cfg().get("phrases") or {}
    out = []
    for cls in CLASSES:
        ws = sorted(p.get(cls) or [], key=lambda w: -len(lists.normalize(w)))
        out.extend((lists.normalize(w), cls, w) for w in ws)
    return out


def classify(desig: str, table: list[tuple[str, str, str]] | None = None) -> tuple[str, str | None]:
    """(class, the phrase that matched) for a designation; unclassified when nothing matched.
    A phrase matches as a whole-word substring of the normalized designation."""
    table = table if table is not None else phrases()
    t = " " + lists.normalize(desig) + " "
    for norm, cls, w in table:
        if norm and (" " + norm + " ") in t:
            return cls, w
    return "unclassified", None


def extract(con=None) -> list[dict]:
    """One row per chain whose top position is the unnamed person."""
    con = con or data.views()
    c = cfg()
    tail_chars = int(c.get("tail_chars", 80))
    scale = grades.load()
    gaps = {k for k, v in scale.placeholders.items() if v["role"] == "gap"}
    chains = con.sql(
        f"""WITH t AS (SELECT s.hadith_id, s.id AS sanad_id, list(sr.rawi_id ORDER BY sr.pos) AS chain
                      FROM sanads s JOIN sanad_rawis sr ON sr.sanad_id = s.id GROUP BY 1, 2)
            SELECT * FROM t WHERE list_last(chain) = {MUBHAM_ID} ORDER BY sanad_id"""
    ).fetchall()
    if not chains:
        return []
    hids = sorted({h for h, _, _ in chains})
    con.execute("CREATE OR REPLACE TEMP TABLE _uh AS SELECT unnest(?::BIGINT[]) AS hid", [hids])
    n_chains = dict(con.sql("""SELECT hadith_id, count(*) FROM sanads WHERE hadith_id IN (SELECT hid FROM _uh)
                               GROUP BY 1""").fetchall())
    texts = {h: (t or "", ms) for h, t, ms in con.sql(
        "SELECT id, nass, matn_start FROM hadiths WHERE id IN (SELECT hid FROM _uh)").fetchall()}
    ments: dict[int, tuple[list, list, list]] = {}
    for h, rid, st, en in con.sql(
            """SELECT hr.hadith_id, list(hr.rawi_id ORDER BY hr.seq), list(hr.start ORDER BY hr.seq),
                      list(hr."end" ORDER BY hr.seq)
               FROM hadith_rawis hr JOIN hadiths h ON h.id = hr.hadith_id
               WHERE hr.hadith_id IN (SELECT hid FROM _uh) AND (h.matn_start IS NULL OR hr.start < h.matn_start)
               GROUP BY 1""").fetchall():
        ments[h] = (rid, st, en)
    out = []
    for h, sid, ch in chains:
        text, ms = texts.get(h, ("", None))
        sanad_end = ms if ms is not None and ms > 0 else len(text)
        rid, st, en = ments.get(h, ([], [], []))
        needle = [ch[p] for p in range(1, len(ch)) if ch[p] not in gaps]
        idx, method = None, None
        if rid and needle:
            if n_chains.get(h, 0) == 1 and needle == rid:
                idx, method = list(range(len(rid))), "exact"
            else:
                idx = words.is_subsequence(needle, rid)
                method = "subseq" if idx is not None else None
        if idx is not None:
            i = idx[-1]
            lim = st[i + 1] if i + 1 < len(st) else sanad_end
            mention = text[st[i]:en[i]]
            desig = designation(text, st[i], en[i], max(lim, en[i]), tail_chars)
        else:
            mi = [i for i, r in enumerate(rid) if r == MUBHAM_ID]
            if mi:
                i = mi[-1]
                lim = st[i + 1] if i + 1 < len(st) else sanad_end
                method = "sanad_fallback_mention"
                mention = text[st[i]:en[i]]
                desig = designation(text, st[i], en[i], max(lim, en[i]), tail_chars)
            else:
                # no mention of him: the text between the last mention of the sanad part and
                # the matn, where his designation would stand
                method = "sanad_fallback_text"
                mention = None
                a = en[-1] if en else 0
                desig = text[a:min(sanad_end, a + tail_chars)] if a < sanad_end else ""
        out.append({"sanad_id": int(sid), "hadith_id": int(h), "mention": mention, "designation": desig,
                    "method": method})
    tbl = phrases()
    for r in out:
        if r["method"] == "sanad_fallback_text":
            # No mention of him in the text: what stands before the matn is mostly the matn's own
            # opening (matn_start is approximate), so nothing is read as a designation (D69).
            r["cls"], r["phrase"] = "none_text", None
        else:
            r["cls"], r["phrase"] = classify(r["designation"], tbl)
    return out


def build(out_path=None) -> dict:
    t0 = time.time()
    rows = extract()
    out_path = out_path or (paths.OUT_DIR / "unnamed_tops.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ("sanad_id", "hadith_id", "mention", "designation", "method", "cls", "phrase")
    types = (pa.int64(), pa.int64(), pa.string(), pa.string(), pa.string(), pa.string(), pa.string())
    pq.write_table(pa.table({c: pa.array([r[c] for r in rows], t) for c, t in zip(cols, types)}), out_path,
                   compression="zstd")
    return {"chain_tops": len(rows), "by_class": dict(Counter(r["cls"] for r in rows)),
            "by_method": dict(Counter(r["method"] for r in rows)), "seconds": round(time.time() - t0, 1)}


def load(path=None) -> dict[int, str]:
    """sanad_id -> class, from out/unnamed_tops.parquet (empty when not built)."""
    path = path or (paths.OUT_DIR / "unnamed_tops.parquet")
    if not path.exists():
        return {}
    t = pq.read_table(path, columns=["sanad_id", "cls"])
    return dict(zip(t.column("sanad_id").to_pylist(), t.column("cls").to_pylist()))


def accepted_classes() -> set[str]:
    """Classes read as an unnamed companion under the current config."""
    c = cfg()
    if not c.get("enabled", True):
        return set()
    out = {"companion"}
    if c.get("ansar_muhajir", "companion") == "companion":
        out.add("ansar_muhajir")
    return out


if __name__ == "__main__":
    print(build())
    sys.exit(0)
