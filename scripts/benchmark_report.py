"""Part 4 report: a DuckDB SQL layer and a survival benchmark for lenders and advisers.

Runs every file in sql/ over the committed snapshot and writes:
- results/BENCHMARK.md            the report (every figure comes from this script)
- results/benchmark.csv           state x industry division x size band: observed, national, adjusted, flags
- results/benchmark_fit.csv       how well "national rate + state adjustment" reproduces the measurable cells
- results/perturbation_check.csv  summed perturbed cells vs exact figures, with the share in small cells
- results/sql_parity.csv          the SQL views vs the Part 1-3 pandas functions, column by column
- results/charts/15-17 *.png
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.profile_source import (  # noqa: E402  (also sets the shared chart style)
    BLUE, CHARTS, GRID, INK, INK_2, MUTED, ORANGE, RESULTS, SAVE, SURFACE, n, pct, plt, rate,
)
from scripts.industry_survival import pts  # noqa: E402
from cabee import sql  # noqa: E402

import matplotlib.colors as mcolors  # noqa: E402
import pandas as pd  # noqa: E402

BANDS = ["Non-employing", "1-4", "5+"]
SMALL_BASE, RELIABLE_BASE, MAX_SMALL_SHARE = 20, 100, 0.10   # must match the macros in sql/01_sources.sql
# Sequential blue ramp (reference palette, steps 100-700)
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# Worked examples: a café or takeaway with a few staff, and a sole-trader tradie.
EXAMPLES = [("Accommodation and Food Services", "1-4"), ("Construction", "Non-employing")]


def short(ind: str) -> str:
    return (ind.replace(" and ", " & ").replace("Professional, Scientific & Technical", "Professional & Technical")
            .replace("Electricity, Gas, Water & Waste", "Electricity, Gas & Water")
            .replace("Information Media & Telecommunications", "Info Media & Telecoms")
            .replace("Agriculture, Forestry & Fishing", "Agriculture"))


def band_name(b: str) -> str:
    return {"Non-employing": "non-employing", "1-4": "1-4 employees", "5+": "5+ employees"}[b]


# ------------------------------------------------------------------ charts
def chart_bias(pc: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    st = pc[pc.check_type == "state x size band"]
    dv = pc[pc.check_type == "industry division"]
    ax.axhline(0, color=GRID, linewidth=1, zorder=0)
    ax.axvline(100 * MAX_SMALL_SHARE, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=0)
    ax.scatter(100 * st.small_share, st.bias, s=46, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
               marker="o", label="State × size band: cells vs state totals")
    ax.scatter(100 * dv.small_share, dv.bias, s=46, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
               marker="s", label="Industry: cells vs data cube 1")
    worst = pc.nsmallest(4, "bias").sort_values("small_share", kind="stable")
    for k, (_, r) in enumerate(worst.iterrows()):
        dy = -12 if k % 2 else 10   # alternate below/above so neighbouring labels don't collide
        ax.annotate(r["label"], (100 * r.small_share, r.bias), xytext=(0, dy), textcoords="offset points",
                    ha="center", va="center", fontsize=8, color=INK_2)
    ax.text(100 * MAX_SMALL_SHARE + 1, -14, f"{pct(MAX_SMALL_SHARE, 0)}: the most a “reliable”\nrate may have in small cells",
            fontsize=8, color=INK_2, va="center")
    ax.set_xlabel("Share of the entrants that sit in cells of 20 or fewer (%)")
    ax.set_ylabel("Summed cells minus exact rate (points)")
    ax.set_xlim(-2, 102)
    ax.set_ylim(pc.bias.min() - 2.5, 1.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0.13, 0.0), fontsize=8.5)
    fig.text(0.015, 0.975, "The more entrants in tiny cells, the further survival reads too low", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.93, "2021-22 entrants still trading in June 2025: rate from summing data cube 5's perturbed cells "
             "minus the exact rate", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_fit(fit: pd.DataFrame, path: Path) -> None:
    f = fit.iloc[::-1].reset_index(drop=True)   # All states at the bottom, NSW at the top
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for i, r in f.iterrows():
        ax.plot([r.mae_national, r.mae_adjusted], [i, i], color=GRID, linewidth=3, zorder=1)
    ax.scatter(f.mae_national, f.index, s=60, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=3,
               label="National rate for the industry and size band")
    ax.scatter(f.mae_adjusted, f.index, s=60, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=4, marker="D",
               label="National rate + the state adjustment")
    for i, r in f.iterrows():
        ax.text(max(r.mae_national, r.mae_adjusted) + 0.12, i, f"{int(r.cells)} cells", va="center", fontsize=8,
                color=INK_2)
    ax.set_yticks(f.index, [s if s != "All states" else "All states" for s in f.state], fontsize=9)
    for lbl in ax.get_yticklabels():
        if lbl.get_text() == "All states":
            lbl.set_fontweight("bold")
    ax.set_xlabel("Average gap to the state's own rate (points)")
    ax.set_xlim(0, max(f.mae_national.max(), f.mae_adjusted.max()) + 1.2)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.16), ncol=2, fontsize=8.5)
    st = fit[fit.state != "All states"]
    k = int((st.mae_adjusted < st.mae_national).sum())
    fig.text(0.015, 0.975, f"Adding the state adjustment brings the national rate closer in {k} of {len(st)} states",
             fontsize=12, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.93, "Cells where both the state's own and the national rate are reliable, 2021-22 entrants "
             "to June 2025", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0.02, 1, 0.9))
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_grid(b: pd.DataFrame, path: Path) -> None:
    cmap = mcolors.LinearSegmentedColormap.from_list("blue", RAMP)
    lo, hi = 25, 80
    norm = mcolors.Normalize(lo, hi)
    order = (b[b.band == "Non-employing"].drop_duplicates("industry").sort_values("national_rate", ascending=False, kind="stable")
             .industry.tolist())
    states = b.drop_duplicates("abbr").sort_values("state_order", kind="stable").abbr.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(13, 8.2), sharey=True)
    for ax, band in zip(axes, ["Non-employing", "1-4"]):
        t = b[b.band == band].set_index(["industry", "abbr"])
        for i, ind in enumerate(order):
            for j, st in enumerate(states):
                r = t.loc[(ind, st)]
                x, y = j, i
                if pd.isna(r.benchmark):
                    ax.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor=SURFACE, edgecolor=GRID, lw=0.8))
                    ax.text(x, y, "–", ha="center", va="center", fontsize=8, color=MUTED)
                    continue
                c = cmap(norm(r.benchmark))
                hatch = "////" if r.benchmark_source != "this state" else None
                ax.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor=c, edgecolor=SURFACE, lw=2,
                                           hatch=hatch))
                lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
                ax.text(x, y, f"{r.benchmark:.0f}", ha="center", va="center", fontsize=8,
                        color=SURFACE if lum < 0.45 else INK,
                        bbox=dict(boxstyle="square,pad=0.1", fc=c, ec="none") if hatch else None)
        ax.set_xlim(-0.5, len(states) - 0.5)
        ax.set_ylim(len(order) - 0.5, -0.5)
        ax.set_xticks(range(len(states)), states, fontsize=9)
        ax.xaxis.tick_top()
        ax.set_yticks(range(len(order)), [short(i) for i in order], fontsize=9)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title({"Non-employing": "Non-employing entrants", "1-4": "Entrants with 1-4 employees"}[band], loc="left", fontsize=10.5, color=INK, pad=24)
    plt.rcParams["hatch.color"] = SURFACE
    fig.text(0.015, 0.985, "Survival benchmark: share of 2021-22 entrants still trading in June 2025 (%)",
             fontsize=12, fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.955, "Plain cell: the state's own rate (reliable). Hatched: national rate for the industry "
             "and band + the state adjustment. “–”: too few entrants to benchmark. Rows: highest non-employing "
             "survival first.", fontsize=9, color=INK_2, va="top")
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cax = fig.add_axes((0.80, 0.035, 0.17, 0.014))
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=8, colors=INK_2)
    cb.set_ticks([30, 40, 50, 60, 70, 80])
    fig.text(0.80, 0.06, "Still trading (%)", fontsize=8.5, color=INK_2)
    fig.subplots_adjust(left=0.19, right=0.985, top=0.86, bottom=0.09, wspace=0.06)
    fig.savefig(path, **SAVE)
    plt.close(fig)


# ------------------------------------------------------------------ report
def main() -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    con = sql.connect()
    # the Python constants above describe the SQL macros; make sure they agree
    macros = con.execute("SELECT small_base(), reliable_base(), max_small_share()").fetchone()
    assert tuple(macros) == (SMALL_BASE, RELIABLE_BASE, MAX_SMALL_SHARE), macros

    par = sql.parity_checks(con)
    pc = sql.table(con, "perturbation_check")
    b = sql.table(con, "benchmark")
    fit = sql.table(con, "benchmark_fit")
    db = sql.table(con, "division_bands").set_index("industry")
    sb = sql.table(con, "state_bands").set_index("state")
    nb = sql.query(con, "SELECT band, weight FROM national_bands WHERE cohort = '2021-22'").set_index("band")["weight"]
    views = {f.name: [line.split("VIEW ", 1)[1].split()[0] for line in f.read_text().splitlines()
                      if line.startswith("CREATE OR REPLACE VIEW")] for f in sql.files()}

    par.assign(max_abs_diff=par["max_abs_diff"].round(12)).to_csv(RESULTS / "sql_parity.csv", index=False)
    pc.round(4).to_csv(RESULTS / "perturbation_check.csv", index=False)
    b.drop(columns=["state_order"]).round(4).to_csv(RESULTS / "benchmark.csv", index=False)
    fit.drop(columns=["state_order"]).round(4).to_csv(RESULTS / "benchmark_fit.csv", index=False)
    chart_bias(pc, CHARTS / "15_perturbation_bias.png")
    chart_fit(fit, CHARTS / "16_state_adjustment_fit.png")
    chart_grid(b, CHARTS / "17_benchmark_grid.png")

    # ---- parity
    n_checks, n_bad = len(par), int(par["mismatches"].sum())
    n_tables = par[["part", "table"]].drop_duplicates().shape[0]
    n_values = int(par["rows"].sum())
    max_diff = float(par["max_abs_diff"].max())
    assert n_bad == 0 and max_diff < 1e-12, par[par.mismatches > 0]

    # ---- perturbation
    ok = pc[pc.small_share <= MAX_SMALL_SHARE]
    over = pc[pc.small_share > MAX_SMALL_SHARE]
    worst_ok = ok.loc[ok.bias.abs().idxmax()]
    worst = pc.loc[pc.bias.idxmin()]
    assert (pc.bias <= 0.05).all()   # "never reads materially high" below
    st_ = pc[pc.check_type == "state x size band"]
    dv = pc[pc.check_type == "industry division"].set_index("label")
    st5 = st_[st_.band == "5+"]
    # Part 2 sensitivity: shift each division's band rates by its own measured bias, re-rank at the common mix
    adj = db[[f"rate_{x}" for x in BANDS]].sub(dv["bias"].reindex(db.index), axis=0)
    std_adj = sum(adj[f"rate_{x}"] * nb[x] for x in BANDS)
    r0, r1 = db["std"].rank(method="min"), std_adj.rank(method="min")
    max_move = int((r1 - r0).abs().max())
    bottom5_same = set(r0.nsmallest(5).index) == set(r1.nsmallest(5).index)
    big_bias = dv[dv.bias < -1].sort_values("bias", kind="stable")
    n12, n_cube5 = con.execute("SELECT count(*) FILTER (WHERE base IN (1, 2) OR survived IN (1, 2)), count(*) "
                               "FROM subdivision_survival WHERE level = 'group'").fetchone()
    assert n12 == 0

    # ---- benchmark coverage
    cov = b.groupby("band").agg(cells=("benchmark", "size"), own=("benchmark_source", lambda s: (s == "this state").sum()),
                                adj=("benchmark_source", lambda s: (s == "national + state adjustment").sum()),
                                none=("benchmark_source", lambda s: (s == "none").sum()),
                                entrants=("entrants", "sum"))
    cov["covered"] = b[b.benchmark.notna()].groupby("band")["entrants"].sum().reindex(cov.index).fillna(0)
    cov = cov.loc[BANDS]
    share_cov = cov["covered"].sum() / cov["entrants"].sum()
    flags = b.groupby(["band", "observed_flag"]).size().unstack(fill_value=0).loc[BANDS]
    five = cov.loc["5+"]

    # ---- fit
    allf = fit[fit.state == "All states"].iloc[0]
    sf = fit[fit.state != "All states"]
    better = sf[sf.mae_adjusted < sf.mae_national]
    worse = sf[sf.mae_adjusted >= sf.mae_national]
    gain = (sf.mae_national - sf.mae_adjusted)
    top_gain = sf.loc[gain.nlargest(3).index]
    # "largest state effect" claim: the 3 biggest gains are the 3 biggest adjustments
    assert set(top_gain.state) == set(sf.loc[sf.state_adjustment.abs().nlargest(3).index, "state"])

    # ---- what it says
    rel = b[b.observed_flag == "reliable"]
    both = rel[rel.national_flag == "reliable"].copy()
    both["vs_adjusted"] = both.observed - both.national_rate - both.state_adjustment
    big_gap = both.reindex(both.vs_adjusted.abs().sort_values(ascending=False, kind="stable").index)
    n_far = int((both.vs_adjusted.abs() > 5).sum())
    low = rel.nsmallest(5, "observed")
    high = rel.nlargest(5, "observed")
    nat_rel = b[b.national_flag == "reliable"].drop_duplicates(["division", "band"])
    ne_rel, e14_rel = rel[rel.band == "Non-employing"], rel[rel.band == "1-4"]
    # employing-vs-non-employing gap within the same state and industry (both reliable)
    pair = rel.pivot_table(index=["abbr", "industry"], columns="band", values="observed").dropna(
        subset=["Non-employing", "1-4"])
    pair_gap = pair["1-4"] - pair["Non-employing"]
    n_pair_pos = int((pair_gap > 0).sum())

    L: list[str] = []
    a = L.append
    a("# Part 4: a SQL layer and a survival benchmark for lenders and advisers")
    a("")
    a("Generated by `scripts/benchmark_report.py` from the SQL in `sql/`, run by DuckDB directly over the committed "
      "snapshot (`data/*.csv.gz`). Every figure below comes from that script.")
    a("")
    a("**Question:** if a lender or adviser knows a new business's industry, state and size, what share of businesses "
      "like it were still trading three years on, and how much can that figure be trusted?")
    a("")

    # 1. the SQL layer
    a("## 1. The SQL layer")
    a("")
    a("Seven SQL files build every table the benchmark needs as DuckDB views over the gzipped CSVs, so no database "
      "file is written and any DuckDB client gives the same answers. The rules from Part 1 (the 20-business floor, "
      "the three size bands, the one detail cohort) are SQL macros in the first file, so every view uses the same ones.")
    a("")
    a("| File | Views |")
    a("|---|---|")
    for f, v in views.items():
        a(f"| `sql/{f}` | {', '.join(f'`{x}`' for x in v)} |")
    a("")
    a("**The SQL gives the same numbers as the pandas analysis.** `cabee.sql.parity_checks` rebuilds "
      f"{n_tables} tables from Parts 1-3 in SQL (national cohorts, industries across cohorts and within size bands, "
      f"states across cohorts and after their mix, LGA growth) and compares {n_checks} columns, {n(n_values)} values "
      f"in all, with the pandas functions: **{n_bad} mismatches**; every difference is below 1e-12, i.e. "
      "floating-point rounding. The column-by-column result is in `results/sql_parity.csv`.")
    a("")

    # 2. perturbation
    a("## 2. Before benchmarking: how much perturbation pulls small cells down")
    a("")
    a("To protect confidentiality the ABS perturbs data cube 5. One visible sign: across its "
      f"{n(n_cube5)} subdivision cells, no count of 1 or 2 appears (published counts jump from 0 to 3). A benchmark for one industry in one state and size band is a sum of such "
      "cells, so the question is how far a sum of small cells drifts from the truth. Two places publish both a sum of "
      "cells and an exact figure: each state × size band (its subdivision cells vs the state-total rows), and each "
      "industry division (its cells summed over states vs data cube 1, which isn't perturbed).")
    a("")
    a(f"- **Summed cells read low, and the more entrants sit in cells of {SMALL_BASE} or fewer, the lower.** "
      f"The worst case is {worst['label']}: {rate(worst.rate_cells)} from the cells against {rate(worst.rate_exact)} "
      f"exact ({pts(worst.bias)}), with {pct(worst.small_share, 0)} of entrants in small cells. In no check does the sum "
      "read more than 0.05 points high.")
    a(f"- **Where at most {pct(MAX_SMALL_SHARE, 0)} of entrants are in small cells, the sum is within "
      f"{abs(worst_ok.bias):.2f} points of the exact rate** ({len(ok)} of the {len(pc)} checks; the largest gap is "
      f"{worst_ok['label']}). Above {pct(MAX_SMALL_SHARE, 0)}, gaps run from {pts(over.bias.max())} to "
      f"{pts(over.bias.min())}.")
    a(f"- **The 5+ employee band is the most affected.** Every state's 5+ band has {pct(st5.small_share.min(), 0)} or "
      f"more of its entrants in small cells, and its summed rate is {abs(st5.bias.max()):.1f} to {abs(st5.bias.min()):.1f} "
      "points too low.")
    a("")
    a("![Perturbation bias](charts/15_perturbation_bias.png)")
    a("")
    a("**What this means for Part 2.** Part 2's industry rates within size bands are summed cells too. "
      f"{len(big_bias)} small industries read more than a point low: "
      + ", ".join(f"{i} ({pts(r.bias)})" for i, r in big_bias.iterrows()) + ". "
      f"Shifting each industry's band rates by its own measured gap and re-ranking at the common size mix moves no "
      f"industry more than {max_move} places"
      + (", and the bottom five are unchanged" if bottom5_same else ", but the bottom five change")
      + ", so Part 2's ranking holds.")
    a("")
    a("**The rule this sets for the benchmark.** A rate is **reliable** when it rests on "
      f"{RELIABLE_BASE}+ entrants (one business more or less moves it by at most 1 point) and at most "
      f"{pct(MAX_SMALL_SHARE, 0)} of them are in cells of {SMALL_BASE} or fewer. Above {SMALL_BASE} entrants but "
      f"short of that, it is shown as **use with care**. At {SMALL_BASE} or fewer, no rate is shown (Part 1, rule 6).")
    a("")

    # 3. the benchmark
    a("## 3. The benchmark")
    a("")
    a("`results/benchmark.csv` has one row per state × industry division × size band "
      f"({len(b)} rows) for businesses that entered in 2021-22, the one cohort with this detail. For each it gives:")
    a("")
    a("- **observed**: the share still trading three Junes later (June 2025) in that state, with its flag;")
    a("- **national_rate**: the same industry and size band across the 8 states, with its flag;")
    a("- **state_adjustment**: Part 3's state effect, the state's actual rate minus the rate its industry × size mix "
      "would give at national rates (points);")
    a("- **benchmark**: the observed rate if it is reliable; otherwise the national rate plus the state adjustment, if "
      "the national rate is reliable; otherwise blank. `benchmark_source` says which.")
    a("")
    a("| Size band | Cells | Own rate reliable | Use with care | No rate | Benchmark from own rate | From national + adjustment | No benchmark | Entrants covered |")
    a("|---|---|---|---|---|---|---|---|---|")
    for band, r in cov.iterrows():
        fl = flags.loc[band]
        a(f"| {band_name(band)} | {int(r.cells)} | {int(fl.get('reliable', 0))} | {int(fl.get('use with care', 0))} | "
          f"{int(fl.get('no rate', 0))} | {int(r.own)} | {int(r.adj)} | {int(r.none)} | "
          f"{pct(r.covered / r.entrants)} |")
    a("")
    a(f"- **The benchmark covers {pct(share_cov)} of the {n(cov['entrants'].sum())} entrants** in the 8 states "
      f"(unknown industry left out), because almost all of them are non-employing or have 1-4 employees.")
    a(f"- **For businesses with 5+ employees there is a benchmark in only {int(five.own + five.adj)} of "
      f"{int(five.cells)} cells.** Industry detail for larger entrants is too thin and too perturbed. For these, use "
      "the exact all-industry rate for the state from the state-total rows, which perturbation doesn't distort:")
    a("")
    a("| State | " + " | ".join(sql.query(con, "SELECT abbr FROM states ORDER BY state_order").abbr) + " |")
    a("|---|" + "---|" * len(sb))
    a("| 5+ employees, all industries | " + " | ".join(rate(x) for x in sb["rate_5+"]) + " |")
    a("")
    a("![Benchmark grid](charts/17_benchmark_grid.png)")
    a("")

    # 4. does the adjustment work
    a("## 4. Does the state adjustment work?")
    a("")
    a(f"Where both a state's own rate and the national rate are reliable ({int(allf.cells)} cells, "
      f"{n(allf.entrants)} entrants), the shortcut can be compared with the real figure. "
      "This is a fit check on the same cohort, not a forecast test: the state adjustment was itself built from these "
      "states' entrants.")
    a("")
    a("| State | Cells | Average gap: national rate | With state adjustment | Entrant-weighted: national | With adjustment | Cells closer with adjustment |")
    a("|---|---|---|---|---|---|---|")
    for _, r in fit.iterrows():
        a(f"| {r.state} | {int(r.cells)} | {r.mae_national:.2f} | {r.mae_adjusted:.2f} | {r.wmae_national:.2f} | "
          f"{r.wmae_adjusted:.2f} | {pct(r.share_closer, 0)} |")
    a("")
    a(f"- **Overall the adjustment cuts the average gap from {allf.mae_national:.2f} to {allf.mae_adjusted:.2f} "
      f"points** ({allf.wmae_national:.2f} to {allf.wmae_adjusted:.2f} weighted by entrants), and brings "
      f"{pct(allf.share_closer, 0)} of cells closer.")
    a(f"- It helps most where the state effect is largest: " + ", ".join(
        f"{r.state} ({r.mae_national:.2f} → {r.mae_adjusted:.2f})" for _, r in top_gain.iterrows()) + ".")
    worse_w = worse[worse.wmae_adjusted < worse.wmae_national]
    a(f"- On the simple average it doesn't help in {' or '.join(worse.state)}, where the adjustments are small "
      f"({', '.join(f'{s} {pts(x)}' for s, x in zip(worse.state, worse.state_adjustment))})"
      + (f"; weighted by entrants it does help in {' and '.join(worse_w.state)} ("
         + ", ".join(f"{r.wmae_national:.2f} → {r.wmae_adjusted:.2f}" for _, r in worse_w.iterrows())
         + "), so its largest cells do move with the state" if len(worse_w) else "")
      + ". Where an adjustment is that small, the national rate is about as good a fallback.")
    a(f"- Even with the adjustment, {n_far} of the {len(both)} cells sit more than 5 points from it. The largest: "
      + "; ".join(f"{r.abbr} {short(r.industry)}, {band_name(r.band)}: {rate(r.observed)} vs "
                  f"{rate(r.national_rate + r.state_adjustment)} ({n(r.entrants)} entrants)"
                  for _, r in big_gap.head(3).iterrows())
      + ". A local figure that is reliable beats the shortcut, which is why the benchmark uses it first.")
    a("")
    a("![State adjustment fit](charts/16_state_adjustment_fit.png)")
    a("")

    # 5. what it says
    a("## 5. What the benchmark says")
    a("")
    a(f"- **Lowest reliable rates:** " + "; ".join(
        f"{r.abbr} {short(r.industry)}, {band_name(r.band)}: {rate(r.observed)} of {n(r.entrants)}"
        for _, r in low.iterrows()) + ".")
    a(f"- **Highest reliable rates:** " + "; ".join(
        f"{r.abbr} {short(r.industry)}, {band_name(r.band)}: {rate(r.observed)} of {n(r.entrants)}"
        for _, r in high.iterrows()) + ".")
    a(f"- Reliable non-employing rates run from {rate(ne_rel.observed.min())} to {rate(ne_rel.observed.max())}; "
      f"1-4 employee rates from {rate(e14_rel.observed.min())} to {rate(e14_rel.observed.max())}. Within the same "
      f"state and industry, entrants with 1-4 employees out-survived non-employing ones in "
      f"{'all' if n_pair_pos == len(pair_gap) else f'{n_pair_pos} of'} {len(pair_gap)} pairs where both are reliable (median gap {pts(pair_gap.median())}).")
    a("")
    for ind, band in EXAMPLES:
        t = b[(b.industry == ind) & (b.band == band)]
        nat = t.iloc[0]
        a(f"**Worked example: {short(ind)}, {band_name(band)}** (national rate {rate(nat.national_rate)}, "
          f"{n(nat.national_entrants)} entrants, {nat.national_flag})")
        a("")
        a("| State | Entrants | Own rate | Flag | Benchmark | Source |")
        a("|---|---|---|---|---|---|")
        for _, r in t.iterrows():
            own = "–" if pd.isna(r.observed) else rate(r.observed)
            bm = "–" if pd.isna(r.benchmark) else rate(r.benchmark)
            a(f"| {r.abbr} | {n(r.entrants)} | {own} | {r.observed_flag} | {bm} | {r.benchmark_source} |")
        a("")
        own = t[t.observed_flag == "reliable"]
        lo_, hi_ = own.loc[own.observed.idxmin()], own.loc[own.observed.idxmax()]
        a(f"Where the state's own rate is reliable it runs from {rate(lo_.observed)} ({lo_.abbr}) to "
          f"{rate(hi_.observed)} ({hi_.abbr}), {hi_.observed - lo_.observed:.1f} points apart.")
        a("")
        care = t[t.observed_flag != "reliable"]
        if len(care):
            a("Where the own rate isn't reliable the table shows it anyway, so a reader can see how far it is from the "
              "benchmark: " + "; ".join(f"{r.abbr} {rate(r.observed)} on {n(r.entrants)} entrants vs "
                                         f"{rate(r.benchmark)}" for _, r in care.iterrows() if pd.notna(r.observed))
              + ". The data can't say which is closer to the truth; a difference that size on so few entrants is "
              "a reason to ask more questions, not to decline.")
            a("")
    a("Look up any combination with `python scripts/benchmark_lookup.py \"<industry>\" <state> <size band>`.")
    a("")

    # 6. so what
    a("## 6. What this means for the business")
    a("")
    a("- **Lenders and investors:** use the benchmark as the starting point for a new business's three-year "
      "survival, not the national average. Industry and size move the rate far more than state does: "
      f"reliable national rates for an industry and size band run from {rate(nat_rel.national_rate.min())} to "
      f"{rate(nat_rel.national_rate.max())}, while the state adjustment "
      f"fine-tunes it by {pts(sf.state_adjustment.min())} to {pts(sf.state_adjustment.max())}. Carry the flag "
      "into the credit file: a \"use with care\" rate should widen the range considered, not set the price.")
    a(f"- **For larger entrants (5+ employees) don't use industry detail from this release.** Only "
      f"{int(five.own + five.adj)} of {int(five.cells)} cells have a benchmark; the state-level 5+ rates above are exact.")
    a("- **Small-business advisers:** the benchmark gives a client a fair comparison: businesses of the same "
      "industry, size and state. The worked examples show the spread a café owner or a sole-trader tradie faces "
      "depending on where they start.")
    a("- **Analysts:** the SQL layer reproduces the key Part 1-3 tables exactly, so the same figures can feed a BI tool or a "
      "credit system straight from SQL without re-running Python. Check the perturbation before trusting any sum "
      "of small cells.")
    a("")
    a("## Caveats")
    a("")
    a("- One cohort: 2021-22 entrants to June 2025. Data cube 1 shows how much survival moves between cohorts "
      "(Parts 1-3), and the 2026 detail is due on 18 December 2026.")
    a("- \"Still trading\" isn't \"didn't fail\": an exit can be a sale, a restructure or a business that stopped "
      "remitting GST (Part 1, rule 1). The benchmark says nothing about profit or loan repayment.")
    a("- The state adjustment is one number per state for all industries and sizes. Section 4 shows where that "
      "holds and where it doesn't.")
    a("- Even reliable rates are summed perturbed cells, read up to "
      f"{abs(worst_ok.bias):.2f} points low by the checks in section 2.")
    a("")
    a("## Output files")
    a("")
    a("- `results/benchmark.csv`: state × industry division × size band, observed and national rates with flags, "
      "the state adjustment and the benchmark")
    a("- `results/benchmark_fit.csv`: section 4, by state")
    a("- `results/perturbation_check.csv`: section 2, every summed-cells vs exact comparison")
    a("- `results/sql_parity.csv`: the SQL vs pandas comparison, column by column")
    (RESULTS / "BENCHMARK.md").write_text("\n".join(L) + "\n")
    print("wrote results/BENCHMARK.md and 3 charts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
