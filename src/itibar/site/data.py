"""Join source citations to pipeline outputs. No bundle analysis runs here."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from itibar import data, gold, grades, mudallisin, paths
from itibar.matn import _matn


def grouped(rows, key="group_id"):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return groups


def query(con, sql, params=None):
    cursor = con.execute(sql, params or [])
    fields = [field[0] for field in cursor.description]
    return [dict(zip(fields, row)) for row in cursor.fetchall()]


def read_verdicts(path: Path):
    """Read PR 7's optional group-linked quotations and scored observations."""
    if not path.is_file():
        return {}
    table = pq.read_table(path)
    missing = {"group_id", "quote", "result"} - set(table.column_names)
    if missing:
        raise ValueError(f"{path}: missing verdict columns {', '.join(sorted(missing))}")
    return grouped(row for row in table.to_pylist() if row["group_id"] is not None)


def read_gold(report: Path):
    """Read the two case tables emitted by make gold, keyed by the stable YAML case ID."""
    scoped, mechanisms = {}, {}
    result = None
    for line in report.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        cells = [part.strip() for part in line.strip("|").split("|")]
        if cells[0] == "entry":
            headers = cells
            result = scoped if "scope chains (kept)" in cells else mechanisms
        elif result is not None:
            result[cells[0]] = dict(zip(headers, cells, strict=True))
    cases = gold.entries()
    for case in cases:
        key = case["id"]
        case["scoped"] = scoped[key]
        case["mechanism"] = mechanisms[key]
    return cases


class Corpus:
    def __init__(self, source: Path, out: Path, report_dir: Path, gids=None):
        self.out = out
        self.con = data.views(parquet_dir=source)
        for name, filename in {
            "records": "records.parquet", "chains": "chains.parquet",
            "words": "words.parquet", "census": "narrators.parquet",
        }.items():
            path = out / filename
            if not path.is_file():
                raise ValueError(f"{path} is missing. Run make bundles narrators first.")
            self.con.read_parquet(str(path)).create_view(name)
        for name in ("nodes", "edges"):
            flat = out / f"{name}.parquet"
            partitioned = out / "bundles" / name
            source_file = str(flat if flat.is_file() else partitioned / "**" / "*.parquet")
            self.con.read_parquet(source_file, hive_partitioning=True).create_view(name)
        self.con.execute("CREATE TEMP TABLE selection (group_id BIGINT PRIMARY KEY)")
        if gids is None:
            self.con.execute("INSERT INTO selection SELECT group_id FROM records")
        else:
            self.con.executemany("INSERT INTO selection VALUES (?)", [(gid,) for gid in sorted(set(gids))])
        self.con.execute("""
            CREATE TEMP VIEW reports AS
            SELECT r.*, coalesce(nullif(t.nass, ''), r.nass) AS opening,
                   CASE WHEN t.matn_no = r.matn_no_group THEN t.matn END AS recorded_label
            FROM records r JOIN selection USING (group_id)
            LEFT JOIN meaning_groups m ON m.id = r.group_id
            LEFT JOIN tarafs t ON t.id = m.taraf_id
        """)
        if "receipt_structure" not in self.con.table("reports").columns:
            raise ValueError("The records predate structural receipts. Run make bundles again.")
        self.books = {row["id"]: row for row in query(self.con, """
            SELECT id, name, author_no, author_name, author_death_year FROM books ORDER BY id
        """)}
        self.authors = {row["author_no"]: row for row in self.books.values()}
        self.people = {row["id"]: row for row in query(self.con, """
            SELECT id, name, nickname, death_year, death_year_raw, tabaka, rank_no, rank, has_tadlis FROM rawis
        """)}
        self.tiers = mudallisin.confirmed_tiers()
        self.mudallis_sources = self._mudallis_sources()
        rulings = yaml.safe_load((paths.ROOT / "lists/conditional.yaml").read_text(encoding="utf-8"))["rulings"]
        self.rulings = grouped(rulings, "rawi_id")
        self.cases = read_gold(report_dir / "gold.md")
        self.gold = grouped(self.cases)
        self.verdicts = read_verdicts(out / "verdicts.parquet")
        self.scale = grades.load()

    def _mudallis_sources(self):
        entries = yaml.safe_load((paths.ROOT / "lists/mudallisin.yaml").read_text(encoding="utf-8"))["entries"]
        by_tier = {}
        # The confirmed mapping defines the tier. The book supplies the kind of tadlīs at that tier.
        for entry in entries:
            by_tier.setdefault(entry["tier"], "https://shamela.ws/book/1186/" + ("9" if entry["tier"] < 4 else "10"))
        return by_tier

    def catalog(self):
        return {row["group_id"]: row for row in query(self.con, """
            SELECT group_id, status, opening, n_chains FROM reports ORDER BY group_id
        """)}

    def routes(self):
        """Index existing on-path flags for narrator navigation, including book-role occurrences."""
        rows = query(self.con, """
            SELECT rawi_id, n.group_id, common_link, cut_vertex
            FROM nodes n JOIN selection USING (group_id)
            WHERE on_path AND kind = 'narrator'
            ORDER BY rawi_id, n.group_id
        """)
        return grouped(rows, "rawi_id")

    def census(self):
        return {row["rawi_id"]: row for row in query(self.con, "SELECT * FROM census")}

    def batch(self, lo, hi):
        window = (lo, hi)
        records = query(self.con, "SELECT * FROM reports WHERE group_id BETWEEN ? AND ? ORDER BY group_id", window)
        nodes = grouped(query(self.con, """
            SELECT n.* FROM nodes n JOIN selection USING (group_id)
            WHERE n.group_id BETWEEN ? AND ? ORDER BY n.group_id, n.node
        """, window))
        edges = grouped(query(self.con, """
            SELECT e.group_id, u, v, on_path, continuity, threshold_mask, len(sanad_ids) AS weight
            FROM edges e JOIN selection USING (group_id)
            WHERE e.group_id BETWEEN ? AND ? ORDER BY e.group_id, u, v
        """, window))
        refs = grouped(query(self.con, """
            SELECT DISTINCT h.group_id, h.book_id, h.no_inbook
            FROM hadiths h JOIN selection USING (group_id)
            WHERE h.group_id BETWEEN ? AND ? ORDER BY 1, 2, 3
        """, window))
        texts = {row["group_id"]: row for row in query(self.con, """
            WITH texts AS (
                SELECT h.group_id, h.id AS hadith_id, h.book_id, h.no_inbook, h.nass,
                       h.matn_start, h.matn_end, h.matn_no AS text_code, h.matn AS text_grade,
                       r.derived_best_sanad_id AS best
                FROM hadiths h JOIN reports r ON r.group_id = h.group_id
                LEFT JOIN chains c ON c.sanad_id = r.derived_best_sanad_id
                WHERE h.group_id BETWEEN ? AND ?
                QUALIFY row_number() OVER (PARTITION BY h.group_id
                    ORDER BY (h.nass IS NOT NULL AND h.nass <> '') DESC,
                             (h.id = c.hadith_id) DESC NULLS LAST, h.book_id, h.no_inbook, h.id) = 1
            )
            SELECT t.*, s.id AS sanad_id, s.matn AS chain_grade, s.matn_no AS chain_code, s.hukum
            FROM texts t LEFT JOIN sanads s ON s.hadith_id = t.hadith_id
            QUALIFY row_number() OVER (PARTITION BY t.group_id
                ORDER BY (s.id = t.best) DESC NULLS LAST, s.id) = 1
        """, window)}
        chains = grouped(query(self.con, """
            SELECT c.group_id, c.sanad_id, c.book_id, h.no_inbook, s.matn AS recorded_grade, c.matn_no,
                   c.defects_v2_ibn_hajar, c.defects_v2_ibn_al_salah, c.unnamed_companion,
                   list(struct_pack(rawi := p.rawi_id, word := w.word_raw) ORDER BY p.pos)
                       FILTER (WHERE p.rawi_id IS NOT NULL) AS people
            FROM chains c JOIN selection USING (group_id)
            JOIN hadiths h ON h.id = c.hadith_id
            JOIN sanads s ON s.id = c.sanad_id
            LEFT JOIN sanad_rawis p ON p.sanad_id = c.sanad_id
            LEFT JOIN words w ON w.sanad_id = p.sanad_id AND w.pos = p.pos
            WHERE c.group_id BETWEEN ? AND ?
            GROUP BY ALL ORDER BY c.group_id, c.book_id, h.no_inbook, c.sanad_id
        """, window))
        for row in records:
            gid = row["group_id"]
            text = texts.get(gid, {})
            text["content"] = _matn(text.get("nass"), text.get("matn_start"), text.get("matn_end")).strip()
            yield row, nodes[gid], edges[gid], refs[gid], text, chains[gid]

    def name(self, rid):
        p = self.people.get(rid, {})
        return p.get("nickname") or p.get("name") or f"Narrator {rid}"

    def node(self, node):
        kind, key = node[0], node[1:]
        if kind == "r":
            return self.name(int(key))
        if kind == "b":
            return self.books[int(key)]["name"]
        if kind == "c":
            return self.authors[int(key)]["author_name"]
        return {"P": "النبي ﷺ", "u": "رجل من أصحاب النبي ﷺ", "m": "اسم مبهم", "g": "موضع انقطاع"}.get(kind, node)


def receipts(record, representative):
    if record["status"] != "ok":
        return {}
    steps = json.loads(record["receipt_structure"])
    steps["grade-v1"] = json.loads(record["receipt"])
    steps.update(json.loads(record["receipt_v2"]))
    steps["source"] = [
        {"check": "Recorded group grade", "rule": "Read meaning_groups.matn_no from hadith-kg.",
         "data": {"group_id": record["group_id"]}, "result": record["matn_no_group"]},
        {"check": "Recorded text and chain", "rule": "Read hadiths.matn and sanads.matn and hukum for the cited occurrence.",
         "data": {key: representative.get(key) for key in ("hadith_id", "sanad_id", "text_grade", "chain_grade")},
         "result": representative.get("hukum")},
    ]
    return steps
