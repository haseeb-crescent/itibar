"""Narrator grade ordinal, built from rawis.rank_no (Ibn Hajar's Taqrib levels).
See config/grades.yaml for the mapping and the reasoning behind it."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from itibar import config, paths

UNKNOWN = 0


@dataclass(frozen=True)
class GradeScale:
    level_ordinal: dict[int, int]       # rank_no -> ordinal
    level_code: dict[int, int]          # rank_no -> hukm code
    level_name: dict[int, str]
    ordinal_code: dict[int, int]        # ordinal -> hukm code (unknown included)
    unknown_code: int
    companion_rank_nos: frozenset[int]
    companion_exclude_labels: frozenset[str]
    placeholders: dict[int, dict]
    thresholds: dict[str, int]          # name -> min ordinal (ordered)
    hukm_codes: dict[int, str]

    def ordinal(self, rank_no: int | None, is_stub: bool = False, rawi_id: int | None = None) -> int:
        if is_stub or rank_no is None or rank_no == 0:
            return UNKNOWN
        if rawi_id is not None and rawi_id in self.placeholders:
            return UNKNOWN
        return self.level_ordinal.get(int(rank_no), UNKNOWN)

    def is_companion(self, rank_no: int | None, label: str | None) -> bool:
        if rank_no is None or int(rank_no) not in self.companion_rank_nos:
            return False
        return (label or "").strip() not in self.companion_exclude_labels

    def code_of_ordinal(self, ordinal: int) -> int:
        return self.ordinal_code.get(ordinal, self.unknown_code)

    def rank_no_of_ordinal(self, ordinal: int) -> int | None:
        for r, o in self.level_ordinal.items():
            if o == ordinal:
                return r
        return None

    def name_of_ordinal(self, ordinal: int) -> str:
        r = self.rank_no_of_ordinal(ordinal)
        return self.level_name.get(r, "unknown") if r is not None else "unknown"


def load() -> GradeScale:
    g = config.load("grades")
    levels = {int(k): v for k, v in g["levels"].items()}
    ordinal_code = {v["ordinal"]: v["code"] for v in levels.values()}
    ordinal_code[UNKNOWN] = g["unknown"]["code"]
    thresholds = {name: int(t["min_ordinal"]) for name, t in g["thresholds"].items()}
    return GradeScale(
        level_ordinal={k: v["ordinal"] for k, v in levels.items()},
        level_code={k: v["code"] for k, v in levels.items()},
        level_name={k: v["taqrib"] for k, v in levels.items()},
        ordinal_code=ordinal_code,
        unknown_code=g["unknown"]["code"],
        companion_rank_nos=frozenset(int(x) for x in g["companion"]["rank_no"]),
        companion_exclude_labels=frozenset(g["companion"].get("exclude_labels") or []),
        placeholders={int(k): v for k, v in g["placeholders"].items()},
        thresholds=thresholds,
        hukm_codes={int(k): v for k, v in g["hukm_codes"].items()},
    )


def write_labels(con) -> int:
    """Regenerate the `labels` section of config/grades.yaml from the data:
    every observed (rank_no, rank) label with its count and ordinal."""
    scale = load()
    ph = ",".join(str(i) for i in scale.placeholders) or "-1"
    rows = con.sql(
        "SELECT rank_no, coalesce(rank, '') AS rank, count(*) AS n, sum(is_stub) AS stubs, "
        f"sum((id IN ({ph}))::int) AS placeholders "
        "FROM rawis GROUP BY 1, 2 ORDER BY 1, n DESC, 2"
    ).fetchall()
    labels: dict[int, list] = {}
    for rank_no, rank, n, stubs, nph in rows:
        if nph and nph == n:
            entry = {"label": rank, "n": int(n), "ordinal": None,
                     "note": "placeholders (break markers / unnamed person), not narrators; see `placeholders`"}
            labels.setdefault(int(rank_no), []).append(entry)
            continue
        ordinal = scale.ordinal(rank_no, is_stub=bool(stubs and stubs == n))
        entry = {"label": rank, "n": int(n), "ordinal": ordinal}
        if stubs and stubs == n:
            entry["note"] = "stub narrators (never described in the source)"
        if rank_no in scale.companion_rank_nos:
            entry["companion"] = scale.is_companion(rank_no, rank)
        labels.setdefault(int(rank_no), []).append(entry)
    path = paths.CONFIG_DIR / "grades.yaml"
    text = path.read_text(encoding="utf-8")
    head = text.split("\nlabels:", 1)[0].rstrip() + "\n\n"
    body = yaml.safe_dump({"labels": labels}, allow_unicode=True, sort_keys=False, width=200)
    path.write_text(head + body, encoding="utf-8")
    config.load.cache_clear()
    return sum(len(v) for v in labels.values())
