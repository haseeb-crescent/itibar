"""`make bundles`: build B(g) and its structural record for every meaning group."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import pickle

import pyarrow as pa
import pyarrow.parquet as pq

from itibar import bundle as bundle_mod
from itibar import config, corroborate, data, derive, load, matn, paths, siblings, structure
from itibar.bundle import PROPHET

_CORPUS: load.Corpus | None = None
_SIBLINGS: siblings.SiblingIndex | None = None


def _init_worker(sibling_path: str | None = None) -> None:
    global _CORPUS, _SIBLINGS
    _CORPUS = load.corpus()
    if sibling_path:
        with open(sibling_path, "rb") as f:
            _SIBLINGS = pickle.load(f)


def _mode(xs):
    if not xs:
        return None
    c = Counter(xs).most_common()
    top = c[0][1]
    return min(x for x, n in c if n == top)


def kappa_zero_reason(kappa_all: int | None, chains: list) -> str | None:
    """Why kappa_all is zero, by precedence (None when kappa_all > 0):
    no_chains, no_companion_end, broken_only, other. `chains` are ChainInfo rows."""
    if not chains:
        return "no_chains"
    if kappa_all:
        return None
    if not any(c.ends_companion for c in chains):
        return "no_companion_end"
    if not any(c.connected for c in chains):
        return "broken_only"
    return "other"


def witness_rows(gid: int, chains: list[load.Chain], corpus: load.Corpus,
                 params: dict[str, corroborate.Params]) -> list[tuple]:
    """The sibling-index rows of one group: per chain (group, sanad, hadith, chain ordinal,
    light bits, hasan bits, companion rawi id, nodes), bits over `params` in order."""
    if not chains:
        return []
    B = bundle_mod.build(gid, chains, corpus)
    info_by = {c.sanad_id: c for c in B.chains}
    cgr = [derive.grade_chain(c, info_by[c.sanad_id], corpus) for c in chains]
    classes = corroborate.classify_group(B, corpus, chains, cgr, params)
    bits = corroborate.witness_bits(classes, params, list(params))
    out = []
    for c, g, (lb, hb) in zip(chains, cgr, bits):
        if not (lb or hb):
            continue
        info = info_by[c.sanad_id]
        out.append((gid, c.sanad_id, c.hadith_id, g.ordinal, lb, hb, c.rawis[-1] if info.ends_companion else None,
                    [v for v in info.nodes if B.kind[v] in ("narrator", "mubham")]))
    return out


def sibling_index(group_chains: dict[int, list[load.Chain]], gids: list[int], corpus: load.Corpus,
                  params: dict[str, corroborate.Params], con=None) -> siblings.SiblingIndex:
    """A sibling index for groups `gids` (in-process; the pipeline builds the whole
    corpus's in its first pass). `group_chains` must hold the chains of their siblings."""
    con = con or data.views()
    sib = siblings.sibling_groups(con, gids)
    need = sorted({s for g in gids for s in sib.get(g, ())})
    rows = []
    for s in need:
        rows.extend(witness_rows(s, group_chains.get(s, []), corpus, params))
    hids = {r[2] for r in rows} | {c.hadith_id for g in gids for c in group_chains.get(g, [])}
    return siblings.SiblingIndex.build(rows, sib, list(params), matn.Matns(hids))


def analyse_group(gid: int, chains: list[load.Chain], corpus: load.Corpus, mg: dict,
                  sibling_idx: siblings.SiblingIndex | None = None) -> dict:
    """Returns {'record': {...}, 'nodes': [...], 'edges': [...], 'chains': [...]}."""
    _load_side_tables()
    scale, nar = corpus.scale, corpus.narrators
    scfg = config.load("structure")
    rec: dict = {
        "group_id": gid,
        "structure_version": int(scfg["structure"]["version"]),
        "derive_version": int(scfg["derive"]["version"]),
        "nass": mg.get("nass"),
        "is_qudsi": mg.get("is_qudsi"),
        "sahaba_qty": mg.get("sahaba_qty"),
        "repeat_qty": mg.get("repeat_qty"),
        "matn_no_group": mg.get("matn_no"),
        "n_chains": len(chains),
        "n_hadith": len({c.hadith_id for c in chains}),
        "n_books": len({c.book_id for c in chains}),
    }
    if not chains:
        rec.update({"status": "no_chains", "kappa_zero_reason": "no_chains", "n_chains_companion_end": 0,
                    "n_chains_broken": 0, "n_chains_connected": 0, "in_sahihayn": False, "in_sahih_class": False,
                    "sound_distinct_routes": False, "huffaz_chain": False, "n_huffaz_chains": 0})
        return {"record": rec, "nodes": [], "edges": [], "chains": []}
    B = bundle_mod.build(gid, chains, corpus)
    S = structure.analyse(B, corpus)
    on = S.on_path

    # ---- chain grades and comparisons
    info_by = {c.sanad_id: c for c in B.chains}
    cgr = [derive.grade_chain(c, info_by[c.sanad_id], corpus) for c in chains]
    best, fell_back = derive.best_chain(cgr)
    steps = derive.receipt(B, corpus, chains, cgr, best, fell_back, mg.get("matn_no"))
    # ---- derived grade v2 (corroboration), every ruleset and variant
    params = corroborate.rulesets()
    v2 = corroborate.grade_group(B, corpus, chains, cgr, params, siblings=sibling_idx)
    infos = [info_by[c.sanad_id] for c in chains]
    v2_rec: dict = {}
    v2_receipts: dict = {}
    for name, verdicts in v2.items():
        i = corroborate.best(verdicts, chains, cgr, infos)
        v = verdicts[i] if i is not None else None
        if name.startswith("alt_"):
            v2_rec[f"code_v2_{name}"] = v.code if v else None
            continue
        v2_rec.update({
            f"code_v2_{name}": v.code if v else None,
            f"rule_v2_{name}": v.rule if v else None,
            f"best_sanad_v2_{name}": chains[i].sanad_id if v else None,
            f"witness_sanad_v2_{name}": v.witness_sanad if v else None,
            f"witness_attested_v2_{name}": v.witness_attested if v else None,
            f"divergence_v2_{name}": v.divergence if v else None,
            f"witness_route_exists_v2_{name}": v.route_exists if v else None,
            f"witness_cross_group_v2_{name}": v.cross_group if v else None,
            f"witness_group_v2_{name}": v.witness_group if v else None,
            f"n_witnesses_v2_{name}": len(v.witnesses) if v else None,
            f"agree_v2_{name}_vs_group": (v.code == mg.get("matn_no")) if v else None,
        })
        v2_receipts[name] = corroborate.receipt(name, params[name], i, verdicts, chains, cgr, B, corpus)
    default_rs = scfg["derive"]["ruleset"]
    v2_rec["v2_differs_from_v1"] = (v2_rec[f"code_v2_{default_rs}"] != best.code) if best else None
    v2_rec["v2_by_corroboration"] = (v2_rec[f"rule_v2_{default_rs}"] in corroborate.UPGRADE_RULES) if best else None
    # ---- qara'in (flags only)
    qcfg = scfg["qarain"]
    sahihayn = set(qcfg["sahihayn_book_ids"])
    in_sahihayn = any(c.book_id in sahihayn for c in chains)
    in_sahih_class = any(corpus.books.tasnif_no.get(c.book_id) == int(qcfg["sahih_class_tasnif_no"]) for c in chains)
    hmax = int(qcfg["huffaz_max_level"])

    def huffaz(c: load.Chain, g: derive.ChainGrade) -> bool:
        info = info_by[c.sanad_id]
        if not info.connected or not g.graded_positions:
            return False
        for p in g.graded_positions:
            rid = c.rawis[p]
            if B.kind[info.nodes[p]] != "narrator" or nar.is_stub[rid] or not (1 <= int(nar.rank_no[rid]) <= hmax):
                return False
        return True

    huffaz_chains = [c.sanad_id for c, g in zip(chains, cgr) if huffaz(c, g)]

    # ---- companions
    comp_on = {v for v in on if B.kind.get(v) == "narrator" and nar.is_companion[B.rawi[v]]}
    comp_direct = {v for v in B.succ.get(PROPHET, ()) if v in on}
    comp_end = {c.rawis[-1] for c in B.chains if c.ends_companion}
    up_end = {c.rawis[-1] for c in B.chains
              if B.kind[c.nodes[-1]] == "narrator" and c.rawis[-1] in _SAHABI_EXACT}

    # ---- terminus
    def death(v: str):
        if B.kind.get(v) != "narrator":
            return None, None
        rid = B.rawi[v]
        d = int(nar.death[rid])
        return (d if d >= 0 else None), _DEATH_RAW.get(rid)

    hadith_codes = [c.hadith_matn_no for c in {c.hadith_id: c for c in chains}.values()]
    sanad_codes = [c.matn_no for c in chains]
    cont_counts = Counter(v for v in S.edge_continuity.values() if v != "n/a")
    incompat_basis = Counter(S.edge_basis[e] for e, v in S.edge_continuity.items() if v == "incompatible")
    mu_counts = Counter(S.edge_muanan.values())
    lsrc = Counter(S.layer_source[v] for v in on if B.kind.get(v) in structure.NARRATOR_KINDS
                   and v in S.layer_source)

    rec.update({
        "status": "ok",
        "n_nodes": sum(1 for k in B.kind.values() if k != "gap"),
        "n_edges": len(B.edges),
        "n_narrators_on_path": sum(1 for v in on if B.kind.get(v) in structure.NARRATOR_KINDS),
        "width_profile": [{"layer": int(k), "width": int(v)} for k, v in S.width.items()],
        "width_max": max(S.width.values()) if S.width else 0,
        "width_min": min(S.width.values()) if S.width else 0,
        "width_taqrib": [{"layer": int(k), "width": int(v)} for k, v in S.width_taqrib.items()],
        "width_taqrib_max": max(S.width_taqrib.values()) if S.width_taqrib else 0,
        "width_taqrib_min": min(S.width_taqrib.values()) if S.width_taqrib else 0,
        "kappa_all": S.kappa["all"],
        "kappa_above_matruk": S.kappa["above_matruk"],
        "kappa_saduq_up": S.kappa["saduq_up"],
        "kappa_thiqa_up": S.kappa["thiqa_up"],
        "kappa_lower_all": S.kappa_lower["all"],
        "kappa_lower_above_matruk": S.kappa_lower["above_matruk"],
        "kappa_lower_saduq_up": S.kappa_lower["saduq_up"],
        "kappa_lower_thiqa_up": S.kappa_lower["thiqa_up"],
        **{f"kappa_lower_source_{th}": S.kappa_lower_source[th] for th in scale.thresholds},
        **{f"kappa_nocompat_{th}": S.kappa_nocompat[th] for th in scale.thresholds},
        **{f"kappa_nocompat_years_{th}": S.kappa_nocompat_years[th] for th in scale.thresholds},
        "kappa_lower_splice": [k for k, v in S.kappa_lower_splice.items() if v],
        "kappa_zero_reason": kappa_zero_reason(S.kappa["all"], B.chains),
        "width_number": [{"layer": int(k), "width": int(v)} for k, v in S.width_number.items()],
        "min_width": S.min_width,
        "tafarrud_layers": S.tafarrud_layers,
        "number_class": S.number_class,
        "number_class_width": S.number_class_width,
        "gharib_cut_kind": S.gharib_cut_kind,
        "number_class_disagree": (None if S.number_class_width is None and S.number_class_kappa is None else
                                  (S.number_class_width or "").replace("_mutlaq", "").replace("_nisbi", "")
                                  != (S.number_class_kappa or "").replace("_mutlaq", "").replace("_nisbi", "")),
        "in_sahihayn": in_sahihayn,
        "in_sahih_class": in_sahih_class,
        "sound_distinct_routes": S.kappa[qcfg["sound_threshold"]] >= int(qcfg["sound_distinct_routes_min"]),
        "huffaz_chain": bool(huffaz_chains) and S.number_class not in (None, "gharib_mutlaq", "gharib_nisbi"),
        "n_huffaz_chains": len(huffaz_chains),
        "cut_set_all": S.cut_set["all"],
        "cut_set_thiqa_up": S.cut_set["thiqa_up"],
        "disjoint_routes_all": structure.routes_json(S.routes_all),
        "companions": len(comp_direct),
        "companions_on_path": len(comp_on),
        "companions_chain_end": len(comp_end),
        "companions_upstream_def": len(up_end),
        "n_single_strand": len(S.single_strand),
        "single_strand": sorted(S.single_strand),
        "pcl_k2": sorted(S.pcl.get(2, ())),
        "pcl_k3": sorted(S.pcl.get(3, ())),
        "n_pcl_k2": len(S.pcl.get(2, ())),
        "n_pcl_k3": len(S.pcl.get(3, ())),
        "common_links": S.common_links,
        "n_common_links": len(S.common_links),
        "cl_in_cycle": S.cl_in_cycle,
        "cut_vertices": S.cut_vertices,
        "n_cut_vertices": len(S.cut_vertices),
        "cut_vertices_above_matruk": S.cut_vertices_by["above_matruk"],
        "cut_vertices_saduq_up": S.cut_vertices_by["saduq_up"],
        "cut_vertices_thiqa_up": S.cut_vertices_by["thiqa_up"],
        "bypass_paths": S.bypass_paths,
        "bypass_paths_capped": S.bypass_capped,
        "bypass_chains": S.bypass_chains,
        "paths_total": S.paths_total,
        "paths_capped": S.paths_capped,
        "paths_on_acyclic_reduction": S.paths_approx,
        "cl_death_year": [death(v)[0] for v in S.common_links],
        "cl_death_year_raw": [death(v)[1] for v in S.common_links],
        "cut_death_year": [death(v)[0] for v in S.cut_vertices],
        "cut_death_year_raw": [death(v)[1] for v in S.cut_vertices],
        "n_mursal_chains": sum(1 for c in B.chains if not c.ends_companion),
        "n_irsal_marker_chains": sum(1 for c in B.chains if c.gaps.get("irsal")),
        "n_inqita_marker_chains": sum(1 for c in B.chains if c.gaps.get("inqita")),
        "n_taliq_marker_chains": sum(1 for c in B.chains if c.gaps.get("taliq")),
        "n_mubham_chains": sum(1 for c in B.chains if c.has_mubham),
        "n_stub_chains": sum(1 for c in B.chains if c.has_stub),
        "n_chains_companion_end": sum(1 for c in B.chains if c.ends_companion),
        "n_chains_broken": sum(1 for c in B.chains if c.gaps),
        "n_chains_connected": sum(1 for c in B.chains if c.connected),
        "n_edges_compatible": cont_counts.get("compatible", 0),
        "n_edges_incompatible": cont_counts.get("incompatible", 0),
        "n_edges_incompatible_years": incompat_basis.get("years", 0),
        "n_edges_incompatible_tabaka": incompat_basis.get("tabaka", 0),
        "n_edges_unknown": cont_counts.get("unknown", 0),
        "n_edges_muanan_mudallis": mu_counts.get("yes", 0),
        "n_edges_mudallis_unknown_word": mu_counts.get("unknown_word", 0),
        "n_layer_fallback_missing": lsrc.get("fallback_missing", 0),
        "n_layer_fallback_backward": lsrc.get("fallback_backward", 0),
        "n_backward_edges": S.backward_edges,
        "n_self_loops": B.self_loops,
        "has_cycle": S.has_cycle,
        "n_takhrij": len({c.takhrij for c in chains if c.takhrij is not None}),
        # derived grade
        "derived_ordinal": best.ordinal if best else None,
        "derived_level": scale.name_of_ordinal(best.ordinal) if best else None,
        "derived_code": best.code if best else None,
        "derived_best_sanad_id": best.sanad_id if best else None,
        "derived_best_continuous": best.continuous if best else None,
        "derived_fell_back": fell_back,
        "widest_path_ordinal": derive.widest_path_ordinal(B, corpus, S.kappa),
        "receipt": json.dumps(steps, ensure_ascii=False),
        **v2_rec,
        "receipt_v2": corroborate.receipt_json(v2_receipts),
        # recorded grades
        "hadith_matn_no_mode": _mode(hadith_codes),
        "sanad_matn_no_mode": _mode(sanad_codes),
        "hadith_matn_no_counts": json.dumps(dict(sorted(Counter(hadith_codes).items()))),
        "sanad_matn_no_counts": json.dumps(dict(sorted(Counter(sanad_codes).items()))),
        "agree_derived_vs_group": (best.code == mg.get("matn_no")) if best else None,
        "agree_derived_vs_hadith_mode": (best.code == _mode(hadith_codes)) if best else None,
        "n_chains_maxrank_agree_full": sum(g.agree_full for g in cgr),
        "n_chains_maxrank_agree_derived": sum(g.agree_derived for g in cgr),
    })

    # ---- bundle rows
    nodes_rows = []
    css = set(S.cut_vertices)
    cls = set(S.common_links)
    for v, k in B.kind.items():
        nodes_rows.append({
            "group_id": gid, "node": v, "kind": k,
            "rawi_id": B.rawi.get(v), "book_id": B.book.get(v), "author_no": B.author_no.get(v),
            "layer": S.layer.get(v), "layer_source": S.layer_source.get(v),
            "ordinal": structure.ordinal_of(B, corpus, v) if k in structure.NARRATOR_KINDS else None,
            "on_path": v in on, "single_strand": v in S.single_strand,
            "pcl_k2": v in S.pcl.get(2, ()), "pcl_k3": v in S.pcl.get(3, ()),
            "common_link": v in cls, "cut_vertex": v in css, "in_bypass": v in S.bypass_nodes,
            "compiler_role": v in B.exempt, "book_transmitter_role": v in B.transmitter_nodes,
            "narrator_role": v in S.narrator_role,
        })
    edges_rows = []
    for (u, v), e in B.edges.items():
        occ = e.occurrences
        edges_rows.append({
            "group_id": gid, "u": u, "v": v,
            "sanad_ids": [o[0] for o in occ], "book_ids": [o[1] for o in occ],
            "words": [o[2] for o in occ], "words_raw": [o[3] for o in occ],
            "word_classes": [o[4] for o in occ],
            "on_path": u in on and v in on,
            "continuity": S.edge_continuity.get((u, v)),
            "continuity_basis": S.edge_basis.get((u, v)),
            "muanan_mudallis": S.edge_muanan.get((u, v)),
        })
    chain_rows = []
    for ci, (c, g) in enumerate(zip(chains, cgr)):
        info = info_by[c.sanad_id]
        v2c = {}
        for name, verdicts in v2.items():
            vv = verdicts[ci]
            v2c[f"code_v2_{name}"] = vv.code
            if not name.startswith("alt_"):
                v2c[f"rule_v2_{name}"] = vv.rule
                v2c[f"witness_sanad_v2_{name}"] = vv.witness_sanad
                v2c[f"divergence_v2_{name}"] = vv.divergence
                v2c[f"weak_nodes_v2_{name}"] = vv.weak_nodes
                v2c[f"defects_v2_{name}"] = vv.defects
                v2c[f"notes_v2_{name}"] = vv.notes
                v2c[f"witness_group_v2_{name}"] = vv.witness_group
                v2c[f"route_exists_v2_{name}"] = vv.route_exists
        chain_rows.append({
            "sanad_id": c.sanad_id, "group_id": gid, "hadith_id": c.hadith_id, "book_id": c.book_id,
            "length": len(c.rawis), "ends_companion": info.ends_companion,
            "gap_irsal": info.gaps.get("irsal", 0), "gap_inqita": info.gaps.get("inqita", 0),
            "gap_taliq": info.gaps.get("taliq", 0), "has_mubham": info.has_mubham,
            "has_stub": info.has_stub, "connected": info.connected,
            "compiler_at_pos0": info.compiler_at_pos0, "transmitter_at_pos0": info.transmitter_at_pos0,
            "book_role_positions": list(g.book_role_positions), "self_loops": info.self_loops,
            "n_words": len(c.words),
            "chain_ordinal": g.ordinal, "chain_code_raw": g.code_raw, "chain_code": g.code,
            "chain_capped": g.capped, "weakest_positions": g.weakest_positions,
            "weakest_rank_no_full": g.weakest_rank_no_full,
            "weakest_rank_no_derived": g.weakest_rank_no_derived,
            "compiler_rank_no": g.compiler_rank_no,
            "max_rank": g.max_rank, "agree_full": g.agree_full, "agree_derived": g.agree_derived,
            "disagreement_class": g.disagreement_class,
            "matn_no": c.matn_no, "hadith_matn_no": c.hadith_matn_no, "takhrij": c.takhrij,
            **v2c,
        })
    return {"record": rec, "nodes": nodes_rows, "edges": edges_rows, "chains": chain_rows}


_SAHABI_EXACT: set[int] = set()
_SIDE_TRIED = [False]
_DEATH_RAW: dict[int, str] = {}


def _load_side_tables() -> None:
    global _SAHABI_EXACT, _DEATH_RAW
    if _SAHABI_EXACT or _SIDE_TRIED[0]:
        return
    _SIDE_TRIED[0] = True
    if not (paths.PARQUET_DIR / "rawis.parquet").exists():
        return
    con = data.views()
    _SAHABI_EXACT = {r[0] for r in con.sql("SELECT id FROM rawis WHERE rank = 'صحابي'").fetchall()}
    _DEATH_RAW = {r[0]: r[1] for r in con.sql(
        "SELECT id, death_year_raw FROM rawis WHERE death_year_raw IS NOT NULL").fetchall()}


def _work(batch: list[tuple[int, list[load.Chain], dict]]) -> list[dict]:
    _load_side_tables()
    return [analyse_group(gid, chs, _CORPUS, mg, _SIBLINGS) for gid, chs, mg in batch]


def _flags_work(batch: list[tuple[int, list[load.Chain], dict]]) -> list[tuple]:
    params = corroborate.rulesets()
    out = []
    for gid, chs, _ in batch:
        out.extend(witness_rows(gid, chs, _CORPUS, params))
    return out


def _batches(items, max_chains: int = 4000):
    cur, n = [], 0
    for it in items:
        cur.append(it)
        n += len(it[1]) + 5
        if n >= max_chains:
            yield cur
            cur, n = [], 0
    if cur:
        yield cur


def run(group_ids: list[int] | None = None, workers: int | None = None, out_dir=None,
        quiet: bool = False, records_only: bool = False) -> dict:
    t0 = time.time()
    out_dir = out_dir or paths.OUT_DIR
    con = data.views()
    mgs = load.meaning_groups(con)
    if group_ids is not None:
        mgs = mgs[mgs["id"].isin(group_ids)]
    by_group = load.chains_by_group(con, list(mgs["id"]) if group_ids is not None else None)
    mg_rows = {int(r.id): r._asdict() for r in mgs.itertuples(index=False)}
    t_load = time.time() - t0
    items = [(gid, by_group.get(gid, []), mg_rows[gid]) for gid in sorted(mg_rows)]
    # big groups first so the pool finishes evenly
    items.sort(key=lambda it: -len(it[1]))
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    results: list[dict] = []
    done = 0
    params = corroborate.rulesets()
    sib_path = None
    t_sib = 0.0
    if corroborate.uses_siblings(params):
        # first pass: which chains can lend a witness, under every parameter set
        ts = time.time()
        matn.ensure(con)
        sib_groups = siblings.sibling_groups(con, list(mg_rows) if group_ids is not None else None)
        lend = {s for v in sib_groups.values() for s in v}
        if group_ids is not None:            # a sample: its siblings' chains are needed too
            extra = sorted(lend - set(by_group))
            if extra:
                by_group.update(load.chains_by_group(con, extra))
        flag_items = [(g, by_group.get(g, []), None) for g in sorted(lend) if by_group.get(g)]
        flag_items.sort(key=lambda it: -len(it[1]))
        rows: list[tuple] = []
        if workers == 1:
            _init_worker()
            for b in _batches(flag_items):
                rows.extend(_flags_work(b))
        else:
            with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as ex:
                for res in ex.map(_flags_work, list(_batches(flag_items))):
                    rows.extend(res)
        hids = {r[2] for r in rows} | {c.hadith_id for g in sib_groups for c in by_group.get(g, [])}
        idx = siblings.SiblingIndex.build(rows, sib_groups, list(params), matn.Matns(hids))
        sib_path = out_dir / ".siblings.pkl"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(sib_path, "wb") as f:
            pickle.dump(idx, f, protocol=pickle.HIGHEST_PROTOCOL)
        t_sib = time.time() - ts
        if not quiet:
            print(f"  sibling index: {len(rows):,} lending chains in {len(lend):,} groups, {t_sib:.1f}s",
                  file=sys.stderr)
    if workers == 1:
        _init_worker(str(sib_path) if sib_path else None)
        for b in _batches(items):
            results.extend(_work(b))
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                                 initargs=(str(sib_path) if sib_path else None,)) as ex:
            last = 0.0
            for res in ex.map(_work, list(_batches(items))):
                results.extend(res)
                done += len(res)
                if not quiet and (time.time() - last > 5 or done == len(items)):
                    last = time.time()
                    print(f"  groups {done:,}/{len(items):,}  {time.time() - t0:6.1f}s", file=sys.stderr)
    write(results, out_dir, bundles=not records_only)
    if sib_path is not None:
        sib_path.unlink(missing_ok=True)
    return {"groups": len(results), "load_s": round(t_load, 1), "siblings_s": round(t_sib, 1),
            "total_s": round(time.time() - t0, 1)}


_WIDTH = pa.list_(pa.struct([("layer", pa.int16()), ("width", pa.int32())]))
RECORD_SCHEMA_OVERRIDES = {
    "width_profile": _WIDTH,
    "width_taqrib": _WIDTH,
    "width_number": _WIDTH,
    "bypass_paths": pa.decimal128(38, 0),
    "paths_total": pa.decimal128(38, 0),
}


def write(results: list[dict], out_dir, bundles: bool = True) -> None:
    recs = sorted((r["record"] for r in results), key=lambda r: r["group_id"])
    for r in recs:
        for k in ("bypass_paths", "paths_total"):
            if k in r and r[k] is not None:
                import decimal
                r[k] = decimal.Decimal(r[k])
    cols = sorted({k for r in recs for k in r}, key=lambda k: (_ORDER.index(k) if k in _ORDER else 999, k))
    arrays = {}
    for k in cols:
        vals = [r.get(k) for r in recs]
        typ = RECORD_SCHEMA_OVERRIDES.get(k)
        arrays[k] = pa.array(vals, type=typ) if typ is not None else pa.array(vals)
    out_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(arrays), out_dir / "records.parquet", compression="zstd")
    chains = [c for r in results for c in r["chains"]]
    chains.sort(key=lambda c: c["sanad_id"])
    pq.write_table(pa.Table.from_pylist(chains), out_dir / "chains.parquet", compression="zstd")
    if not bundles:
        return
    bdir = out_dir / "bundles"
    if bdir.exists():
        shutil.rmtree(bdir)
    for part in ("nodes", "edges"):
        rows = [x for r in results for x in r[part]]
        if not rows:
            continue
        for x in rows:
            x["bucket"] = x["group_id"] // 1000
        t = pa.Table.from_pylist(rows)
        pq.write_to_dataset(t, root_path=str(bdir / part), partition_cols=["bucket"],
                            existing_data_behavior="delete_matching")


_ORDER = [
    "group_id", "structure_version", "derive_version", "status", "nass", "is_qudsi", "n_hadith", "n_chains", "n_books", "n_nodes",
    "n_edges", "n_narrators_on_path", "width_profile", "width_max", "width_min",
    "width_taqrib", "width_taqrib_max", "width_taqrib_min",
    "kappa_all", "kappa_above_matruk", "kappa_saduq_up", "kappa_thiqa_up", "kappa_zero_reason",
    "kappa_lower_all", "kappa_lower_above_matruk", "kappa_lower_saduq_up", "kappa_lower_thiqa_up",
    "kappa_lower_source_all", "kappa_lower_source_above_matruk", "kappa_lower_source_saduq_up",
    "kappa_lower_source_thiqa_up",
    "kappa_nocompat_all", "kappa_nocompat_above_matruk", "kappa_nocompat_saduq_up", "kappa_nocompat_thiqa_up",
    "kappa_nocompat_years_all", "kappa_nocompat_years_above_matruk", "kappa_nocompat_years_saduq_up",
    "kappa_nocompat_years_thiqa_up", "kappa_lower_splice",
    "width_number", "min_width", "tafarrud_layers", "number_class", "number_class_width", "gharib_cut_kind",
    "number_class_disagree",
    "in_sahihayn", "in_sahih_class", "sound_distinct_routes", "huffaz_chain", "n_huffaz_chains",
    "cut_set_all", "cut_set_thiqa_up", "disjoint_routes_all",
    "companions", "companions_on_path", "companions_chain_end", "companions_upstream_def", "sahaba_qty", "repeat_qty",
    "n_single_strand", "single_strand", "n_pcl_k2", "pcl_k2", "n_pcl_k3", "pcl_k3",
    "n_common_links", "common_links", "cl_in_cycle", "n_cut_vertices", "cut_vertices",
    "cut_vertices_above_matruk", "cut_vertices_saduq_up", "cut_vertices_thiqa_up",
    "bypass_paths", "bypass_paths_capped", "bypass_chains", "paths_total", "paths_capped",
    "paths_on_acyclic_reduction", "cl_death_year", "cl_death_year_raw", "cut_death_year", "cut_death_year_raw",
    "n_mursal_chains", "n_irsal_marker_chains", "n_inqita_marker_chains", "n_taliq_marker_chains",
    "n_mubham_chains", "n_stub_chains", "n_chains_companion_end", "n_chains_broken", "n_chains_connected",
    "n_edges_compatible", "n_edges_incompatible", "n_edges_incompatible_years", "n_edges_incompatible_tabaka",
    "n_edges_unknown", "n_edges_muanan_mudallis",
    "n_edges_mudallis_unknown_word", "n_layer_fallback_missing", "n_layer_fallback_backward",
    "n_backward_edges", "n_self_loops", "has_cycle", "n_takhrij",
    "derived_ordinal", "derived_level", "derived_code", "derived_best_sanad_id", "derived_best_continuous",
    "derived_fell_back", "widest_path_ordinal", "receipt",
    *[f"{k}_v2_{rs}" for rs in ("ibn_hajar", "ibn_al_salah") for k in (
        "code", "rule", "best_sanad", "witness_sanad", "witness_attested", "divergence", "witness_route_exists",
        "witness_cross_group", "witness_group", "n_witnesses")],
    "agree_v2_ibn_hajar_vs_group", "agree_v2_ibn_al_salah_vs_group",
    "code_v2_alt_weakest", "code_v2_alt_all_light_defects", "code_v2_alt_shahid_group", "code_v2_alt_tasrih_corpus",
    "code_v2_alt_mudallis_union", "code_v2_alt_unknown_none", "code_v2_alt_mursal_shafii", "code_v2_alt_no_level_8",
    "code_v2_alt_witness_not_below",
    "v2_differs_from_v1", "v2_by_corroboration", "receipt_v2",
    "matn_no_group", "hadith_matn_no_mode", "sanad_matn_no_mode", "hadith_matn_no_counts",
    "sanad_matn_no_counts", "agree_derived_vs_group", "agree_derived_vs_hadith_mode",
    "n_chains_maxrank_agree_full", "n_chains_maxrank_agree_derived",
]


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, nargs="*")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--records-only", action="store_true", help="skip the bundle partitions (stage runs)")
    a = ap.parse_args()
    print(run(a.groups, a.workers, records_only=a.records_only))


if __name__ == "__main__":
    main()
