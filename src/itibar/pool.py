"""Pooled bundles: one bundle built from every chain of a set of meaning groups
(the same builder as B(g)), with kappa at every threshold, the width profile,
the number class and the companions.

A pool mixes distinct reports, so pooled kappa measures tawatur in meaning at
the granularity of the pool (a topic node, a list entry), not of a wording.

  itibar pool --groups 28 1795 ...
  itibar pool --topic 12345
  itibar pool --entry kattani:1
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb

from itibar import bundle as bundle_mod
from itibar import data, load, paths, structure
from itibar.bundle import PROPHET

POOL_ID = -1


def topic_groups(con, topic_id: int) -> list[int]:
    rows = con.sql(
        f"""SELECT DISTINCT t2.group_id FROM topics t1
            JOIN topics t2 ON t2.lft BETWEEN t1.lft AND t1.rgt AND t2.tree_id = t1.tree_id
            WHERE t1.id = {int(topic_id)} AND t2.group_id IS NOT NULL ORDER BY 1""").fetchall()
    return [int(r[0]) for r in rows]


def topic_name(con, topic_id: int) -> str | None:
    r = con.sql(f"SELECT name FROM topics WHERE id = {int(topic_id)}").fetchall()
    return r[0][0] if r else None


def entry_groups(entry: str, confirmed: Path | None = None) -> list[int]:
    """Groups confirmed for a list entry ('kattani:12'), from lists/confirmed.csv."""
    confirmed = confirmed or (paths.ROOT / "lists" / "confirmed.csv")
    lst, idx = entry.split(":", 1)
    out = []
    if confirmed.exists():
        with open(confirmed, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["list"] == lst and r["entry"] == idx and r.get("group_id"):
                    out.append(int(r["group_id"]))
    return sorted(set(out))


def analyse(group_ids: list[int], con=None, corpus: load.Corpus | None = None, label: str | None = None,
            by_group: dict | None = None) -> dict:
    con = con or data.views()
    corpus = corpus or load.corpus(con)
    gids = sorted({int(g) for g in group_ids})
    by_group = by_group if by_group is not None else load.chains_by_group(con, gids)
    chains = [c for g in gids for c in by_group.get(g, [])]
    out: dict = {"label": label, "groups": gids, "n_groups": len(gids), "n_chains": len(chains),
                 "n_groups_with_chains": sum(1 for g in gids if by_group.get(g))}
    if not chains:
        out["status"] = "no_chains"
        return out
    B = bundle_mod.build(POOL_ID, chains, corpus)
    S = structure.analyse(B, corpus)
    nar = corpus.narrators
    on = S.on_path
    comp_direct = sorted(v for v in B.succ.get(PROPHET, ()) if v in on)
    comp_end = sorted({c.nodes[-1] for c in B.chains if c.ends_companion})
    out.update({
        "status": "ok",
        "n_books": len({c.book_id for c in chains}),
        **{f"kappa_{th}": S.kappa[th] for th in corpus.scale.thresholds},
        **{f"kappa_lower_{th}": S.kappa_lower[th] for th in corpus.scale.thresholds},
        "width_profile": {int(k): int(v) for k, v in S.width.items()},
        "width_number": {int(k): int(v) for k, v in S.width_number.items()},
        "min_width": S.min_width,
        "tafarrud_layers": S.tafarrud_layers,
        "number_class": S.number_class,
        "number_class_kappa": S.number_class_kappa,
        "companions": len(comp_direct),
        "companions_chain_end": len(comp_end),
        "companion_ids": [int(v[1:]) for v in comp_direct],
        "cut_vertices": S.cut_vertices,
        "common_links": S.common_links,
        "n_chains_connected": sum(1 for c in B.chains if c.connected),
        "tawatur_n": structure.tawatur_n(),
    })
    out["companion_names"] = None
    try:
        names = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
        out["companion_names"] = [names.get(i) for i in out["companion_ids"]]
        out["cut_vertex_names"] = [names.get(int(v[1:])) if v.startswith("r") else v for v in S.cut_vertices]
        out["common_link_names"] = [names.get(int(v[1:])) if v.startswith("r") else v for v in S.common_links]
    except (AttributeError, duckdb.Error):  # names are decoration (a synthetic test passes no connection)
        pass
    del nar
    return out


def card(res: dict) -> str:
    L = [f"# Pool: {res.get('label') or 'groups'}", ""]
    L.append(f"- groups: {res['n_groups']} ({res['n_groups_with_chains']} with chains); chains: {res['n_chains']:,}")
    if res.get("status") != "ok":
        L.append("- no chains: nothing to compute")
        return "\n".join(L) + "\n"
    L.append(f"- books: {res['n_books']}; continuous chains: {res['n_chains_connected']:,}")
    L.append(f"- companions narrating from the Prophet on an unbroken route: {res['companions']} "
             f"(chain-end companions {res['companions_chain_end']})")
    L.append("")
    L.append("| threshold | κ | κ_lower |")
    L.append("|---|---|---|")
    for th in ("all", "above_matruk", "saduq_up", "thiqa_up"):
        L.append(f"| {th} | {res[f'kappa_{th}']} | {res[f'kappa_lower_{th}']} |")
    L.append("")
    L.append(f"- number class (width, Taqrib layers 1–12): **{res['number_class']}** "
             f"(min width {res['min_width']}, tafarrud layers {res['tafarrud_layers']}); "
             f"by κ_all: **{res['number_class_kappa']}** (tawatur_n = {res['tawatur_n']})")
    L.append("- width by layer (1–12, compiler roles excluded): "
             + ", ".join(f"{k}: {v}" for k, v in res["width_number"].items()))
    if res.get("cut_vertex_names"):
        L.append("- cut vertices: " + " → ".join(str(x) for x in res["cut_vertex_names"]))
    if res.get("common_link_names"):
        L.append(f"- common links ({len(res['common_link_names'])}): "
                 + ", ".join(str(x) for x in res["common_link_names"][:20]))
    if res.get("companion_names"):
        L.append("- companions: " + ", ".join(str(x) for x in res["companion_names"]))
    L.append("")
    L.append("A pool mixes distinct reports: pooled κ measures tawātur in meaning at the granularity of the pool,")
    L.append("not of a wording.")
    return "\n".join(L) + "\n"


def save(res: dict, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    stem.with_suffix(".md").write_text(card(res), encoding="utf-8")
