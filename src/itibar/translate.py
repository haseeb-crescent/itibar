"""The English layer: one file format, any producer (DECISIONS D102).

`translations/<kind>.parquet` is the contract. One row per item:

    key         the item's id within its kind (book id, topic id, place text, critic id,
                narrator id, group id, "group:hadith" for a representative text)
    source      the Arabic the item translates, exactly as read from the source tables
    source_sha  sha256 of `source` (first 16 hex); an item whose source changed is stale and not shown
    en          the English (a title, a translation, a transliteration)
    extra       JSON with the kind's other fields (short name, transliterated title, author), or null
    producer    what made it: "session:<date>:<label>" for a translation written in a Claude session,
                "api-batch:<batch id>" for `make translate`; anything else that follows the format
    model       the model id that produced it
    prompt_sha  the hash of the fixed prompt (PROMPT, the kind's instruction and the glossary)
    created     ISO date

`translations/checks.parquet` records the second pass: a sample checked against the Arabic, with
the verdict, the problem found and whether it was fixed.

Producers write through `import` (validated against the current sources), so a session and an API
run produce identical files. `pending` writes the items still missing as JSONL work sets for a
session; `api` is the optional Message Batches path (`make translate`, needs credentials). Nothing
in itibar's computation reads these files: only the site does, and labels them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import date
from pathlib import Path

import yaml

from itibar import paths

DIR = paths.ROOT / "translations"
CHECKS = DIR / "checks.parquet"
KINDS = ("book", "topic", "place", "critic", "narrator", "opening", "text")
COLUMNS = ("key", "source", "source_sha", "en", "extra", "producer", "model", "prompt_sha", "created")
MODEL = "claude-opus-5-5"

PROMPT = """You translate items from an Arabic hadith corpus into English for a scholarly reference website
whose readers include people who know no Arabic. Your English is shown beside the Arabic and is labelled
as machine translation.

Rules:
- Translate faithfully and completely. Add no explanation, commentary, grading or judgement of authenticity.
- Clear modern English, sentence case. Keep the narrative frame ("He said: …").
- Render صلى الله عليه وسلم as "ﷺ" after "the Prophet" or "the Messenger of Allah"; render رضي الله عنه / عنها
  / عنهما / عنهم as "(may Allah be pleased with him / her / them)" only where the Arabic has it. Use "Allah".
- Quranic quotations: translate the meaning, in quotation marks.
- Names: IJMES / EI3 transliteration — ʿ for ʿayn, ʾ for hamza (not word-initially), macrons (ā ī ū), dots
  for emphatics (ḥ ṣ ḍ ṭ ẓ), dh th kh sh gh; "b." for ibn/bin between two names and "bt." for bint; "Ibn",
  "Abū", "Umm" at the start of a name; the article as "al-" without assimilation (al-Zuhrī, al-Shaʿbī);
  ʿAbd Allāh and ʿAbd al-Raḥmān as separate words; tāʾ marbūṭa as -a (Ṭalḥa, ʿĀʾisha). Well-known places
  take their English names (Mecca, Medina, Basra, Kufa, Syria, Egypt, Yemen, Baghdad).
- Terms of the hadith sciences, when they occur, are written as in this glossary:
{glossary}

{instruction}

Return JSON only: {{"items": [...]}}, one object per input item, in the input order, each with "key" and
"source_sha" copied from the input and the fields named above."""

INSTRUCTIONS = {
    "opening": ('Each item is the opening of a hadith as the corpus lists it (often a fragment). Field "en": an '
                "English title — a faithful translation of the fragment, at most about 30 words, no final full "
                'stop; if the fragment stops mid-sentence end it with "…".'),
    "text": ('Each item is the full text (matn) of one narration, without its chain. Field "en": a complete, '
             "faithful English translation."),
    "narrator": ('Each item is the name by which the corpus lists a narrator, with fuller details as context. '
                 'Field "en": the transliteration of that name exactly as written. Field "short": the name by '
                 "which English scholarship commonly knows him or her (al-Zuhrī, Ibn ʿUyayna, Abū Hurayra, "
                 "ʿĀʾisha, Mālik); if there is none, the most distinctive part of the name (kunya or nisba)."),
    "critic": ('Each item is the name of a narrator critic (an author of jarḥ wa-taʿdīl). Field "en": the '
               'transliteration of the name as written. Field "short": the name English scholarship knows '
               "him by (Yaḥyā b. Maʿīn, Ibn Ḥajar, al-Dhahabī)."),
    "place": ('Each item is a place where narrators lived or died. Field "en": its usual English name, or a '
              "transliteration for lesser-known places."),
    "book": ('Each item is a hadith-corpus book title with its author. Field "title": the transliterated title '
             'by which it is commonly cited (Ṣaḥīḥ al-Bukhārī, Musnad Aḥmad, al-Sunan al-Kubrā lil-Bayhaqī). '
             'Field "en": an English title, the standard one where it exists (The Ṣaḥīḥ of al-Bukhārī; '
             'The History of Damascus). Field "author": the author\'s common short name (al-Bukhārī, Ibn ʿAsākir).'),
    "topic": 'Each item is a heading in a subject index of hadith. Field "en": a short English heading.',
}
FIELDS = {"opening": ("en",), "text": ("en",), "narrator": ("en", "short"), "critic": ("en", "short"),
          "place": ("en",), "book": ("en", "title", "author"), "topic": ("en",)}
CHUNK = {"opening": 25, "text": 4, "narrator": 60, "critic": 60, "place": 80, "book": 40, "topic": 60}


def sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def glossary_lines() -> str:
    terms = yaml.safe_load((paths.CONFIG_DIR / "glossary.yaml").read_text(encoding="utf-8"))["terms"]
    return "\n".join(f"  {t['term']}" + (f" ({t['translit']})" if t.get("translit") and t["translit"] != t["term"] else "")
                     + f" — {t['arabic']}" for t in terms if t.get("arabic"))


def prompt(kind: str) -> str:
    return PROMPT.format(glossary=glossary_lines(), instruction=INSTRUCTIONS[kind])


def prompt_sha(kind: str) -> str:
    return hashlib.sha256(prompt(kind).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- the files

def path(kind: str, root: Path = DIR) -> Path:
    if kind not in KINDS:
        raise ValueError(f"Unknown translation kind {kind}")
    return root / f"{kind}.parquet"


def read(kind: str, root: Path = DIR) -> dict[str, dict]:
    import pyarrow.parquet as pq
    p = path(kind, root)
    if not p.is_file():
        return {}
    return {row["key"]: row for row in pq.read_table(p).to_pylist()}


def write(kind: str, rows: dict[str, dict], root: Path = DIR) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    root.mkdir(parents=True, exist_ok=True)
    ordered = [rows[k] for k in sorted(rows, key=_order)]
    table = pa.table({c: pa.array([r.get(c) for r in ordered], pa.string()) for c in COLUMNS})
    pq.write_table(table, path(kind, root), compression="zstd", use_dictionary=["producer", "model", "prompt_sha", "created"])


def _order(key: str):
    parts = key.split(":")
    return tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in parts)


def load(root: Path = DIR) -> dict[str, dict[str, dict]]:
    """Every kind, for display: key -> {en, extra fields, producer, model, source_sha}."""
    out = {}
    for kind in KINDS:
        items = {}
        for key, row in read(kind, root).items():
            item = {"en": row["en"], "producer": row["producer"], "model": row["model"],
                    "source_sha": row["source_sha"]}
            item.update(json.loads(row["extra"]) if row.get("extra") else {})
            items[key] = item
        out[kind] = items
    return out


def fresh(item: dict | None, source: str | None) -> dict | None:
    """The item if it translates this exact source text, else None (stale items are never shown)."""
    if item and source is not None and item.get("source_sha") == sha(source):
        return item
    return None


def merge(kind: str, results: list[dict], sources: dict[str, str], producer: str, model: str | None,
          prompt_hash: str | None, created: str | None = None, root: Path = DIR) -> dict:
    """Validate results against the current sources and merge them into the kind's file.

    results: dicts with key, source_sha and the kind's fields. sources: key -> current source text.
    A result for an unknown key, for a changed source, or missing a field is rejected, not written.
    """
    rows = read(kind, root)
    created = created or date.today().isoformat()
    accepted, rejected = 0, []
    for result in results:
        key = str(result.get("key"))
        if key not in sources:
            rejected.append((key, "unknown key"))
            continue
        source = sources[key]
        if result.get("source_sha") != sha(source):
            rejected.append((key, "source changed or source_sha missing"))
            continue
        values = {f: (result.get(f) or "").strip() for f in FIELDS[kind]}
        if not all(values.values()):
            rejected.append((key, f"missing {', '.join(f for f, v in values.items() if not v)}"))
            continue
        extra = {f: v for f, v in values.items() if f != "en"}
        rows[key] = {"key": key, "source": source, "source_sha": sha(source), "en": values["en"],
                     "extra": json.dumps(extra, ensure_ascii=False, sort_keys=True) if extra else None,
                     "producer": producer, "model": model, "prompt_sha": prompt_hash, "created": created}
        accepted += 1
    write(kind, rows, root)
    return {"kind": kind, "accepted": accepted, "rejected": rejected}


# ---------------------------------------------------------------- the items to translate

def items(kinds=KINDS, groups=None):
    """kind -> {key: (source, context)} for the current outputs; groups limits reports and their narrators."""
    from itibar.site.data import Corpus
    corpus = Corpus(paths.PARQUET_DIR, paths.OUT_DIR, paths.REPORTS_DIR, groups)
    try:
        return _items(corpus, kinds)
    finally:
        corpus.con.close()


def _items(corpus, kinds):
    from itibar.site.data import query
    con = corpus.con
    out = {kind: {} for kind in kinds}
    if "book" in kinds:
        for book in corpus.books.values():
            out["book"][str(book["id"])] = (book["name"], {"author": book["author_name"],
                                                           "author_death_year": book["author_death_year"]})
    if "topic" in kinds:
        for row in query(con, "SELECT id, name, level, parent_id FROM topics WHERE level IN (1, 2) ORDER BY id"):
            out["topic"][str(row["id"])] = (row["name"], {"level": row["level"]})
    routes = corpus.routes()
    people = {rid: corpus.people[rid] for rid in routes}
    if "narrator" in kinds:
        details = {row["id"]: row for row in query(con, "SELECT id, name, nickname, nasab, death_year FROM rawis")}
        for rid in sorted(people):
            d = details[rid]
            out["narrator"][str(rid)] = (d["nickname"] or d["name"], {
                "full_name": d["name"], "nasab": d["nasab"], "death_year": d["death_year"]})
    if "place" in kinds:
        for place in sorted({p for rid in people for p in corpus.places(rid)}):
            out["place"][place] = (place, {})
    if "critic" in kinds and corpus.has_critics:
        ids = sorted(people)
        con.execute("CREATE OR REPLACE TEMP TABLE page_people AS SELECT unnest(?::BIGINT[]) AS rawi_id", [ids])
        for row in query(con, """
            SELECT DISTINCT a.id, a.name, coalesce(nullif(a.shuhra, ''), a.nickname, a.name) AS known, a.death_year
            FROM aqwal q JOIN page_people USING (rawi_id) JOIN alems a ON a.id = q.alem_id ORDER BY a.id
        """):
            out["critic"][str(row["id"])] = (row["known"], {"full_name": row["name"], "death_year": row["death_year"]})
    if "opening" in kinds or "text" in kinds:
        catalog = corpus.catalog()
        for lo in sorted({gid // 1000 * 1000 for gid in catalog}):
            for gid, text in corpus.representatives(lo, lo + 999).items():
                if "text" in kinds and text.get("content"):
                    out["text"][f"{gid}:{text['hadith_id']}"] = (text["content"], {"opening": catalog[gid]["opening"]})
            for gid, row in catalog.items():
                if lo <= gid <= lo + 999 and "opening" in kinds and row["opening"]:
                    out["opening"][str(gid)] = (row["opening"], {})
    return out


def fixture_groups():
    import pyarrow.parquet as pq
    table = pq.read_table(paths.FIXTURE_DIR / "parquet" / "meaning_groups.parquet", columns=["id"])
    return sorted(table.column("id").to_pylist())


# ---------------------------------------------------------------- commands

def pending(kinds, groups, dest: Path, root: Path = DIR, chunk: int | None = None, limit: int | None = None):
    """Write the missing or stale items as JSONL work sets (one file per chunk) for a session or a batch."""
    dest.mkdir(parents=True, exist_ok=True)
    summary = {}
    for kind, entries in items(kinds, groups).items():
        done = read(kind, root)
        todo = [(key, source, context) for key, (source, context) in entries.items()
                if key not in done or done[key]["source_sha"] != sha(source)]
        todo = todo[:limit] if limit else todo
        size = chunk or CHUNK[kind] * 10
        for n, start in enumerate(range(0, len(todo), size), 1):
            with (dest / f"{kind}-{n:04d}.jsonl").open("w", encoding="utf-8") as out:
                for key, source, context in todo[start:start + size]:
                    out.write(json.dumps({"kind": kind, "key": key, "source": source, "source_sha": sha(source),
                                          "context": context}, ensure_ascii=False, default=str) + "\n")
        summary[kind] = {"items": len(entries), "translated": len(entries) - len(todo), "pending": len(todo)}
    (dest / "PROMPTS.md").write_text("".join(f"## {kind}\n\nprompt_sha {prompt_sha(kind)}\n\n```\n{prompt(kind)}\n```\n\n"
                                             for kind in kinds), encoding="utf-8")
    return summary


def import_files(files, producer, model, groups=None, root: Path = DIR):
    results = {}
    for file in files:
        for line in Path(file).read_text(encoding="utf-8").splitlines():
            if line.strip():
                result = json.loads(line)
                results.setdefault(result["kind"], []).append(result)
    current = items(tuple(results), groups)
    return [merge(kind, rows, {k: s for k, (s, _) in current[kind].items()}, producer, model, prompt_sha(kind), root=root)
            for kind, rows in results.items()]


def status(groups=None, root: Path = DIR):
    out = {}
    for kind, entries in items(KINDS, groups).items():
        done = read(kind, root)
        current = sum(1 for k, (s, _) in entries.items() if k in done and done[k]["source_sha"] == sha(s))
        producers = {}
        for row in done.values():
            producers[row["producer"]] = producers.get(row["producer"], 0) + 1
        out[kind] = {"items": len(entries), "current": current, "stale": sum(
            1 for k, (s, _) in entries.items() if k in done and done[k]["source_sha"] != sha(s)), "producers": producers}
    return out


def sample(n: int, seed: int, dest: Path, root: Path = DIR):
    """A random sample of translated items with their Arabic, for the second pass (checks.parquet)."""
    pool = [(kind, row) for kind in KINDS for row in read(kind, root).values()]
    picked = random.Random(seed).sample(pool, min(n, len(pool)))
    with dest.open("w", encoding="utf-8") as out:
        for kind, row in sorted(picked, key=lambda x: (KINDS.index(x[0]), _order(x[1]["key"]))):
            out.write(json.dumps({"kind": kind, "key": row["key"], "source": row["source"], "source_sha": row["source_sha"],
                                  "en": row["en"], "extra": json.loads(row["extra"]) if row["extra"] else {}},
                                 ensure_ascii=False) + "\n")
    return {"sampled": len(picked), "pool": len(pool)}


def record_checks(file: Path, checker: str, root: Path = DIR):
    """Append check verdicts: kind, key, source_sha, verdict (ok | minor | wrong), problem, fixed."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    rows = []
    if (root / "checks.parquet").is_file():
        rows = pq.read_table(root / "checks.parquet").to_pylist()
    seen = {(r["kind"], r["key"], r["checker"]) for r in rows}
    for line in Path(file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["verdict"] not in ("ok", "minor", "wrong"):
            raise ValueError(f"{r['key']}: verdict must be ok, minor or wrong")
        if (r["kind"], r["key"], checker) in seen:
            continue
        rows.append({"kind": r["kind"], "key": str(r["key"]), "source_sha": r["source_sha"], "verdict": r["verdict"],
                     "problem": r.get("problem") or None, "fixed": bool(r.get("fixed")), "checker": checker,
                     "created": date.today().isoformat()})
    cols = ("kind", "key", "source_sha", "verdict", "problem", "fixed", "checker", "created")
    table = pa.table({c: pa.array([r[c] for r in rows], pa.bool_() if c == "fixed" else pa.string()) for c in cols})
    pq.write_table(table, root / "checks.parquet", compression="zstd")
    return {v: sum(r["verdict"] == v for r in rows) for v in ("ok", "minor", "wrong")}


def api(kinds, groups, root: Path = DIR, model: str = MODEL, poll: int = 60):
    """The optional Message Batches path: submit every pending item, wait, import (needs credentials)."""
    import time

    import anthropic  # optional dependency: uv sync --extra translate

    client = anthropic.Anthropic()
    entries = items(kinds, groups)
    requests, chunks = [], {}
    for kind in kinds:
        done = read(kind, root)
        todo = [(k, s, c) for k, (s, c) in entries[kind].items() if k not in done or done[k]["source_sha"] != sha(s)]
        schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {"items": {
            "type": "array", "items": {"type": "object", "additionalProperties": False,
                                       "required": ["key", "source_sha", *FIELDS[kind]],
                                       "properties": {f: {"type": "string"} for f in ("key", "source_sha", *FIELDS[kind])}}}}}
        for n, start in enumerate(range(0, len(todo), CHUNK[kind])):
            batch = todo[start:start + CHUNK[kind]]
            custom_id = f"{kind}-{n:05d}"
            chunks[custom_id] = kind
            requests.append({"custom_id": custom_id, "params": {
                "model": model, "max_tokens": 16000,
                "system": [{"type": "text", "text": prompt(kind), "cache_control": {"type": "ephemeral"}}],
                "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
                "messages": [{"role": "user", "content": "\n".join(json.dumps(
                    {"key": k, "source_sha": sha(s), "source": s, "context": c}, ensure_ascii=False, default=str)
                    for k, s, c in batch)}]}})
    if not requests:
        return {"submitted": 0}
    results = {}
    for start in range(0, len(requests), 50_000):
        batch = client.messages.batches.create(requests=requests[start:start + 50_000])
        print(f"batch {batch.id}: {len(requests[start:start + 50_000])} requests", file=sys.stderr)
        while client.messages.batches.retrieve(batch.id).processing_status != "ended":
            time.sleep(poll)
        for result in client.messages.batches.results(batch.id):
            if result.result.type != "succeeded":
                print(f"  {result.custom_id}: {result.result.type}", file=sys.stderr)
                continue
            text = next((b.text for b in result.result.message.content if b.type == "text"), "")
            kind = chunks[result.custom_id]
            results.setdefault((kind, f"api-batch:{batch.id}"), []).extend(json.loads(text)["items"])
    summary = []
    for (kind, producer), rows in results.items():
        sources = {k: s for k, (s, _) in entries[kind].items()}
        summary.append(merge(kind, rows, sources, producer, model, prompt_sha(kind), root=root))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("pending", "import", "status", "api"):
        p = sub.add_parser(name)
        p.add_argument("--kinds", default=",".join(KINDS))
        p.add_argument("--fixture", action="store_true", help="limit reports and narrators to the committed fixture")
        if name == "pending":
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--chunk", type=int)
            p.add_argument("--limit", type=int)
        if name == "import":
            p.add_argument("files", nargs="+")
            p.add_argument("--producer", required=True)
            p.add_argument("--model", default=MODEL)
        if name == "api":
            p.add_argument("--model", default=MODEL)
    p = sub.add_parser("sample")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("record-checks")
    p.add_argument("file", type=Path)
    p.add_argument("--checker", required=True)
    p = sub.add_parser("prompt")
    p.add_argument("kind", choices=KINDS)
    args = parser.parse_args()
    kinds = tuple(k for k in getattr(args, "kinds", "").split(",") if k)
    groups = fixture_groups() if getattr(args, "fixture", False) else None
    if args.command == "pending":
        result = pending(kinds, groups, args.out, chunk=args.chunk, limit=args.limit)
    elif args.command == "import":
        result = import_files(args.files, args.producer, args.model, groups)
    elif args.command == "status":
        result = status(groups)
    elif args.command == "api":
        result = api(kinds, groups, model=args.model)
    elif args.command == "sample":
        result = sample(args.n, args.seed, args.out)
    elif args.command == "record-checks":
        result = record_checks(args.file, args.checker)
    else:
        print(prompt(args.kind))
        print(f"\nprompt_sha {prompt_sha(args.kind)}")
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
