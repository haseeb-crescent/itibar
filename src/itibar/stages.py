"""`make stages`: the PR 5 corrections applied cumulatively, for the audit's before/after
tables (reports/audit.md, section 11). Each config/stages/<name>.yaml is deep-merged over
config/ (ITIBAR_CONFIG_OVERRIDE) and the pipeline reruns into out/stages/<name>/ (records
and chains only; out/words.parquet and the matn tokens are shared). Stage 0 reproduces
PR 4; the last stage equals the defaults (`make bundles`)."""

from __future__ import annotations

import os
import subprocess
import sys
import time

from itibar import paths

STAGES_DIR = paths.CONFIG_DIR / "stages"


def stage_files() -> list:
    return sorted(STAGES_DIR.glob("s*.yaml"))


def out_dir(stem: str):
    return paths.OUT_DIR / "stages" / stem


def run(only: list[str] | None = None) -> None:
    for f in stage_files():
        if only and f.stem not in only:
            continue
        od = out_dir(f.stem)
        od.mkdir(parents=True, exist_ok=True)
        for shared in ("words.parquet", "matn_tokens.parquet", "matn_vocab.parquet"):
            src, dst = paths.OUT_DIR / shared, od / shared
            if src.exists() and not dst.exists():
                os.symlink(src, dst)
        env = {**os.environ, "ITIBAR_CONFIG_OVERRIDE": str(f), "ITIBAR_OUT_DIR": str(od)}
        t0 = time.time()
        subprocess.run([sys.executable, "-m", "itibar.pipeline", "--records-only"], env=env, check=True)
        print(f"{f.stem}: {time.time() - t0:.0f}s -> {od}", file=sys.stderr)


if __name__ == "__main__":
    run(sys.argv[1:] or None)
