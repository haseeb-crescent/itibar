"""Bundle B(g): the directed graph of every chain of every hadith in meaning group g.

Node ids (strings, stable across runs):
  P                  PROPHET, virtual source
  r<rawi_id>         a narrator
  m<student>|<teacher>  an unnamed person (placeholder 1131), one node per
                     (student, teacher) context: "a man" between the same two
                     people is taken to be the same man; across contexts never
  g<sanad_id>.<pos>  a break marker (irsal / inqita' / ta'liq); one per chain
                     occurrence and never traversable, so it records the gap
                     without fusing unrelated routes
  c<author_no>       a book's compiler (books.author_no); every route into a
                     book passes through it
  b<book_id>         a book record (sink; never cut)

Edges run teacher -> student: sanad_rawis pos+1 -> pos; then pos 0 -> compiler
-> book; and PROPHET -> last narrator only when that narrator is a companion.

Book roles, per chain occurrence: the book's compiler at pos 0; its book transmitter
at pos 0 (books.transmitter_rawi) and, with him, the compiler at pos 1. A narrator in
a role is exempt from grade thresholds on his role edges (into the book: his compiler
node, or the transmitter) and is excluded from the chain grade there; his other
occurrences are ordinary narrator occurrences (`role_edges`, `role_in`, `nr_in`,
`nr_out` record which is which, for single strands and partial common links).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from itibar import config
from itibar.load import Chain, Corpus

PROPHET = "P"
SINK = "T"


@dataclass
class EdgeInfo:
    occurrences: list = field(default_factory=list)   # [(sanad_id, book_id, word, word_raw, word_class)]


@dataclass
class ChainInfo:
    sanad_id: int
    hadith_id: int
    book_id: int
    nodes: list[str]                 # node per position (pos 0 first)
    rawis: tuple[int, ...]
    ends_companion: bool
    gaps: dict[str, int]
    has_mubham: bool
    has_stub: bool
    self_loops: int
    compiler_at_pos0: bool
    connected: bool                  # companion end, no break marker: one unbroken PROPHET->book route
    transmitter_at_pos0: bool = False   # pos 0 is the book's transmitter
    compiler_pos: int | None = None     # position of the book's compiler in the chain (0, 1 after a transmitter)

    @property
    def role_positions(self) -> tuple[int, ...]:
        """Positions in a book role: excluded from the chain grade, exempt from thresholds."""
        out = []
        if self.compiler_at_pos0 or self.transmitter_at_pos0:
            out.append(0)
        if self.compiler_pos == 1:
            out.append(1)
        return tuple(out)


@dataclass
class Bundle:
    group_id: int
    kind: dict[str, str] = field(default_factory=dict)          # node -> prophet|narrator|mubham|gap|compiler|book
    rawi: dict[str, int] = field(default_factory=dict)          # node -> rawi id (narrators, mubham=1131)
    book: dict[str, int] = field(default_factory=dict)          # node -> book id (book nodes)
    author_no: dict[str, int] = field(default_factory=dict)     # compiler node -> author_no
    edges: dict[tuple[str, str], EdgeInfo] = field(default_factory=dict)
    succ: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    pred: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    chains: list[ChainInfo] = field(default_factory=list)
    compiler_rawi_nodes: set[str] = field(default_factory=set)  # r-nodes that compiled a book of the group (pos 0, or pos 1 after its transmitter)
    transmitter_nodes: set[str] = field(default_factory=set)    # r-nodes at pos 0 as a book's transmitter
    role_edges: set[tuple[str, str]] = field(default_factory=set)   # (u, v) where u is in a book role: his edge into the book
    role_in: set[tuple[str, str]] = field(default_factory=set)      # (u, v) where v is in a book role in that occurrence
    nr_in: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))   # narrator-role in-neighbours
    nr_out: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # narrator-role out-neighbours
    nr_nodes: set[str] = field(default_factory=set)             # nodes with at least one narrator-role occurrence
    self_loops: int = 0

    @property
    def role_nodes(self) -> set[str]:
        return self.compiler_rawi_nodes | self.transmitter_nodes

    @property
    def exempt(self) -> set[str]:
        """Nodes kept at every threshold: compilers and book transmitters in their role."""
        return {n for n, k in self.kind.items() if k == "compiler"} | self.role_nodes

    @property
    def terminals(self) -> set[str]:
        return self.exempt | {n for n, k in self.kind.items() if k == "book"}

    def add_edge(self, u: str, v: str, occ: tuple) -> None:
        e = self.edges.get((u, v))
        if e is None:
            e = self.edges[(u, v)] = EdgeInfo()
            self.succ[u].add(v)
            self.pred[v].add(u)
        e.occurrences.append(occ)


def build(group_id: int, chains: list[Chain], corpus: Corpus) -> Bundle:
    nar, books = corpus.narrators, corpus.books
    drop_loops = config.load("structure")["bundle"]["drop_self_loops"]
    B = Bundle(group_id)
    B.kind[PROPHET] = "prophet"
    for ch in chains:
        r = ch.rawis
        n = len(r)
        nodes: list[str] = []
        gaps: dict[str, int] = {}
        has_mubham = has_stub = False
        for p, rid in enumerate(r):
            if nar.is_gap(rid):
                nid = f"g{ch.sanad_id}.{p}"
                B.kind[nid] = "gap"
                B.rawi[nid] = rid
                k = nar.placeholder_kind[rid]
                gaps[k] = gaps.get(k, 0) + 1
            elif nar.is_mubham(rid):
                student = r[p - 1] if p > 0 else f"B{ch.book_id}"
                teacher = r[p + 1] if p + 1 < n else "END"
                nid = f"m{student}|{teacher}"
                B.kind[nid] = "mubham"
                B.rawi[nid] = rid
                has_mubham = True
            else:
                nid = f"r{rid}"
                B.kind.setdefault(nid, "narrator")
                B.rawi[nid] = rid
                if rid < len(nar.is_stub) and nar.is_stub[rid]:
                    has_stub = True
            nodes.append(nid)
        # book roles in this chain
        crawi = books.compiler_rawi.get(ch.book_id)
        trawi = books.transmitter_rawi.get(ch.book_id)
        transmitter_at_pos0 = trawi is not None and r[0] == trawi
        compiler_at_pos0 = (not transmitter_at_pos0) and crawi == r[0]
        compiler_pos = 0 if compiler_at_pos0 else (1 if transmitter_at_pos0 and n > 1 and r[1] == crawi else None)
        role_pos = {0} if (compiler_at_pos0 or transmitter_at_pos0) else set()
        if compiler_pos == 1:
            role_pos.add(1)
        if compiler_at_pos0:
            B.compiler_rawi_nodes.add(nodes[0])
        if transmitter_at_pos0:
            B.transmitter_nodes.add(nodes[0])
        if compiler_pos == 1:
            B.compiler_rawi_nodes.add(nodes[1])
        for p in range(n):
            if p not in role_pos:
                B.nr_nodes.add(nodes[p])
        loops = 0
        for p in range(n - 1):
            u, v = nodes[p + 1], nodes[p]
            if u == v and drop_loops:
                loops += 1
                continue
            w = ch.words.get(p + 1)
            B.add_edge(u, v, (ch.sanad_id, ch.book_id) + (w if w else (None, None, None)))
            if p in role_pos:
                B.role_in.add((u, v))
            else:
                B.nr_in[v].add(u)
            if p + 1 in role_pos:
                B.role_edges.add((u, v))
            else:
                B.nr_out[u].add(v)
        B.self_loops += loops
        # bottom: pos 0 -> compiler -> book
        comp = f"c{books.author_no[ch.book_id]}"
        B.kind[comp] = "compiler"
        B.author_no[comp] = books.author_no[ch.book_id]
        bnode = f"b{ch.book_id}"
        B.kind[bnode] = "book"
        B.book[bnode] = ch.book_id
        B.add_edge(nodes[0], comp, (ch.sanad_id, ch.book_id, None, None, None))
        if 0 in role_pos:
            B.role_edges.add((nodes[0], comp))
        else:
            B.nr_out[nodes[0]].add(comp)
        B.add_edge(comp, bnode, (ch.sanad_id, ch.book_id, None, None, None))
        # top: PROPHET -> companion
        last = r[-1]
        ends_comp = (B.kind[nodes[-1]] == "narrator" and last < len(nar.is_companion)
                     and bool(nar.is_companion[last]))
        if ends_comp:
            B.add_edge(PROPHET, nodes[-1], (ch.sanad_id, ch.book_id, None, None, None))
            B.nr_in[nodes[-1]].add(PROPHET)
            B.nr_out[PROPHET].add(nodes[-1])
        B.chains.append(ChainInfo(
            sanad_id=ch.sanad_id, hadith_id=ch.hadith_id, book_id=ch.book_id, nodes=nodes, rawis=r,
            ends_companion=ends_comp, gaps=gaps, has_mubham=has_mubham, has_stub=has_stub,
            self_loops=loops, compiler_at_pos0=compiler_at_pos0,
            connected=ends_comp and not gaps, transmitter_at_pos0=transmitter_at_pos0, compiler_pos=compiler_pos,
        ))
    return B
