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
    with open(paths.GOLD_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)["entries"]


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
    out = pipeline.analyse_group(gid, kept, corpus, mgd)
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
    res.observed = {
        "scope_chains": len(chains), "kept_chains": len(kept), "deviations": len(listed),
        **{k: rec[k] for k in ("kappa_all", "kappa_above_matruk", "kappa_saduq_up", "kappa_thiqa_up",
                               "kappa_lower_all", "kappa_lower_thiqa_up", "companions",
                               "n_common_links", "n_cut_vertices")},
        "cut_vertices": list(rec["cut_vertices"]),
        "cut_vertices_thiqa_up": list(rec["cut_vertices_thiqa_up"]),
    }
    return res


def whole_group(gid: int, con, corpus) -> dict:
    chains = load.chains_by_group(con, [gid]).get(gid, [])
    mg = con.sql(f"SELECT * FROM meaning_groups WHERE id = {gid}").df()
    rec = pipeline.analyse_group(gid, chains, corpus, mg.iloc[0].to_dict())["record"]
    return {k: rec.get(k) for k in ("n_chains", "kappa_all", "kappa_above_matruk", "kappa_saduq_up",
                                    "kappa_thiqa_up", "kappa_lower_all", "companions", "sahaba_qty")}


def report() -> tuple[str, bool]:
    con = data.views()
    corpus = load.corpus(con)
    names = dict(con.sql("SELECT id, nickname FROM rawis").fetchall())
    lines = ["# Gold set results", "",
             "Generated by `make gold` from tests/gold/gold.yaml. Scoped values are what the assertions",
             "were evaluated on (documented deviations removed); whole-group values are the record for the",
             "entire meaning group, recorded and never asserted.", "",
             "| entry | group | class | pass | scope chains (kept) | κ all | κ ≥matruk | κ saduq+ | κ thiqa+ | κ_lower all | companions | cut vertices (all) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    all_ok = True
    detail = []
    for e in entries():
        r = evaluate(e, con, corpus)
        all_ok &= r.ok
        o = r.observed
        cuts = ", ".join(names.get(_rid(x), x) if x.startswith("r") else x for x in o.get("cut_vertices", []))
        lines.append(
            f"| {e['id']} | {e['group_id']} | {e['class']} | {'yes' if r.ok else 'NO'} | "
            f"{o.get('scope_chains', '')} ({o.get('kept_chains', '')}) | {o.get('kappa_all', '')} | "
            f"{o.get('kappa_above_matruk', '')} | {o.get('kappa_saduq_up', '')} | {o.get('kappa_thiqa_up', '')} | "
            f"{o.get('kappa_lower_all', '')} | {o.get('companions', '')} | {cuts} |")
        wg = whole_group(int(e["group_id"]), con, corpus)
        detail.append(f"- **{e['id']}** (group {e['group_id']}, whole group): "
                      + ", ".join(f"{k}={v}" for k, v in wg.items())
                      + ("" if r.ok else f" — FAILURES: {'; '.join(r.failures)}"))
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
