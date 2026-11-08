"""`make figures`:
fig1 — distribution of kappa across all groups at each of the four thresholds;
fig2 — heatmap of width by tabaka for groups recorded in al-Bukhari, in Muslim,
       in other Sahih/mustakhraj books (books.tasnif_no = 1), and the rest.
Each figure is written as PNG + SVG with a CSV of the plotted numbers beside it."""

from __future__ import annotations

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from itibar import paths  # noqa: E402

# reference palette (dataviz skill, light mode): sequential blue ramp + text tokens
BLUE = {100: "#cde2fb", 150: "#b7d3f6", 200: "#9ec5f4", 250: "#86b6ef", 300: "#6da7ec", 350: "#5598e7",
        400: "#3987e5", 450: "#2a78d6", 500: "#256abf", 550: "#1c5cab", 600: "#184f95", 650: "#104281",
        700: "#0d366b"}
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
THRESHOLDS = [("all", "everyone"), ("above_matruk", "above matruk"), ("saduq_up", "saduq and above"),
              ("thiqa_up", "thiqa and above")]
ORDINAL = [BLUE[250], BLUE[400], BLUE[550], BLUE[700]]   # nested thresholds: lighter = looser

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def _records() -> pd.DataFrame:
    r = pd.read_parquet(paths.records_path())
    return r[r["status"] == "ok"].copy()


def fig1(out_dir) -> pd.DataFrame:
    r = _records()
    n = len(r)
    ks = np.arange(1, 81)
    surv = pd.DataFrame({"k": ks})
    for col, _ in THRESHOLDS:
        v = r[f"kappa_{col}"].to_numpy()
        surv[col] = [(v >= k).mean() for k in ks]
    bins = [(0, 0, "0"), (1, 1, "1"), (2, 4, "2–4"), (5, 9, "5–9"), (10, 10**9, "10+")]
    share = pd.DataFrame([{"threshold": lab, **{b[2]: ((r[f"kappa_{c}"] >= b[0]) & (r[f"kappa_{c}"] <= b[1])).mean()
                                                for b in bins}} for c, lab in THRESHOLDS])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.25, 1]})
    for (col, lab), colr in zip(THRESHOLDS, ORDINAL):
        a1.plot(surv["k"], surv[col].where(surv[col] > 0), color=colr, lw=2, solid_capstyle="round",
                drawstyle="steps-post")
    a1.set_xscale("log")
    a1.set_yscale("log")
    a1.set_xlim(1, 100)
    a1.set_ylim(1 / n / 2, 1.05)
    a1.set_xlabel("κ (vertex-disjoint routes from PROPHET to the books)")
    a1.set_ylabel("share of groups with κ ≥ k")
    a1.grid(True, which="major", color=GRID, lw=0.6)
    a1.set_title(f"κ across {n:,} meaning groups, by narrator-grade threshold")
    a1.legend([plt.Line2D([], [], color=c, lw=2) for c in ORDINAL], [t[1] for t in THRESHOLDS],
              frameon=False, loc="lower left", fontsize=8)
    seq = [BLUE[150], BLUE[300], BLUE[450], BLUE[600], BLUE[700]]
    left = np.zeros(len(share))
    y = np.arange(len(share))[::-1]
    for (lo, hi, lab), colr in zip(bins, seq):
        w = share[lab].to_numpy()
        a2.barh(y, w, left=left, color=colr, edgecolor=SURFACE, linewidth=2, height=0.62, label=f"κ = {lab}")
        for yi, li, wi in zip(y, left, w):
            if wi >= 0.06:
                a2.text(li + wi / 2, yi, f"{wi:.0%}", ha="center", va="center", fontsize=7.5,
                        color="#ffffff" if colr in (BLUE[450], BLUE[600], BLUE[700]) else INK)
        left += w
    a2.set_yticks(y, share["threshold"])
    a2.set_xlim(0, 1)
    a2.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    a2.set_title("share of groups by κ")
    a2.legend(ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=8,
              handlelength=1, columnspacing=1)
    a2.spines["left"].set_visible(False)
    a2.tick_params(axis="y", length=0)
    fig.text(0.01, 0.005, "κ = 0: no unbroken route from a companion to a book at that threshold. "
             "Source: hadith-kg (CC-BY-4.0), itibar records.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    for ext in ("png", "svg"):
        fig.savefig(out_dir / f"fig1_kappa.{ext}", dpi=200)
    plt.close(fig)
    surv.to_csv(out_dir / "fig1_kappa_survival.csv", index=False)
    share.to_csv(out_dir / "fig1_kappa_share.csv", index=False)
    return share


WIDTH_BINS = [(0, 0, "0"), (1, 1, "1"), (2, 2, "2"), (3, 4, "3–4"), (5, 8, "5–8"), (9, 16, "9–16"),
              (17, 32, "17–32"), (33, 10**9, "33+")]
MAX_LAYER = 16


def fig2(out_dir) -> pd.DataFrame:
    r = _records()
    r = r[r["n_narrators_on_path"] > 0]
    ch = duckdb.sql(f"""SELECT c.group_id, max((c.book_id = 1)::INT) AS bukhari, max((c.book_id = 2)::INT) AS muslim,
                        max((b.tasnif_no = 1)::INT) AS sahih
                        FROM read_parquet('{paths.chains_path().as_posix()}') c
                        JOIN read_parquet('{(paths.PARQUET_DIR / 'books.parquet').as_posix()}') b ON b.id = c.book_id
                        GROUP BY 1""").df()
    r = r.merge(ch, on="group_id")
    cats = [("al-Bukhari", r["bukhari"] == 1), ("Muslim", r["muslim"] == 1),
            ("other Sahih / mustakhraj (tasnif 1)", (r["sahih"] == 1) & (r["bukhari"] == 0) & (r["muslim"] == 0)),
            ("rest of the corpus", r["sahih"] == 0)]
    rows = []
    mats = []
    for name, mask in cats:
        sub = r[mask]
        W = np.zeros((len(sub), MAX_LAYER), dtype=int)
        for i, prof in enumerate(sub["width_profile"]):
            for e in prof:
                if 1 <= e["layer"] <= MAX_LAYER:
                    W[i, e["layer"] - 1] = e["width"]
        M = np.zeros((len(WIDTH_BINS), MAX_LAYER))
        for j, (lo, hi, lab) in enumerate(WIDTH_BINS):
            M[j] = ((W >= lo) & (W <= hi)).mean(axis=0)
            for L in range(MAX_LAYER):
                rows.append({"panel": name, "groups": len(sub), "layer": L + 1, "width_bin": lab, "share": M[j, L]})
        med = np.median(W, axis=0)
        mats.append((name, len(sub), M, med))
    cmap = LinearSegmentedColormap.from_list("seq", [SURFACE] + [BLUE[k] for k in (100, 200, 300, 400, 500, 600, 700)])
    fig, axes = plt.subplots(1, 4, figsize=(13, 4.0), sharey=True)
    for ax, (name, ng, M, med) in zip(axes, mats):
        im = ax.imshow(M, origin="lower", aspect="auto", cmap=cmap, vmin=0, vmax=0.6,
                       extent=(0.5, MAX_LAYER + 0.5, -0.5, len(WIDTH_BINS) - 0.5))
        ax.set_title(f"{name}\n{ng:,} groups", fontsize=9)
        ax.set_xticks(range(1, MAX_LAYER + 1, 3))
        ax.set_xlabel("layer (tabaka)")
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].set_yticks(range(len(WIDTH_BINS)), [b[2] for b in WIDTH_BINS])
    axes[0].set_ylabel("narrators on path at that layer (width)")
    fig.subplots_adjust(left=0.06, right=0.9, bottom=0.17, top=0.8, wspace=0.08)
    cax = fig.add_axes((0.915, 0.17, 0.01, 0.63))
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("share of groups (column sums to 1)", color=INK2)
    cb.outline.set_visible(False)
    fig.suptitle("Width by tabaka: groups recorded in the Sahihayn vs the rest", x=0.01, ha="left",
                 fontweight="bold", fontsize=10)
    fig.text(0.01, 0.005, "A group appears in every panel whose books record it (al-Bukhari and Muslim overlap). "
             "Width counts distinct narrators on a PROPHET→book route. Source: hadith-kg (CC-BY-4.0).",
             fontsize=7, color=MUTED)
    for ext in ("png", "svg"):
        fig.savefig(out_dir / f"fig2_width_by_tabaka.{ext}", dpi=200)
    plt.close(fig)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "fig2_width_by_tabaka.csv", index=False)
    return df


def main() -> None:
    out = paths.FIGURES_DIR
    out.mkdir(parents=True, exist_ok=True)
    s = fig1(out)
    print(s.to_string(index=False))
    fig2(out)
    print(f"wrote figures to {out}")


if __name__ == "__main__":
    main()
