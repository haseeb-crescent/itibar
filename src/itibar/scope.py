"""Scoped views of a bundle, for gold tests and exploration.

A classical structural claim is usually about one part of a meaning group:
"through 'Umar the report is a single strand ..." is a claim about the chains
that end in 'Umar, as transmitted by continuous links. A scope selects chains
(never edits them) and re-runs the same analysis:

  companion          keep chains whose last narrator is this rawi id
  drop_incompatible  drop chains containing a link the continuity rule marks
                     incompatible (a generation gap the data itself contradicts).
                     The nocompat graph of kappa_lower drops the same links as
                     edges instead of dropping whole chains.
  drop_breaks        drop chains containing a break marker
"""

from __future__ import annotations

from dataclasses import dataclass

from itibar import data, load, pipeline, structure


@dataclass(frozen=True)
class Scope:
    companion: int | None = None
    drop_incompatible: bool = False
    drop_breaks: bool = False


def link_continuity(nar: load.Narrators, teacher: int, student: int) -> str:
    """Verdict of the shared continuity rule (structure.link_continuity)."""
    return structure.link_continuity(nar, teacher, student)[0]


def chain_has_incompatible(ch: load.Chain, nar: load.Narrators) -> bool:
    rule = structure.ContinuityRule.load()
    r = ch.rawis
    return any(structure.link_continuity(nar, r[p + 1], r[p], rule)[0] == "incompatible"
               for p in range(len(r) - 1))


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
