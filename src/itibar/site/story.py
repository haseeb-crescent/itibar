"""The story view: a report's bundle summarised as generations, named where few and grouped where many.

Input is what the pipeline stored (on-route nodes and edges with their chains and threshold masks,
and the receipts' maximum sets of vertex-disjoint routes per threshold); nothing here changes a
number. The layout rules (DECISIONS D98):

* One row per generation (the stored layer), the Prophet at the top and the books at the bottom.
  Compiler nodes are contracted: a chain runs from its last narrator straight into the book.
* A row of at most NAMED_ROW narrators names them all. A wider row names its marked narrators (cut
  vertices at any threshold, common links) and any narrator carrying a large share of the row's
  chains, and groups the rest by the item above them that most of their chains come through
  ("26 students of Yaḥyā b. Saʿīd").
* Once two successive rows have had to be grouped, everything below is folded into one band per
  anchor ("Yaḥyā b. Saʿīd's line: 590 narrators, generations 7–30"), then the books row: the major
  collections by name and the rest as one group.
* Links between items carry the chains along them and the thresholds at which they survive.
* The independent lines are the stored routes, mapped onto the items they pass through.
"""
from __future__ import annotations

from collections import defaultdict

NAMED_ROW = 6          # a row with at most this many narrators is named in full
MAX_ITEMS = 7          # display items per row before small groups merge into "others"
SHARE = 0.25           # a narrator carrying this share of a wide row's chains is named
MEMBERS = 12           # members described per group (by chains); the rest are counted
MAX_LINES = 8          # independent lines drawn; the rest are counted
MAJOR = (1, 2, 4, 3, 5, 6, 8, 9, 7)   # al-Bukhārī, Muslim, Abū Dāwūd, al-Tirmidhī, al-Nasāʾī, Ibn Mājah, Mālik, Aḥmad, al-Dārimī
PERSON_KINDS = ("narrator", "ucomp", "mubham")


def contract(node_rows, edge_rows):
    """On-route people, the Prophet and books, with compiler nodes contracted out.

    Returns (nodes: id -> row, edges: (u, v) -> [chain ids, threshold mask])."""
    nodes = {n["node"]: n for n in node_rows if n["on_path"] and n["kind"] != "gap"}
    edges = {}
    into, out = defaultdict(list), defaultdict(list)
    for e in edge_rows:
        if not e["on_path"] or e["u"] not in nodes or e["v"] not in nodes:
            continue
        chains = set(e["sanad_ids"])
        if nodes[e["u"]]["kind"] == "compiler":
            out[e["u"]].append((e["v"], chains, e["threshold_mask"]))
        elif nodes[e["v"]]["kind"] == "compiler":
            into[e["v"]].append((e["u"], chains, e["threshold_mask"]))
        else:
            edges[(e["u"], e["v"])] = [chains, e["threshold_mask"]]
    for compiler in sorted(set(into) | set(out)):
        for u, chains_in, mask_in in into[compiler]:
            for v, chains_out, mask_out in out[compiler]:
                shared = chains_in & chains_out
                if shared and u != v:
                    entry = edges.setdefault((u, v), [set(), 0])
                    entry[0] |= shared
                    entry[1] |= mask_in & mask_out
    nodes = {k: n for k, n in nodes.items() if n["kind"] != "compiler"}
    edges = {k: v for k, v in edges.items() if k[0] in nodes and k[1] in nodes}
    return nodes, edges


def _order_rows(rows, links):
    """Barycentre sweeps so that items sit near the items they connect to."""
    neighbours = defaultdict(list)
    for a, b in links:
        neighbours[a].append(b)
        neighbours[b].append(a)
    pos = {item: (j + 0.5) / len(row) for row in rows for j, item in enumerate(row)}
    for sweep in (rows, rows[::-1], rows):
        for row in sweep:
            if len(row) < 2:
                continue
            row.sort(key=lambda i: (sum(pos[j] for j in neighbours[i]) / len(neighbours[i])
                                    if neighbours[i] else pos[i], i))
            pos.update({item: (j + 0.5) / len(row) for j, item in enumerate(row)})


def build(record, node_rows, edge_rows, steps, thresholds):
    """The story-view structure for one report, or None when no route reaches the Prophet.

    thresholds: the pipeline's threshold names in mask-bit order."""
    nodes, edges = contract(node_rows, edge_rows)
    if "P" not in nodes:
        return None
    full = (1 << len(thresholds)) - 1
    weight, alive = defaultdict(int), defaultdict(int)
    teachers, students = defaultdict(list), defaultdict(list)
    for (u, v), (chains, mask) in edges.items():
        weight[v] += len(chains)
        if u == "P":
            weight["P"] += len(chains)
        alive[u] |= mask
        alive[v] |= mask
        teachers[v].append((len(chains), u))
        students[u].append((len(chains), v))
    alive["P"] = full
    for table in (teachers, students):
        for key in table:
            table[key].sort(key=lambda x: (-x[0], x[1]))

    marked = set(record.get("common_links") or [])
    for name in thresholds:
        marked |= set(record["cut_vertices" if name == "all" else f"cut_vertices_{name}"] or [])
    by_layer = defaultdict(list)
    for k in sorted((k for k, n in nodes.items() if n["kind"] in PERSON_KINDS),
                    key=lambda k: (-weight[k], k)):
        by_layer[nodes[k]["layer"]].append(k)
    layers = sorted(by_layer)

    items = {"P": {"id": "P", "kind": "prophet", "members": ["P"]}}
    item_of = {"P": "P"}
    rows = [{"gen": 0, "items": ["P"]}]

    def anchor_of(node, extra=None):
        for _, t in teachers[node]:
            if t in item_of:
                return item_of[t]
            if extra and t in extra:
                return extra[t]
        return None

    grouped_rows, fold_from = 0, None
    for index, layer in enumerate(layers):
        row = by_layer[layer]
        total = sum(weight[k] for k in row) or 1
        if len(row) <= NAMED_ROW:
            named, rest = list(row), []
        else:
            cuts = {k for k in row if k in marked and k not in (record.get("common_links") or ())}
            named = [k for k in row if k in marked or weight[k] / total >= SHARE]
            named = sorted(named, key=lambda k: (k not in cuts, -weight[k], k))[:MAX_ITEMS - 1]
            rest = [k for k in row if k not in named]
        for k in named:
            item_of[k] = k
        groups = defaultdict(list)
        for k in rest:
            groups[anchor_of(k)].append(k)
        for anchor in [a for a, members in groups.items() if len(members) == 1]:
            single = groups.pop(anchor)[0]
            named.append(single)
            item_of[single] = single
        if groups and grouped_rows >= 1:
            for k in named:
                del item_of[k]
            fold_from = index
            break
        grouped_rows = grouped_rows + 1 if groups else 0
        row_items = []
        for k in sorted(named, key=lambda k: (-weight[k], k)):
            items[k] = {"id": k, "kind": "person", "members": [k]}
            item_of[k] = k
            row_items.append(k)
        ordered = sorted(groups.items(), key=lambda kv: (-sum(weight[m] for m in kv[1]), str(kv[0])))
        room = max(MAX_ITEMS - len(row_items), 1)
        if len(ordered) > room:
            ordered = ordered[:room - 1] + [(None, [m for _, ms in ordered[room - 1:] for m in ms])]
        for n, (anchor, members) in enumerate(ordered):
            gid = f"g{layer}-{n}"
            direct = anchor is not None and items[anchor]["kind"] == "person" and all(
                any(t == anchor for _, t in teachers[m]) for m in members)
            items[gid] = {"id": gid, "kind": "group", "members": members, "anchor": anchor, "direct": direct}
            item_of.update({m: gid for m in members})
            row_items.append(gid)
        rows.append({"gen": layer, "items": row_items})

    if fold_from is not None:
        folded = [k for layer in layers[fold_from:] for k in by_layer[layer]]
        band_of = {}
        for _ in range(3):   # a teacher folded earlier (or found on a later pass) passes his band on
            for k in folded:
                band_of[k] = anchor_of(k, {t: b for t, b in band_of.items() if b is not None})
        bands = defaultdict(list)
        for k in folded:
            bands[band_of[k]].append(k)
        ordered = sorted(bands.items(), key=lambda kv: (-sum(weight[m] for m in kv[1]), str(kv[0])))
        if len(ordered) > MAX_ITEMS:
            ordered = ordered[:MAX_ITEMS - 1] + [(None, [m for _, ms in ordered[MAX_ITEMS - 1:] for m in ms])]
        band_items = []
        for n, (anchor, members) in enumerate(ordered):
            bid = f"band{n}"
            gens = sorted({nodes[m]["layer"] for m in members})
            members = sorted(members, key=lambda k: (-weight[k], k))
            items[bid] = {"id": bid, "kind": "band", "members": members, "anchor": anchor, "gens": [gens[0], gens[-1]]}
            item_of.update({m: bid for m in members})
            band_items.append(bid)
        rows.append({"gen": layers[fold_from], "band": True, "items": band_items})

    books = sorted((k for k, n in nodes.items() if n["kind"] == "book"), key=lambda k: (-weight[k], k))
    major = sorted((k for k in books if nodes[k]["book_id"] in MAJOR), key=lambda k: MAJOR.index(nodes[k]["book_id"]))
    others = [k for k in books if k not in major]
    book_items = []
    for k in major:
        items[k] = {"id": k, "kind": "book", "members": [k]}
        item_of[k] = k
        book_items.append(k)
    if others:
        items["books"] = {"id": "books", "kind": "books", "members": others}
        item_of.update({k: "books" for k in others})
        book_items.append("books")
    rows.append({"gen": "books", "items": book_items})

    links = {}
    for (u, v), (chains, mask) in sorted(edges.items()):
        a, b = item_of.get(u), item_of.get(v)
        if a is None or b is None or a == b:
            continue
        entry = links.setdefault((a, b), [set(), 0])
        entry[0] |= chains
        entry[1] |= mask
    _order_rows([r["items"] for r in rows], links)

    for item in items.values():
        item["count"] = len(item["members"])
        item["chains"] = sum(weight[m] for m in item["members"])
        item["alive"] = [sum(1 for m in item["members"] if alive[m] >> bit & 1) for bit in range(len(thresholds))]

    lines = {}
    for name in thresholds:
        routes = (steps or {}).get(name, [{}])[0].get("data", {}).get("routes", [])
        mapped = []
        for route in routes:
            path = []
            for node in route["nodes"]:
                item = item_of.get(node)
                if item and (not path or path[-1] != item):
                    path.append(item)
            mapped.append({"items": path, "nodes": [n for n in route["nodes"] if n in nodes and n != "P"]})
        lines[name] = mapped

    return {"items": items, "rows": rows, "links": {k: [len(v[0]), v[1]] for k, v in links.items()},
            "lines": lines, "nodes": nodes, "edges": edges, "weight": weight, "alive": alive, "marked": marked,
            "teachers": teachers, "students": students, "item_of": item_of}
