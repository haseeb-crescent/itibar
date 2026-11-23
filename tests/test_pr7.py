"""PR 7 on known answers: the source's grade sentences parsed, the template code, the code-map switch in v1 and
v2, the critics' claims extracted with their spans and names, and the cut test."""

from itibar import critics, lists, pipeline, source_template, verdicts
from tests.synthetic import chain, make_corpus

C1 = 1
A1 = 91
T, S, W = 10, 21, 50


def corpus(extra=None):
    p = {C1: {"rank_no": 1, "tabaka": 1}, T: {"rank_no": 3, "tabaka": 3}, S: {"rank_no": 3, "tabaka": 5},
         A1: {"rank_no": 3, "tabaka": 9}}
    p.update(extra or {})
    return make_corpus(p, {3: {"author_no": 100, "compiler_rawi": A1}})


# ---------------------------------------------------------------- 1. the sentences

def test_hukum_parse():
    P = source_template.parse("إسناده حسن رجاله ثقات عدا محمد بن عمرو الليثي وهو صدوق له أوهام ، رجاله رجال مسلم")
    assert P.opening == "hasan" and P.thiqat == "thiqat" and P.rijal == "مسلم"
    assert P.named == [("محمد بن عمرو الليثي", "صدوق له أوهام")]
    P = source_template.parse("إسناد ضعيف لأن به موضع انقطاع بين عبد الرحمن بن عمرو الأوزاعي وحميري بن بشير البصري ، "
                              "وباقي رجاله ثقات")
    assert P.opening == "daif" and P.breaks == ["inqita"] and P.between and P.ok
    P = source_template.parse("إسناد فيه متهمان بالوضع وهما داود بن المحبر الطائي ، وميسرة بن عبد ربه الفارسي")
    assert P.opening == "muttaham" and [n for n, _ in P.muttaham] == ["داود بن المحبر الطائي", "ميسرة بن عبد ربه الفارسي"]
    P = source_template.parse("إسناده متصل ، رجاله ثقات ، رجاله رجال البخاري عدا محمد بن إدريس الشافعي روى له البخاري "
                              "تعليقًا")
    assert P.rijal == "البخاري" and P.rijal_exc == [("محمد بن إدريس الشافعي", "taliq")]
    assert source_template.family(P) == "إسناده متصل ، رجاله ثقات ، رجاله رجال البخاري عدا {N} روى له البخاري تعليقًا"


# ---------------------------------------------------------------- 2. the template code

def test_template_code():
    c = corpus({W: {"rank_no": 6, "tabaka": 4}, 200: {"rank_no": 8, "tabaka": 10}, 201: {"rank_no": 0, "stub": 1}})
    nar, sc = c.narrators, c.scale
    code = lambda *r: source_template.chain_code(r, nar.rank_no, nar.is_stub, sc)  # noqa: E731
    assert code(A1, S, T, C1).code == 0
    assert code(A1, W, T, C1).code == 1                       # maqbul: 1 under the template's map
    assert code(200, S, T, C1).code == 2                      # the compiler at pos 0 is graded
    assert code(A1, 201, T, C1).code == 2                     # an undescribed narrator reads level 7
    assert code(A1, S, 1131, C1).code == 0                    # the unnamed person is not graded
    assert code(A1, S, T, 30002).code == 2                    # one break -> 2
    assert code(A1, 30001, T, 30002).code == 3                # two breaks -> 3
    assert code(A1, 1131, 30000, C1).code == 3                # with an inqita' marker, the unnamed person is an irsal
    assert code(A1, 1131, T, 30002).code == 2                 # ... counted once with an irsal marker
    assert source_template.group_code([(2, 5), (1, 9), (1, 7)]) == (1, 7)


# ---------------------------------------------------------------- 3. the code maps

def test_code_maps_v1_and_v2():
    c = corpus({W: {"rank_no": 6, "tabaka": 4}})
    ch = chain(3, A1, W, T, C1)
    out = pipeline.analyse_group(1, [ch], c, {"matn_no": 1, "nass": "", "sahaba_qty": 1}, None)
    rec, row = out["record"], out["chains"][0]
    assert rec["derived_code_classical"] == 2 and rec["derived_code_source"] == 1 and rec["derived_code"] == 2
    assert row["chain_code_classical"] == 2 and row["chain_code_source"] == 1
    assert rec["code_v2_ibn_hajar_classical"] == 2 and rec["code_v2_ibn_hajar_source"] == 1
    assert rec["code_source_template"] == 1 and row["code_source_template"] == 1
    c = corpus({W: {"rank_no": 8, "tabaka": 4}})                 # level 8: 2 under both maps
    out = pipeline.analyse_group(1, [chain(3, A1, W, T, C1)], c, {"matn_no": 2, "nass": "", "sahaba_qty": 1}, None)
    assert out["record"]["code_v2_ibn_hajar_classical"] == out["record"]["code_v2_ibn_hajar_source"] == 2


# ---------------------------------------------------------------- 4. the critics' claims

def test_norm_map_spans():
    text = "قَالَ أَبُو عِيسَى : هَذَا حَدِيثٌ حَسَنٌ صَحِيحٌ ، وَفِي الْبَابِ عَنْ عَلِيٍّ"
    n, pos = verdicts.norm_map(text)
    assert n == lists.normalize(text)
    a = n.index("هذا حديث")
    b = a + len("هذا حديث حسن صحيح")
    s0, s1, span = verdicts.source_span(text, pos, a, b)
    assert span in text and lists.normalize(span) == "هذا حديث حسن صحيح" and text[s0:s1] == span


def test_formula_matches():
    fam = {f.key: f for f in verdicts.FAMILIES}
    m = fam["tabarani_lam_yarwi"].pattern.search(lists.normalize(
        "لَمْ يَرْوِ هَذَا الْحَدِيثَ عَنْ عَاصِمٍ الأَحْوَلِ إِلا زُهَيْرُ بْنُ مُعَاوِيَةَ ، تَفَرَّدَ بِهِ أَحْمَدُ"))
    assert m.group("x") == "عاصم الاحول" and m.group("y") == "زهير بن معاويه"
    m = fam["tirmidhi_verdict"].pattern.search("قال ابو عيسي هذا حديث حسن غريب من هذا الوجه")
    assert m.group("grade") == "حسن غريب" and m.group("scope") == "من هذا الوجه"
    m = fam["hakim_shart"].pattern.search("هذا حديث صحيح علي شرط الشيخين ولم يخرجاه")
    assert m.group("clause") == "الشيخين"
    assert verdicts.split_names("سعد بن ابي وقاص وعلي وابن عمر ووايل بن حجر") == \
        ["سعد بن ابي وقاص", "علي", "ابن عمر", "وايل بن حجر"]


def test_cut_test():
    succ = {"P": ["r1"], "r1": ["r2", "r3"], "r2": ["r4"], "r3": ["r4"], "r4": ["c9"], "c9": ["b1"]}
    assert critics.reaches_book_avoiding(succ, "r1", "r2")     # r3 is another student of r1
    assert not critics.reaches_book_avoiding(succ, "r1", "r4")  # every route from r1 passes r4
    assert not critics.reaches_book_avoiding(succ, "P", "r1")
