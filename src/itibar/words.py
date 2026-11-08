"""Transmission words (صيغ الأداء) recovered from the inline narrator mentions.

hadith_rawis gives [start, end) offsets of each narrator mention inside
hadiths.nass, in text order. In "حدثنا قتيبة قال حدثنا سفيان عن الزهري", the
word before a narrator's mention is how *the previous narrator* received from
him: "عن" before الزهري is Sufyan's mode of receiving from al-Zuhri. So for a
chain link teacher u -> student v, the word that matters is the one before u's
mention. (The brief phrases it as "before v's mention"; see DECISIONS.md.)

A chain is *aligned* with its hadith's mentions when we can say which mention
is which chain position:
  exact   - single-chain hadith, sanad-part mention sequence == chain minus
            compiler and minus break markers
  subseq  - the chain (same reduction) is an in-order subsequence of the
            sanad-part mention sequence; used for multi-chain hadith (tahwil),
            where shared upper links are written once, and for single-chain
            hadith whose text carries extra mentions
Unaligned chains get no word ("unknown word").

Per aligned link we store
  word_raw   - the one or two tokens immediately before the mention, as written
  word       - the last recognised transmission token in the connector segment
               (text between the previous mention's end and this mention's
               start), normalized; falls back to the last token
  word_class - a coarse class of `word`
"""

from __future__ import annotations

import re
import time

import pyarrow as pa
import pyarrow.parquet as pq

from itibar import data, grades, paths

NORMALIZE_VERSION = 1
_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_SPLIT = re.compile(r"[\s،؛؟:;,.!?()\[\]{}«»\"'\-–—/0-9٠-٩]+")

# normalized token -> class
WORD_CLASSES: dict[str, str] = {}
for cls, words in {
    "haddathana": "حدثنا حدثني ثنا نا حدثه حدثهم وحدثنا وحدثني وثنا حدثتني حدثناه حدثتنا حدثنيه دثنا قثنا حدثكم فحدثنا فحدثناه ونا ثني حوحدثنا",
    "akhbarana": "أخبرنا أخبرني أنا أخبره أخبرهم وأخبرنا وأخبرني خبرنا أخبرتنا أخبرناه أخبرتني أخبرنيه أخبركم أخبرك فأخبرنا فأخبرناه وأنا",
    "anbaana": "أنبأنا أنبأني أنبأ وأنبأنا أنبا أبنا أنبأناه أنبأتنا نبأنا نبا وأنبأ",
    "samitu": "سمعت سمعنا سمع يسمع وسمعت سمعته سمعا",
    "qiraa": "قرأت قرئ قرأ على",
    "an": "عن وعن",
    "anna": "أن أنه وأن أنها",
    "qala": "قال قالت وقال يقول قالا قالوا فقال تقول فقالت",
    "kitaba": "كتب إلي كتاب",
    "tahwil": "ح",
}.items():
    for w in words.split():
        WORD_CLASSES.setdefault(w.rstrip("_"), cls)

# word normalization helpers
def normalize(token: str) -> str:
    """Versioned normalization (v1): strip diacritics and tatweel."""
    return _DIACRITICS.sub("", token)


def tokens(segment: str) -> list[str]:
    return [t for t in _SPLIT.split(segment) if t]


def transmission_word(segment: str) -> tuple[str | None, str | None, str | None]:
    """(word_raw, word, word_class) for a connector segment."""
    toks = tokens(segment)
    if not toks:
        return None, None, None
    raw = " ".join(toks[-2:])
    for t in reversed(toks[-6:]):
        n = normalize(t)
        if n in WORD_CLASSES:
            return raw, n, WORD_CLASSES[n]
    n = normalize(toks[-1])
    return raw, n, "other"


def is_subsequence(needle: list[int], hay: list[int]) -> list[int] | None:
    """Greedy earliest in-order match; returns hay indices or None."""
    out, j = [], 0
    for x in needle:
        while j < len(hay) and hay[j] != x:
            j += 1
        if j == len(hay):
            return None
        out.append(j)
        j += 1
    return out


def build(out_path=None) -> dict:
    t0 = time.time()
    scale = grades.load()
    gaps = {k for k, v in scale.placeholders.items() if v["role"] == "gap"}
    con = data.views()
    chains = con.sql(
        """SELECT s.hadith_id, s.id AS sanad_id, list(sr.rawi_id ORDER BY sr.pos) AS chain
           FROM sanads s JOIN sanad_rawis sr ON sr.sanad_id = s.id
           GROUP BY 1, 2 ORDER BY 1, 2"""
    ).to_arrow_table()
    ments = con.sql(
        """SELECT hr.hadith_id, list(hr.rawi_id ORDER BY hr.seq) AS rid,
                  list(hr.start ORDER BY hr.seq) AS st, list(hr."end" ORDER BY hr.seq) AS en
           FROM hadith_rawis hr JOIN hadiths h ON h.id = hr.hadith_id
           WHERE h.id IN (SELECT hadith_id FROM sanads)
             AND (h.matn_start IS NULL OR hr.start < h.matn_start)
           GROUP BY 1"""
    ).to_arrow_table()
    texts = con.sql(
        "SELECT id, nass FROM hadiths WHERE id IN (SELECT hadith_id FROM sanads)"
    ).to_arrow_table()
    nass = dict(zip(texts.column("id").to_pylist(), texts.column("nass").to_pylist()))
    del texts
    mention = {
        h: (r, s, e)
        for h, r, s, e in zip(ments.column("hadith_id").to_pylist(), ments.column("rid").to_pylist(),
                              ments.column("st").to_pylist(), ments.column("en").to_pylist())
    }
    del ments

    by_hadith: dict[int, list[tuple[int, list[int]]]] = {}
    for h, sid, ch in zip(chains.column("hadith_id").to_pylist(), chains.column("sanad_id").to_pylist(),
                          chains.column("chain").to_pylist()):
        by_hadith.setdefault(h, []).append((sid, ch))
    del chains

    cols = {k: [] for k in ("sanad_id", "pos", "word_raw", "word", "word_class", "method")}
    stats = {"chains": 0, "chains_exact": 0, "chains_subseq": 0, "chains_unaligned": 0,
             "chains_no_mentions": 0}
    for h, chs in by_hadith.items():
        rid, st, en = mention.get(h, ([], [], []))
        text = nass.get(h, "")
        single = len(chs) == 1
        for sid, ch in chs:
            stats["chains"] += 1
            keep = [p for p in range(1, len(ch)) if ch[p] not in gaps]
            needle = [ch[p] for p in keep]
            if not rid:
                stats["chains_no_mentions"] += 1
                stats["chains_unaligned"] += 1
                continue
            if single and needle == rid:
                method, idx = "exact", list(range(len(rid)))
            else:
                idx = is_subsequence(needle, rid) if needle else None
                method = "subseq" if idx is not None else None
            if method is None:
                stats["chains_unaligned"] += 1
                continue
            stats["chains_" + method] += 1
            for p, i in zip(keep, idx):
                seg_start = en[i - 1] if i > 0 else max(0, st[i] - 64)
                raw, word, cls = transmission_word(text[seg_start:st[i]])
                cols["sanad_id"].append(sid)
                cols["pos"].append(p)
                cols["word_raw"].append(raw)
                cols["word"].append(word)
                cols["word_class"].append(cls)
                cols["method"].append(method)
    table = pa.table({
        "sanad_id": pa.array(cols["sanad_id"], pa.int64()),
        "pos": pa.array(cols["pos"], pa.int16()),
        "word_raw": pa.array(cols["word_raw"], pa.string()),
        "word": pa.array(cols["word"], pa.string()),
        "word_class": pa.array(cols["word_class"], pa.string()),
        "method": pa.array(cols["method"], pa.string()),
    })
    out_path = out_path or (paths.OUT_DIR / "words.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path, compression="zstd")
    stats["rows"] = table.num_rows
    stats["normalize_version"] = NORMALIZE_VERSION
    stats["seconds"] = round(time.time() - t0, 1)
    return stats


if __name__ == "__main__":
    print(build())
