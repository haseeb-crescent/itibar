"""Derived grade v1: a mechanical reading of the classical narrator verdicts.

Chain grade  = minimum narrator ordinal over the chain, excluding the positions in a
               book role: the book's compiler at pos 0, or its book transmitter at
               pos 0 and the compiler at pos 1 (break markers are not narrators).
Chain code   = that ordinal's code in the source's matn_no scale; a chain that
               does not reach PROPHET through a companion, or contains a break
               marker, cannot be placed above `discontinuity_cap_code`.
Best chain   = maximum chain grade (the widest attested route), preferring
               continuous companion-ending chains.
Group grade  = best chain's grade and code.
Receipt      = ordered list of {check, rule, data, result}.
No corroboration upgrades in v1 (config hook in structure.yaml: derive.corroboration).
"""

from __future__ import annotations

from dataclasses import dataclass

from itibar import config
from itibar.bundle import Bundle, ChainInfo
from itibar.load import Chain, Corpus


@dataclass
class ChainGrade:
    sanad_id: int
    graded_positions: list[int]
    ordinal: int                      # min ordinal over graded positions (0 = unknown narrator)
    weakest_positions: list[int]
    code_raw: int
    code: int
    capped: bool
    continuous: bool
    weakest_rank_no_full: int         # max rank_no over the whole stored chain (source's reading)
    weakest_rank_no_derived: int      # max rank_no over graded positions (same rows, compiler excluded)
    max_rank: int | None
    agree_full: bool
    agree_derived: bool
    disagreement_class: str | None
    compiler_rank_no: int | None
    book_role_positions: tuple[int, ...] = ()


def grade_chain(ch: Chain, info: ChainInfo, corpus: Corpus) -> ChainGrade:
    cfg = config.load("structure")["derive"]
    nar, scale = corpus.narrators, corpus.scale
    r = ch.rawis
    excl = set(info.role_positions) if bool(cfg["exclude_compiler"]) else set()
    graded = [p for p in range(len(r)) if p not in excl and not nar.is_gap(r[p])]
    ords = [int(nar.ordinal[r[p]]) for p in graded]
    ordinal = min(ords) if ords else 0
    weakest = [p for p, o in zip(graded, ords) if o == ordinal]
    code_raw = scale.code_of_ordinal(ordinal)
    continuous = info.connected
    cap = cfg.get("discontinuity_cap_code")
    code, capped = code_raw, False
    if cap is not None and not continuous and code_raw < cap:
        code, capped = int(cap), True
    rn = [int(nar.rank_no[x]) for x in r]
    full = max(rn)
    der_pos = [p for p in range(len(r)) if p not in excl]
    derived_rn = max(rn[p] for p in der_pos) if der_pos else full
    agree_full = ch.max_rank is not None and full == ch.max_rank
    agree_derived = ch.max_rank is not None and derived_rn == ch.max_rank
    role_rn = max((rn[p] for p in excl), default=None)
    cls = None
    if not agree_derived:
        if ch.max_rank is None:
            cls = "max_rank_missing"
        elif excl == {0} and info.compiler_at_pos0 and rn[0] == ch.max_rank and rn[0] > derived_rn:
            cls = "compiler_strictly_weakest"
        elif excl and role_rn == ch.max_rank and role_rn > derived_rn:
            cls = "book_role_strictly_weakest"
        elif not agree_full:
            cls = "source_disagrees_with_its_own_rows"
        else:
            cls = "unclassified"
    return ChainGrade(
        sanad_id=ch.sanad_id, graded_positions=graded, ordinal=ordinal, weakest_positions=weakest,
        code_raw=code_raw, code=code, capped=capped, continuous=continuous,
        weakest_rank_no_full=full, weakest_rank_no_derived=derived_rn, max_rank=ch.max_rank,
        agree_full=agree_full, agree_derived=agree_derived, disagreement_class=cls,
        compiler_rank_no=(rn[info.compiler_pos] if info.compiler_pos is not None and info.compiler_pos in excl
                          else (rn[0] if 0 in excl else None)),
        book_role_positions=tuple(sorted(excl)),
    )


def best_chain(grades: list[ChainGrade]) -> tuple[ChainGrade | None, bool]:
    """(best, fell_back) — maximise ordinal among continuous chains, else all."""
    cfg = config.load("structure")["derive"]
    if not grades:
        return None, False
    pool = [g for g in grades if g.continuous] if cfg["prefer_continuous"] else list(grades)
    fell_back = False
    if not pool:
        pool, fell_back = list(grades), True
    best = min(pool, key=lambda g: (-g.ordinal, g.code, g.sanad_id))
    return best, fell_back


def widest_path_ordinal(B: Bundle, corpus: Corpus, kappa: dict[str, int]) -> int | None:
    """Largest threshold ordinal with a PROPHET->book route in the graph (routes
    may splice chains; reported beside the attested best chain)."""
    best = None
    for name, theta in corpus.scale.thresholds.items():
        if kappa.get(name, 0) > 0:
            best = theta if best is None else max(best, theta)
    return best


def receipt(B: Bundle, corpus: Corpus, chains: list[Chain], cgrades: list[ChainGrade],
            best: ChainGrade | None, fell_back: bool, mg_matn_no: int | None) -> list[dict]:
    scale, nar = corpus.scale, corpus.narrators
    cfg = config.load("structure")["derive"]
    steps: list[dict] = []
    n = len(cgrades)
    nc = sum(1 for g in cgrades if g.continuous)
    steps.append({
        "check": "chains read",
        "rule": "every sanad of every hadith with this group_id",
        "data": {"chains": n, "continuous_companion_end": nc,
                 "not_reaching_companion": sum(1 for c in B.chains if not c.ends_companion),
                 "with_break_marker": sum(1 for c in B.chains if c.gaps)},
        "result": f"{n} chains, {nc} continuous",
    })
    if best is None:
        steps.append({"check": "best chain", "rule": "none available", "data": {}, "result": "no grade"})
        return steps
    ch = next(c for c in chains if c.sanad_id == best.sanad_id)
    info = next(c for c in B.chains if c.sanad_id == best.sanad_id)
    narrators = []
    for p in range(len(ch.rawis)):
        rid = ch.rawis[p]
        narrators.append({
            "pos": p, "rawi_id": rid, "rank_no": int(nar.rank_no[rid]),
            "ordinal": int(nar.ordinal[rid]) if not nar.is_gap(rid) else None,
            "graded": p in best.graded_positions,
        })
    steps.append({
        "check": "best chain selection",
        "rule": ("maximum chain grade among continuous companion-ending chains"
                 + ("; none qualified, fell back to all chains" if fell_back else "")),
        "data": {"sanad_id": best.sanad_id, "book_id": ch.book_id, "hadith_id": ch.hadith_id,
                 "candidates": nc if not fell_back else n},
        "result": f"sanad {best.sanad_id}",
    })
    steps.append({
        "check": "chain grade",
        "rule": ("minimum narrator ordinal over the chain"
                 + (", compiler at pos 0 excluded" if info.compiler_at_pos0 and cfg["exclude_compiler"] else "")
                 + (", book transmitter at pos 0 excluded" if info.transmitter_at_pos0 and cfg["exclude_compiler"] else "")
                 + (", compiler at pos 1 excluded" if info.compiler_pos == 1 and cfg["exclude_compiler"] else "")
                 + "; ordinal = 13 - rawis.rank_no; undescribed/unnamed = 0; break markers are not narrators"),
        "data": {"narrators": narrators, "weakest_positions": best.weakest_positions},
        "result": f"ordinal {best.ordinal} ({scale.name_of_ordinal(best.ordinal)})",
    })
    steps.append({
        "check": "code",
        "rule": "config/grades.yaml levels[rank_no].code (source matn_no scale)",
        "data": {"ordinal": best.ordinal},
        "result": f"code {best.code_raw}",
    })
    if best.capped:
        steps.append({
            "check": "continuity cap",
            "rule": f"chain not continuous to a companion -> code >= {cfg['discontinuity_cap_code']}",
            "data": {"ends_companion": info.ends_companion, "break_markers": info.gaps},
            "result": f"code {best.code}",
        })
    steps.append({
        "check": "corroboration",
        "rule": "not applied in v1 (bucket 2)",
        "data": {"enabled": bool(cfg["corroboration"]["enabled"])},
        "result": f"code {best.code}",
    })
    steps.append({
        "check": "recorded grade",
        "rule": "compare, never overwrite",
        "data": {"meaning_groups.matn_no": mg_matn_no},
        "result": "agree" if mg_matn_no == best.code else "differ",
    })
    return steps
