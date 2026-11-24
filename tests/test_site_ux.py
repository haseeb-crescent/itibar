"""The reading layer (site-ux brief): story tree, sentences, translations contract, glossary, search words."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from itibar import narrators, paths, pipeline, translate
from itibar.hadeethenc import match, strip_intro
from itibar.site import story as storylib
from itibar.site import validate, view, vocab
from itibar.site.search import english_tokens
from tests.synthetic import chain, make_corpus

THRESHOLDS = ["all", "above_matruk", "saduq_up", "thiqa_up"]


def bundle():
    """One companion, a single line of two, then a teacher with eight students who each compile a book."""
    people = {1: {"rank_no": 1, "tabaka": 1}, 2: {"rank_no": 3, "tabaka": 2}, 3: {"rank_no": 2, "tabaka": 4}}
    books, chains = {}, []
    for n in range(8):
        student, compiler = 10 + n, 30 + n
        people[student] = {"rank_no": 3 if n < 6 else 8, "tabaka": 6}
        people[compiler] = {"rank_no": 3, "tabaka": 9}
        books[100 + n] = {"author_no": 200 + n, "compiler_rawi": compiler}
        chains.append(chain(100 + n, compiler, student, 3, 2, 1))
    source = make_corpus(people, books)
    result = pipeline.analyse_group(7, chains, source, {"matn_no": 0})
    record = result["record"]
    steps = json.loads(record["receipt_structure"])
    edges = [{**e, "sanad_ids": list(e["sanad_ids"])} for e in result["edges"]]
    return record, result["nodes"], edges, steps


def test_story_names_the_single_line_and_groups_the_fan():
    record, nodes, edges, steps = bundle()
    story = storylib.build(record, nodes, edges, steps, THRESHOLDS)
    rows = story["rows"]
    assert rows[0]["items"] == ["P"] and rows[-1]["gen"] == "books"
    named = [row["items"] for row in rows[1:4]]
    assert named == [["r1"], ["r2"], ["r3"]]
    groups = [item for item in story["items"].values() if item["kind"] in ("group", "band")]
    fan = next(item for item in groups if set(item["members"]) >= {f"r{10 + n}" for n in range(8)})
    assert fan["anchor"] == "r3" and fan["count"] >= 8
    # Every chain runs through r1, r2, r3: one independent line, drawn through those items.
    assert record["kappa_all"] == 1
    line = story["lines"]["all"][0]["items"]
    assert line[:4] == ["P", "r1", "r2", "r3"]
    # Two students are rated weak: with trustworthy narrators only, the fan keeps six.
    assert fan["alive"][THRESHOLDS.index("thiqa_up")] == 6 + (fan["count"] - 8)
    # Compilers are contracted: links run from the last narrator into the books.
    assert all(not a.startswith("c") and not b.startswith("c") for a, b in story["links"])


def test_story_payload_and_sentences_restate_the_record():
    record, nodes, edges, steps = bundle()
    story = storylib.build(record, nodes, edges, steps, THRESHOLDS)
    corpus = FakeCorpus()
    names = view.Names(corpus, {1, 2, 3})
    payload, outline = view.story_payload(story, names, corpus, record, steps)
    assert outline[0]["label"] == "The Prophet" and outline[1]["label"] == "Companions"
    assert {"rows", "items", "links", "lines", "th", "people"} <= payload.keys()
    assert validate.story_problems("story", payload) == []
    glance = view.glance(record, names, story, [], steps)
    text = " ".join(str(s) for s in glance["sentences"])
    assert "Every line passes through" in text and "bottleneck" in text
    assert [t["n"] for t in glance["tiles"]] == [record["companions"], 1, record["kappa_thiqa_up"], 8]
    assert "This hadith is" not in text and "κ" not in text
    sentence = str(view.threshold_sentence("thiqa_up", record, story, names, steps, corpus.people))
    assert sentence.startswith("With trustworthy narrators only, 1 independent line remains")


class FakeCorpus:
    def __init__(self):
        self.people = {rid: {"id": rid, "nickname": f"راو {rid}", "name": f"راو {rid}", "rank_no": 3, "tabaka": 4,
                             "death_year": 100 + rid, "death_year_raw": None, "rank": "ثقة"} for rid in range(1, 40)}
        self.english = {"narrator": {}}

    def person(self, rid):
        return (f"Narrator {rid}", f"N{rid}", f"راو {rid}") if rid < 5 else (None, None, f"راو {rid}")

    def book(self, book_id):
        return (None, None, f"كتاب {book_id}", None)

    def place(self, place):
        return None

    def places(self, rid):
        return []

    def node(self, node):
        return node


def test_translation_contract_validates_against_the_source(tmp_path):
    sources = {"1": "إنما الأعمال بالنيات", "2": "لا تكذبوا علي"}
    results = [
        {"key": "1", "source_sha": translate.sha(sources["1"]), "en": "Actions are only by intentions"},
        {"key": "2", "source_sha": translate.sha("an older text"), "en": "Stale"},
        {"key": "3", "source_sha": "x", "en": "Unknown"},
    ]
    summary = translate.merge("opening", results, sources, "session:2026-11-23:test", "claude-opus-5-5", "abc", root=tmp_path)
    assert summary["accepted"] == 1 and {k for k, _ in summary["rejected"]} == {"2", "3"}
    rows = translate.read("opening", tmp_path)
    assert rows["1"]["producer"] == "session:2026-11-23:test" and rows["1"]["source"] == sources["1"]
    loaded = translate.load(tmp_path)["opening"]["1"]
    assert translate.fresh(loaded, sources["1"])["en"] == "Actions are only by intentions"
    assert translate.fresh(loaded, "a changed source") is None
    # A narrator needs both fields; the extra field is stored and returned.
    bad = translate.merge("narrator", [{"key": "9", "source_sha": translate.sha("راو"), "en": "Rāwī"}],
                          {"9": "راو"}, "api-batch:msgbatch_1", "claude-opus-5-5", "abc", root=tmp_path)
    assert bad["accepted"] == 0
    translate.merge("narrator", [{"key": "9", "source_sha": translate.sha("راو"), "en": "Rāwī", "short": "al-Rāwī"}],
                    {"9": "راو"}, "api-batch:msgbatch_1", "claude-opus-5-5", "abc", root=tmp_path)
    assert translate.load(tmp_path)["narrator"]["9"]["short"] == "al-Rāwī"


def test_prompt_includes_the_glossary_and_hashes_stably():
    text = translate.prompt("narrator")
    assert "independent lines" in text and "IJMES" in text and '"short"' in text
    assert translate.prompt_sha("narrator") == translate.prompt_sha("narrator") != translate.prompt_sha("text")


def test_glossary_covers_every_term_the_interface_links():
    terms = vocab.terms()
    used = set()
    for path in list((paths.ROOT / "src/itibar/site").rglob("*.html")) + list((paths.ROOT / "src/itibar/site").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        used |= set(re.findall(r"""\bt\(['"]([a-z-]+)['"]""", text))
        used |= set(re.findall(r"""\bterm\(['"]([a-z-]+)['"]""", text))
        used |= set(re.findall(r"glossary/#([a-z-]+)", text))
    used.discard("")
    assert used and used <= terms.keys(), used - terms.keys()
    for term in terms.values():
        assert set(term.get("see", [])) <= terms.keys()
        assert term["short"] and term["source"]
    g = vocab.glossary()
    assert sorted(g["levels"]) == list(range(1, 13)) and all(v["badge"] and v["meaning"] for v in g["levels"].values())
    assert sorted(g["generations"]) == list(range(1, 13)) and sorted(g["tadlis_tiers"]) == [1, 2, 3, 4, 5]
    assert set(g["thresholds"]) == set(THRESHOLDS)


def test_dates_in_both_calendars():
    assert vocab.ce(124) == "741–742 CE"
    assert vocab.died(143) == "d. 143 AH (760–761 CE)"
    assert vocab.died(130, "130 - 121") == "d. 130 - 121 AH (as recorded)"
    assert vocab.died(None) is None


def test_english_words_are_normalized_and_stemmed():
    assert english_tokens("Actions are judged by intentions") == ["action", "judg", "intention"]
    assert english_tokens("Whoever lies about me deliberately") == ["whoever", "lie", "deliberately"]
    assert english_tokens("al-Zuhrī, ʿUmar") == ["al", "zuhri", "umar"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required for browser normalization parity")
def test_javascript_english_tokens_match_python():
    texts = ["Actions are judged by intentions", "Whoever lies about me deliberately", "al-Zuhrī ʿUmar b. al-Khaṭṭāb",
             "The Prophet's companions said: 'yes'", "studies classes passing used", "", "Ṣaḥīḥ al-Bukhārī 1"]
    source = (paths.ROOT / "site/assets/normalizer.mjs").as_uri()
    script = f"""import {{ englishTokens }} from {json.dumps(source)};
    import {{ readFileSync }} from "node:fs";
    process.stdout.write(JSON.stringify(JSON.parse(readFileSync(0, "utf8")).map(englishTokens)));"""
    run = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(texts),
                         check=True, capture_output=True, text=True)
    assert json.loads(run.stdout) == [english_tokens(t) for t in texts]


def test_teachers_and_students_count_reports_and_chains():
    d = duckdb.connect()
    d.register("e", pd.DataFrame([
        {"group_id": 1, "u": "r1", "v": "r2", "on_path": True, "sanad_ids": [1, 2]},
        {"group_id": 2, "u": "r1", "v": "r2", "on_path": True, "sanad_ids": [3]},
        {"group_id": 2, "u": "r1", "v": "r3", "on_path": False, "sanad_ids": [4]},
        {"group_id": 2, "u": "r3", "v": "c9", "on_path": True, "sanad_ids": [5]},
    ]))
    rows = narrators.links(d).to_dict("records")
    assert rows == [{"teacher": 1, "student": 2, "reports": 2, "chains": 3}]


def test_hadeethenc_items_join_only_on_a_clear_match():
    hadiths = {1: {"انما", "الاعمال", "بالنيات"}, 2: {"لا", "تكذبوا", "علي"}, 3: {"انما", "الاعمال", "بالخواتيم"}}
    idf = {"انما": 0.5, "الاعمال": 1.0, "بالنيات": 3.0, "لا": 0.1, "تكذبوا": 3.0, "علي": 0.3, "بالخواتيم": 3.0}
    groups = {1: 319, 2: 1, 3: 999}
    items = [{"id": "5", "hadeeth_ar": "عن عمر: إنما الأعمال بالنيات", "hadeeth_intro_ar": "عن عمر:"},
             {"id": "6", "hadeeth_ar": "إنما الأعمال", "hadeeth_intro_ar": ""}]
    found = match(items, hadiths, idf, groups)
    assert found["5"][0] == 319 and "6" not in found   # 6 fits 319 and 999 equally: no clear match
    assert strip_intro("عن عمر: نص", "عن عمر:") == " نص"


def test_checks_flag_internal_identifiers_and_verdicts():
    parser = validate.PageLinks()
    parser.feed('<p>rule sahih_li_dhatihi</p><code>kappa_all</code><p>This hadith is weak.</p>'
                '<p id="x">κ 4</p><section id="specialists"><p>κ 4</p></section>')
    problems = validate.page_text_problems("reports/1/index.html", parser)
    assert any("sahih_li" in p for p in problems) and any("verdict" in p for p in problems)
    assert any("κ outside" in p for p in problems)
    assert not any("kappa_all" in p for p in problems)   # code is the specialists' notation
