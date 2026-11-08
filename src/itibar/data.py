"""`make data`: fetch hadith-kg.db (pinned revision, verified digest) and convert
its tables to Parquet. The SQLite file is opened read-only + immutable, so not
even a -wal/-shm sidecar is written next to it."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import time
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from itibar import config, paths

BATCH = 250_000

_SQL_TO_ARROW = {
    "INTEGER": pa.int64(),
    "TEXT": pa.string(),
    "REAL": pa.float64(),
    "BLOB": pa.binary(),
}


def sha256(path: Path, bufsize: int = 1 << 24) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(bufsize):
            h.update(chunk)
    return h.hexdigest()


def download() -> Path:
    cfg = config.load("source")["huggingface"]
    dest = paths.SOURCE_DB
    if not dest.exists():
        from huggingface_hub import hf_hub_download

        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"downloading {cfg['repo_id']}/{cfg['filename']} @ {cfg['revision'][:10]} ...")
        got = hf_hub_download(
            repo_id=cfg["repo_id"],
            repo_type=cfg["repo_type"],
            filename=cfg["filename"],
            revision=cfg["revision"],
            local_dir=str(paths.DATA_DIR),
        )
        dest = Path(got)
    digest = sha256(dest)
    if digest != cfg["sha256"]:
        sys.exit(
            f"sha256 mismatch for {dest}: got {digest}, expected {cfg['sha256']}.\n"
            "Refusing to continue: the pinned input is not the file on disk."
        )
    print(f"source ok: {dest} sha256={digest[:16]}…")
    return dest


def connect_source(db: Path | None = None) -> sqlite3.Connection:
    db = db or paths.SOURCE_DB
    uri = f"file:{db.resolve()}?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def _schema(con: sqlite3.Connection, table: str) -> pa.Schema:
    cols = con.execute(f"PRAGMA table_info({table})").fetchall()
    fields = []
    for _cid, name, typ, _notnull, _dflt, _pk in cols:
        fields.append(pa.field(name, _SQL_TO_ARROW.get((typ or "TEXT").upper(), pa.string())))
    return pa.schema(fields)


def convert_table(con: sqlite3.Connection, table: str, out_dir: Path) -> int:
    schema = _schema(con, table)
    names = schema.names
    out = out_dir / f"{table}.parquet"
    tmp = out.with_suffix(".parquet.tmp")
    cur = con.execute(f"SELECT {', '.join(names)} FROM {table} ORDER BY rowid" if _has_rowid(con, table)
                      else f"SELECT {', '.join(names)} FROM {table}")
    n = 0
    with pq.ParquetWriter(tmp, schema, compression="zstd") as w:
        while rows := cur.fetchmany(BATCH):
            cols = list(zip(*rows))
            arrays = [pa.array(c, type=f.type) for c, f in zip(cols, schema)]
            w.write_table(pa.Table.from_arrays(arrays, schema=schema))
            n += len(rows)
    tmp.replace(out)
    return n


def _has_rowid(con: sqlite3.Connection, table: str) -> bool:
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
    return "WITHOUT ROWID" not in sql.upper()


def convert(db: Path | None = None, out_dir: Path | None = None, tables: list[str] | None = None) -> None:
    out_dir = out_dir or paths.PARQUET_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    con = connect_source(db)
    tables = tables or config.load("source")["tables"]
    for t in tables:
        t0 = time.time()
        n = convert_table(con, t, out_dir)
        print(f"  {t:16s} {n:>10,} rows  {time.time() - t0:5.1f}s")
    con.close()
    write_derived(out_dir)
    write_duckdb(out_dir)


def write_derived(out_dir: Path) -> None:
    """Derived tables computed once from the full corpus and kept beside the
    source tables (so a sampled fixture reproduces them exactly)."""
    from itibar import load

    con = views(parquet_dir=out_dir)
    bc = load.compute_book_compilers(con)
    pq.write_table(pa.Table.from_pandas(bc, preserve_index=False), out_dir / "book_compilers.parquet",
                   compression="zstd")
    print(f"  {'book_compilers':16s} {len(bc):>10,} rows  (derived)")


def write_duckdb(parquet_dir: Path) -> Path:
    """A small DuckDB catalogue of views over the Parquet files, for ad-hoc
    querying (`duckdb data/parquet/hkg.duckdb`). Views hold absolute paths;
    `make data` regenerates the file."""
    path = parquet_dir / "hkg.duckdb"
    if path.exists():
        path.unlink()
    con = duckdb.connect(str(path))
    for p in sorted(parquet_dir.glob("*.parquet")):
        con.execute(f"CREATE VIEW {p.stem} AS SELECT * FROM read_parquet('{p.resolve().as_posix()}')")
    con.close()
    return path


def views(con: duckdb.DuckDBPyConnection | None = None, parquet_dir: Path | None = None) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB connection with one view per Parquet table."""
    parquet_dir = parquet_dir or paths.PARQUET_DIR
    con = con or duckdb.connect()
    for p in sorted(parquet_dir.glob("*.parquet")):
        con.execute(f"CREATE OR REPLACE VIEW {p.stem} AS SELECT * FROM read_parquet('{p.as_posix()}')")
    return con


def main() -> None:
    download()
    convert()


if __name__ == "__main__":
    main()
