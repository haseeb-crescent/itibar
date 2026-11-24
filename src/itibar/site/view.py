"""What a report page says, generated from the stored record by fixed templates (no model, no judgement).

Every sentence here restates a stored number or flag in words and links to the section that computes
it. Grades are classical terms with their attribution; nothing is phrased as the site's verdict.
"""
from __future__ import annotations

import json
from collections import defaultdict

from markupsafe import Markup, escape

from itibar.site import story as storylib
from itibar.site import vocab

THRESHOLDS = ("all", "above_matruk", "saduq_up", "thiqa_up")
MAJOR = storylib.MAJOR
SHORT_BOOK = {1: "al-Bukhārī", 2: "Muslim", 3: "al-Tirmidhī", 4: "Abū Dāwūd", 5: "al-Nasāʾī", 6: "Ibn Mājah",
              7: "al-Dārimī", 8: "Mālik", 9: "Aḥmad"}
BOOK_GROUPS = (
    ("sahihayn", "The Ṣaḥīḥayn", "sahihayn", lambda b: b["id"] in (1, 2)),
    ("six", "The other Six Books", "six-books", lambda b: b["id"] in (3, 4, 5, 6)),
    ("early", "Musnads, Sunan, Muwaṭṭaʾs and other Ṣaḥīḥs", None,
     lambda b: b["tasnif_no"] in (1, 2, 3, 4) and b["id"] not in (1, 2, 3, 4, 5, 6)),
    ("later", "Later collections and other works", None, lambda b: True),
)
DIVERGENCE = {
    "mutabaa_tamma": ("mutābaʿa tāmma", "a complete following: it reaches the weak narrator's own teacher"),
    "mutabaa_qasira": ("mutābaʿa qāṣira", "a partial following: it joins the chain higher up, through the same companion"),
    "shahid": ("shāhid", "a witness: the same meaning through another companion"),
    "wasl": ("waṣl", "it supplies the link the mursal chain leaves out"),
}


ROOT = "@root/"   # replaced by the page's relative root when the page (or its JSON) is written


def term(glossary_id, text):
    """A glossary-linked term: the interface's only way to show a term of art (tooltip from the glossary)."""
    return Markup('<a class=term href="@root/glossary/#{id}">{text}</a>').format(id=glossary_id, text=text)


def join(names):
    names = [n for n in names if n]
    if len(names) <= 1:
        return Markup("").join(names)
    return Markup(", ").join(names[:-1]) + Markup(" and ") + names[-1]


class Names:
    """Display names for one report: English where a current translation exists, Arabic beside or instead."""

    def __init__(self, corpus, route_narrators):
        self.corpus = corpus
        self.routes = route_narrators

    def person(self, node):
        """{en, short, ar, rid, page} for a node id (r<id>, u<group>, m…)."""
        if node.startswith("r"):
            rid = int(node[1:])
            en, short, ar = self.corpus.person(rid)
            return {"en": en, "short": short, "ar": ar, "rid": rid, "page": rid in self.routes}
        if node.startswith("u"):
            return {"en": "an unnamed companion", "short": "an unnamed companion", "ar": "رجل من أصحاب النبي ﷺ",
                    "rid": None, "page": False}
        if node.startswith("m"):
            return {"en": "an unnamed narrator", "short": "an unnamed narrator", "ar": "اسم مبهم", "rid": None, "page": False}
        if node.startswith("b"):
            en, title, ar, _ = self.corpus.book(int(node[1:]))
            return {"en": title or en, "short": title or en, "ar": ar, "rid": None, "page": False}
        if node == "P":
            return {"en": "the Prophet", "short": "the Prophet", "ar": "النبي ﷺ", "rid": None, "page": False}
        return {"en": None, "short": None, "ar": self.corpus.node(node), "rid": None, "page": False}

    def short(self, node):
        p = self.person(node)
        return p["short"] or p["en"] or p["ar"]

    def html(self, node, *, full=False, link=True, arabic=False):
        """A name in running English text; Arabic when untranslated. arabic=True adds the Arabic as a tooltip
        (chain strips); the side panel and the narrator page give it in full."""
        p = self.person(node)
        text = (p["en"] if full else p["short"]) or p["en"]
        if text and arabic:
            inner = Markup('<span title="{ar}">{text}</span>').format(ar=p["ar"], text=text)
        elif text:
            inner = Markup(text)
        else:
            inner = Markup('<bdi lang=ar dir=rtl>{ar}</bdi>').format(ar=p["ar"])
        if link and p["page"]:
            return Markup('<a href="@root/narrators/{rid}/">{inner}</a>').format(rid=p["rid"], inner=inner)
        return inner

    def died(self, node):
        if not node.startswith("r"):
            return None
        person = self.corpus.people.get(int(node[1:]), {})
        return vocab.died(person.get("death_year"), person.get("death_year_raw"))


def book_view(corpus, book_id, numbers=None):
    en, title, ar, author = corpus.book(book_id)
    return {"id": book_id, "en": en, "title": title or (SHORT_BOOK.get(book_id)), "ar": ar, "author": author,
            "short": SHORT_BOOK.get(book_id) or title or en, "numbers": numbers or []}


def header(corpus, row, references):
    books = defaultdict(list)
    for ref in references:
        if ref["no_inbook"] is not None:
            books[ref["book_id"]].append(ref["no_inbook"])
    for book_id in {ref["book_id"] for ref in references}:
        books.setdefault(book_id, [])
    chips = [book_view(corpus, b, sorted(books[b], key=_number)) for b in MAJOR if b in books]
    return {"chips": chips, "more": len(books) - len(chips), "n_books": len(books)}


def _number(value):
    text = str(value)
    digits = "".join(c for c in text if c.isdigit())
    return (int(digits) if digits else 0, text)


def book_groups(corpus, references):
    books = defaultdict(list)
    for ref in references:
        books[ref["book_id"]].append(ref["no_inbook"])
    groups, seen = [], set()
    for key, label, glossary_id, test in BOOK_GROUPS:
        members = []
        for book_id in sorted(books, key=lambda b: (MAJOR.index(b) if b in MAJOR else 99, b)):
            source = corpus.books[book_id]
            if book_id in seen or not test(source):
                continue
            seen.add(book_id)
            members.append(book_view(corpus, book_id, sorted({n for n in books[book_id] if n is not None}, key=_number)))
        if members:
            groups.append({"key": key, "label": label, "term": glossary_id, "books": members,
                           "numbers": sum(len(m["numbers"]) for m in members)})
    return groups


# ---------------------------------------------------------------- at a glance

def _plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def glance(record, names, story, cases, steps, why=None):
    """Three to five sentences and four tiles, each restating a stored value."""
    s, tiles = [], []
    top = []
    if story:
        first_row = [k for k, n in story["nodes"].items() if n["kind"] in ("narrator", "ucomp", "mubham")
                     and any(t == "P" for _, t in story["teachers"][k])]
        top = sorted(first_row, key=lambda k: (-story["weight"][k], k))
    n_comp = record.get("companions") or 0
    chains, books = record.get("n_chains") or 0, record.get("n_books") or 0
    if record["status"] != "ok":
        return {"sentences": [Markup("The dataset records no chains for this report, so there is nothing to trace.")],
                "tiles": []}
    if n_comp and top:
        named = [names.html(k) + Markup(f' <span class=quiet>({_plural(story["weight"][k], "chain")})</span>')
                 if i == 0 and len(top) > 1 else names.html(k) for i, k in enumerate(top[:4])]
        if len(top) > 4:
            lead = Markup("{n} {companions} narrate it in the dataset, most often {names}.").format(
                n=n_comp, companions=term("companion", "companions"), names=join(named[:3]))
        elif len(top) == 1:
            lead = Markup("One {companion} narrates it: {name}.").format(companion=term("companion", "companion"), name=named[0])
        else:
            lead = Markup("{n} {companions} narrate it: {names}.").format(
                n=len(top), companions=term("companion", "companions"), names=join(named))
        s.append(_linked(lead, "tree"))
    elif record.get("kappa_zero_reason"):
        s.append(Markup("No chain in the dataset reaches the Prophet through a named {companion}: {why}.").format(
            companion=term("companion", "companion"), why=ZERO_REASONS.get(record["kappa_zero_reason"], "")))

    k_all, k_thiqa = record.get("kappa_all") or 0, record.get("kappa_thiqa_up") or 0
    lines = term("independent-lines", "independent lines" if k_all != 1 else "independent line")
    if k_all:
        if k_thiqa == k_all:
            tail = Markup("and all {n} remain with {only}").format(n=k_thiqa, only=term("reliability-filter", "trustworthy narrators only"))
        elif k_thiqa == 0:
            tail = Markup("but none is made up of {only}").format(only=term("reliability-filter", "trustworthy narrators only"))
        else:
            tail = Markup("and {n} with {only}").format(n=k_thiqa, only=term("reliability-filter", "trustworthy narrators only"))
        s.append(_linked(Markup("Its {chains} reach the books along {k} {lines} when everyone is counted, {tail}.").format(
            chains=_plural(chains, "chain"), k=k_all, lines=lines, tail=tail), "tree"))

    cuts = list(record.get("cut_vertices") or [])
    cut_thiqa = list(record.get("cut_vertices_thiqa_up") or [])
    if k_all == 1 and cuts:
        people = [c for c in cuts if not c.startswith("b")]
        s.append(_linked(Markup("Every line passes through {names}: {bottleneck}.").format(
            names=join([_dated(names, story, c) for c in people]),
            bottleneck=term("bottleneck", "the " + ("bottleneck" if len(people) == 1 else "bottlenecks"))), "specialists"))
    elif k_all > 1 and k_thiqa == 1 and cut_thiqa:
        s.append(_linked(Markup("With trustworthy narrators only, every line passes through {names}.").format(
            names=join([names.html(c) for c in cut_thiqa])), "tree"))
    elif k_all > 1:
        s.append(Markup("No single narrator carries every line."))

    nc = vocab.number_class(record.get("number_class"))
    if nc:
        s.append(_linked(Markup("By the number of its lines it is {term} <bdi lang=ar dir=rtl>{ar}</bdi> "
                                "<span class=gloss>({gloss})</span> in the classical {nc}.").format(
            term=term(nc["glossary"], nc["term"]), ar=nc["arabic"], gloss=nc["gloss"],
            nc=term("number-class", "sorting of reports")), "specialists"))

    for case in cases:
        sentence = scoped_sentence(case, record, names)
        if sentence:
            s.append(_linked(sentence, "classical"))
            break

    spread = spread_sentence(record, names, story, steps)
    if spread:
        s.append(_linked(spread, "specialists"))

    grade = grade_sentence(record)
    if grade:
        s.append(_linked(grade, "grade"))
    weak = weak_sentence(why)
    if weak:
        s.append(_linked(weak, "grade"))

    tiles = [
        {"n": n_comp, "label": "companions" if n_comp != 1 else "companion", "term": "companion", "href": "#tree"},
        {"n": k_all, "label": "independent lines, everyone counted" if k_all != 1 else "independent line, everyone counted",
         "term": "independent-lines", "href": "#tree"},
        {"n": k_thiqa, "label": "with trustworthy narrators only", "term": "reliability-filter", "href": "#tree"},
        {"n": chains, "label": f"chains in {_plural(books, 'book')}", "term": "chain", "href": "#chains"},
    ]
    return {"sentences": s, "tiles": tiles}


ZERO_REASONS = {
    "no_chains": "it has no chains",
    "no_companion_end": "every chain stops at a Successor, an unnamed person or an undescribed narrator",
    "broken_only": "every chain that reaches a companion carries a marked break",
    "other": "the chains that reach a companion do not join into an unbroken route",
}


def _linked(sentence, anchor):
    return Markup('{s} <a class=see href=#{a} title="How this is computed">↓</a>').format(s=sentence, a=anchor)


def _dated(names, story, node):
    year = names.died(node)
    return names.html(node) + (Markup(' <span class=quiet>({y})</span>').format(y=year) if year else Markup(""))


def spread_sentence(record, names, story, steps):
    links = list(record.get("common_links") or [])
    if not links:
        return None
    branches = {}
    for step in (steps or {}).get("structure", []):
        if step.get("check") == "Common links":
            branches = step["data"].get("qualifying_branches", {})
    years = dict(zip(record.get("common_links") or [], record.get("cl_death_year") or []))
    raws = dict(zip(record.get("common_links") or [], record.get("cl_death_year_raw") or []))
    head = term("common-link", "common link")
    if len(links) == 1:
        node = links[0]
        died = vocab.died(years.get(node), raws.get(node))
        n = len(branches.get(node, []))
        return Markup("It begins to spread at {who}{died}{students}: the {cl}.").format(
            who=names.html(node), died=Markup(", {d}").format(d=died) if died else Markup(""), cl=head,
            students=Markup(", whose {n} carry it on").format(n=_plural(n, "student")) if n else Markup(""))
    if len(links) <= 3:
        return Markup("It begins to spread at {n} points ({cl}s): {who}.").format(
            n=len(links), cl=head, who=join([names.html(n) for n in links]))
    ordered = sorted(links, key=lambda n: -len(branches.get(n, [])))
    return Markup("It spreads from {n} different narrators ({cl}s), among them {who}.").format(
        n=len(links), cl=head, who=join([names.html(n) for n in ordered[:3]]))


def scoped_sentence(case, record, names):
    """The gold check's scoped result, in words, beside the unscoped numbers (DECISIONS D99)."""
    scope = case.get("scope") or {}
    expect = case.get("expect") or {}
    scoped = case.get("scoped") or {}
    companion = scope.get("companion")
    if not companion or not scoped.get("κ all"):
        return None
    kept = scoped.get("scope chains (kept)", "")
    total, _, kept_n = kept.partition(" (")
    kept_n = kept_n.rstrip(")") or total
    cut = (expect.get("cut_vertices_eq") or {}).get("all") or []
    who = names.html(f"r{companion}")
    deviations = int(total) - int(kept_n) if total.isdigit() and kept_n.isdigit() else 0
    other = (record.get("n_chains") or 0) - (int(total) if total.isdigit() else 0)
    sentence = Markup("The classical account counts only the chains through {who}. Counting those {n} chains")
    sentence = sentence.format(who=who, n=f"{int(total):,}" if total.isdigit() else total)
    if deviations:
        sentence += Markup(" less {d} documented deviations").format(d=deviations)
    k = scoped["κ all"]
    sentence += Markup(", itibar finds {k} {lines}").format(
        k=k, lines=term("independent-lines", "independent line" if k == "1" else "independent lines"))
    if cut:
        sentence += Markup(", through {names} one after another").format(names=join([names.html(c) for c in cut]))
    if k == "1":
        sentence += Markup(": {g} in that account").format(g=term("gharib", "gharīb"))
    sentence += Markup(".")
    if other > 0:
        sentence += Markup(" The other {n} through other companions are outside that account.").format(n=_plural(other, "chain"))
    return sentence


def grade_terms(rule, code):
    """(classical term, Arabic, gloss, glossary id) for a v2 rule and code."""
    entry = vocab.grade_rule(rule) if rule in ("sahih_li_dhatihi", "sahih_li_ghayrihi", "hasan_li_dhatihi",
                                               "hasan_li_ghayrihi", "daif") else None
    if entry is None or (rule == "daif" and code is not None and code > 2):
        entry = vocab.grade_code(code if code is not None else 2)
    return entry["term"], entry["arabic"], entry["gloss"], {"sahih": "sahih", "hasan": "hasan"}.get(entry["family"], "daif")


def grade_html(rule, code):
    name, arabic, gloss, gid = grade_terms(rule, code)
    return Markup('{t} <bdi lang=ar dir=rtl>{a}</bdi> <span class=gloss>({g})</span>').format(
        t=term(gid, name), a=arabic, g=gloss)


def recorded_html(code, label):
    entry = vocab.grade_code(code) if code is not None else None
    if entry is None:
        return Markup('<span class=quiet>none recorded</span>')
    return Markup('{t} <bdi lang=ar dir=rtl>{a}</bdi> <span class=gloss>({g})</span>').format(
        t=entry["term"], a=label or entry["arabic"], g=entry["gloss"])


def weak_sentence(why):
    """The weak point of the best chain, and whether a second chain covers it (from the grade receipt)."""
    if not why:
        return None
    reading = why["readings"][0]
    rule = reading["rule"]
    weak = [n for n in reading["weak"] if n]
    if rule in ("sahih_li_dhatihi", "hasan_li_dhatihi") or not weak and rule not in ("daif", "not_repairable", "fatal"):
        return None
    who = join([reading["names"].html(n) for n in sorted(weak)]) if weak else Markup("a break in the chain")
    if rule in ("hasan_li_ghayrihi", "sahih_li_ghayrihi"):
        return Markup("Its weak point is {who}; a second chain that avoids {them} raises it.").format(
            who=who, them="him" if len(weak) == 1 else "them")
    if rule == "daif":
        return Markup("Its weak point is {who}, and no other chain of the report avoids {them}.").format(
            who=who, them="him" if len(weak) == 1 else "them")
    return Markup("Its weak point is {who}, a weakness the rules do not let another chain repair.").format(who=who)


def grade_sentence(record):
    rule, code = record.get("rule_v2_ibn_hajar"), record.get("code_v2_ibn_hajar")
    if rule is None:
        return None
    other = record.get("rule_v2_ibn_al_salah"), record.get("code_v2_ibn_al_salah")
    best = Markup("By the {rules}, from the narrators' ratings, its best chain is {grade}").format(
        rules=term("classical-rules", "classical rules"), grade=grade_html(rule, code))
    if other != (rule, code) and other[0] is not None:
        best += Markup(" on Ibn Ḥajar's reading and {g} on Ibn al-Ṣalāḥ's").format(g=grade_html(*other))
    recorded = record.get("matn_no_group")
    best += Markup("; {recorded} gives {g}.").format(recorded=term("recorded-grade", "the dataset's recorded grade"),
                                                      g=recorded_html(recorded, record.get("recorded_label")))
    return best


# ---------------------------------------------------------------- why this grade

DEFECT_WORDS = {
    "mursal": 'the chain stops at a Successor and names no companion (<a class="term" href="@root/glossary/#mursal" data-term="mursal">mursal</a>)',
    "break_inqita": 'the dataset marks a <a class="term" href="@root/glossary/#break" data-term="break">break</a> inside the chain (inqiṭāʿ)',
    "break_taliq": 'the compiler leaves out the start of the chain (<a class="term" href="@root/glossary/#break" data-term="break">taʿlīq</a>)',
    "break_irsal_not_at_top": "a link is missing inside the chain",
    "unnamed_narrator": "an unnamed narrator (“a man”) stands in the chain",
    "undescribed_narrator": "a narrator stands in the chain whom the dataset does not describe",
    "no_graded_narrator": "no narrator in the chain carries a rating",
}
RULE_SENTENCE = {
    "sahih_li_dhatihi": "Every narrator is a companion or rated trustworthy or better, and the chain is unbroken, so the classical rules make this chain {grade}.",
    "hasan_li_dhatihi": "The chain is unbroken, but {weak} rated truthful rather than trustworthy, and no other chain of good grade avoids {them}; so the rules make it {grade}.",
    "sahih_li_ghayrihi": "{weak_cap} rated truthful rather than trustworthy, which on its own would make the chain ḥasan; a second chain of good grade that avoids {them} raises it to {grade}.",
    "hasan_li_ghayrihi": "The chain has {a_weakness} — {defects} — and {covered}, so the rules raise it to {grade}.",
    "daif": "The chain has {a_weakness} — {defects} — and {uncovered}, so the rules leave it {grade}.",
    "not_repairable": "{defects_cap}: a weakness the rules do not let another chain repair, so the chain is {grade}.",
    "fatal": "{defects_cap}: the rules never raise such a chain, so it is {grade}.",
}


def defect_words(defect, node, names, people):
    if defect.startswith("level_"):
        level = vocab.level(int(defect.split("_")[1].split("+")[0]))
        who = names.html(node) if node else Markup("a narrator")
        label = (people.get(int(node[1:]), {}).get("rank") if node and node.startswith("r") else None) or level["arabic"]
        text = Markup("{who} is rated {name} <bdi lang=ar dir=rtl>{ar}</bdi>").format(
            who=who, name=level["name"].lower(), ar=label)
        if "+conditional" in defect:
            text += Markup(" on this link, by a {c}").format(c=term("conditional-rating", "conditional rating"))
        return text
    if defect == "conditional":
        return Markup("{who}'s {c} applies on this link").format(
            who=names.html(node) if node else "a narrator", c=term("conditional-rating", "conditional rating"))
    if defect.startswith("mudallis_muanan_tier_"):
        tier = defect.rsplit("_", 1)[1]
        return Markup("{who}, a narrator of {tadlis} (tier {t}), says “from” without stating that he heard it").format(
            who=names.html(node) if node else Markup("a narrator"), tadlis=term("tadlis", "tadlīs"), t=tier)
    words = DEFECT_WORDS.get(defect)
    if words:
        return Markup(words)
    return Markup(escape(defect.replace("_", " ")))


def pair_defects(defects, nodes, corpus):
    """The receipt lists a chain's defects and the positions to cover separately; pair each weak narrator
    with the defect his own record explains (his level, his tier of tadlīs, a conditional ruling), and keep
    the defects of the chain itself (mursal, a break, an unnamed or undescribed narrator) without a name."""
    remaining = list(defects)
    pairs = []
    for node in nodes:
        person = corpus.people.get(int(node[1:]), {}) if node and node.startswith("r") else {}
        level = person.get("rank_no")
        tier = corpus.tiers.get(int(node[1:])) if node and node.startswith("r") else None
        found = None
        for d in remaining:
            if d.startswith("level_") and level and int(d.split("_")[1].split("+")[0]) == level:
                found = d
            elif d.startswith("mudallis_muanan_tier_") and (person.get("has_tadlis") or tier) and (
                    tier is None or str(tier) == d.rsplit("_", 1)[1]):
                found = d
            elif d == "conditional":
                found = d
            if found:
                break
        if found:
            remaining.remove(found)
        pairs.append((found or (f"level_{level}" if level else "undescribed_narrator"), node))
    pairs.extend((d, None) for d in remaining if not d.startswith(("level_", "mudallis_", "conditional")))
    return pairs


def chain_people(chain, people, names, scale):
    """A chain from the Prophet to the book: each person with the rating badge the grade reads."""
    order = list(reversed(chain["people"] or []))
    book_role = set(chain.get("book_role_positions") or [])
    n = len(chain["people"] or [])
    out = []
    for i, entry in enumerate(order):
        pos = n - 1 - i
        rid = entry["rawi"]
        node = f"r{rid}"
        if chain.get("unnamed_companion") and i == 0:
            out.append({"node": f"u{chain['group_id']}", "html": names.html(f"u{chain['group_id']}"), "level": vocab.level(1),
                        "label": None, "role": "companion", "word": None})
            continue
        if rid in scale.placeholders:
            kind = scale.placeholders[rid]["kind"]
            out.append({"node": node, "html": Markup({"irsal": "[companion missing]", "inqita": "[break]",
                                                      "taliq": "[start omitted]", "mubham": "an unnamed narrator"}.get(kind, "[gap]")),
                        "level": None, "label": None, "role": "gap", "word": entry.get("word")})
            continue
        p = people.get(rid, {})
        out.append({"node": node, "html": names.html(node), "level": vocab.level(p.get("rank_no")),
                    "label": p.get("rank"), "role": "book" if pos in book_role else "narrator",
                    "word": entry.get("word")})
    return out


def why_grade(record, chains_by_id, steps, names, corpus):
    """The best chain under each ruleset, its rule in one sentence, the weak point and any second chain."""
    if record["status"] != "ok" or record.get("rule_v2_ibn_hajar") is None:
        return None
    readings = []
    for key, label in (("ibn_hajar", "Ibn Ḥajar"), ("ibn_al_salah", "Ibn al-Ṣalāḥ")):
        rule, code = record[f"rule_v2_{key}"], record[f"code_v2_{key}"]
        sid = record[f"best_sanad_v2_{key}"]
        chain = chains_by_id.get(sid)
        receipt = steps.get(key, [])
        cover = next((s["data"] for s in receipt if s["check"] == "positions to cover"), {})
        blocking = next((s["data"] for s in receipt if s["check"] == "defect"), None)
        witness_step = next((s["data"] for s in receipt if s["check"] == "witnesses"), {})
        weak_nodes = cover.get("nodes", [])
        defect_nodes = pair_defects(cover.get("defects", []), weak_nodes, corpus)
        if blocking:
            defect_nodes = [(blocking["reason"], blocking.get("node"))]
        phrases = [defect_words(d, n, names, corpus.people) for d, n in defect_nodes]
        grade = grade_html(rule, code)
        weak = join([names.html(n) for n in weak_nodes]) if weak_nodes else Markup("a narrator")
        verb = Markup(" is") if len(weak_nodes) <= 1 else Markup(" are")
        template = RULE_SENTENCE.get(rule, "The rules give {grade}.")
        sentence = Markup(template).format(
            grade=grade, weak=weak + verb, weak_cap=weak + verb, them="him" if len(weak_nodes) <= 1 else "them",
            it="it" if len(phrases) <= 1 else "each",
            a_weakness="a light weakness" if len(phrases) <= 1 else "light weaknesses",
            covered="another chain in the report avoids it" if len(phrases) <= 1 else "other chains in the report avoid each of them",
            uncovered="no other chain in the report avoids it" if len(phrases) <= 1 else "no set of other chains in the report avoids them all",
            defects=join(phrases) if phrases else Markup("a light weakness"),
            defects_cap=_cap(join(phrases)) if phrases else Markup("A weakness"))
        witnesses = []
        for w in witness_step.get("witnesses", []) if rule in ("hasan_li_ghayrihi", "sahih_li_ghayrihi") else []:
            wid = w.get("witness_sanad")
            name, gloss = DIVERGENCE.get(w.get("divergence"), (w.get("divergence"), ""))
            witnesses.append({"sanad": wid, "group": w.get("group") if w.get("cross_group") else None,
                              "covers": join([names.html(n) for n in w.get("nodes", [])]),
                              "kind": name, "gloss": gloss, "joins": names.html(w["joins_at"]) if w.get("joins_at") else None,
                              "chain": chain_view(chains_by_id.get(wid), corpus, names) if wid in chains_by_id else None})
        uncovered = witness_step.get("uncovered") if rule in ("daif", "hasan_li_dhatihi") else None
        readings.append({"key": key, "label": label, "rule": rule, "code": code, "grade": grade, "sentence": sentence,
                         "names": names,
                         "sanad": sid, "chain": chain_view(chain, corpus, names) if chain else None,
                         "weak": set(weak_nodes) | ({blocking.get("node")} if blocking and blocking.get("node") else set()),
                         "witnesses": witnesses, "uncovered": uncovered})
    same = (readings[0]["rule"], readings[0]["code"], readings[0]["sanad"]) == (readings[1]["rule"], readings[1]["code"], readings[1]["sanad"])
    return {"readings": readings[:1] if same else readings, "differ": not same,
            "recorded": recorded_html(record.get("matn_no_group"), record.get("recorded_label")),
            "n_chains": record.get("n_chains")}


def _cap(text):
    s = str(text)
    if s and s[0].islower():
        return Markup(s[0].upper() + s[1:])
    return text


def chain_view(chain, corpus, names):
    if not chain:
        return None
    en, title, ar, _ = corpus.book(chain["book_id"])
    return {"sanad": chain["sanad_id"], "book": title or SHORT_BOOK.get(chain["book_id"]) or en or ar, "book_ar": ar,
            "number": chain.get("no_inbook"),
            "people": chain_people(chain, corpus.people, names, corpus.scale)}


# ---------------------------------------------------------------- the story view as page data

def story_payload(story, names, corpus, record, steps, cases=()):
    """Compact JSON for the browser, and the same content as an outline for the page (and screen readers)."""
    if story is None:
        return None, None
    people_info = {}

    def describe(node):
        if node in people_info:
            return people_info[node]
        n = story["nodes"].get(node)
        p = names.person(node)
        entry = {"en": p["en"], "ar": p["ar"]}
        if p["short"] and p["short"] != p["en"]:
            entry["short"] = p["short"]
        if p["page"]:
            entry["rid"] = p["rid"]
        if n is not None and n["kind"] == "book":
            entry["book"] = int(node[1:])
            entry["chains"] = story["weight"].get(node, 0)
        elif node.startswith("r"):
            person = corpus.people.get(int(node[1:]), {})
            level = vocab.level(person.get("rank_no"))
            entry["level"] = level["n"] if level else 0
            if person.get("rank"):
                entry["label"] = person["rank"]
            year, raw = person.get("death_year"), person.get("death_year_raw")
            if raw and str(raw).strip() not in ("", str(year)):
                entry["dr"] = str(raw)
            elif year and year > 0:
                entry["d"] = year
            places = [corpus.place(x) or x for x in corpus.places(int(node[1:]))][:3]
            if places:
                entry["places"] = places
            if person.get("tabaka"):
                entry["gen"] = person["tabaka"]
        elif node.startswith("u"):
            entry.update({"level": 1})
        if n is not None and n["kind"] != "book":
            entry["chains"] = story["weight"].get(node, 0)
            entry["students"] = sum(1 for _, s in story["students"][node] if story["nodes"][s]["kind"] != "book")
            entry["alive"] = story["alive"].get(node, 0)
            if node in story["marked"]:
                roles = []
                if node in (record.get("common_links") or []):
                    roles.append("cl")
                for i, th in enumerate(THRESHOLDS):
                    key = "cut_vertices" if th == "all" else f"cut_vertices_{th}"
                    if node in (record.get(key) or []):
                        roles.append(f"cut{i}")
                entry["roles"] = roles
        if node in scoped:
            entry.setdefault("roles", []).append("scut")
            entry["scope"] = scoped[node]
        people_info[node] = entry
        return entry

    scoped = {}
    for case in cases:   # the classical account's single line (a gold check's scoped cut vertices)
        companion = (case.get("scope") or {}).get("companion")
        for node in ((case.get("expect") or {}).get("cut_vertices_eq") or {}).get("all") or []:
            if companion and node in story["nodes"]:
                scoped[node] = names.short(f"r{companion}")
    item_ids = {}
    items_out = []
    for row in story["rows"]:
        for item_id in row["items"]:
            item_ids[item_id] = len(item_ids)
    for item_id in item_ids:
        item = story["items"][item_id]
        members = item["members"]
        entry = {"k": item["kind"], "n": item["count"], "c": item["chains"], "a": item["alive"]}
        if item["kind"] in ("person", "book"):
            entry["p"] = members[0]
            describe(members[0])
        elif item["kind"] in ("group", "band", "books"):
            entry["m"] = members[:storylib.MEMBERS]
            for m in entry["m"]:
                describe(m)
            entry["label"] = group_label(item, story, names, row_gen(story, item_id))
        items_out.append(entry)
    lines = {}
    texts = {}
    for th in THRESHOLDS:
        routes = story["lines"].get(th, [])
        lines[th] = [[item_ids[i] for i in line["items"] if i in item_ids] for line in routes[:storylib.MAX_LINES]]
        texts[th] = {"k": record.get(f"kappa_{th}") or 0, "total": len(routes),
                     "nodes": [[n for n in line["nodes"] if not n.startswith("b")][:12]
                               + [n for n in line["nodes"] if n.startswith("b")][-1:]
                               for line in routes[:storylib.MAX_LINES]],
                     "text": str(threshold_sentence(th, record, story, names, steps, corpus.people))}
        for line in routes[:storylib.MAX_LINES]:
            for n in line["nodes"]:
                describe(n)
    rows = [{"g": r["gen"], "label": vocab.generation_label(r["gen"]) if not r.get("band") else "Their students, and theirs",
             "band": bool(r.get("band")), "i": [item_ids[i] for i in r["items"]]} for r in story["rows"]]
    links = [[item_ids[a], item_ids[b], w, m] for (a, b), (w, m) in story["links"].items() if a in item_ids and b in item_ids]
    payload = {"rows": rows, "items": items_out, "links": links, "lines": lines, "th": texts, "people": people_info}
    story["people_info"] = people_info
    outline = [{"label": row["label"], "entries": [_outline_item(items_out[i], people_info) for i in row["i"]]} for row in rows]
    return payload, outline


def row_gen(story, item_id):
    for row in story["rows"]:
        if item_id in row["items"]:
            return row["gen"]
    return None


def group_label(item, story, names, gen):
    n = item["count"]
    anchor = item.get("anchor")
    if item["kind"] == "books":
        return f"{n:,} more books"
    if gen == 1:
        return f"{n:,} more companions"
    if anchor in (None, "P") or story["items"].get(anchor, {}).get("kind") != "person":
        if item["kind"] == "band":
            g = item["gens"]
            return f"Other lines: {n:,} narrators, generations {g[0]}–{g[1]}" if g[0] != g[1] else f"Other lines: {n:,} narrators"
        return f"{n:,} more narrators"
    who = names.short(anchor)
    if item["kind"] == "band":
        g = item["gens"]
        span = f", generations {g[0]}–{g[1]}" if g[0] != g[1] else ""
        return f"{who}’s line: {n:,} {'narrator' if n == 1 else 'narrators'}{span}"
    if item.get("direct"):
        return f"{n:,} students of {who}"
    return f"{n:,} narrators in {who}’s line"


def _outline_item(item, people):
    if item["k"] in ("person", "book"):
        p = people.get(item["p"], {})
        return {"en": p.get("short") or p.get("en"), "ar": p.get("ar"), "rid": p.get("rid"), "chains": item["c"]}
    if item["k"] == "prophet":
        return {"en": "The Prophet", "ar": "النبي ﷺ", "chains": item["c"]}
    return {"en": item["label"], "ar": None, "chains": item["c"]}


def threshold_sentence(th, record, story, names, steps, people):
    """What changes at a filter step, in words: the count, the narrators every line then passes through,
    and the companions whose chains no longer reach the books."""
    k = record.get(f"kappa_{th}") or 0
    k_all = record.get("kappa_all") or 0
    phrase = vocab.threshold(th)["phrase"]
    if th == "all":
        if k == 0:
            return Markup("No unbroken line from a companion reaches the books.")
        return Markup("With everyone counted, {k} {lines} share no narrator.").format(
            k=k, lines="independent line" if k == 1 else "independent lines")
    head = Markup("{phrase}, {k} {lines} {verb}").format(
        phrase=_cap(Markup(phrase)), k=k, lines="independent line" if k == 1 else "independent lines",
        verb="remains" if k == 1 else "remain")
    if k == 0:
        head = Markup("{phrase}, no line reaches the books").format(phrase=_cap(Markup(phrase)))
    cut = ((steps or {}).get(th, [{}])[0].get("data", {}).get("cut")) or []
    people_cut = [c for c in cut if c.startswith(("r", "u"))]
    if 0 < k <= 4 and people_cut and k < k_all:
        head += Markup(": every remaining line passes through {names}").format(
            names=join([names.html(c) for c in people_cut]) if k == 1 else Markup(" or ").join([names.html(c) for c in people_cut]))
    head += Markup(".")
    bit = THRESHOLDS.index(th)
    lost = []
    if story:
        for comp, n in story["nodes"].items():
            if n["kind"] not in ("narrator", "ucomp") or not any(t == "P" for _, t in story["teachers"][comp]):
                continue
            if (story["alive"].get(comp, 0) >> 0) & 1 and not reaches(story, comp, bit):
                lost.append(comp)
    if lost:
        lost.sort(key=lambda c: -story["weight"][c])
        example = weakest_on_best(story, lost[0], bit, people)
        tail = Markup(" The chains of {names} no longer reach the books").format(names=join([names.html(c) for c in lost[:4]])
                                                                                + (Markup(f" and {len(lost) - 4} more") if len(lost) > 4 else ""))
        if example:
            node, level = example
            tail += Markup(": each passes through a narrator rated below this step, such as {who} ({lvl})").format(
                who=names.html(node), lvl=level["name"].lower() if level else "unrated")
        head += tail + Markup(".")
    return head


def reaches(story, start, bit):
    """Whether any route from this node to a book survives at the threshold (edge masks)."""
    seen, stack = {start}, [start]
    out = defaultdict(list)
    for (u, v), (chains, mask) in story["edges"].items():
        if mask >> bit & 1:
            out[u].append(v)
    while stack:
        node = stack.pop()
        if story["nodes"][node]["kind"] == "book":
            return True
        for v in out[node]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return False


def weakest_on_best(story, start, bit, people):
    """On the heaviest path down from a companion, the first narrator whose links fail at the threshold."""
    node, seen = start, set()
    while node and node not in seen:
        seen.add(node)
        nxt = [v for _, v in story["students"][node]]
        if not nxt:
            return None
        for _, v in story["students"][node]:
            mask = story["edges"].get((node, v), [None, 0])[1]
            if not mask >> bit & 1 and story["nodes"][v]["kind"] != "book":
                person = people.get(int(v[1:]), {}) if v.startswith("r") else {}
                if not (story["alive"].get(v, 0) >> bit & 1):
                    return v, vocab.level(person.get("rank_no"))
        node = nxt[0]
    return None


def specialist(record, steps, names, cases):
    rows = []
    for th in THRESHOLDS:
        cut_key = "cut_vertices" if th == "all" else f"cut_vertices_{th}"
        rows.append({"key": th, "label": vocab.threshold(th)["label"], "levels": vocab.threshold(th)["levels"],
                     "k": record.get(f"kappa_{th}"), "lower": record.get(f"kappa_lower_{th}"),
                     "cut": [names.html(c) for c in (record.get(cut_key) or [])]})
    nc = vocab.number_class(record.get("number_class"))
    years = zip(record.get("common_links") or [], record.get("cl_death_year") or [], record.get("cl_death_year_raw") or [])
    links = [{"html": names.html(n), "died": vocab.died(y, r)} for n, y, r in years]
    cut_years = zip(record.get("cut_vertices") or [], record.get("cut_death_year") or [], record.get("cut_death_year_raw") or [])
    cuts = [{"html": names.html(n), "died": vocab.died(y, r)} for n, y, r in cut_years]
    scoped = []
    for case in cases:
        companion = (case.get("scope") or {}).get("companion")
        if companion and case.get("scoped", {}).get("κ all"):
            total, _, kept = case["scoped"].get("scope chains (kept)", "").partition(" (")
            scoped.append({"who": names.html(f"r{companion}"), "total": total, "kept": kept.rstrip(")") or total,
                           "k": case["scoped"]["κ all"], "k_thiqa": case["scoped"].get("κ thiqa+")})
            break
    return {"rows": rows, "number_class": nc, "common": links, "cuts": cuts, "scoped": scoped,
            "zero": ZERO_REASONS.get(record.get("kappa_zero_reason"))}


def _plain(value):
    from decimal import Decimal
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if isinstance(value, float) and value != value:
        return None
    return value


def record_json(record):
    """The whole stored record, with its receipts parsed, for download."""
    out = {}
    for key, value in record.items():
        if key in ("receipt", "receipt_v2", "receipt_structure") and isinstance(value, str):
            value = json.loads(value)
        out[key] = _plain(value)
    return out
