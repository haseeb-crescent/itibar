"""Gold-set evaluation (`make gold`): classically documented structures checked
against the computed bundles. See tests/gold/gold.yaml for the entries."""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml

from itibar import data, load, paths, pipeline


@dataclass
class Result:
    entry_id: str
    group_id: int
    failures: list[str] = field(default_factory=list)
    observed: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failures


def entries() -> list[dict]:
    """Gold entries; `scope_from: <id>` copies another entry's scope and documented
    deviations (so a new mechanism can be checked on an existing scope unchanged)."""
    with open(paths.GOLD_FILE, encoding="utf-8") as f:
        es = yaml.safe_load(f)["entries"]
    by_id = {e["id"]: e for e in es}
    for e in es:
        src = e.get("scope_from")
        if src:
            base = by_id[src]
            for k in ("scope", "deviation_key", "known_deviations"):
                if k in base and k not in e:
                    e[k] = base[k]
    return es


def gold_group_ids() -> list[int]:
    return sorted({int(e["group_id"]) for e in entries()})


def _rid(node: str) -> int:
    return int(node[1:])


def evaluate(entry: dict, con=None, corpus: load.Corpus | None = None) -> Result:
    con = con or data.views()
    corpus = corpus or load.corpus(con)
    gid = int(entry["group_id"])
    res = Result(entry["id"], gid)
    scope = entry.get("scope") or {}
    chains = load.chains_by_group(con, [gid]).get(gid, [])
    if scope.get("companion") is not None:
        chains = [c for c in chains if c.rawis[-1] == int(scope["companion"])]
    if scope.get("companions") is not None:
        keep_c = {int(x) for x in scope["companions"]}
        chains = [c for c in chains if c.rawis[-1] in keep_c]
    # deviations: exactly the in-scope chains that miss a deviation_key narrator
    listed: set[int] = set()
    for d in entry.get("known_deviations") or []:
        listed.update(int(x) for x in d["sanad_ids"])
    key = [_rid(k) for k in entry.get("deviation_key") or []]
    if key:
        actual = {c.sanad_id for c in chains if any(k not in c.rawis for k in key)}
        if actual != listed:
            extra, missing = sorted(actual - listed), sorted(listed - actual)
            res.failures.append(f"known_deviations out of date: undocumented {extra[:20]}, no longer deviating {missing[:20]}")
    elif listed:
        res.failures.append("known_deviations given without deviation_key")
    kept = [c for c in chains if c.sanad_id not in listed]
    mg = con.sql(f"SELECT * FROM meaning_groups WHERE id = {gid}").df()
    mgd = mg.iloc[0].to_dict() if len(mg) else {}
    out = pipeline.analyse_group(gid, kept, corpus, mgd, sibling_index_for(gid, kept, con, corpus))
    rec = out["record"]
    if rec.get("status") != "ok":
        res.failures.append(f"no analysable chains in scope (status {rec.get('status')})")
        return res
    on_edges = [e for e in out["edges"] if e["on_path"]]
    kind = {n["node"]: n["kind"] for n in out["nodes"]}

    def students(node: str) -> set[str]:
        return {e["v"] for e in on_edges if e["u"] == node and kind.get(e["v"]) in ("narrator", "mubham")}

    def cut(th: str) -> list[str]:
        return list(rec["cut_vertices"] if th == "all" else rec[f"cut_vertices_{th}"])

    exp = entry.get("expect") or {}
    F = res.failures
    for th, v in (exp.get("kappa_eq") or {}).items():
        if rec[f"kappa_{th}"] != v:
            F.append(f"kappa_{th} = {rec[f'kappa_{th}']}, expected {v}")
    for th, v in (exp.get("kappa_ge") or {}).items():
        if rec[f"kappa_{th}"] < v:
            F.append(f"kappa_{th} = {rec[f'kappa_{th}']}, expected >= {v}")
    for th, v in (exp.get("kappa_gt") or {}).items():
        if rec[f"kappa_{th}"] <= v:
            F.append(f"kappa_{th} = {rec[f'kappa_{th}']}, expected > {v}")
    for th, v in (exp.get("cut_vertices_eq") or {}).items():
        if cut(th) != list(v):
            F.append(f"cut_vertices[{th}] = {cut(th)}, expected {v}")
    for th, v in (exp.get("cut_vertices_include") or {}).items():
        miss = [x for x in v if x not in cut(th)]
        if miss:
            F.append(f"cut_vertices[{th}] lacks {miss}")
    for th, v in (exp.get("not_cut_vertex") or {}).items():
        bad = [x for x in v if x in cut(th)]
        if bad:
            F.append(f"{bad} unexpectedly cut vertices at {th}")
    miss = [x for x in exp.get("single_strand_include") or [] if x not in rec["single_strand"]]
    if miss:
        F.append(f"not single-strand: {miss}")
    for k, v in (exp.get("pcl_include") or {}).items():
        miss = [x for x in v if x not in rec[f"pcl_k{k}"]]
        if miss:
            F.append(f"not partial common links (k={k}): {miss}")
    for node, v in (exp.get("students_include") or {}).items():
        miss = [x for x in v if x not in students(node)]
        if miss:
            F.append(f"{node} lacks on-path students {miss}")
    for node, v in (exp.get("min_students") or {}).items():
        n = len(students(node))
        if n < v:
            F.append(f"{node} has {n} on-path students, expected >= {v}")
    comps = students("P") | {e["v"] for e in on_edges if e["u"] == "P"}
    miss = [x for x in exp.get("companions_include") or [] if x not in comps]
    if miss:
        F.append(f"companions on path lack {miss}")
    if "companions_ge" in exp and rec["companions"] < exp["companions_ge"]:
        F.append(f"companions = {rec['companions']}, expected >= {exp['companions_ge']}")
    for node, v in (exp.get("death_year") or {}).items():
        d = int(corpus.narrators.death[_rid(node)])
        if d != v:
            F.append(f"death_year({node}) = {d}, expected {v}")
    # ---- bucket 2: number class, qara'in, derived grade v2, lists
    for k in ("number_class", "number_class_width", "in_sahihayn", "in_sahih_class", "huffaz_chain",
              "sound_distinct_routes"):
        if f"{k}_eq" in exp and rec.get(k) != exp[f"{k}_eq"]:
            F.append(f"{k} = {rec.get(k)}, expected {exp[f'{k}_eq']}")
    miss = [x for x in exp.get("tafarrud_layers_include") or [] if x not in list(rec.get("tafarrud_layers") or [])]
    if miss:
        F.append(f"tafarrud_layers {list(rec.get('tafarrud_layers') or [])} lack {miss}")
    for rs, want in (exp.get("v2") or {}).items():
        for k, v in want.items():
            got = rec.get(f"{k}_v2_{rs}")
            if got != v:
                F.append(f"{k}_v2_{rs} = {got}, expected {v}")
    if exp.get("no_upgrade"):
        for row in out["chains"]:
            for rs in ruleset_names():
                if row[f"code_v2_{rs}"] != row["chain_code"]:
                    F.append(f"sanad {row['sanad_id']}: code_v2_{rs} {row[f'code_v2_{rs}']} != v1 {row['chain_code']}")
                    break
        for rs in ruleset_names():
            if rec.get(f"code_v2_{rs}") != rec.get("derived_code"):
                F.append(f"group code_v2_{rs} {rec.get(f'code_v2_{rs}')} != v1 {rec.get('derived_code')}")
    cv = exp.get("chain_v2")
    chain_obs = {}
    if cv:
        path = [_rid(x) for x in cv["path"]]          # companion first, then down the chain
        by_sid = {c.sanad_id: c for c in kept}

        def has_path(c) -> bool:
            r = list(c.rawis)[::-1]
            return any(r[i:i + len(path)] == path for i in range(len(r) - len(path) + 1))

        sel = [row for row in out["chains"] if has_path(by_sid[row["sanad_id"]])]
        if not sel:
            F.append(f"chain_v2: no chain carries {cv['path']}")
        else:
            b = min(sel, key=lambda row: (row["code_v2_ibn_hajar"], not row["connected"], -row["chain_ordinal"],
                                          row["sanad_id"]))
            ch = by_sid[b["sanad_id"]]
            weak = [ch.rawis[p] for p in b["weakest_positions"]]
            chain_obs = {"chains_selected": len(sel), "sanad_id": b["sanad_id"], "weakest": [f"r{x}" for x in weak],
                         "weakest_level": [int(corpus.narrators.rank_no[x]) for x in weak],
                         **{f"{k}_{rs}": b.get(f"{k}_v2_{rs}") for rs in ruleset_names()
                            for k in ("code", "rule", "divergence")}}
            w = cv.get("weakest")
            if w and (len(weak) != 1 or f"r{weak[0]}" != w["node"]
                      or int(corpus.narrators.rank_no[weak[0]]) != int(w["level"])):
                F.append(f"chain_v2 weakest {chain_obs['weakest']} levels {chain_obs['weakest_level']}, expected {w}")
            for rs in ruleset_names() + [k for k in cv if k.startswith("alt_")]:
                for k, v in (cv.get(rs) or {}).items():
                    if b.get(f"{k}_v2_{rs}") != v:
                        F.append(f"chain_v2 {k}_v2_{rs} = {b.get(f'{k}_v2_{rs}')}, expected {v}")
    # one chain by sanad id: its v2 rule, defects, notes (defects_eq, notes_include, rule, code)
    cc = exp.get("chain_check")
    if cc:
        row = next((r for r in out["chains"] if r["sanad_id"] == int(cc["sanad_id"])), None)
        if row is None:
            F.append(f"chain_check: sanad {cc['sanad_id']} not in scope")
        else:
            chain_obs = chain_obs or {}
            chain_obs.update({"check_sanad": row["sanad_id"],
                              **{f"{k}_{rs}": row.get(f"{k}_v2_{rs}") for rs in ruleset_names()
                                 for k in ("rule", "code", "defects", "notes")}})
            for rs in ruleset_names():
                want = cc.get(rs) or {}
                for k in ("rule", "code"):
                    if k in want and row.get(f"{k}_v2_{rs}") != want[k]:
                        F.append(f"chain_check {k}_v2_{rs} = {row.get(f'{k}_v2_{rs}')}, expected {want[k]}")
                if "defects_eq" in want and list(row.get(f"defects_v2_{rs}") or []) != list(want["defects_eq"]):
                    F.append(f"chain_check defects_v2_{rs} = {row.get(f'defects_v2_{rs}')}, expected {want['defects_eq']}")
                miss = [x for x in want.get("notes_include") or [] if x not in list(row.get(f"notes_v2_{rs}") or [])]
                if miss:
                    F.append(f"chain_check notes_v2_{rs} {row.get(f'notes_v2_{rs}')} lack {miss}")
    lm = exp.get("list_match")
    if lm:
        import csv
        rows = []
        conf = paths.ROOT / "lists" / "confirmed.csv"
        if conf.exists():
            with open(conf, encoding="utf-8") as f:
                rows = [r for r in csv.DictReader(f) if r["list"] == lm["list"] and r["entry"] == str(lm["entry"])]
        ok = any(r.get("group_id") and int(r["group_id"]) == gid and r.get("confirmed_by") == lm.get("confirmed_by", "auto")
                 for r in rows)
        if not ok:
            F.append(f"list {lm['list']}:{lm['entry']} not confirmed to group {gid} ({lm.get('confirmed_by', 'auto')}): {rows}")
    res.observed = {
        "scope_chains": len(chains), "kept_chains": len(kept), "deviations": len(listed),
        **{k: rec[k] for k in ("kappa_all", "kappa_above_matruk", "kappa_saduq_up", "kappa_thiqa_up",
                               "kappa_lower_all", "kappa_lower_source_all", "kappa_lower_thiqa_up", "companions",
                               "n_common_links", "n_cut_vertices")},
        "cut_vertices": list(rec["cut_vertices"]),
        "cut_vertices_thiqa_up": list(rec["cut_vertices_thiqa_up"]),
        **{k: rec.get(k) for k in ("number_class", "number_class_width", "gharib_cut_kind", "min_width", "in_sahihayn",
                                   "huffaz_chain")},
        "tafarrud_layers": list(rec.get("tafarrud_layers") or []),
        **{f"{k}_v2_{rs}": rec.get(f"{k}_v2_{rs}") for rs in ruleset_names() for k in ("code", "rule", "divergence")},
        "chain_v2": chain_obs,
    }
    return res


_SIB_CACHE: dict = {}


def sibling_index_for(gid: int, own: list, con, corpus):
    """The sibling index the full run would give group `gid` (its sibling groups' chains
    classified in their own groups), or None when no ruleset searches siblings."""
    from itibar import corroborate, siblings
    params = corroborate.rulesets()
    if not corroborate.uses_siblings(params):
        return None
    sib = siblings.sibling_groups(con, [gid]).get(gid, ())
    key = (gid, tuple(c.sanad_id for c in own))
    if key not in _SIB_CACHE:
        gc = load.chains_by_group(con, list(sib)) if sib else {}
        gc[gid] = own
        _SIB_CACHE[key] = pipeline.sibling_index(gc, [gid], corpus, params, con)
    return _SIB_CACHE[key]


def ruleset_names() -> list[str]:
    from itibar import corroborate
    return corroborate.ruleset_names()


def whole_group(gid: int, con, corpus) -> dict:
    chains = load.chains_by_group(con, [gid]).get(gid, [])
    mg = con.sql(f"SELECT * FROM meaning_groups WHERE id = {gid}").df()
    rec = pipeline.analyse_group(gid, chains, corpus, mg.iloc[0].to_dict(),
                                 sibling_index_for(gid, chains, con, corpus))["record"]
    return {k: rec.get(k) for k in ("n_chains", "kappa_all", "kappa_above_matruk", "kappa_saduq_up",
                                    "kappa_thiqa_up", "kappa_nocompat_all", "kappa_lower_all", "kappa_lower_source_all",
                                    "companions", "sahaba_qty")}


def report() -> tuple[str, bool]:
    con = data.views()
    corpus = load.corpus(con)
    names = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
    lines = ["# Gold set results", "",
             "Generated by `make gold` from tests/gold/gold.yaml. Scoped values are what the assertions",
             "were evaluated on (documented deviations removed); whole-group values are the record for the",
             "entire meaning group, recorded and never asserted. κ_lower is the minimum of κ over three",
             "stated hypotheses (same-name clusters merged, unmerged, continuity-incompatible links removed);",
             "the column after it names the first hypothesis attaining it.", "",
             "| entry | group | class | pass | scope chains (kept) | κ all | κ ≥matruk | κ saduq+ | κ thiqa+ | κ_lower all | attained by | companions | cut vertices (all) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    all_ok = True
    detail = []
    obs_by: dict = {}
    for e in entries():
        r = evaluate(e, con, corpus)
        all_ok &= r.ok
        o = r.observed
        obs_by[e["id"]] = o
        cuts = ", ".join(names.get(_rid(x), x) if x.startswith("r") else x for x in o.get("cut_vertices", []))
        lines.append(
            f"| {e['id']} | {e['group_id']} | {e['class']} | {'yes' if r.ok else 'NO'} | "
            f"{o.get('scope_chains', '')} ({o.get('kept_chains', '')}) | {o.get('kappa_all', '')} | "
            f"{o.get('kappa_above_matruk', '')} | {o.get('kappa_saduq_up', '')} | {o.get('kappa_thiqa_up', '')} | "
            f"{o.get('kappa_lower_all', '')} | {o.get('kappa_lower_source_all', '')} | {o.get('companions', '')} | {cuts} |")
        wg = whole_group(int(e["group_id"]), con, corpus)
        detail.append(f"- **{e['id']}** (group {e['group_id']}, whole group): "
                      + ", ".join(f"{k}={v}" for k, v in wg.items())
                      + ("" if r.ok else f" — FAILURES: {'; '.join(r.failures)}"))
    lines += ["", "## Bucket-2 mechanisms (scoped values)", "",
              "Number class on Taqrīb layers 1–12 (width, and κ_all with the same cut points); derived grade v2 under",
              "both rulesets for the group's v2 chain; for chain-level entries, the selected chains' best chain.", "",
              "| entry | number class (κ) | by width | tafarrud layers (width) | in Ṣaḥīḥayn | v2 ibn_hajar | v2 ibn_al_salah | chain-level |",
              "|---|---|---|---|---|---|---|---|"]
    for e in entries():
        o = obs_by.get(e["id"], {})
        cv = o.get("chain_v2") or {}
        chain = (f"sanad {cv['sanad_id']}: weakest {cv['weakest']} (level {cv['weakest_level']}); "
                 f"ibn_hajar {cv.get('rule_ibn_hajar')} → {cv.get('code_ibn_hajar')} ({cv.get('divergence_ibn_hajar')}); "
                 f"ibn_al_salah {cv.get('rule_ibn_al_salah')} → {cv.get('code_ibn_al_salah')}") if cv.get("sanad_id") else ""
        if cv.get("check_sanad"):
            chain += (f" sanad {cv['check_sanad']}: ibn_hajar {cv.get('rule_ibn_hajar')}, defects {cv.get('defects_ibn_hajar')}, "
                      f"notes {cv.get('notes_ibn_hajar')}")
        lines.append(f"| {e['id']} | {o.get('number_class')} | {o.get('number_class_width')} | {o.get('tafarrud_layers')} | "
                     f"{o.get('in_sahihayn')} | {o.get('rule_v2_ibn_hajar')} → {o.get('code_v2_ibn_hajar')} | "
                     f"{o.get('rule_v2_ibn_al_salah')} → {o.get('code_v2_ibn_al_salah')} | {chain} |")
    lines += ["", "## Whole-group records", ""] + detail + [""]
    return "\n".join(lines), all_ok


def main() -> None:
    text, ok = report()
    out = paths.REPORTS_DIR / "gold.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
