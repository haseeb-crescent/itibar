"""`itibar show <group_id>` prints a record as a readable card;
`itibar render <group_id>` writes an SVG of the bundle via Graphviz;
`itibar pool --groups/--topic/--entry` builds and prints a pooled bundle."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

from itibar import data, grades, paths

BAR = "█"
THRESHOLD_LABELS = {"all": "everyone", "above_matruk": "above matruk", "saduq_up": "saduq+", "thiqa_up": "thiqa+"}
ZERO_REASONS = {
    "no_chains": "the group has no chains",
    "no_companion_end": "no chain ends in a companion (each ends at an irsal marker, an unnamed person, "
                        "a non-companion or a stub)",
    "broken_only": "companion-ending chains exist, but every one contains a break marker",
    "other": "continuous chains exist yet no PROPHET → book route survived (see reports/audit.md §9)",
}


def _record(gid: int) -> dict:
    if not paths.records_path().exists():
        sys.exit(f"{paths.records_path()} not found: run `make bundles` first")
    t = ds.dataset(paths.records_path()).to_table(filter=ds.field("group_id") == gid).to_pylist()
    if not t:
        sys.exit(f"no record for group {gid}")
    return t[0]


def _bundle(gid: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    part = gid // 1000
    out = []
    for name in ("nodes", "edges"):
        d = paths.bundles_dir() / name
        t = ds.dataset(d, partitioning="hive").to_table(
            filter=(ds.field("bucket") == part) & (ds.field("group_id") == gid)).to_pandas()
        out.append(t)
    return out[0], out[1]


class Names:
    def __init__(self, con):
        self.r = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
        self.full = dict(con.sql("SELECT id, name FROM rawis").fetchall())
        self.b = dict(con.sql("SELECT id, name FROM books").fetchall())
        self.a = dict(con.sql("SELECT DISTINCT author_no, author_name FROM books").fetchall())

    def __call__(self, node: str) -> str:
        if node == "P":
            return "PROPHET ﷺ"
        if node.startswith("r"):
            return self.r.get(int(node[1:]), node)
        if node.startswith("b"):
            return self.b.get(int(node[1:]), node)
        if node.startswith("c"):
            return f"[{self.a.get(int(node[1:]), node)}]"
        if node.startswith("m"):
            return "مبهم"
        if node.startswith("h"):
            return f"homonym cluster {node[1:]}"
        return node


def show(gid: int, file=sys.stdout) -> None:
    rec = _record(gid)
    con = data.views()
    nm = Names(con)
    scale = grades.load()
    p = lambda *a: print(*a, file=file)  # noqa: E731
    hk = scale.hukm_codes
    p("═" * 78)
    p(f" group {gid}   ·   {rec.get('status')}")
    p("═" * 78)
    p(f" {rec.get('nass') or ''}")
    p("")
    if rec.get("status") != "ok":
        p(f" recorded grade (meaning_groups.matn_no): {rec.get('matn_no_group')} {hk.get(rec.get('matn_no_group'), '')}")
        p(f" κ = 0 — reason: {rec.get('kappa_zero_reason')}: {ZERO_REASONS.get(rec.get('kappa_zero_reason'), '')}")
        p(" no chains: nothing to compute")
        return
    p(f" chains {rec['n_chains']:,} · hadith {rec['n_hadith']:,} · books {rec['n_books']:,} · "
      f"narrators on path {rec['n_narrators_on_path']:,}")
    p(f" companions from the Prophet {rec['companions']} (source sahaba_qty {rec['sahaba_qty']}; "
      f"chain-end companions {rec['companions_chain_end']})")
    p("")
    p(" κ (vertex-disjoint routes PROPHET → books)")
    p(f"   {'':<12}" + "".join(f"{lab:>14}" for lab in THRESHOLD_LABELS.values()))
    p(f"   {'κ':<12}" + "".join(f"{rec[f'kappa_{th}']:>14}" for th in THRESHOLD_LABELS))
    p(f"   {'κ_nocompat':<12}" + "".join(f"{rec[f'kappa_nocompat_{th}']:>14}" for th in THRESHOLD_LABELS))
    p(f"   {'κ_lower':<12}" + "".join(f"{rec[f'kappa_lower_{th}']:>14}" for th in THRESHOLD_LABELS))
    p(f"   {'attained by':<12}" + "".join(f"{rec[f'kappa_lower_source_{th}']:>14}" for th in THRESHOLD_LABELS))
    p("   κ_lower: the minimum of κ over three stated hypotheses (same-name clusters merged, unmerged,")
    p("   continuity-incompatible links removed); a lower bound under those hypotheses, not a guarantee.")
    if rec["kappa_all"] == 0:
        reason = rec.get("kappa_zero_reason")
        p(f"   κ = 0 — reason: {reason}: {ZERO_REASONS.get(reason, '')}")
        p("   (κ = 0 means no unbroken companion-ending route in this data, not no support.)")
    p(f"   one minimum cut (everyone): {', '.join(nm(x) for x in rec['cut_set_all'])}")
    if rec["cut_vertices"]:
        p("   cut vertices (on every route): " + " → ".join(
            f"{nm(v)} (d. {d if d is not None else '?'}{'' if not raw or str(raw) == str(d) else ' / ' + str(raw)})"
            for v, d, raw in zip(rec["cut_vertices"], rec["cut_death_year"], rec["cut_death_year_raw"])))
    if rec["cut_vertices_thiqa_up"] and rec["cut_vertices_thiqa_up"] != rec["cut_vertices"]:
        p("   cut vertices at thiqa+: " + " → ".join(nm(v) for v in rec["cut_vertices_thiqa_up"]))
    p("")
    cls = rec["common_links"]
    p(f" common link(s) {len(cls)}: " + ", ".join(
        f"{nm(v)} (d. {d if d is not None else '?'})" for v, d in list(zip(cls, rec["cl_death_year"]))[:8])
      + (" …" if len(cls) > 8 else ""))
    p(f" partial common links: k=2 {rec['n_pcl_k2']}, k=3 {rec['n_pcl_k3']} · single-strand nodes {rec['n_single_strand']}"
      f" · bypass paths {rec['bypass_paths']} (chains {rec['bypass_chains']}) of {rec['paths_total']}"
      + (" [acyclic reduction]" if rec["paths_on_acyclic_reduction"] else ""))
    p("")
    p(" width by layer (tabaka)")
    wp = rec["width_profile"]
    mx = max((w["width"] for w in wp), default=1)
    for w in wp[:16]:
        note = "   (13+: later compilers and quoters)" if w["layer"] == 13 else ""
        p(f"   {w['layer']:>3} {w['width']:>5} {BAR * max(1, round(40 * w['width'] / mx))}{note}")
    if len(wp) > 16:
        p(f"   … {len(wp) - 16} more layers")
    p(f"   Taqrib layers 1–12: max width {rec['width_taqrib_max']}, min {rec['width_taqrib_min']}")
    p("")
    p(f" number class (narrowest Taqrib layer 1–12, compiler roles excluded): {rec.get('number_class')} "
      f"(min width {rec.get('min_width')}, tafarrud layers {list(rec.get('tafarrud_layers') or [])}); "
      f"by κ_all: {rec.get('number_class_kappa')}"
      + ("   ← the two readings differ" if rec.get("number_class_disagree") else ""))
    p(f" qarāʾin (flags only; knowledge yield is not computed): in the Ṣaḥīḥayn {rec.get('in_sahihayn')}, "
      f"in a ṣaḥīḥ-class book {rec.get('in_sahih_class')}, ≥3 distinct ṣadūq+ routes {rec.get('sound_distinct_routes')}, "
      f"chain of ḥuffāẓ (not gharīb) {rec.get('huffaz_chain')}")
    p("")
    p(f" chains: mursal {rec['n_mursal_chains']} (irsal marker {rec['n_irsal_marker_chains']}), "
      f"inqita' {rec['n_inqita_marker_chains']}, ta'liq {rec['n_taliq_marker_chains']}, "
      f"unnamed narrator {rec['n_mubham_chains']}, undescribed narrator {rec['n_stub_chains']}, "
      f"companion-ending {rec['n_chains_companion_end']}, with a break marker {rec['n_chains_broken']}, "
      f"continuous {rec['n_chains_connected']}")
    p(f" links: compatible {rec['n_edges_compatible']}, incompatible {rec['n_edges_incompatible']} "
      f"(by years {rec['n_edges_incompatible_years']}, by tabaka {rec['n_edges_incompatible_tabaka']}), "
      f"unknown {rec['n_edges_unknown']}; mu'an'an by a mudallis {rec['n_edges_muanan_mudallis']} "
      f"(+{rec['n_edges_mudallis_unknown_word']} mudallis links with no recovered word)")
    p("")
    p(f" derived grade v1: ordinal {rec['derived_ordinal']} — Taqrib level {rec['derived_level']} — "
      f"code {rec['derived_code']} ({hk.get(rec['derived_code'], '')}, on the source's scale)")
    p(f" recorded: group {rec['matn_no_group']} ({hk.get(rec['matn_no_group'], '')}), modal hadith "
      f"{rec['hadith_matn_no_mode']} ({hk.get(rec['hadith_matn_no_mode'], '')}) → "
      f"{'agree' if rec['agree_derived_vs_group'] else 'differ'} / "
      f"{'agree' if rec['agree_derived_vs_hadith_mode'] else 'differ'}")
    p(f" chains whose weakest link equals sanads.max_rank: {rec['n_chains_maxrank_agree_full']}/{rec['n_chains']} "
      f"(compiler excluded: {rec['n_chains_maxrank_agree_derived']})")
    for rs in ("ibn_hajar", "ibn_al_salah"):
        code = rec.get(f"code_v2_{rs}")
        wit = rec.get(f"witness_sanad_v2_{rs}")
        p(f" derived grade v2 ({rs}): {rec.get(f'rule_v2_{rs}')} → code {code} ({hk.get(code, '')}) · chain "
          f"{rec.get(f'best_sanad_v2_{rs}')}"
          + (f" · witness {'sanad ' + str(wit) if wit is not None else 'a spliced route'} ({rec.get(f'divergence_v2_{rs}')})"
             if rec.get(f"divergence_v2_{rs}") else ""))
    alts = {k[len('code_v2_alt_'):]: v for k, v in rec.items() if k.startswith("code_v2_alt_")}
    if alts:
        p("   variants on ibn_hajar: " + ", ".join(f"{k} {v}" for k, v in alts.items()))
    p("")
    p(" receipt")
    for i, step in enumerate(json.loads(rec["receipt"]), 1):
        p(f"  {i}. {step['check']}: {step['result']}")
        p(f"     rule: {step['rule']}")
        if step["check"] == "chain grade":
            for n in step["data"]["narrators"][::-1]:
                rid = n["rawi_id"]
                mark = "  ◀ weakest" if n["pos"] in step["data"]["weakest_positions"] else ""
                p(f"       pos {n['pos']:>2}  {nm('r' + str(rid))}  [rank_no {n['rank_no']}, ordinal {n['ordinal']}"
                  f"{'' if n['graded'] else ', not graded'}]{mark}")
    if rec.get("receipt_v2"):
        p("")
        p(" receipt v2 (ibn_hajar)")
        for i, step in enumerate(json.loads(rec["receipt_v2"]).get("ibn_hajar", []), 1):
            p(f"  {i}. {step['check']}: {step['result']}")
            p(f"     rule: {step['rule']}")
    sid = rec["derived_best_sanad_id"]
    txt = con.sql(f"SELECT h.nass FROM sanads s JOIN hadiths h ON h.id = s.hadith_id WHERE s.id = {int(sid)}").fetchall()
    if txt:
        p("")
        p(" best chain, as written:")
        p("  " + txt[0][0][:900] + (" …" if len(txt[0][0]) > 900 else ""))
    p("═" * 78)


def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(gid: int, include_off_path: bool = False, max_nodes: int = 1500) -> str:
    rec = _record(gid)
    nodes, edges = _bundle(gid)
    con = data.views()
    nm = Names(con)
    if not include_off_path:
        nodes = nodes[nodes["on_path"]]
        edges = edges[edges["on_path"]]
    nodes = nodes[nodes["kind"] != "gap"] if not include_off_path else nodes
    if len(nodes) > max_nodes:
        sys.exit(f"bundle has {len(nodes)} nodes (> {max_nodes}); pass --max-nodes to render anyway")
    keep = set(nodes["node"])
    edges = edges[edges["u"].isin(keep) & edges["v"].isin(keep)]
    cut = set(rec["cut_vertices"] or [])
    cl = set(rec["common_links"] or [])
    L = ["digraph bundle {",
         '  graph [rankdir=TB, splines=true, nodesep=0.15, ranksep=0.5, fontname="Noto Naskh Arabic,Geeza Pro,sans-serif",'
         f' label="group {gid}: κ all {rec["kappa_all"]} · thiqa+ {rec["kappa_thiqa_up"]} · '
         f'{rec["n_chains"]} chains · {rec["n_books"]} books", labelloc=t];',
         '  node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="#555555", '
         'fontname="Noto Naskh Arabic,Geeza Pro,sans-serif", fontsize=10];',
         '  edge [color="#88888899", arrowsize=0.5];']
    layer_of: dict[int, list[str]] = {}
    max_layer = int(nodes["layer"].dropna().max()) if nodes["layer"].notna().any() else 1
    for n in nodes.itertuples(index=False):
        k, node = n.kind, n.node
        lab = nm(node)
        attrs = {}
        if k == "prophet":
            attrs = {"shape": "doubleoctagon", "fillcolor": "#f3e6c4"}
            layer = 0
        elif k == "book":
            attrs = {"shape": "note", "fillcolor": "#e8eef7"}
            layer = max_layer + 2
        elif k == "compiler":
            attrs = {"shape": "box", "style": "filled", "fillcolor": "#eef2f5", "fontsize": "9"}
            layer = max_layer + 1
        else:
            layer = int(n.layer) if n.layer == n.layer and n.layer is not None else 0
            if n.single_strand:
                attrs.update({"style": "rounded,filled,dashed", "fillcolor": "#f2f2f2", "color": "#999999"})
            if n.pcl_k2:
                attrs.update({"fillcolor": "#e9f5e9"})
            if node in cl:
                attrs.update({"penwidth": "2.5", "color": "#2f7d32"})
            if node in cut:
                attrs.update({"peripheries": "2", "color": "#b3261e", "penwidth": "2", "fillcolor": "#fdecea"})
            if k == "gap":
                attrs.update({"shape": "point", "width": "0.08"})
                lab = ""
            if k == "narrator" and n.layer is not None and n.layer == n.layer:
                lab = (lab, int(n.layer))
        layer_of.setdefault(layer, []).append(node)
        a = ", ".join(f'{k2}="{v2}"' for k2, v2 in attrs.items())
        text = (f"{_dot_escape(lab[0])}\\n{lab[1]}" if isinstance(lab, tuple) else _dot_escape(lab))
        L.append(f'  "{node}" [label="{text}"{", " + a if a else ""}];')
    for layer, ns in sorted(layer_of.items()):
        rank = "min" if layer == 0 else ("max" if layer == max_layer + 2 else "same")
        L.append("  { rank=" + rank + "; " + " ".join(f'"{x}";' for x in ns) + " }")
    for e in edges.itertuples(index=False):
        n = len(e.sanad_ids)
        w = min(6.0, 0.6 + 0.5 * (n ** 0.5))
        style = ""
        if e.continuity == "incompatible":
            style = ', color="#b3261e", style=dashed'
        L.append(f'  "{e.u}" -> "{e.v}" [penwidth={w:.2f}{style}];')
    L.append("}")
    return "\n".join(L)


def render(gid: int, out: Path | None = None, include_off_path: bool = False, max_nodes: int = 1500) -> Path:
    dot = shutil.which("dot")
    if not dot:
        sys.exit("Graphviz `dot` not found on PATH")
    out = out or (paths.FIGURES_DIR / "bundles" / f"group_{gid}.svg")
    out.parent.mkdir(parents=True, exist_ok=True)
    src = to_dot(gid, include_off_path, max_nodes)
    r = subprocess.run([dot, "-Tsvg", "-o", str(out)], input=src.encode("utf-8"), capture_output=True)
    if r.returncode != 0:
        sys.exit(r.stderr.decode())
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="itibar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show", help="print a group's structural record as a card")
    s.add_argument("group_id", type=int)
    r = sub.add_parser("render", help="write an SVG of a group's bundle (Graphviz)")
    r.add_argument("group_id", type=int)
    r.add_argument("-o", "--out", type=Path)
    r.add_argument("--all", action="store_true", help="include off-path nodes and break markers")
    r.add_argument("--max-nodes", type=int, default=1500)
    pl = sub.add_parser("pool", help="pooled bundle over several groups, a topic subtree or a list entry")
    g = pl.add_mutually_exclusive_group(required=True)
    g.add_argument("--groups", type=int, nargs="+")
    g.add_argument("--topic", type=int, help="topics.id: every group under the node")
    g.add_argument("--entry", help="list entry, e.g. kattani:2 (groups from lists/confirmed.csv)")
    pl.add_argument("--save", type=Path, help="write <stem>.json and <stem>.md")
    a = ap.parse_args(argv)
    if a.cmd == "show":
        show(a.group_id)
    elif a.cmd == "render":
        print(render(a.group_id, a.out, a.all, a.max_nodes))
    elif a.cmd == "pool":
        from itibar import pool
        con = data.views()
        if a.groups:
            gids, label = a.groups, "groups " + " ".join(map(str, a.groups[:8])) + (" …" if len(a.groups) > 8 else "")
        elif a.topic is not None:
            gids, label = pool.topic_groups(con, a.topic), f"topic {a.topic}: {pool.topic_name(con, a.topic)}"
        else:
            gids, label = pool.entry_groups(a.entry), f"list entry {a.entry}"
        res = pool.analyse(gids, con, label=label)
        print(pool.card(res))
        if a.save:
            pool.save(res, a.save)


if __name__ == "__main__":
    main()
