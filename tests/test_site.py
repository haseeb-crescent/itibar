"""Page builders, source evidence, and Python/browser normalization parity."""
import gzip
import json
import shutil
import subprocess
from collections import defaultdict
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from itibar import grades, lists, paths, pipeline
from itibar.site.data import read_verdicts
from itibar.site.pages import Pages
from itibar.site.search import SearchIndex
from tests.synthetic import chain, make_corpus


def test_structure_receipts_certify_threshold_values_and_book_edges():
    source = make_corpus(
        {1: {"rank_no": 1}, 2: {"rank_no": 4}, 3: {"rank_no": 10}},
        {1: {"author_no": 1, "compiler_rawi": 3}},
    )
    attested = chain(1, 3, 2, 1)
    result = pipeline.analyse_group(42, [attested], source, {"matn_no": 1})
    record = result["record"]
    receipts = json.loads(record["receipt_structure"])
    data = receipts["saduq_up"][0]["data"]
    assert data["routes"] == [{"nodes": ["P", "r1", "r2", "r3", "c1", "b1"],
                               "sanads": [attested.sanad_id] * 5}]
    assert len(data["cut"]) == receipts["saduq_up"][0]["result"] == record["kappa_saduq_up"]
    assert receipts["thiqa_up"][0]["result"] == record["kappa_thiqa_up"] == 0
    for threshold, (flow, lower, cuts) in receipts.items():
        if threshold == "structure":
            continue
        assert flow["result"] == len(flow["data"]["routes"]) == len(flow["data"]["cut"])
        assert lower["result"] == min(lower["data"][key] for key in ("unmerged", "merged", "nocompat"))
        assert cuts["result"] == record["cut_vertices" if threshold == "all" else f"cut_vertices_{threshold}"]
    mask = {(edge["u"], edge["v"]): edge["threshold_mask"] for edge in result["edges"]}
    assert mask["r1", "r2"] == 0b0111
    assert mask["r3", "c1"] == 0b1111


def test_report_and_narrator_page_builders(tmp_path):
    source = make_corpus({10: {"rank_no": 1}, 20: {"rank_no": 3}}, {1: {"author_no": 1, "compiler_rawi": 20}})
    attested = chain(1, 20, 10)
    result = pipeline.analyse_group(42, [attested], source, {"matn_no": 0})
    result["chains"][0]["people"] = [{"rawi": 20, "word": None}, {"rawi": 10, "word": "عن"}]
    result["chains"][0]["no_inbook"] = 1
    result["chains"][0]["recorded_grade"] = "صحيح"
    book = {"id": 1, "name": "كتاب", "author_name": "محدث", "author_death_year": 120}
    person = {"id": 10, "name": "راو بن راو", "nickname": "راو", "rank_no": 1, "tabaka": 1,
              "rank": "صحابي", "death_year": 50}
    row = {**result["record"], "opening": "أول الحديث"}
    corpus = SimpleNamespace(
        people={10: person}, books={1: book}, authors={1: book}, node=lambda node: "النبي" if node == "P" else str(node),
        name=lambda rid: str(rid), gold=defaultdict(list), scale=grades.load(), verdicts={},
        tiers={10: 2}, mudallis_sources={2: "https://shamela.ws/book/1186/9"},
        rulings={10: [{"kind": "from_shaykh", "quote": "قول الناقد", "observable": True,
                       "effect": "level:4", "source_book": "الكتاب",
                       "citation": "[شاهد](https://shamela.ws/book/8609/549)"}]},
    )
    representative = {"content": "نص الحديث", "book_id": 1, "no_inbook": 1, "text_code": 0, "text_grade": "صحيح",
                      "sanad_id": attested.sanad_id, "chain_code": 0, "chain_grade": "صحيح", "hukum": "قول المصدر"}
    references = [{"book_id": 1, "no_inbook": 1}]
    pages = Pages(tmp_path)
    edges = [{**edge, "weight": len(edge["sanad_ids"])} for edge in result["edges"]]
    args = (row, result["nodes"], edges, references, representative, result["chains"], {10})
    pages.report(corpus, *args)
    report_path = tmp_path / "reports/42/index.html"
    html = report_path.read_text()
    assert "نص الحديث" in html and "قول المصدر" in html
    assert "Derived by itibar" in html and "Recorded by hadith-kg" in html
    assert "What the critics said" not in html
    assert json.loads(gzip.decompress((report_path.parent / "chains.json.gz").read_bytes()))["words"] == [None, "عن"]

    file = tmp_path / "verdicts.parquet"
    assert read_verdicts(file) == {}
    pq.write_table(pa.Table.from_pylist([
        {"group_id": 42, "critic": "al-Tirmidhī", "quote": "قال الناقد <mark>", "result": "Matched"},
        {"group_id": None, "critic": "al-Tirmidhī", "quote": "Unlinked quote", "result": "Unmapped"},
    ]), file)
    corpus.verdicts = read_verdicts(file)
    pages.report(corpus, *args)
    html = report_path.read_text()
    assert "What the critics said" in html and "al-Tirmidhī" in html and "Matched" in html
    assert "قال الناقد &lt;mark&gt;" in html and "Unlinked quote" not in html

    pages.narrator(corpus, 10, [{"group_id": 42, "common_link": False, "cut_vertex": True}], {}, {42: row})
    html = (tmp_path / "narrators/10/index.html").read_text()
    assert "50 AH" in html and "Tier 2" in html and "قول الناقد" in html
    assert "https://shamela.ws/book/8609/549" in html and "../../reports/42/" in html

    pages.report(corpus, {"group_id": 0, "status": "no_chains", "opening": "غير منشور"},
                 [], [], [], {}, [], set())
    html = (tmp_path / "reports/0/index.html").read_text()
    assert "No chains recorded" in html and "Transmission bundle" not in html


def test_search_index_reads_titles_text_names_and_citations(tmp_path):
    index = SearchIndex()
    index.report(319, "إِنَّـمَا الأَعْمَالُ", "بالنِّيَّات", [{"book_id": 1, "no_inbook": 1}])
    index.narrator(8272, "يحيى بن سعيد", "يحيى بن سعيد الأنصاري")
    assert index.postings["انما"] == [319 * 2 + 1]
    assert index.postings["بالنيات"] == [319 * 2]
    assert index.postings["الانصاري"] == [-8272 * 2 + 1]
    assert index.citations["1"] == {(1, 319)}
    index.write(tmp_path, {1: {"name": "صحيح البخاري", "author_name": "محمد بن إسماعيل البخاري"}})
    assert "bukhari" in json.loads((tmp_path / "books.json").read_text())["1"][1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is required for browser normalization parity")
def test_javascript_normalizer_matches_lists():
    texts = [None, "", "إِنَّـمَا الأَعْمَالُ بِالنِّيَّاتِ ﷺ", "أإآٱ ى ة ؤ ئ",
             "72، البُخاري ١", "ا\u0085ب\u2000ت\u001cث", "ا\ufeffب\u200bت", "الله ABC ح"]
    texts.extend(f"ا{chr(code)}ب" for code in range(0x600, 0x900))
    source = (paths.ROOT / "site/assets/normalizer.mjs").as_uri()
    script = f"""import {{ normalizeArabic }} from {json.dumps(source)};
    import {{ readFileSync }} from "node:fs";
    const items = JSON.parse(readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(items.map(normalizeArabic)));
    """
    run = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(texts),
                         check=True, capture_output=True, text=True)
    assert json.loads(run.stdout) == [lists.normalize(text) for text in texts]
