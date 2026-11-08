"""Scoped views of a bundle, for gold tests and exploration.

A classical structural claim is usually about one part of a meaning group:
"through 'Umar the report is a single strand ..." is a claim about the chains
that end in 'Umar, as transmitted by continuous links. A scope selects chains
(never edits them) and re-runs the same analysis:

  companion          keep chains whose last narrator is this rawi id
  drop_incompatible  drop chains containing a link the continuity rule marks
                     incompatible (a generation gap the data itself contradicts)
  drop_breaks        drop chains containing a break marker
"""

from __future__ import annotations

from dataclasses import dataclass

from itibar import config, data, load, pipeline


@dataclass(frozen=True)
class Scope:
    companion: int | None = None
    drop_incompatible: bool = False
    drop_breaks: bool = False


def link_continuity(nar: load.Narrators, teacher: int, student: int, window: set[int]) -> str:
    if nar.placeholder_role.get(teacher) or nar.placeholder_role.get(student):
        return "n/a"
    du, bv = int(nar.death[teacher]), int(nar.birth[student])
    tu, tv = int(nar.tabaka[teacher]), int(nar.tabaka[student])
    if du >= 0 and bv >= 0:
        return "compatible" if du >= bv else "incompatible"
    if tu > 0 and tv > 0:
        return "compatible" if (tv - tu) in window else "incompatible"
    return "unknown"


def chain_has_incompatible(ch: load.Chain, nar: load.Narrators) -> bool:
    window = set(config.load("structure")["continuity"]["tabaka_window"])
    r = ch.rawis
    return any(link_continuity(nar, r[p + 1], r[p], window) == "incompatible" for p in range(len(r) - 1))


def select(chains: list[load.Chain], scope: Scope, corpus: load.Corpus) -> list[load.Chain]:
    nar = corpus.narrators
    out = []
    for c in chains:
        if scope.companion is not None and c.rawis[-1] != scope.companion:
            continue
        if scope.drop_breaks and any(nar.is_gap(x) for x in c.rawis):
            continue
        if scope.drop_incompatible and chain_has_incompatible(c, nar):
            continue
        out.append(c)
    return out


_CACHE: dict = {}


def analyse(group_id: int, scope: Scope = Scope(), con=None, corpus=None) -> dict:
    """Full analysis (record, nodes, edges, chains) of a scoped bundle."""
    con = con or _CACHE.setdefault("con", data.views())
    corpus = corpus or _CACHE.setdefault("corpus", load.corpus(con))
    chains = load.chains_by_group(con, [group_id]).get(group_id, [])
    mg = con.sql(f"SELECT * FROM meaning_groups WHERE id = {int(group_id)}").df()
    mgd = mg.iloc[0].to_dict() if len(mg) else {}
    return pipeline.analyse_group(group_id, select(chains, scope, corpus), corpus, mgd)
