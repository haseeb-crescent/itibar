"""The residue (PR 6 §3): every group whose v2 grade (`ibn_hajar`) differs from the source's
recorded grade (meaning_groups.matn_no), tagged by mechanical cause, with receipts.

Tags (not exclusive; all stored per group in out/records.parquet as residue_tags, the primary one
picked by config/structure.yaml: residue.precedence):

  chain_choice          another attested chain of the group yields exactly the source's code under
                        the same ruleset (we grade the group by its best chain; the source may have
                        graded a particular hadith)
  source_severe         source code 3-5 while every narrator of our v2 chain is level <= 9
  conditional_narrator  a weakest-position narrator of our v2 chain has a ruling (lists/conditional.yaml);
                        residue_conditional: resolved (agrees now, disagreed with conditional_off),
                        unobservable (his only rulings are unobservable), unresolved
  tadlis_only           the v2 chain's only defects are a mudallis's 'an
  mursal_only           ... only the mursal
  unnamed_top           ... only an unnamed person at the top read as mursal
  unnamed_mid           ... only an unnamed person below the top
  corroboration         v2 upgraded by a witness and the source did not follow, or v2 found no witness
                        and the source is higher (the witness's divergence class recorded)
  boundary_0_1          both codes in {0, 1}; sub-tag tahrir_vs_ibn_hajar where Ibn Hajar's and
                        Tahrir's verdicts on the weakest narrator differ in the direction that explains it
  level_only            no defect beyond the levels and no corroboration: a plain weakest-link mismatch
  unexplained           none of the above
Direction: stricter (our code higher than the source's) or lenient (lower).

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

TAGS = ("chain_choice", "conditional_narrator", "tadlis_only", "mursal_only", "unnamed_top", "unnamed_mid",
        "corroboration", "source_severe", "boundary_0_1", "level_only", "unexplained")
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


def tag_group(matn_no, verdicts, classes, chains, i, B, corpus, alt_conditional_off=None) -> dict:
    """Residue columns for one group (default ruleset). `verdicts`/`classes` are per chain,
    `i` the index of the group's v2 chain."""
    out = {"residue_disagree": None, "residue_direction": None, "residue_tags": None, "residue_primary": None,
           "residue_conditional": None, "residue_weakest": None, "residue_divergence": None,
           "residue_tahrir_vs_ibn_hajar": None}
    if i is None or matn_no is None or not (0 <= int(matn_no) <= 5):
        return out
    src = int(matn_no)
    v, cc = verdicts[i], classes[i]
    ours = int(v.code)
    nar = corpus.narrators
    r = chains[i].rawis
    # weakest positions of the v2 chain: the defect positions, else the positions of its weakest level
    if cc.defects:
        weak = sorted({p for p, _, _ in cc.defects if 0 <= p < len(r)})
    elif cc.level_at:
        hi = max(cc.level_at.values())
        weak = sorted(p for p, lv in cc.level_at.items() if lv == hi)
    else:
        weak = []
    weak_r = [int(r[p]) for p in weak if not nar.placeholder_role.get(r[p])]
    out["residue_weakest"] = weak_r
    # conditional status (also for agreeing groups: resolved)
    has_rule = [x for x in weak_r if x in corpus.rulings]
    if has_rule:
        obs = [x for x in has_rule if any(ru.observable for ru in corpus.rulings[x])]
        fired = bool(v.rulings)
        if ours == src:
            out["residue_conditional"] = ("resolved" if (fired and alt_conditional_off is not None
                                                         and int(alt_conditional_off) != src) else None)
        else:
            out["residue_conditional"] = "unobservable" if not obs else "unresolved"
    if ours == src:
        out["residue_disagree"] = False
        return out
    out["residue_disagree"] = True
    out["residue_direction"] = "stricter" if ours > src else "lenient"
    tags = []
    if any(int(w.code) == src for j, w in enumerate(verdicts) if j != i):
        tags.append("chain_choice")
    if has_rule:
        tags.append("conditional_narrator")
    reasons = {why for _, _, why in cc.defects}
    top_kind = B.kind.get(cc.nodes[-1]) if cc.nodes else None
    if reasons and all(w.startswith("mudallis_muanan") for w in reasons):
        tags.append("tadlis_only")
    if reasons == {"mursal"}:
        tags.append("unnamed_top" if top_kind == "mubham" else "mursal_only")
    if reasons == {"unnamed_narrator"}:
        tags.append("unnamed_mid")
    if (v.rule in UPGRADE and ours < src) or (v.rule in ("daif", "hasan_li_dhatihi") and v.uncovered and ours > src):
        tags.append("corroboration")
        out["residue_divergence"] = v.divergence
    if src >= 3 and all(lv <= 9 for lv in cc.level_at.values()):
        tags.append("source_severe")
    if ours in (0, 1) and src in (0, 1):
        tags.append("boundary_0_1")
        bv = boundary_verdicts()
        for x in weak_r:
            b = bv.get(x)
            if not b:
                continue
            ih, th = int(b["ibn_hajar_level"]), int(b["tahrir_level"])
            # ours 0 / source 1: Ibn Hajar weaker than Tahrir (the label follows Tahrir); ours 1 /
            # source 0: Ibn Hajar stronger
            if (ours < src and ih > th and ih >= 4) or (ours > src and ih < th and ih <= 3):
                out["residue_tahrir_vs_ibn_hajar"] = x
                break
    if all(w.startswith("level_") and "+" not in w for w in reasons) and "corroboration" not in tags \
            and v.rule not in UPGRADE:
        tags.append("level_only")
    if not tags:
        tags.append("unexplained")
    out["residue_tags"] = tags
    prec = precedence()
    out["residue_primary"] = min(tags, key=lambda t: prec.index(t) if t in prec else len(prec))
    return out


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
