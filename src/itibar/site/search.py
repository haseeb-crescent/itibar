"""Static inverted indexes for representative texts, names and book references."""
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
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ALIASES = {
    1: ["bukhari", "sahih bukhari", "sahih al bukhari", "صحيح البخاري", "البخاري"],
    2: ["muslim", "sahih muslim", "صحيح مسلم", "مسلم"],
    3: ["tirmidhi", "jami tirmidhi", "jami al tirmidhi", "sunan al tirmidhi", "الترمذي"],
    4: ["abu dawud", "sunan abu dawud", "sunan abi dawud", "أبو داود", "أبي داود"],
    5: ["nasai", "sunan al nasai", "النسائي"],
    6: ["ibn majah", "sunan ibn majah", "ابن ماجه"],
    7: ["darimi", "sunan al darimi", "الدارمي"],
    8: ["malik", "muwatta malik", "موطأ مالك"],
    9: ["ahmad", "musnad ahmad", "مسند أحمد"],
    45: ["tabarani", "musnad al shamiyyin", "الطبراني"],
}


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
    def __init__(self):
        self.postings = defaultdict(list)
        self.docs = defaultdict(dict)
        self.citations = defaultdict(set)

    def report(self, gid, opening, text, references):
        self.document(gid, opening, "", (opening,), text)
        for ref in references:
            if ref["no_inbook"] is not None:
                number = str(ref["no_inbook"]).translate(DIGITS)
                self.citations[number].add((ref["book_id"], gid))

    def narrator(self, rid, nickname, name):
        self.document(-rid, nickname or name, name if nickname and name != nickname else "", (nickname, name))

    def document(self, doc_id, title, other, headings, body=None):
        if doc_id in self.docs[doc_id // DOC_SHARD_SIZE]:
            raise ValueError(f"Duplicate search document {doc_id}")
        self.docs[doc_id // DOC_SHARD_SIZE][doc_id] = [title, other]
        head = {word for heading in headings for word in lists.tokens(heading)}
        for word in head:
            self.postings[word].append(doc_id * 2 + 1)
        for word in set(lists.tokens(body)) - head:
            self.postings[word].append(doc_id * 2)

    def write(self, dest, books):
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
        save_json(dest / "meta.json", {
            "normalization": lists.NORMALIZE_VERSION, "tokens": TOKEN_SHARDS, "refs": REFERENCE_SHARDS,
            "docs": DOC_SHARD_SIZE, "token_buckets": sorted(tokens), "reference_buckets": sorted(refs),
            "document_buckets": sorted(self.docs), "popular": popular,
        })
        save_json(dest / "books.json", {k: [v["name"], list(dict.fromkeys(
            book_key(t) for t in [v["name"], v["author_name"], *ALIASES.get(k, [])] if t))]
            for k, v in books.items()})
