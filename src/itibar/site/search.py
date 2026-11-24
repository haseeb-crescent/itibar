"""Static inverted indexes for English and Arabic, names, book titles and citations (DECISIONS D103).

Documents are numbered by how widely they are carried — reports by their number of chains, narrators by
the number of reports they are on a line of — so a lower id is a more widely transmitted document. The
browser ranks matches by how many query words they contain, then by that id: among equally good matches,
the famous report comes first, and the most relevant results sit in the first few document shards.
Arabic words are normalized with `lists.normalize`; English with `english_tokens` (lower case, accents
and ʿ/ʾ removed, a short stop list, light suffix stripping), mirrored in site/assets/normalizer.mjs.
"""
from __future__ import annotations

import re
import unicodedata
from base64 import b64encode
from collections import defaultdict

from itibar import lists
from itibar.site.pages import save_json

TOKEN_SHARDS = 512
REFERENCE_SHARDS = 512
DOC_SHARD_SIZE = 24
POPULAR_TERM = 520
OPENING_CHARS = 180
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ALIASES = {
    1: ["bukhari", "sahih bukhari", "sahih al bukhari", "صحيح البخاري", "البخاري"],
    2: ["muslim", "sahih muslim", "صحيح مسلم", "مسلم"],
    3: ["tirmidhi", "jami tirmidhi", "jami al tirmidhi", "sunan al tirmidhi", "الترمذي"],
    4: ["abu dawud", "sunan abu dawud", "sunan abi dawud", "أبو داود", "أبي داود"],
    5: ["nasai", "sunan al nasai", "النسائي"],
    6: ["ibn majah", "sunan ibn majah", "ابن ماجه"],
    7: ["darimi", "sunan al darimi", "الدارمي"],
    8: ["malik", "muwatta malik", "muwatta", "موطأ مالك"],
    9: ["ahmad", "musnad ahmad", "مسند أحمد"],
    45: ["tabarani", "musnad al shamiyyin", "الطبراني"],
}
STOP = frozenset("""a an the and or but of to in on at by for with from into onto is are was were be been being it its
that this these those as me my mine i you your yours he his him she her hers they them their we us our not no will
shall would should do does did has have had about upon all so then there which who whom what when where while than
also very just o oh""".split())
ENGLISH_VERSION = 1


def english_tokens(text):
    """English normalization v1 (mirrored in normalizer.mjs; parity is tested)."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[ʿʾ'’‘`]", "", text)
    out = []
    for word in re.split(r"[^a-z0-9]+", text):
        if not word or word in STOP:
            continue
        out.append(stem(word))
    return out


def stem(word):
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    return word


def shard(key, count):
    number = 0
    for letter in str(key):
        number = (number * 31 + ord(letter)) % count
    return number


def book_key(text):
    text = text or ""
    arabic = lists.normalize(text)
    if arabic:
        return arabic
    text = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    text = re.sub(r"['’ʾʿ]", "", text)
    return " ".join(re.sub(r"[^a-z0-9]", " ", text).split())


def encode_postings(postings):
    """Encode a signed first entry, then unsigned differences, as 7-bit varints."""
    ordered = sorted(postings)
    first = ordered[0]
    packed = bytearray()
    values = [first * 2 if first >= 0 else -first * 2 - 1]
    values.extend(b - a for a, b in zip(ordered, ordered[1:]))
    for value in values:
        while value >= 128:
            packed.append((value & 127) | 128)
            value >>= 7
        packed.append(value)
    return b64encode(packed).decode("ascii")


class SearchIndex:
    """Add reports and narrators in any order with their rank; write() shards everything."""

    def __init__(self):
        self.postings = defaultdict(set)
        self.docs = defaultdict(dict)
        self.citations = defaultdict(set)

    def _add(self, doc, head, body):
        for word in head:
            self.postings[word].add(doc * 2 + 1)
        for word in set(body) - set(head):
            self.postings[word].add(doc * 2)

    def report(self, rank, gid, record, references, *, opening, variants=(), text="", english=(), english_body=()):
        """rank: the report's place by chains (0 = most chains). record: the result-card fields."""
        if rank in self.docs[rank // DOC_SHARD_SIZE]:
            raise ValueError(f"Duplicate search document {rank}")
        self.docs[rank // DOC_SHARD_SIZE][rank] = record
        head = {w for t in (opening, *variants) for w in lists.tokens(t)}
        head |= {w for t in english for w in english_tokens(t)}
        body = set(lists.tokens(text)) | {w for t in english_body for w in english_tokens(t)}
        self._add(rank, head, body)
        for ref in references:
            if ref["no_inbook"] is not None:
                number = str(ref["no_inbook"]).translate(DIGITS)
                self.citations[number].add((ref["book_id"], rank))

    def narrator(self, rank, rid, record, names, english=()):
        doc = -(rank + 1)
        self.docs[doc // DOC_SHARD_SIZE][doc] = record
        head = {w for t in names for w in lists.tokens(t)} | {w for t in english for w in english_tokens(t)}
        self._add(doc, head, ())

    def write(self, dest, books, extra=None):
        tokens, refs = defaultdict(dict), defaultdict(dict)
        popular = []
        for token, values in sorted(self.postings.items()):
            encoded = encode_postings(values)
            if len(values) > POPULAR_TERM:
                popular.append(token)
                save_json(dest / "terms" / f"{len(popular) - 1}.json", encoded)
            else:
                tokens[shard(token, TOKEN_SHARDS)][token] = encoded
        for number, values in self.citations.items():
            refs[shard(number, REFERENCE_SHARDS)][number] = sorted(values)
        for kind, items in (("tokens", tokens), ("refs", refs), ("docs", self.docs)):
            for index, content in items.items():
                save_json(dest / kind / f"{index}.json", content)
        n_reports = sum(1 for shard_docs in self.docs.values() for d in shard_docs if d >= 0)
        save_json(dest / "meta.json", {
            "normalization": lists.NORMALIZE_VERSION, "english": ENGLISH_VERSION, "tokens": TOKEN_SHARDS,
            "refs": REFERENCE_SHARDS, "docs": DOC_SHARD_SIZE, "token_buckets": sorted(tokens),
            "reference_buckets": sorted(refs), "document_buckets": sorted(self.docs), "popular": popular,
            "reports": n_reports, **(extra or {}),
        })
        save_json(dest / "books.json", {k: [v["name"], list(dict.fromkeys(
            book_key(t) for t in [v["name"], v["author_name"], *v.get("english", []), *ALIASES.get(k, [])] if t)),
            v.get("title")] for k, v in books.items()})
