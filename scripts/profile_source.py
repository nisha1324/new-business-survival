"""Part 1 report: what the CABEE numbers mean, and the rules that follow.

Reads the tidy snapshot in data/ and writes:
- results/SOURCE_PROFILE.md        the report (every figure comes from this script)
- results/headline.csv              national survival by release (cohort)
- results/flow_series.csv           national entries, exits and counts, 2019-20 to 2025-26
- results/division_size_mix.csv     entries by industry: non-employing share, survival by size
- results/small_cells.csv           detail cells whose published rate disagrees with their counts
- results/charts/01-05 *.png
"""
from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cabee import load, profile as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CHARTS = RESULTS / "charts"

# Reference palette (validated: 2 slots, light mode, all checks pass)
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID,
    "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "svg.hashsalt": "cabee", "path.simplify": False,
})
SAVE = {"dpi": 150, "metadata": {"Software": None}}


def n(x: float, nd: int = 0) -> str:
    return f"{x:,.{nd}f}"


def pct(x: float, nd: int = 1) -> str:
    """A share (0-1) as a percentage."""
    return f"{x * 100:.{nd}f}%"


def rate(x: float) -> str:
    """A published survival rate (already in %)."""
    return f"{x:.1f}%"


def signed(x: float, nd: int = 1, unit: str = "%") -> str:
    return f"{x:+.{nd}f}{unit}".replace("-", "−")


def ordinal(k: int) -> str:
    return f"{k}{'th' if 10 <= k % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(k % 10, 'th')}"


def style(ax, title: str, subtitle: str | None = None) -> None:
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=22 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2)


# ------------------------------------------------------------------ charts
def chart_flows(fs: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    x = range(len(fs))
    w = 0.38
    ax.bar([i - w / 2 - 0.01 for i in x], fs["entries"] / 1000, width=w, color=BLUE, label="Entries")
    ax.bar([i + w / 2 + 0.01 for i in x], fs["exits"] / 1000, width=w, color=ORANGE, label="Exits")
    for i, r in fs.reset_index(drop=True).iterrows():
        ax.text(i - w / 2, r["entries"] / 1000 + 6, f"{r['entries'] / 1000:.0f}k", ha="center", fontsize=8, color=INK)
        ax.text(i + w / 2, r["exits"] / 1000 + 6, f"{r['exits'] / 1000:.0f}k", ha="center", fontsize=8, color=INK)
    ax.set_xticks(list(x), fs["fin_year"])
    ax.set_ylabel("Businesses (thousands)")
    ax.set_ylim(0, fs["entries"].max() / 1000 * 1.18)
    first, last = fs.iloc[0], fs.iloc[-1]
    style(ax, "More businesses enter than exit every year",
          f"Actively trading businesses: {first['operating_start'] / 1e6:.2f}m at June {first['fin_year'][:4]}"
          f" → {last['operating_end'] / 1e6:.2f}m at June 20{last['fin_year'][-2:]}")
    ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=9, labelcolor=INK_2)
    fig.tight_layout()
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_cohorts(h: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    x = list(range(len(h)))
    ax.plot(x, h["businesses_rate"], color=BLUE, linewidth=2, marker="o", markersize=8)
    ax.plot(x, h["entries_rate"], color=ORANGE, linewidth=2, marker="o", markersize=8)
    for i, r in h.iterrows():
        ax.text(i, r["businesses_rate"] + 1.3, rate(r["businesses_rate"]), ha="center", fontsize=9, color=INK)
        ax.text(i, r["entries_rate"] - 3.2, rate(r["entries_rate"]), ha="center", fontsize=9, color=INK)
    ax.text(len(h) - 0.72, h["businesses_rate"].iloc[-1], "All businesses,\n4 Junes later", color=INK_2, fontsize=9, va="center")
    ax.text(len(h) - 0.72, h["entries_rate"].iloc[-1], "New entries,\n3 Junes after\nthe entry year", color=INK_2, fontsize=9, va="center")
    ax.set_xticks(x, [f"{a}\n{b} entries" for a, b in zip(h["businesses_start"], h["entries_year"])])
    ax.set_xlim(-0.4, len(h) + 0.45)
    ax.set_ylim(40, 72)
    ax.set_ylabel("Still actively trading (%)")
    style(ax, "About half of new entrants have stopped trading three Junes on",
          "Share still trading, by cohort (businesses operating in June / entries during the financial year)")
    fig.tight_layout()
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_size(sm: pd.DataFrame, path: Path) -> None:
    t = sm.loc[P.SIZES]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    labels = [f"{g}\n{pct(s) if s >= 0.001 else '<0.1%'} of entries" for g, s in zip(t.index, t["share"])]
    ax.bar(labels, t["rate_pub"], color=BLUE, width=0.6)
    for i, v in enumerate(t["rate_pub"]):
        ax.text(i, v + 1.2, rate(v), ha="center", fontsize=9, color=INK)
    tot = sm.loc["Total", "rate_pub"]
    ax.axhline(tot, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(-0.45, tot + 1.2, f"All entries {rate(tot)}", color=INK_2, fontsize=9, ha="left")
    ax.set_ylim(0, 92)
    ax.set_ylabel("Still trading at June 2026 (%)")
    ax.set_xlabel("Employment size when the business entered")
    style(ax, "Bigger entrants last longer, but almost 3 in 4 entrants employ no one",
          "Businesses that entered in 2022-23: share still trading at June 2026, by employment size")
    fig.tight_layout()
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_mix(mix: pd.DataFrame, path: Path) -> None:
    m = mix.sort_values("rate_all", kind="stable")
    fig, ax = plt.subplots(figsize=(8.5, 7.2))
    y = list(range(len(m)))
    for i, (_, r) in enumerate(m.iterrows()):
        ax.plot([r["rate_non_employing"], r["rate_employing"]], [i, i], color=GRID, linewidth=2, zorder=1)
    ax.scatter(m["rate_non_employing"], y, s=64, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2,
               label="Non-employing entrants")
    ax.scatter(m["rate_employing"], y, s=64, color=BLUE, zorder=3, edgecolor=SURFACE, linewidth=2,
               label="Employing entrants")
    ax.scatter(m["rate_all"], y, s=70, marker="|", color=INK, zorder=4, label="All entrants")
    ax.set_yticks(y, [f"{r['industry']}  ({pct(r['non_employing_share'], 0)} non-emp.)" for _, r in m.iterrows()],
                  fontsize=8.5)
    ax.set_xlabel("Still trading at June 2025 (%)")
    ax.set_xlim(25, 75)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.975, "An industry's overall rate mixes industry with size", fontsize=12, fontweight="bold",
             color=INK, va="top")
    fig.text(0.015, 0.943, "Businesses that entered in 2021-22, by industry: survival to June 2025 for non-employing "
             "and employing entrants", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper left", bbox_to_anchor=(0.008, 0.925), frameon=False, ncol=3, fontsize=9,
               labelcolor=INK_2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_small(sc: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    ax.bar(sc["base_band"].astype(str), sc["off_share"] * 100, color=BLUE, width=0.6)
    for i, r in sc.reset_index(drop=True).iterrows():
        ax.text(i, r["off_share"] * 100 + 1.2, f"{pct(r['off_share'])}\n({n(r['off'])} of {n(r['cells'])})",
                ha="center", fontsize=8.5, color=INK)
    ax.set_ylim(0, max(sc["off_share"]) * 100 * 1.3)
    ax.set_ylabel("Cells with a mismatched rate (%)")
    ax.set_xlabel("Businesses in the cell's base (state × subdivision × size)")
    style(ax, "Rates on tiny cells don't match their own counts",
          "Data cubes 4-5: share of rated cells where survived ÷ base is more than rounding away from the published rate")
    fig.tight_layout()
    fig.savefig(path, **SAVE)
    plt.close(fig)


# ------------------------------------------------------------------ report
def main() -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    s, f = load.read("survival"), load.read("flows")
    sub, lga = load.read("subdivision_survival"), load.read("lga_counts")

    h = P.headline(s)
    curves = P.entry_curves(s)
    rc = P.rate_consistency(s)
    add = P.additivity(s)
    fs = P.flow_series(f)
    rev = P.revisions(f)
    sm = P.size_mix(s)
    eo = P.entries_other_share(f)
    mix = P.division_check(sub, s)
    dt = P.detail_totals_check(sub, s)
    pt = P.perturbation(sub)
    sc = P.small_cells(sub)
    lc = P.lga_checks(lga, f)

    h.to_csv(RESULTS / "headline.csv", index=False)
    fs.to_csv(RESULTS / "flow_series.csv", index=False)
    mix.round(4).to_csv(RESULTS / "division_size_mix.csv")
    sc.round(4).to_csv(RESULTS / "small_cells.csv", index=False)

    chart_flows(fs, CHARTS / "01_entries_exits.png")
    chart_cohorts(h, CHARTS / "02_cohort_survival.png")
    chart_size(sm, CHARTS / "03_entries_by_size.png")
    chart_mix(mix, CHARTS / "04_industry_size_mix.png")
    chart_small(sc, CHARTS / "05_small_cells.png")

    first, last = fs.iloc[0], fs.iloc[-1]
    growth = last["operating_end"] / first["operating_start"] - 1
    lh, fh = h.iloc[-1], h.iloc[0]
    emp = sm.loc["Total employing"]
    non = sm.loc["Non employing"]
    worst_entry = h.loc[h["entries_rate"].idxmin()]
    ex = fs.iloc[-1]
    canc_share = ex["cancellations"] / ex["exits"]
    low = mix["non_employing_share"].idxmin()
    acc = mix.loc[low]
    rank_all = int(mix["rate_all"].rank().loc[low])
    rank_emp = int(mix["rate_employing"].rank().loc[low])
    hi_non = mix.sort_values("non_employing_share", ascending=False, kind="stable")
    top2 = hi_non.iloc[:2]
    gm = rev["group_max"]
    dmax = mix.loc[mix["diff"].abs().idxmax()]
    sc_idx = sc.set_index("base_band")
    worst_lga = lc["worst_states"]
    over_20 = sc[~sc["base_band"].isin(["1-5", "6-10", "11-20"])]

    L: list[str] = []
    a = L.append
    a("# Part 1: source profile")
    a("")
    a("*Generated by `scripts/profile_source.py` from the snapshot in `data/`. Do not edit by hand.*")
    a("")
    a("## Source")
    a("")
    a("Australian Bureau of Statistics, *Counts of Australian Businesses, including Entries and Exits* "
      "(CABEE, cat. no. 8165.0). Licence: CC BY 4.0, © Commonwealth of Australia. CABEE counts every "
      "actively trading business on the ABS Business Register (an ABN that is registered for and remitting "
      "GST, plus the large, complex businesses ABS profiles directly) at 30 June each year.")
    a("")
    a("| File | Release | What it gives |")
    a("|---|---|---|")
    for rel in load.DC01:
        a(f"| Data cube 1 | June {rel[:4]} – June {rel[-4:]} | national and state counts, entries, exits, survival "
          f"(not perturbed) |")
    a(f"| Data cubes 4 and 5 | June 2021 – June 2025 | survival of businesses and entries by state × ANZSIC "
      f"subdivision × employment size (perturbed) |")
    a(f"| Data cube 10 | June 2021 – June 2025 | business counts by LGA × industry division × employment size, "
      f"June 2023-2025 (perturbed) |")
    a("")
    a("The August 2026 release has data cube 1, tables 1-16 only; its detailed cubes are due on 18 December 2026, "
      "so the state × subdivision and LGA views are one release behind.")
    a("")
    a("## At a glance")
    a("")
    a(f"- **{n(last['operating_end'])} businesses** were actively trading at June 20{last['fin_year'][-2:]}, "
      f"up {pct(growth)} from {n(first['operating_start'])} at June {first['fin_year'][:4]}. Entries outnumbered "
      f"exits in {'every one' if (fs['entries'] > fs['exits']).all() else str(int((fs['entries'] > fs['exits']).sum()))}"
      f" of the {len(fs)} years from {first['fin_year']} to {last['fin_year']}.")
    a(f"- Of the **{n(lh['entries'])} businesses that entered in {lh['entries_year']}**, {n(lh['entries_survived'])} "
      f"({rate(lh['entries_rate'])}) were still trading at June {lh['entries_to']}. For the {fh['entries_year']} "
      f"entrants the same figure was {rate(fh['entries_rate'])}; the low point was the {worst_entry['entries_year']} "
      f"cohort at {rate(worst_entry['entries_rate'])}.")
    a(f"- Of the {n(lh['businesses'])} businesses trading at {lh['businesses_start']}, {rate(lh['businesses_rate'])} "
      f"were still trading four years later, down from {rate(fh['businesses_rate'])} for the {fh['businesses_start']} "
      f"cohort.")
    a(f"- {pct(non['share'])} of {lh['entries_year']} entrants employed no one. "
      f"{rate(non['rate_pub'])} of them were still trading at June {lh['entries_to']}, against "
      f"{rate(emp['rate_pub'])} of employing entrants.")
    a("")
    a("![Entries and exits](charts/01_entries_exits.png)")
    a("")
    a("![Survival by cohort](charts/02_cohort_survival.png)")
    a("")
    a("Survival of each entry cohort, by June after the entry year:")
    a("")
    a("| Entered in | 1st June | 2nd June | 3rd June |")
    a("|---|---|---|---|")
    for start, r in curves.iterrows():
        a(f"| {start} | {rate(r[1])} | {rate(r[2])} | {rate(r[3])} |")
    a("")
    a("## Checks")
    a("")
    a("| Check | Result |")
    a("|---|---|")
    a(f"| Data cube 1: published rate vs survived ÷ base | {n(rc['rates'])} rates, largest gap "
      f"{rc['max_diff']:.3f} points, {rc['over_rounding']} beyond rounding |")
    a(f"| Data cube 1: groups + 'unknown' add to the total | {int(add['tables'].sum())} tables across 5 dimensions, "
      f"largest gap {int(add[['max_gap_base', 'max_gap_survived']].max().max())} businesses |")
    a(f"| Survival base for entries = entries in the counts table | equal in every release, industry and state "
      f"(checked in tests) |")
    a(f"| National totals across overlapping releases | {rev['total_cells']} overlapping cells, "
      f"{rev['total_changed']} revised |")
    a(f"| Industry and state groups across overlapping releases | {rev['group_changed']} of {rev['group_cells']} "
      f"overlapping cells revised, median {rev['group_median_pct']:.2f}%, largest named group {gm['group']} "
      f"({gm['variable'].replace('_', ' ')}, {gm['fin_year']}): {n(gm['min'])} to {n(gm['max'])} "
      f"({gm['pct']:.1f}%) |")
    a(f"| Data cubes 4/5 state totals vs data cube 1 (June 2021 – June 2025) | {dt['pairs']} pairs, largest gap "
      f"{dt['max_gap_base']} (base), {dt['max_gap_survived']} (survived), {dt['max_gap_rate']:.1f} (rate) |")
    a(f"| Division rates rebuilt from data cube 5's cells vs data cube 1's published rates | within "
      f"{abs(dmax['diff']):.2f} points (largest: {dmax['industry']}) |")
    a(f"| Data cubes 4/5: size bands add to the row total | {n(pt['rows_not_adding'])} of {n(pt['rows'])} rows "
      f"don't, by {signed(pt['size_gap_min'], 0, '')} to {signed(pt['size_gap_max'], 0, '')} businesses |")
    a(f"| Data cube 10: national total = data cube 1's June count | {'yes' if lc['national_matches_dc01'] else 'NO'} "
      f"for June 2023, 2024 and 2025 ({', '.join(n(v) for v in lc['national'].values())}) |")
    a(f"| Data cube 10: LGAs add to their state | within {signed(lc['state_pct_min'], 2)} to "
      f"{signed(lc['state_pct_max'], 2)} (worst {worst_lga[0][0]} {signed(worst_lga[0][1], 2)}, "
      f"{worst_lga[1][0]} {signed(worst_lga[1][1], 2)}) |")
    a(f"| Data cube 10: industries add to the LGA total | {pct(lc['industry_gap_share'], 0)} of LGA-years don't, "
      f"by {signed(lc['industry_gap_min'], 0, '')} to {signed(lc['industry_gap_max'], 0, '')} |")
    a("")
    a("## Traps, and the rule each one sets")
    a("")
    a(f"1. **An exit isn't a failure.** ABS counts an exit when a business stops actively trading: a cancelled ABN "
      f"(closed, sold, restructured or moved overseas) or a long-term GST non-remitter. In {ex['fin_year']}, "
      f"{pct(canc_share)} of the {n(ex['exits'])} exits were cancellations and the rest 'other exits'. "
      f"**Rule:** say \"still trading\" or \"exited\", never \"failed\".")
    a(f"2. **Not every entry is a new business.** 'Other entries' (re-activated ABNs, non-remitters resuming GST, "
      f"businesses coming into scope) were {pct(eo['other_share'].min())} to {pct(eo['other_share'].max())} of entries "
      f"each year. A business that starts and stops between two 30 Junes is never counted at all, so true early "
      f"closures are higher than any CABEE rate shows. **Rule:** call the cohort \"entries\", not \"start-ups\", and "
      f"note that survival is measured at 30 June only.")
    a(f"3. **The two survival tables measure different things.** 'Businesses' follows everything trading at the first "
      f"June, new or long-established, for four Junes; 'entries' follows that year's newcomers, first counted at the "
      f"June ending their entry year, for three. {rate(lh['businesses_rate'])} vs {rate(lh['entries_rate'])} in the "
      f"latest release is not a like-for-like gap. **Rule:** new-business questions use the entries tables, and every "
      f"rate names its cohort and its June.")
    a(f"4. **Size mix drives industry rankings.** Non-employing entrants survive at {rate(non['rate_pub'])} vs "
      f"{rate(emp['rate_pub'])} for employing ones, and the non-employing share of entries ranges from "
      f"{pct(mix['non_employing_share'].min(), 0)} to {pct(mix['non_employing_share'].max(), 0)} by industry "
      f"(2021-22 entrants). {acc['industry']} has the lowest share ({pct(acc['non_employing_share'], 0)}), so its "
      f"overall rate is {ordinal(rank_all)} lowest of {len(mix)}, but its employing entrants' rate is {ordinal(rank_emp)} lowest. "
      f"{top2.iloc[0]['industry']} and {top2.iloc[1]['industry']} are both about "
      f"{pct(top2['non_employing_share'].mean(), 0)} non-employing, yet survive at {top2.iloc[0]['rate_all']:.1f}% and "
      f"{top2.iloc[1]['rate_all']:.1f}%. **Rule:** compare industries within a size band (or at a common size mix), "
      f"not on the overall rate alone.")
    a(f"5. **Releases revise groups, not totals.** National totals never changed between overlapping releases, but "
      f"industry and state groups did (median {rev['group_median_pct']:.2f}%, up to {gm['pct']:.1f}% for a named "
      f"group and {rev['unknown_max_pct']:.0f}% for the 'unknown' rows: industry not yet coded, or state unknown). "
      f"**Rule:** a time series takes each year from the latest release that has it; a single comparison never mixes "
      f"releases.")
    a(f"6. **Detail cells are perturbed, and tiny ones mislead.** In data cubes 4/5, {n(pt['off_cells'])} of "
      f"{n(pt['rated_cells'])} rated cells have a published rate {pt['off_min_diff']:.1f} to "
      f"{pt['off_max_diff']:.0f} points away from their own counts, all with a base of {pt['off_max_base']} "
      f"businesses or fewer ({pct(sc_idx.loc['1-5', 'off_share'])} of cells with 1-5 businesses, "
      f"{'none' if over_20['off'].sum() == 0 else n(over_20['off'].sum())} above {P.SMALL_BASE}). Rates rebuilt by "
      f"summing cells to divisions land within {abs(dmax['diff']):.2f} points of the unperturbed figures. "
      f"**Rule:** no rate on a base of {P.SMALL_BASE} businesses or fewer; aggregate cells first, then compute the rate.")
    a(f"7. **Regions below state level have counts, not survival.** Survival is published by state only; data cube "
      f"10 gives {lc['lgas']} LGAs' business counts. Multi-state businesses "
      f"sit in each state's 'No usual address' row ({pct(min(lc['no_usual_address_share'].values()), 2)} to "
      f"{pct(max(lc['no_usual_address_share'].values()), 2)} of businesses), and some LGAs have blank rows "
      f"({', '.join(x for x in lc['blank_lga_rows'] if x != 'No usual address')}). **Rule:** regional survival is a "
      f"state comparison; LGAs are compared on growth in business numbers, with a floor on the base.")
    a(f"8. **'Currently Unknown' has counts but no rates.** It is kept in totals and left out of rankings.")
    a("")
    a("![Entries by size](charts/03_entries_by_size.png)")
    a("")
    a("![Industry size mix](charts/04_industry_size_mix.png)")
    a("")
    a("![Small cells](charts/05_small_cells.png)")
    a("")
    a("## Output files")
    a("")
    a("- `results/headline.csv`: national survival by release")
    a("- `results/flow_series.csv`: national entries, exits and counts, each year from the latest release")
    a("- `results/division_size_mix.csv`: 2021-22 entrants by industry division, size mix and survival to June 2025")
    a("- `results/small_cells.csv`: mismatched rates by base size")
    (RESULTS / "SOURCE_PROFILE.md").write_text("\n".join(x for x in L if x is not None) + "\n")
    print("wrote results/SOURCE_PROFILE.md and 5 charts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
