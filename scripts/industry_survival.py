"""Part 2 report: which industries new businesses last in, compared fairly.

Reads the tidy snapshot in data/ and writes:
- results/INDUSTRY_SURVIVAL.md        the report (every figure comes from this script)
- results/industry_cohorts.csv         divisions: survival of four entry cohorts (data cube 1)
- results/industry_size_bands.csv      divisions: survival by size band and at the national size mix
- results/subdivision_survival.csv     subdivisions: overall and common-mix survival (where the floor allows)
- results/national_size_bands.csv      national entrants by size band and cohort
- results/charts/06-09 *.png
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.profile_source import (  # noqa: E402  (also sets the shared chart style)
    BLUE, CHARTS, GRID, INK, INK_2, MUTED, ORANGE, RESULTS, SAVE, SURFACE, n, ordinal, pct, plt, rate, signed, style,
)
from cabee import load, industries as I  # noqa: E402
from cabee.profile import SMALL_BASE  # noqa: E402

import pandas as pd  # noqa: E402

AQUA = "#1baf7a"  # categorical slot 3 (validated with blue/orange; below 3:1 contrast, so lines are direct-labelled)
MIN_ENTRANTS = 500  # subdivision league tables: subdivisions with at least this many 2021-22 entrants


def sgn(x: float, nd: int = 1) -> str:
    """A signed difference; exactly zero after rounding is shown without a sign."""
    return f"{0:.{nd}f}" if round(x, nd) == 0 else signed(x, nd, "")


def pts(x: float, nd: int = 1) -> str:
    """A difference between two rates, in percentage points."""
    return sgn(x, nd) + " points"


# ------------------------------------------------------------------ charts
def chart_cohorts(t: pd.DataFrame, path: Path) -> None:
    first, last = I.COHORTS[0], I.COHORTS[-1]
    m = t.sort_values(last, kind="stable")
    fig, ax = plt.subplots(figsize=(8.5, 7.4))
    y = list(range(len(m)))
    for i, (_, r) in enumerate(m.iterrows()):
        ax.plot([r["low"], r["high"]], [i, i], color=GRID, linewidth=6, solid_capstyle="round", zorder=1)
        ax.text(r["high"] + 0.8, i, rate(r[last]), va="center", fontsize=8, color=INK_2)
    ax.scatter(m[first], y, s=56, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2, label=f"{first} entrants")
    ax.scatter(m[last], y, s=64, color=BLUE, zorder=4, edgecolor=SURFACE, linewidth=2, label=f"{last} entrants")
    ax.plot([], [], color=GRID, linewidth=6, label="Range across the four cohorts")
    ax.set_yticks(y, list(m.index), fontsize=8.5)
    ax.set_xlabel("Still trading three Junes after the entry year (%)")
    ax.set_xlim(32, 68)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.975, "The same industries sit at the bottom in every cohort", fontsize=12, fontweight="bold",
             color=INK, va="top")
    fig.text(0.015, 0.945, f"Entrants by industry: share still trading three Junes on, {first} to {last} cohorts "
             f"(label: {last})", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper left", bbox_to_anchor=(0.008, 0.93), frameon=False, ncol=3, fontsize=9,
               labelcolor=INK_2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_common_mix(d: pd.DataFrame, path: Path) -> None:
    m = d.sort_values("std", ascending=False, kind="stable")
    fig, ax = plt.subplots(figsize=(8.5, 7.4))
    y = list(range(len(m)))
    for i, (_, r) in enumerate(m.iterrows()):
        ax.plot([r["rate_all"], r["std"]], [i, i], color=GRID, linewidth=2, zorder=1)
        if abs(r["mix_effect"]) >= 2:
            ax.text(max(r["rate_all"], r["std"]) + 0.9, i, f"{pts(-r['mix_effect'])}", va="center", fontsize=8,
                    color=INK_2)
    ax.scatter(m["rate_all"], y, s=56, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2,
               label="Overall (own size mix)")
    ax.scatter(m["std"], y, s=64, color=BLUE, zorder=4, edgecolor=SURFACE, linewidth=2,
               label="At the national size mix")
    labels = [f"{r['industry']}  ({ordinal(int(r['rank_std']))})" for _, r in m.iterrows()]
    ax.set_yticks(y, labels, fontsize=8.5)
    ax.set_xlabel("Still trading at June 2025 (%)")
    ax.set_xlim(32, 66)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    mv = d.sort_values("mix_effect", kind="stable").iloc[-1]
    short = mv["industry"].replace(" Services", "").replace(" and ", " & ")
    fig.text(0.015, 0.975, f"At the same size mix, {short} drops to {ordinal(int(mv['rank_std']))} lowest", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.945, "2021-22 entrants by industry. In brackets: rank from lowest at the national size mix. "
             "Labels: overall → national mix, where 2+ points", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper left", bbox_to_anchor=(0.008, 0.93), frameon=False, ncol=2, fontsize=9,
               labelcolor=INK_2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_subdivisions(sd: pd.DataFrame, national: float, path: Path, k: int = 10) -> None:
    big = sd[(sd["entries"] >= MIN_ENTRANTS) & sd["std_2"].notna()].sort_values("std_2", kind="stable")
    m = pd.concat([big.head(k), big.tail(k)])
    fig, ax = plt.subplots(figsize=(8.5, 7.6))
    y = [i if i < k else i + 1 for i in range(len(m))]
    ax.barh(y, m["std_2"], color=BLUE, height=0.62)
    for yi, v in zip(y, m["std_2"]):
        ax.text(v + 0.6, yi, rate(v), va="center", fontsize=8, color=INK)
    ax.axvline(national, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(national + 0.5, -1.0, f"All entrants {rate(national)}", fontsize=8.5, color=INK_2, va="center")
    names = [f"{r['subdivision'][:46]}{'…' if len(r['subdivision']) > 46 else ''} ({n(r['entries'])})"
             for _, r in m.iterrows()]
    ax.set_yticks(y, names, fontsize=8)
    ax.text(0.5, k, f"· · ·  {len(big) - 2 * k} subdivisions in between  · · ·", fontsize=8, color=MUTED, va="center")
    ax.invert_yaxis()
    ax.set_xlim(0, 80)
    ax.set_xlabel("Still trading at June 2025, at the national size mix (%)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.975, "Courier, transport support and cleaning sit near the bottom", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.945, f"2021-22 entrants: the {k} lowest and {k} highest of {len(big)} ANZSIC subdivisions with "
             f"{MIN_ENTRANTS}+ entrants (in brackets)", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_bands(nb: pd.DataFrame, path: Path) -> None:
    w, r = nb["weight"].unstack(), nb["rate"].unstack()
    tot = (w * r).sum(axis=1)
    x = list(range(len(r)))
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    colours = {"Non-employing": BLUE, "1-4": ORANGE, "5+": AQUA}
    names = {"Non-employing": "Non-employing", "1-4": "1-4 employees", "5+": "5 or more employees"}
    for b in I.BANDS:
        ax.plot(x, r[b], color=colours[b], linewidth=2, marker="o", markersize=8, markeredgecolor=SURFACE,
                markeredgewidth=2, label=names[b])
        ax.text(len(x) - 1 + 0.12, r[b].iloc[-1], f"{names[b]}\n{rate(r[b].iloc[-1])}", va="center", fontsize=8.5,
                color=INK_2)
    ax.plot(x, tot, color=INK, linewidth=1.5, linestyle=(0, (4, 3)), label="All entrants")
    ax.text(len(x) - 1 + 0.12, tot.iloc[-1], f"All entrants\n{rate(tot.iloc[-1])}", va="center", fontsize=8.5,
            color=INK_2)
    for i, v in enumerate(r["Non-employing"]):
        ax.text(i, v - 3.0, f"{pct(w['Non-employing'].iloc[i])}\nnon-emp.", ha="center", fontsize=7.5, color=INK_2)
    ax.set_xticks(x, [f"{c}\nentrants" for c in r.index])
    ax.set_xlim(-0.3, len(x) - 1 + 0.95)
    ax.set_ylim(36, 74)
    ax.set_ylabel("Still trading three Junes on (%)")
    style(ax, f"{r.index[0]} to {r.index[-1]}: survival fell inside every size band, not through the mix",
          "National entrants by employment size at entry (data cube 1). Under the blue line: non-employing share of entrants")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.0), frameon=False, ncol=4, fontsize=8.5, labelcolor=INK_2)
    fig.tight_layout()
    fig.savefig(path, **SAVE)
    plt.close(fig)


# ------------------------------------------------------------------ report
def main() -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    s, sub = load.read("survival"), load.read("subdivision_survival")

    t = I.division_trend(s)
    st = I.rank_stability(t)
    nb = I.national_bands(s)
    first, last = I.COHORTS[0], I.COHORTS[-1]
    dec = I.mix_decomposition(nb, first, last)
    steps = [I.mix_decomposition(nb, a, b) for a, b in zip(I.COHORTS, I.COHORTS[1:])]
    w3 = I.weights(s)
    d = I.division_bands(sub, s)
    sd = I.subdivision_bands(sub, s)

    t.round(4).to_csv(RESULTS / "industry_cohorts.csv")
    d.round(4).to_csv(RESULTS / "industry_size_bands.csv")
    sd.round(4).to_csv(RESULTS / "subdivision_survival.csv")
    nb.round(4).to_csv(RESULTS / "national_size_bands.csv")

    nat_r = nb["rate"].unstack()
    nat_w = nb["weight"].unstack()
    nat_tot = (nat_r * nat_w).sum(axis=1)
    pub_nat = s[(s.dimension == "industry") & (s.level == "total") & (s.cohort == "entries") & (s.years_after == 3)]
    pub_nat = pub_nat.set_index("start")["rate_pub"]
    nat_2122 = float(nat_tot["2021-22"])

    chart_cohorts(t, CHARTS / "06_industry_cohorts.png")
    chart_common_mix(d, CHARTS / "07_common_size_mix.png")
    chart_subdivisions(sd, nat_2122, CHARTS / "08_subdivisions.png")
    chart_bands(nb, CHARTS / "09_national_size_bands.png")

    # --- figures used in the text
    bottom = t.head(5)
    top = t.tail(3).iloc[::-1]
    falls = t.sort_values("change", kind="stable")
    rises = t[t["change"] > 0].sort_values("change", ascending=False, kind="stable")
    fjs = t["first_june_share_of_loss"]
    r1_nat = s[(s.dimension == "industry") & (s.level == "total") & (s.cohort == "entries") & (s.start == last)]
    r1_nat = r1_nat.set_index("years_after")["rate_pub"]
    nat_fjs = (100 - r1_nat[1]) / (100 - r1_nat[3])
    retail = t.loc["Retail Trade"]
    movers = d.sort_values("mix_effect", kind="stable")
    up = movers.iloc[-1]   # overall rate most flattered by its size mix
    down = movers.iloc[0]  # overall rate most held down by its size mix
    std_gap = (d["std"] - d["std_2"]).abs()
    same_order = bool((d["std"].rank() == d["std_2"].rank()).all())
    big = sd[(sd["entries"] >= MIN_ENTRANTS) & sd["std_2"].notna()].sort_values("std_2", kind="stable")
    rated = sd[sd["std_2"].notna()]
    big_share = big["entries"].sum() / sd["entries"].sum()
    low5, high5 = big.head(5), big.tail(5).iloc[::-1]
    unrated = sd[sd["std_2"].isna()]
    fnb = sd.loc["45"]  # Food and Beverage Services
    acc = d.loc["H"]
    bands_hi = d[[f"rate_{b}" for b in I.BANDS]]
    band_order = bool(((bands_hi["rate_1-4"] > bands_hi["rate_Non-employing"])).all())
    n_5_below_14 = int((d["rate_5+"] < d["rate_1-4"]).sum())
    nat_entries_latest = int(s[(s.dimension == "industry") & (s.level == "total") & (s.cohort == "entries")
                               & (s.years_after == 3) & (s.start == last)]["base"].iloc[0])
    top3 = t[I.COHORTS].rank(ascending=False) <= 3
    top_stable = bool(top3.all(axis=1).sum() == 3 and top3.all(axis=1).loc[top.index].all())
    low_share = nat_w["Non-employing"].idxmin()
    all_bands_fell = all(v < 0 for v in dec["band_change"].values())
    retail_bottom_latest = bool((t[I.COHORTS[-2:]].rank(method="min").loc["Retail Trade"] <= 5).all())
    low5_non = (low5["entries"] * low5["non_employing_share"]).sum() / low5["entries"].sum()
    assert low_share == I.COHORTS[1], "the mix sentence in section 2 assumes the 2nd cohort has the lowest share"
    gap_14_non = d["rate_1-4"] - d["rate_Non-employing"]

    L: list[str] = []
    a = L.append
    a("# Part 2: which industries new businesses last in")
    a("")
    a("*Generated by `scripts/industry_survival.py` from the snapshot in `data/`. Do not edit by hand.*")
    a("")
    a("Part 1's rules apply throughout: survival means \"still actively trading\" at 30 June (an exit isn't a failure); "
      "industries are compared within size bands or at a common size mix; no rate on a base of "
      f"{SMALL_BASE} businesses or fewer, and perturbed cells are summed before a rate is computed; 'Currently "
      "Unknown' is left out of rankings.")
    a("")
    a("## At a glance")
    a("")
    a(f"- **The bottom of the table doesn't move.** {'; '.join(st['always_bottom'][:-1])}; and "
      f"{st['always_bottom'][-1]} are among the 5 industries with the lowest survival in all four entry cohorts "
      f"({first} to {last}). {bottom.index[0]} is lowest in the latest cohort: {rate(bottom.iloc[0][last])} of its "
      f"{n(bottom.iloc[0]['entries_latest'])} {last} entrants were still trading three Junes on, against "
      f"{rate(pub_nat[last])} for all industries.")
    a(f"- **Survival fell in {int((t['change'] < 0).sum())} of 19 industries** between the {first} and {last} "
      f"cohorts. {falls.index[0]} fell the most ({rate(falls.iloc[0][first])} → {rate(falls.iloc[0][last])}, "
      f"{pts(falls.iloc[0]['change'])}), then {falls.index[1]} ({pts(falls.iloc[1]['change'])}).")
    assert dec["total"] < 0 and dec["within"] < 0
    a(f"- **The national fall isn't a shift towards sole traders.** National survival went from "
      f"{rate(pub_nat[first])} for the {first} cohort to {rate(pub_nat[last])} for the {last} cohort. On unrounded "
      f"counts that is {pts(dec['total'])}: {pts(dec['within'])} inside the size bands and {pts(dec['mix'])} from "
      f"the size mix.")
    assert up.name == "H", "the text below assumes Accommodation and Food Services is the most flattered"
    a(f"- **Size mix flatters some industries.** At the national size mix of 2021-22 entrants, {acc['industry']} "
      f"falls from {ordinal(int(acc['rank_rate_all']))} to {ordinal(int(acc['rank_std']))} lowest "
      f"({rate(acc['rate_all'])} → {rate(acc['std'])}): only {pct(acc['non_employing_share'], 0)} of its entrants "
      f"employ no one, against {pct(w3['Non-employing'], 0)} nationally. {down['industry']} is the opposite case: "
      f"{pct(down['non_employing_share'], 0)} non-employing, so its overall rate is {abs(down['mix_effect']):.1f} points below "
      f"its rate at the national mix ({rate(down['rate_all'])} → {rate(down['std'])}).")
    a(f"- **An industry average can hide a wide gap.** Among the {len(big)} subdivisions with "
      f"{MIN_ENTRANTS}+ entrants, survival at the national size mix runs from {rate(big.iloc[0]['std_2'])} "
      f"({big.iloc[0]['subdivision']}) to {rate(big.iloc[-1]['std_2'])} ({big.iloc[-1]['subdivision']}). Within "
      f"{fnb['industry']}, {fnb['subdivision']} is at {rate(fnb['std_2'])} and {sd.loc['44', 'subdivision']} at "
      f"{rate(sd.loc['44', 'std_2'])}.")
    assert 0.4 <= fjs.min() and fjs.max() <= 0.6, "'about half' no longer describes the first-June share"
    a(f"- **About half of the three-year loss happens by the first June.** In every industry, {pct(fjs.min(), 0)} to "
      f"{pct(fjs.max(), 0)} of the {last} entrants that had stopped trading by the third June had already stopped by "
      f"the first ({pct(nat_fjs, 0)} nationally).")
    a("")

    # 1. four cohorts
    a("## 1. Four cohorts by industry (data cube 1, not perturbed)")
    a("")
    a(f"Share of each cohort's entrants still trading three Junes after the entry year (the {last} entrants at June "
      f"2026). Sorted by the {last} cohort; rank 1 = lowest survival.")
    a("")
    a(f"| Industry | {' | '.join(I.COHORTS)} | Change | {last} entrants | Rank | Cohorts in bottom 5 |")
    a("|---|" + "---|" * (len(I.COHORTS) + 4))
    for ind, r in t.iterrows():
        a(f"| {ind} | {' | '.join(rate(r[c]) for c in I.COHORTS)} | {sgn(r['change'])} | "
          f"{n(r['entries_latest'])} | {int(r['rank_latest'])} | {int(r['cohorts_in_bottom'])} |")
    a(f"| **All industries** | {' | '.join(rate(pub_nat[c]) for c in I.COHORTS)} | "
      f"{sgn(pub_nat[last] - pub_nat[first])} | {n(nat_entries_latest)} | | |")
    a("")
    a("Change is in percentage points, " f"{first} to {last}.")
    a("")
    a(f"- **Rankings are stable but not fixed.** The rank correlation between any two cohorts is "
      f"{st['min']:.2f} to {st['max']:.2f}. Industries moved by up to {(t['high'] - t['low']).max():.1f} points "
      f"across the four cohorts ({(t['high'] - t['low']).idxmax()}), so one cohort's rate is a guide, not a constant.")
    a(f"- **{retail.name} is the one to watch.** It fell from {rate(retail[first])} to {rate(retail[last])} and "
      f"was in the bottom 5 in {int(retail['cohorts_in_bottom'])} of 4 cohorts"
      f"{', the two latest included' if retail_bottom_latest else ''}.")
    a(f"- **Only {len(rises)} industries improved:** "
      + "; ".join(f"{i} ({pts(r['change'])}, {n(r['entries_latest'])} entrants)" for i, r in rises.iterrows())
      + ".")
    a(f"- **The top three are the same in every cohort:** {top.index[0]} ({rate(top.iloc[0][last])} in {last}), "
      f"{top.index[1]} ({rate(top.iloc[1][last])}) and {top.index[2]} ({rate(top.iloc[2][last])})." if top_stable else
      f"- **The top three in the {last} cohort** are {top.index[0]}, {top.index[1]} and {top.index[2]}; the top "
      f"three changed between cohorts.")
    a("")
    a("![Four cohorts by industry](charts/06_industry_cohorts.png)")
    a("")

    # 2. national trend
    a("## 2. Is the national fall just more sole traders?")
    a("")
    a("No. National survival can fall because each size band does worse, or because the mix shifts towards "
      "non-employing entrants, who survive less. A shift-share split (average weights × change in rates, plus "
      "change in weights × average rates; the two parts add to the total) separates the two. Changes are computed "
      "from counts, so they can differ by 0.1 from the gap between the rounded published rates:")
    a("")
    a("| Cohorts | Change in national survival | Inside the size bands | From the size mix |")
    a("|---|---|---|---|")
    for x in steps + [dec]:
        a(f"| {x['from']} → {x['to']} | {pts(x['total'])} | {pts(x['within'])} | {pts(x['mix'])} |")
    a("")
    a(f"From {first} to {last}, non-employing entrants' survival moved {pts(dec['band_change']['Non-employing'])}, "
      f"1-4 employees {pts(dec['band_change']['1-4'])} and 5 or more {pts(dec['band_change']['5+'])}. The "
      f"non-employing share of entrants was {pct(nat_w.loc[first, 'Non-employing'])} in {first} and "
      f"{pct(nat_w.loc[last, 'Non-employing'])} in {last}; the {low_share} cohort had the lowest share "
      f"({pct(nat_w.loc[low_share, 'Non-employing'])}), which is why the mix added "
      f"{pts(steps[0]['mix'])} that year and took back {pts(abs(steps[1]['mix'])).lstrip('+')} the next. The three bands' rates "
      f"rebuilt from data cube 1 give the published national rate to within "
      f"{(nat_tot - pub_nat[I.COHORTS]).abs().max():.2f} points.")
    a("")
    a("![National size bands](charts/09_national_size_bands.png)")
    a("")

    # 3. size bands
    a("## 3. Industries within size bands and at a common size mix (data cube 5)")
    a("")
    a(f"Entrants of 2021-22, still trading at June 2025, summed over states. Bands: non-employing, 1-4 employees, "
      f"5 or more (20-199 and 200+ are folded in because by industry they fall under the floor; 20+ employee entrants: "
      f"{', '.join(f'{r.industry} {n(r.entrants)}' for r in sub_small_bands(sub).itertuples())}). "
      f"The common-mix rate weights each industry's band rates by the national share of 2021-22 entrants in that "
      f"band ({', '.join(f'{b} {pct(w3[b])}' for b in I.BANDS)}). Rank 1 = lowest survival.")
    a("")
    a("| Industry | Entrants | Non-employing share | Overall | Non-employing | 1-4 | 5+ | At national mix | "
      "Rank overall | Rank at mix |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for _, r in d.iterrows():
        a(f"| {r['industry']} | {n(r['entries'])} | {pct(r['non_employing_share'], 0)} | {rate(r['rate_all'])} | "
          f"{rate(r['rate_Non-employing'])} | {rate(r['rate_1-4'])} | {rate(r['rate_5+'])} | {rate(r['std'])} | "
          f"{int(r['rank_rate_all'])} | {int(r['rank_std'])} |")
    a("")
    a(f"- **{acc['industry']}** has the lowest non-employing share ({pct(acc['non_employing_share'], 0)}; next lowest "
      f"{pct(d['non_employing_share'].nsmallest(2).iloc[-1], 0)}), so "
      f"its overall rate ({rate(acc['rate_all'])}) is {abs(acc['mix_effect']):.1f} points above its rate at the national mix "
      f"({rate(acc['std'])}). Within each band it is {ordinal(int(acc['rank_rate_Non-employing']))} lowest "
      f"(non-employing), {ordinal(int(acc['rank_rate_1-4']))} (1-4) and {ordinal(int(acc['rank_rate_5+']))} (5+). "
      f"For a lender, a non-employing entrant in {fnb['subdivision']} (cafés, restaurants, takeaways, pubs and "
      f"clubs) is a weaker prospect than the industry's overall rate suggests: {rate(fnb['rate_Non-employing'])} "
      f"of them were still trading, against {rate(fnb['rate_Employing'])} of employing ones.")
    assert down["rank_rate_all"] == 1, "the text below assumes the most held-down industry is lowest overall"
    a(f"- **{down['industry']}** is lowest overall ({rate(down['rate_all'])}) but {ordinal(int(down['rank_std']))} "
      f"lowest at the national mix ({rate(down['std'])}): {pct(down['non_employing_share'], 0)} of its entrants "
      f"employ no one. Its non-employing entrants rank {ordinal(int(down['rank_rate_Non-employing']))} lowest "
      f"({rate(down['rate_Non-employing'])}) but its 1-4 employee entrants only "
      f"{ordinal(int(down['rank_rate_1-4']))} lowest ({rate(down['rate_1-4'])}).")
    a(f"- **Employing entrants last longer in every industry.** The 1-4 band beats the non-employing band in "
      f"{'all' if band_order else 'most'} {len(d)} industries, by {gap_14_non.min():.1f} to "
      f"{gap_14_non.max():.1f} points. The 5+ band is noisier (bases of {n(d['base_5+'].min())} to "
      f"{n(d['base_5+'].max())}) and is below the 1-4 band in {n_5_below_14} industries.")
    a(f"- **The method holds up.** With two bands (non-employing, employing) instead of three, every industry's "
      f"common-mix rate moves by at most {std_gap.max():.2f} points and the ranking is "
      f"{'identical' if same_order else 'different'}. The overall rates rebuilt here from data cube 5 are within "
      f"0.78 points of data cube 1's published ones (Part 1).")
    a("")
    a("![Common size mix](charts/07_common_size_mix.png)")
    a("")

    # 4. subdivisions
    a("## 4. Subdivisions (data cube 5)")
    a("")
    a(f"The {len(sd)} ANZSIC subdivisions with entrants, summed over states. With three bands, too many small "
      f"subdivisions fall under the floor in the 5+ band, so the common mix uses two: non-employing "
      f"({pct(w3['Non-employing'])}) and employing ({pct(1 - w3['Non-employing'])}). {len(rated)} subdivisions clear "
      f"the floor in both bands; {len(unrated)} don't ({', '.join(unrated['subdivision'])}). The tables below show "
      f"the {len(big)} with {MIN_ENTRANTS} or more entrants ({pct(big_share)} of all entrants); the rest are in "
      f"`results/subdivision_survival.csv`.")
    a("")
    for title, part in (("Lowest", big.head(10)), ("Highest", big.tail(10).iloc[::-1])):
        a(f"**{title} 10 at the national size mix**")
        a("")
        a("| Subdivision | Industry | Entrants | Non-employing share | Overall | Non-employing | Employing | "
          "At national mix |")
        a("|---|---|---|---|---|---|---|---|")
        for code, r in part.iterrows():
            a(f"| {r['subdivision']} ({code}) | {r['industry']} | {n(r['entries'])} | "
              f"{pct(r['non_employing_share'], 0)} | {rate(r['rate_all'])} | {rate(r['rate_Non-employing'])} | "
              f"{rate(r['rate_Employing'])} | {rate(r['std_2'])} |")
        a("")
    lo_ind = low5["industry"].value_counts()
    a(f"- **The five weakest {'have more non-employing entrants than average' if low5_non > w3['Non-employing'] else 'are'}.** {low5.iloc[0]['subdivision']}, "
      f"{low5.iloc[1]['subdivision']}, {low5.iloc[2]['subdivision']}, {low5.iloc[3]['subdivision']} and "
      f"{low5.iloc[4]['subdivision']} have the five lowest common-mix rates "
      f"({rate(low5['std_2'].min())} to {rate(low5['std_2'].max())}); together they had "
      f"{n(low5['entries'].sum())} entrants, {pct(low5['entries'].sum() / sd['entries'].sum())} of all 2021-22 "
      f"entrants, {pct(low5_non, 0)} of them non-employing (against {pct(w3['Non-employing'], 0)} nationally).")
    a(f"- **The five strongest:** {high5.iloc[0]['subdivision']} "
      f"({rate(high5.iloc[0]['std_2'])}), {high5.iloc[1]['subdivision']} ({rate(high5.iloc[1]['std_2'])}), "
      f"{high5.iloc[2]['subdivision']} ({rate(high5.iloc[2]['std_2'])}), "
      f"{high5.iloc[3]['subdivision']} ({rate(high5.iloc[3]['std_2'])}) and "
      f"{high5.iloc[4]['subdivision']} ({rate(high5.iloc[4]['std_2'])}).")
    a(f"- **One division can hold both ends.** In {fnb['industry']}, {fnb['subdivision']} is at "
      f"{rate(fnb['std_2'])} at the national mix and {sd.loc['44', 'subdivision']} at "
      f"{rate(sd.loc['44', 'std_2'])}; a division-level benchmark hides that gap.")
    a("")
    a("![Subdivisions](charts/08_subdivisions.png)")
    a("")

    # 5. so what
    a("## 5. What this means for the business")
    a("")
    a(f"- **Lenders and investors:** price a new business on its industry *and* its size, not the industry's overall "
      f"rate. For a non-employing entrant the relevant figure is the non-employing column, which is "
      f"{gap_14_non.min():.1f} to {gap_14_non.max():.1f} points below the 1-4 employee column in every industry. "
      f"Use the range across cohorts (section 1) as a guide to how much an industry's rate can move, not one year's "
      f"rate alone.")
    a(f"- **Small-business advisers and programmes:** support should be front-loaded. About half of the three-year "
      f"loss has happened by the first June in every industry, so the first one to two years after entering are where "
      f"help counts. On a like-for-like basis, the industries where entrants most need it are "
      f"{', '.join(d.head(5)['industry'].iloc[:-1])} and {d.head(5)['industry'].iloc[-1]}.")
    a(f"- **Policy and industry bodies:** {retail.name}'s fall ({pts(retail['change'])} over four cohorts) is the "
      f"largest of any industry and worth explaining. The national decline happened "
      f"{'inside every size band' if all_bands_fell else 'mostly inside the size bands'}, so it isn't explained by "
      f"more sole traders registering.")
    a("")
    a("## Caveats")
    a("")
    a(f"- Sections 3 and 4 cover one cohort (2021-22 entrants to June 2025); the industry × size detail for later "
      f"cohorts is due on 18 December 2026. Section 1 shows how much a single cohort can move.")
    a("- Data cube 5 is perturbed. Rates are computed from counts summed over states, never from single cells, and "
      f"bands with {SMALL_BASE} or fewer businesses get no rate. Because cells are perturbed, the size bands don't add "
      "exactly to the published totals.")
    a("- The common-mix rate is a what-if (the industry's own band rates at the national size mix), not a forecast. It "
      "removes the effect of size, not of anything else that differs between industries (location, capital, "
      "licensing).")
    a("- Survival is measured at 30 June. Businesses that start and stop within a year are never counted, and an "
      "exit can be a sale or a restructure.")
    a("")
    a("## Output files")
    a("")
    a("- `results/industry_cohorts.csv`: divisions, survival of four entry cohorts, change, ranks, first-June share")
    a("- `results/industry_size_bands.csv`: divisions, 2021-22 entrants by size band and at the national size mix")
    a("- `results/subdivision_survival.csv`: subdivisions, overall and two-band common-mix rates (blank under the floor)")
    a("- `results/national_size_bands.csv`: national entrants by size band and cohort (weights and rates)")
    (RESULTS / "INDUSTRY_SURVIVAL.md").write_text("\n".join(L) + "\n")
    print("wrote results/INDUSTRY_SURVIVAL.md and 4 charts")
    return 0


def sub_small_bands(sub: pd.DataFrame) -> pd.DataFrame:
    """Divisions whose 20+ employee entrants are at or under the floor (why 20-199 and 200+ are folded in)."""
    x = sub[(sub.cohort == "entries") & (sub.years_after == 3) & (sub.level == "group") & (sub.division != "X")
            & sub["size"].isin(["20-199", "200+"])]
    g = x.groupby("division")["base"].sum()
    g = g[g <= SMALL_BASE].sort_values(kind="stable")
    return pd.DataFrame({"industry": [I.DIVISION_NAMES[k] for k in g.index], "entrants": g.values})


if __name__ == "__main__":
    sys.exit(main())
