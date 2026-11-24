"""Prepare vertical drawing layouts from stored generations, graph flags and edges."""
from __future__ import annotations

from collections import defaultdict
from itertools import zip_longest

OVERVIEW_NODES = 220
ON_PATH, COMMON_LINK, BOOK_ROLE, NARRATOR_PAGE, SINGLE_STRAND = 1, 2, 4, 8, 16


def project_edges(nodes, edges, node_ids, collapse):
    """Contract long unbranched drawing segments, retaining all marked nodes."""
    shown = set(node_ids)
    pairs = [e for e, (u, v, *_) in enumerate(edges) if u in shown and v in shown]
    if not collapse:
        return shown, pairs
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for i in pairs:
        u, v, *_ = edges[i]
        outgoing[u].append(i)
        incoming[v].append(i)
    strand = {i for i in shown
              if nodes[i][6] & SINGLE_STRAND and not nodes[i][6] & (COMMON_LINK | BOOK_ROLE)
              and not nodes[i][7] and len(incoming[i]) == len(outgoing[i]) == 1}
    compressed, removed = [], set()
    for u in sorted(shown - strand):
        for edge in outgoing[u]:
            _, v, mask, attr, weight = edges[edge]
            interior = []
            while v in strand:
                interior.append(v)
                _, v, mask_next, attr_next, weight_next = edges[outgoing[v][0]]
                mask &= mask_next
                attr |= attr_next
                weight = min(weight, weight_next)
            if len(interior) >= 3 and u != v:
                removed.update(interior)
                compressed.append([u, v, mask, attr, weight, len(interior)])
    return shown - removed, [i for i in pairs if not removed.intersection(edges[i][:2])] + compressed


def layout(nodes, edges, shown, draw_edges):
    rows = defaultdict(list)
    for i in sorted(shown):
        node, _, _, _, _, layer, *_ = nodes[i]
        band = 200 if node.startswith("b") else 199 if node.startswith("c") else layer
        rows[band].append(i)

    # Keep neighbors near each other within each generation in the drawing.
    neighbors = defaultdict(list)
    for item in draw_edges:
        u, v, *_ = edges[item] if isinstance(item, int) else item
        neighbors[u].append(v)
        neighbors[v].append(u)

    bands = sorted(rows)
    x = {i: (2 * j - len(row) + 1) / len(row) for row in rows.values() for j, i in enumerate(row)}
    for sweep in (bands, reversed(bands)):
        for band in sweep:
            row = rows[band]
            if len(row) < 2:
                continue
            row.sort(key=lambda i: (sum(x[j] for j in neighbors[i]) / len(neighbors[i])
                                    if neighbors[i] else x[i], i))
            x.update({i: (2 * j - len(row) + 1) / len(row) for j, i in enumerate(row)})

    labels = {0: "Prophet", 199: "Compilers", 200: "Books"}
    return [
        [labels.get(b, f"Generation {b}") for b in bands],
        [[i, 2 * j - len(rows[b]) + 1, y]
         for y, b in enumerate(bands) for j, i in enumerate(rows[b])],
        draw_edges,
    ]


def graph_data(corpus, record, node_rows, edge_rows, route_narrators, receipt):
    thresholds = list(corpus.scale.thresholds)
    cut = defaultdict(int)
    for i, threshold in enumerate(thresholds):
        for node in record["cut_vertices" if threshold == "all" else f"cut_vertices_{threshold}"]:
            cut[node] |= 1 << i

    # A report with routes is drawn from its on-route nodes only; the off-route view is kept for the reports
    # where no route reaches the Prophet, the only drawing they have (DECISIONS D105).
    if any(n["on_path"] for n in node_rows):
        node_rows = [n for n in node_rows if n["on_path"]]
        keep = {n["node"] for n in node_rows}
        edge_rows = [e for e in edge_rows if e["u"] in keep and e["v"] in keep]
    nodes, by_id = [], {}
    for n in node_rows:
        key, rid = n["node"], n["rawi_id"]
        p = corpus.people.get(rid, {})
        name = corpus.name(rid) if n["kind"] == "gap" else corpus.node(key)
        level = (1 if n["kind"] == "ucomp" else p.get("rank_no")) if n["ordinal"] is not None else None
        death = p.get("death_year_raw") or p.get("death_year")
        if n["kind"] == "compiler":
            death = corpus.authors[n["author_no"]]["author_death_year"]
        flags = (int(n["on_path"]) * ON_PATH | int(n["common_link"]) * COMMON_LINK
                 | int(n["compiler_role"] or n["book_transmitter_role"]) * BOOK_ROLE
                 | int(n["kind"] == "narrator" and rid in route_narrators) * NARRATOR_PAGE
                 | int(n["single_strand"]) * SINGLE_STRAND)
        by_id[key] = len(nodes)
        nodes.append([key, name, death, level, p.get("rank"), n["layer"], flags, cut[key], n["ordinal"]])

    # Edges carry the pipeline's threshold mask, a drawing flag for continuity/off-route and frequency.
    edges = [[by_id[e["u"]], by_id[e["v"]], e["threshold_mask"],
              int(e["continuity"] == "incompatible") | (0 if e["on_path"] else 2), min(e["weight"], 16)]
             for e in edge_rows]

    witnesses = receipt["all"][0]["data"]["routes"]
    witness_nodes = [by_id[k] for route in witnesses[:12] for k in route["nodes"]]
    weight = defaultdict(int)
    for u, v, _, _, occurrences in edges:
        weight[u] += occurrences
        weight[v] += occurrences
    views = []
    selections = []
    off_route = 0
    for include_all in (False, True):
        eligible = [i for i, node in enumerate(nodes) if include_all or node[6] & ON_PATH]
        off_route = len(nodes) - len(eligible) if not include_all else off_route
        for expanded in (False, True):
            shown, drawn = project_edges(nodes, edges, eligible, collapse=not expanded)
            if not expanded and len(shown) > OVERVIEW_NODES:
                marked = [i for i in sorted(shown) if nodes[i][7] or nodes[i][6] & COMMON_LINK or nodes[i][0] == "P"]
                bands = defaultdict(list)
                for i in sorted(shown, key=lambda i: (-weight[i], i)):
                    bands[nodes[i][5]].append(i)
                sample = [i for row in zip_longest(*bands.values()) for i in row if i is not None]
                order = dict.fromkeys(marked + witness_nodes + sample)
                shown = set([i for i in order if i in shown][:max(len(marked), OVERVIEW_NODES)])
                drawn = [e for e in drawn if all(i in shown for i in (edges[e] if isinstance(e, int) else e)[:2])]
            view = layout(nodes, edges, shown, drawn)
            if view not in views:
                views.append(view)
            selections.append(views.index(view))
    return {"nodes": nodes, "edges": edges, "views": views, "selection": selections,
            "off_route": off_route, "thresholds": list(corpus.scale.thresholds.values())}
