"""The residue (PR 6 §3, rebased in PR 7 §3): every group whose v2 grade (`ibn_hajar`) differs from the
source's recorded grade (meaning_groups.matn_no), decomposed into three layers that add up, and tagged by
mechanical cause within its layer, with receipts.

The decoding (src/itibar/source_template.py, reports/source_grade.md) shows the recorded grade is a template read
off the narrator table, chain by chain (the template code), and the group's grade is its best chain's, with the
editors' exceptions. With R = the recorded best chain code of the group (min sanads.matn_no) and ST = the template
code of the group on itibar's chains (`source_template`, the v1 ruleset), the difference splits exactly:

    recorded - v2  =  (recorded - R)        aggregation layer: what the editors did beyond the template
                   +  (R - ST)              chain layer: what differs in reading the narrator table
                   +  (ST - v2)             substance layer: what the classical ladder changes

The substance tags say which defects v2 counts on the compared chain that the template does not (PR 6's
`tadlis_only` and `mursal_only` became `tadlis` and `mursal`: a chain carrying both now shows both). Every
disagreeing group is attributed to the first layer that is non-zero (aggregation, chain, substance), so the
three counts sum to the disagreement count; `residue_layers` lists every non-zero layer. Tags (stored in
residue_tags, the primary one by config/structure.yaml: residue.precedence):

  aggregation   group_below_best_chain   the recorded group grade is worse than its best chain (the editors)
                group_above_best_chain   ... better than its best chain
  chain         template_vs_record       the recorded best chain code is not the template's on itibar's chains
                                         (the chains' residual classes are in reports/source_grade.md)
  substance     code_map                 v2 under the source's code map (levels 4-6 -> 1) equals the template: the
                                         difference is the map's convention on levels 5-6, not the ladder
                book_role                the template's code is set by the compiler (or book transmitter) at pos 0,
                                         whom the template grades and itibar does not
                break_rule               the template's two-break rule (code >= 3) against v2's reading of breaks
                conditional_narrator     a weakest-position narrator of the v2 chain has a ruling
                                         (residue_conditional: resolved / unobservable / unresolved)
                unnamed_top              the compared chain carries an unnamed person at the top read as mursal
                                         (the template does not grade the unnamed person)
                unnamed_mid              ... an unnamed person below the top, not named elsewhere (likewise)
                undescribed              ... an undescribed narrator (v2: unrepairable; the template: «مجهول الحال»)
                tadlis                   ... a mudallis's uncovered 'an (the template has no tadlis rule)
                mursal                   ... a mursal not due to an unnamed person
                corroboration            v2 upgraded by a witness where the template never corroborates, or v2 found
                                         no witness for a defect the template does not count (divergence recorded)
                boundary_0_1             both codes in {0, 1}; sub-tag tahrir_vs_ibn_hajar
                level_only               no defect beyond the levels and no corroboration
                unexplained              none of the above
The compared chain is v2's chain when v2 is lower than the template, else the template's best chain as v2 grades
it. Direction: stricter (our code higher than the source's) or lenient (lower). PR 6's `chain_choice` (another chain
of the group yields the source's code) and `source_severe` (source 3-5 over narrators <= 9) are retired: the first
read a per-chain code that is attached to the wrong chain in multi-chain hadith (reports/source_grade.md §3), and
both are what the aggregation layer now measures directly.

  python -m itibar.residue fetch    Taqrib and Tahrir verdicts of the 100 narrators most often weakest
                                    in boundary_0_1 groups -> lists/source/boundary_verdicts.jsonl
  python -m itibar.residue report   reports/residue.md, figures/fig6_residue.{png,svg,csv}
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

from itibar import config, lists, paths

LAYERS = ("aggregation", "chain", "substance")
TAGS = ("group_below_best_chain", "group_above_best_chain", "template_vs_record", "code_map", "book_role",
        "break_rule", "conditional_narrator", "unnamed_top", "unnamed_mid", "undescribed", "tadlis", "mursal",
        "corroboration", "boundary_0_1", "level_only", "unexplained")
SUBSTANCE_TAGS = TAGS[3:]
BOUNDARY_SRC = lists.SOURCE_DIR / "boundary_verdicts.jsonl"
UPGRADE = ("hasan_li_ghayrihi", "sahih_li_ghayrihi")


def cfg() -> dict:
    return config.load("structure").get("residue") or {}


def precedence() -> list[str]:
    return list(cfg().get("precedence") or TAGS)


@lru_cache(maxsize=1)
def boundary_verdicts(path: str | None = None) -> dict[int, dict]:
    """rawi id -> {ibn_hajar_level, tahrir_level, direction} for the narrators whose Taqrib and
    Tahrir verdicts were read (lists/source/boundary_verdicts.jsonl)."""
    p = Path(path) if path else BOUNDARY_SRC
    if not p.exists():
        return {}
    out = {}
    for line in open(p, encoding="utf-8"):
        r = json.loads(line)
        if r.get("ibn_hajar_level") and r.get("tahrir_level"):
            out[int(r["rawi_id"])] = r
    return out


def _weak(cc, r, nar) -> list[int]:
    if cc.defects:
        weak = sorted({p for p, _, _ in cc.defects if 0 <= p < len(r)})
    elif cc.level_at:
        hi = max(cc.level_at.values())
        weak = sorted(p for p, lv in cc.level_at.items() if lv == hi)
    else:
        weak = []
    return [int(r[p]) for p in weak if not nar.placeholder_role.get(r[p])]


def tag_group(matn_no, verdicts, classes, chains, i, B, corpus, alt_conditional_off=None, rec=None, st=None,
              cgr=None) -> dict:
    """Residue columns for one group (default ruleset). `verdicts`/`classes` are per chain, `i` the index of
    the group's v2 chain; `rec` the group's record so far (code_source_template, matn_no_best_chain,
    code_v2_<rs>_source), `st` the template codes per chain (source_template.chain_code), `cgr` the v1 grades."""
    out = {"residue_disagree": None, "residue_direction": None, "residue_tags": None, "residue_primary": None,
           "residue_layer": None, "residue_layers": None, "residue_d_aggregation": None, "residue_d_chain": None,
           "residue_d_substance": None, "residue_compared_sanad": None,
           "residue_conditional": None, "residue_weakest": None, "residue_divergence": None,
           "residue_tahrir_vs_ibn_hajar": None}
    if i is None or matn_no is None or not (0 <= int(matn_no) <= 5):
        return out
    rec = rec or {}
    src = int(matn_no)
    v, cc = verdicts[i], classes[i]
    ours = int(v.code)
    nar = corpus.narrators
    r = chains[i].rawis
    weak_r = _weak(cc, r, nar)
    out["residue_weakest"] = weak_r
    has_rule = [x for x in weak_r if x in corpus.rulings]
    if has_rule:
        obs = [x for x in has_rule if any(ru.observable for ru in corpus.rulings[x])]
        fired = bool(v.rulings)
        if ours == src:
            out["residue_conditional"] = ("resolved" if (fired and alt_conditional_off is not None
                                                         and int(alt_conditional_off) != src) else None)
        else:
            out["residue_conditional"] = "unobservable" if not obs else "unresolved"
    R, ST = rec.get("matn_no_best_chain"), rec.get("code_source_template")
    if R is not None and ST is not None:
        out["residue_d_aggregation"] = src - int(R)
        out["residue_d_chain"] = int(R) - int(ST)
        out["residue_d_substance"] = int(ST) - ours
    if ours == src:
        out["residue_disagree"] = False
        return out
    out["residue_disagree"] = True
    out["residue_direction"] = "stricter" if ours > src else "lenient"
    layers = [k for k, dv in zip(LAYERS, (out["residue_d_aggregation"], out["residue_d_chain"],
                                          out["residue_d_substance"])) if dv]
    out["residue_layers"] = layers
    out["residue_layer"] = layers[0] if layers else "substance"
    tags: list[str] = []
    if out["residue_d_aggregation"]:
        tags.append("group_below_best_chain" if out["residue_d_aggregation"] > 0 else "group_above_best_chain")
    if out["residue_d_chain"]:
        tags.append("template_vs_record")
    if out["residue_d_substance"]:
        tags += _substance_tags(ours, int(ST), verdicts, classes, chains, i, B, corpus, rec, st, cgr, has_rule, out)
    if not tags:
        tags.append("unexplained")
    out["residue_tags"] = tags
    prec = precedence()
    by_layer = {"aggregation": ("group_below_best_chain", "group_above_best_chain"), "chain": ("template_vs_record",),
                "substance": SUBSTANCE_TAGS}
    own = [t for t in tags if t in by_layer[out["residue_layer"]]] or tags
    out["residue_primary"] = min(own, key=lambda t: prec.index(t) if t in prec else len(prec))
    return out


def _substance_tags(ours, st_code, verdicts, classes, chains, i, B, corpus, rec, st, cgr, has_rule, out) -> list[str]:
    from itibar import source_template
    rs = cfg().get("ruleset", "ibn_hajar")
    tags = []
    # the compared chain: v2's chain when v2 is lower than the template, else the template's best chain
    j = i
    if ours > st_code and st is not None:
        sid = rec.get("best_sanad_source_template")
        j = next((k for k, c in enumerate(chains) if c.sanad_id == sid), i)
    out["residue_compared_sanad"] = chains[j].sanad_id
    vj, cj = verdicts[j], classes[j]
    tj = st[j] if st is not None else None
    if rec.get(f"code_v2_{rs}_source") is not None and int(rec[f"code_v2_{rs}_source"]) == st_code:
        tags.append("code_map")
    if tj is not None and cgr is not None:
        roles = set(cgr[j].book_role_positions)
        if roles and set(tj.weakest_positions) <= roles:
            rest = source_template.chain_code(chains[j].rawis, corpus.narrators.rank_no, corpus.narrators.is_stub,
                                              corpus.scale, skip=roles)
            if rest.code != tj.code:
                tags.append("book_role")
        if tj.n_breaks >= 2 and tj.code > max(tj.level_code, 2):
            tags.append("break_rule")
    if has_rule:
        tags.append("conditional_narrator")
    reasons = {why for _, _, why in cj.defects}
    top_kind = B.kind.get(cj.nodes[-1]) if cj.nodes else None
    if "mursal" in reasons and top_kind == "mubham":
        tags.append("unnamed_top")
    if "unnamed_narrator" in reasons:
        tags.append("unnamed_mid")
    if "undescribed_narrator" in reasons:
        tags.append("undescribed")
    if any(w.startswith("mudallis_muanan") for w in reasons):
        tags.append("tadlis")
    if "mursal" in reasons and top_kind != "mubham":
        tags.append("mursal")
    vi = verdicts[i]
    if (vi.rule in UPGRADE and ours < st_code) or (vj.rule in ("daif", "hasan_li_dhatihi") and vj.uncovered
                                                    and ours > st_code):
        tags.append("corroboration")
        out["residue_divergence"] = vi.divergence if vi.rule in UPGRADE else None
    if ours in (0, 1) and st_code in (0, 1):
        tags.append("boundary_0_1")
        bv = boundary_verdicts()
        for x in out["residue_weakest"] or []:
            b = bv.get(x)
            if not b:
                continue
            ih, th = int(b["ibn_hajar_level"]), int(b["tahrir_level"])
            if (ours < st_code and ih > th and ih >= 4) or (ours > st_code and ih < th and ih <= 3):
                out["residue_tahrir_vs_ibn_hajar"] = x
                break
    if reasons and all(w.startswith("level_") and "+" not in w for w in reasons) and "corroboration" not in tags \
            and vi.rule not in UPGRADE:
        tags.append("level_only")
    if not tags:
        tags.append("unexplained")
    return tags


# ---------------------------------------------------------------- report

def report() -> Path:
    from itibar import residue_report
    return residue_report.write()


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "fetch":
        from itibar import residue_report
        print(residue_report.fetch_boundary())
    elif cmd == "report":
        print(report())


if __name__ == "__main__":
    main()
