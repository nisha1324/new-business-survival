"""Part 3 report: where new businesses last, and where business numbers are growing.

Reads the tidy snapshot in data/ and writes:
- results/REGIONS.md                  the report (every figure comes from this script)
- results/state_cohorts.csv           states: survival of four entry cohorts (data cube 1)
- results/state_flows.csv             states: businesses, entries and exits, 2019-20 to 2025-26 (data cube 1)
- results/state_mix.csv               states, 2021-22 entrants: size bands, expected rate given the mix, split
- results/state_excess_vic.csv        Victoria's 2021-22 entrants by subdivision vs the other states
- results/lga_growth.csv              LGAs: businesses and employing businesses, June 2023 and June 2025
- results/lga_growth_by_industry.csv  change by industry, all LGAs and the 20 fastest-growing
- results/charts/10-14 *.png
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.profile_source import (  # noqa: E402  (also sets the shared chart style)
    BLUE, CHARTS, GRID, INK, INK_2, MUTED, ORANGE, RESULTS, SAVE, SURFACE, n, ordinal, pct, plt, rate,
)
from scripts.industry_survival import MIN_ENTRANTS, pts, sgn  # noqa: E402
from cabee import load, industries as I, regions as R  # noqa: E402
from cabee.industries import BANDS, COHORTS, weights  # noqa: E402
from cabee.profile import SMALL_BASE  # noqa: E402

import pandas as pd  # noqa: E402

TOP_K = 20     # "fastest-growing LGAs" = the top 20 by growth among LGAs above the floor
EXCESS_K = 3   # Victoria's subdivisions with the largest excess of 2021-22 entrants
KEYS = {"division x 3 size bands": ("division", "band"), "subdivision x 2 size bands": ("subdivision_code", "band"),
        "subdivision x 5 sizes": ("subdivision_code", "size")}
MAIN_KEY = "division x 3 size bands"


def sn(x: float) -> str:
    """A signed whole number with a true minus sign."""
    return f"{'+' if x >= 0 else '−'}{n(abs(x))}"


def pc(x: float, nd: int = 1) -> str:
    """A share (0-1) as a percentage with a true minus sign; a value that rounds to zero has no sign."""
    return f"{0:.{nd}f}%" if round(x * 100, nd) == 0 else pct(x, nd).replace("-", "−")


def lowest(k: int) -> str:
    return "the lowest" if k == 1 else f"{ordinal(k)} lowest"


def short(ind: str) -> str:
    return ind.replace(" and ", " & ").replace(", Postal & Warehousing", ", Postal & W/housing")


# ------------------------------------------------------------------ charts
def chart_state_cohorts(t: pd.DataFrame, path: Path) -> None:
    first, last = COHORTS[0], COHORTS[-1]
    m = t.drop(index=R.NATIONAL).sort_values(last, kind="stable")
    nat = t.loc[R.NATIONAL]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    y = list(range(len(m)))
    for i, (_, r) in enumerate(m.iterrows()):
        ax.plot([r["low"], r["high"]], [i, i], color=GRID, linewidth=6, solid_capstyle="round", zorder=1)
        ax.text(r["high"] + 0.35, i, rate(r[last]), va="center", fontsize=8.5, color=INK_2)
    ax.scatter(m[first], y, s=56, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2, label=f"{first} entrants")
    ax.scatter(m[last], y, s=64, color=BLUE, zorder=4, edgecolor=SURFACE, linewidth=2, label=f"{last} entrants")
    ax.plot([], [], color=GRID, linewidth=6, label="Range across the four cohorts")
    ax.axvline(nat[last], color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=0)
    ax.text(nat[last] + 0.12, len(m) - 0.45, f"Australia, {last}: {rate(nat[last])}", fontsize=8, color=INK_2)
    ax.set_yticks(y, list(m.index), fontsize=9)
    ax.set_xlabel("Still trading three Junes after the entry year (%)")
    ax.set_xlim(43.5, 57)
    ax.set_ylim(-0.6, len(m) - 0.1)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    lo, hi = m.index[0], m.index[-1]
    fig.text(0.015, 0.975, f"{hi} keeps its new businesses longest; {R.ABBR[lo]} the least in {last}", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.93, f"Entrants by state: share still trading three Junes on, {first} to {last} cohorts "
             f"(label: {last})", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper left", bbox_to_anchor=(0.008, 0.905), frameon=False, ncol=3, fontsize=9,
               labelcolor=INK_2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_state_mix(ms: pd.DataFrame, national: float, path: Path) -> None:
    m = ms.sort_values("local", kind="stable")
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    y = list(range(len(m)))
    for i, (_, r) in enumerate(m.iterrows()):
        ax.annotate("", xy=(r["actual"], i), xytext=(r["expected"], i),
                    arrowprops={"arrowstyle": "-", "color": GRID, "linewidth": 2.5}, zorder=1)
        right = max(r["actual"], r["expected"])
        ax.text(right + 0.35, i, f"{pts(r['local'])} not explained by mix", va="center", fontsize=8, color=INK_2)
    ax.scatter(m["expected"], y, s=56, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2,
               label="Expected from its industry × size mix")
    ax.scatter(m["actual"], y, s=64, color=BLUE, zorder=4, edgecolor=SURFACE, linewidth=2, label="Actual")
    ax.axvline(national, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=0)
    ax.text(national + 0.12, len(m) - 0.45, f"Australia {rate(national)}", fontsize=8, color=INK_2)
    ax.set_yticks(y, list(m.index), fontsize=9)
    ax.set_xlabel(f"{R.COHORT} entrants still trading at June 2025 (%)")
    ax.set_xlim(44, 63)
    ax.set_ylim(-0.6, len(m) - 0.1)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.975, f"After allowing for mix, {m.index[-1]} leads and {m.index[0]} trails", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.93, "Expected = the state's own industry × size mix at national survival rates per cell "
             "(data cube 5)", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper left", bbox_to_anchor=(0.008, 0.905), frameon=False, ncol=2, fontsize=9,
               labelcolor=INK_2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_excess(ex: pd.DataFrame, path: Path, k: int = 8) -> None:
    m = ex.head(k)
    share = ex.attrs["overall_share"]
    fig, ax = plt.subplots(figsize=(8.5, 4.9))
    y = list(range(len(m)))
    ax.barh(y, m["share"] * 100, color=BLUE, height=0.62)
    for yi, (_, r) in zip(y, m.iterrows()):
        ax.text(r["share"] * 100 + 0.8, yi, f"{pct(r['share'], 0)}  ·  +{n(r['excess'])} entrants  ·  "
                f"{rate(r['rate_state'])} vs {rate(r['rate_rest'])}", va="center", fontsize=8, color=INK)
    ax.axvline(share * 100, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(share * 100 + 0.5, -0.95, f"Vic share of all entrants {pct(share, 0)}", fontsize=8.5, color=INK_2,
            va="center")
    names = [f"{s[:44]}{'…' if len(s) > 44 else ''}" for s in m["subdivision"]]
    ax.set_yticks(y, names, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel(f"Victoria's share of the 8 states' {R.COHORT} entrants in the subdivision (%)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.975, f"Victoria's {R.COHORT} entrants were over-represented in transport and cleaning", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.935, "Labels: Vic share · entrants above Vic's overall share · still trading at June 2025, "
             "Vic vs other states", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_lga(top: pd.DataFrame, path: Path) -> None:
    m = top.head(15)
    fig, ax = plt.subplots(figsize=(8.5, 6.0))
    y = list(range(len(m)))
    first = m["businesses_2023"]
    ne = 100 * m["non_employing_change"] / first
    em = 100 * m["employing_change"] / first
    ax.barh(y, ne, color=BLUE, height=0.62, label="Non-employing businesses")
    ax.barh(y, em, left=ne.where(em >= 0, 0), color=ORANGE, height=0.62, label="Employing businesses")
    for yi, (_, r) in zip(y, m.iterrows()):
        ax.text(100 * r["growth"] + 0.4 if r["employing_change"] >= 0 else 100 * r["non_employing_change"] /
                r["businesses_2023"] + 0.4, yi,
                f"{pct(r['growth'])}  ({n(r['businesses_2023'])} → {n(r['businesses_2025'])})", va="center",
                fontsize=8, color=INK)
    ax.set_yticks(y, [f"{r['lga']} ({r['state_abbr']})" for _, r in m.iterrows()], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 32)
    ax.set_xlabel(f"Growth in businesses operating, June {R.LGA_FIRST} to June {R.LGA_LAST} (%), split by size")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.975, "The fastest-growing areas are adding businesses that employ no one", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.94, f"The 15 fastest-growing of {len(top)} LGAs with {n(R.LGA_FLOOR)}+ businesses in June "
             f"{R.LGA_FIRST} (data cube 10)", fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper left", bbox_to_anchor=(0.008, 0.92), frameon=False, ncol=2, fontsize=9,
               labelcolor=INK_2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


def chart_drivers(dr: pd.DataFrame, path: Path) -> None:
    m = dr[dr.index != "Currently Unknown"].sort_values("change", ascending=False, kind="stable")
    assert (m["non_employing_change"] > 0).sum() > len(m) / 2 and (m["employing_change"] < 0).sum() > len(m) / 2
    fig, ax = plt.subplots(figsize=(8.5, 6.6))
    y = list(range(len(m)))
    h = 0.38
    ax.barh([i - h / 2 for i in y], m["non_employing_change"] / 1000, height=h, color=BLUE,
            label="Non-employing businesses")
    ax.barh([i + h / 2 for i in y], m["employing_change"] / 1000, height=h, color=ORANGE,
            label="Employing businesses")
    for i, (_, r) in enumerate(m.iterrows()):
        x = max(r["non_employing_change"], r["employing_change"], 0) / 1000
        ax.text(x + 0.4, i, f"net {'+' if r['change'] >= 0 else '−'}{n(abs(r['change']))}", va="center", fontsize=8,
                color=INK_2)
    ax.axvline(0, color=INK_2, linewidth=0.8)
    ax.set_yticks(y, [short(i) for i in m.index], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(-6, 40)
    ax.set_xlabel(f"Change in businesses operating, June {R.LGA_FIRST} to June {R.LGA_LAST} (thousands)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.975, "Most industries added non-employing businesses and lost employing ones", fontsize=12,
             fontweight="bold", color=INK, va="top")
    fig.text(0.015, 0.943, "All LGAs (data cube 10), by industry: change in non-employing and employing businesses",
             fontsize=9, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper left", bbox_to_anchor=(0.008, 0.928), frameon=False, ncol=2, fontsize=9,
               labelcolor=INK_2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


# ------------------------------------------------------------------ report
def main() -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    s, f, sub, lga = (load.read(k) for k in ("survival", "flows", "subdivision_survival", "lga_counts"))
    first, last = COHORTS[0], COHORTS[-1]

    sc = R.state_cohorts(s)
    sf = R.state_flows(f)
    sb = R.state_bands(sub, s)
    nat_pub = float(sc.loc[R.NATIONAL, R.COHORT])
    exps = {k: R.expected(sub, key) for k, key in KEYS.items()}
    splits = {k: R.mix_split(sb, e, nat_pub) for k, e in exps.items()}
    ms = splits[MAIN_KEY]
    e = exps[MAIN_KEY]
    vic_row = s[(s.dimension == "state") & (s.group == "Victoria") & (s.cohort == "entries") & (s.years_after == 3)
                & (s.start == R.COHORT)].iloc[0]
    ex = R.excess_entrants(sub, "Victoria")
    vic_wo = R.without(float(vic_row["base"]), float(vic_row["survived"]), ex.head(EXCESS_K))
    g = R.lga_growth(lga)
    rk = R.ranked(g)
    top = rk.head(TOP_K)
    dr_all = R.growth_drivers(lga)
    dr_top = R.growth_drivers(lga, top["lga_code"])
    sz_all = R.size_change(lga)
    sz_top = R.size_change(lga, top["lga_code"])
    spread = R.state_lga_spread(g)

    sc.round(4).to_csv(RESULTS / "state_cohorts.csv")
    sf.round(4).to_csv(RESULTS / "state_flows.csv")
    mix_out = sb.join(e[["expected", "cells_actual", "national_cells"]]).join(
        ms[["gap", "mix", "local", "residual", "rank_local"]])
    for k, sp in splits.items():
        if k != MAIN_KEY:
            mix_out[f"local [{k}]"] = sp["local"]
    mix_out.round(4).to_csv(RESULTS / "state_mix.csv")
    ex.round(4).to_csv(RESULTS / "state_excess_vic.csv")
    g.assign(above_floor=g["businesses_2023"] >= R.LGA_FLOOR).round(4).to_csv(RESULTS / "lga_growth.csv", index=False)
    pd.concat({"all_lgas": dr_all, f"top_{TOP_K}_lgas": dr_top}, names=["set"]).round(4).to_csv(
        RESULTS / "lga_growth_by_industry.csv")

    chart_state_cohorts(sc, CHARTS / "10_state_cohorts.png")
    chart_state_mix(ms, nat_pub, CHARTS / "11_state_mix.png")
    chart_excess(ex, CHARTS / "12_victoria_2021_22.png")
    chart_lga(rk, CHARTS / "13_lga_growth.png")
    chart_drivers(dr_all, CHARTS / "14_growth_by_industry.png")

    # --- figures used in the text
    st = sc.drop(index=R.NATIONAL)
    nat = sc.loc[R.NATIONAL]
    hi, lo = st[last].idxmax(), st[last].idxmin()
    always_top = [x for x in st.index if (st[[f"rank_{c}" for c in COHORTS]] == len(st)).all(axis=1)[x]]
    top2 = st[[f"rank_{c}" for c in COHORTS]] >= len(st) - 1
    top2_states = [x for x in st.index if top2.all(axis=1)[x]]
    vic = st.loc["Victoria"]
    sfs = sf.drop(index=R.NATIONAL)
    fastest, slowest = sfs["growth"].idxmax(), sfs["growth"].idxmin()
    loc_rank = ms.sort_values("local", kind="stable")
    gap_spread = max((sp["local"] - ms["local"]).abs().max() for sp in splits.values())
    swapped = sorted({x for sp in splits.values() for x in sp.index
                      if sp["local"].rank()[x] != ms["local"].rank()[x]}, key=R.STATES.index)
    rank_same = all((sp["local"].rank() == ms["local"].rank()).all() for sp in splits.values())
    bias = (e["cells_actual"] - ms["actual"])
    worst_bias = bias.idxmin()
    vic_mix_share = ms.loc["Victoria", "mix"] / ms.loc["Victoria", "gap"]
    ex3 = ex.head(EXCESS_K)
    vic_lower_all = bool((ex3["rate_state"] < ex3["rate_rest"]).all())
    neighbours = sc.loc["Victoria", COHORTS]
    vic_entries = s[(s.dimension == "state") & (s.group == "Victoria") & (s.cohort == "entries") & (s.years_after == 3)]
    vic_entries = vic_entries.set_index("start")["base"]
    nat_entries = s[(s.dimension == "state") & (s.group == R.NATIONAL) & (s.cohort == "entries")
                    & (s.years_after == 3)].set_index("start")["base"]
    vic_share_e = vic_entries / nat_entries
    tot_chg = sz_all["change"].sum()
    ne_all = sz_all.loc["Non employing", "change"]
    emp_all = tot_chg - ne_all
    ne_top = sz_top.loc["Non employing", "change"]
    tot_top = sz_top["change"].sum()
    tr_all, tr_top = dr_all.loc["Transport, Postal and Warehousing"], dr_top.loc["Transport, Postal and Warehousing"]
    assert dr_all.index[0] == "Transport, Postal and Warehousing" and dr_top.index[0] == tr_top.name
    first_lga, all_first = rk.iloc[0], g["businesses_2023"].sum()
    top_states = top["state_abbr"].value_counts()
    top_tr = int((top["top_division"] == "Transport, Postal and Warehousing").sum())
    shrink = rk[rk["growth"] < 0]
    emp_fell = rk[rk["employing_growth"] < 0]
    emp_top = rk.sort_values(["employing_growth", "lga"], ascending=[False, True], kind="stable").head(5)
    corr = float(rk[["growth", "employing_growth"]].corr().iloc[0, 1])
    neg_emp_ind = dr_all[(dr_all["employing_change"] < 0) & (dr_all.index != "Currently Unknown")]
    n_ind = int((dr_all.index != "Currently Unknown").sum())
    hc = dr_all.loc["Health Care and Social Assistance"]
    assert hc["employing_change"] == dr_all["employing_change"].max(), "text assumes health care adds the most employers"
    w = weights(s, R.COHORT)
    nsw = ms.loc["New South Wales"]
    tas = ms.loc["Tasmania"]
    lga_cells = len(g)
    nat_growth_g = float(sz_all["change"].sum() / sz_all["businesses_2023"].sum())
    wa = spread.loc["Western Australia"]
    vic_sp = spread.loc["Victoria"]
    above = rk["growth"] > nat_growth_g
    assert always_top == [hi], "the text says the top state is first in every cohort"
    assert (st["high"] - st["low"]).idxmax() == "Victoria" and st[COHORTS].min().min() == vic["low"]
    assert (sfs["growth"] > 0).all() and sfs["entry_rate"].idxmin() == slowest
    assert sb["non_employing_share"].idxmax() == "Victoria"
    assert spread.loc[spread["lgas"] > 1, "median"].idxmax() == wa.name and spread["median"].idxmin() == vic_sp.name
    assert spread["shrinking"].idxmax() == vic_sp.name
    top3_14 = set(sb["rate_1-4"].nlargest(3).index) == set(loc_rank.index[-3:])
    p2 = I.division_bands(sub, s)
    p2_span = float(p2["rate_Non-employing"].max() - p2["rate_Non-employing"].min())
    assert p2_span > 2 * (ms["local"].max() - ms["local"].min())
    p2_big = I.subdivision_bands(sub, s)
    p2_big = p2_big[(p2_big["entries"] >= MIN_ENTRANTS) & p2_big["std_2"].notna()].sort_values("std_2", kind="stable")
    p2_pos = sorted(int(p2_big.index.get_loc(c)) + 1 for c in ex3.index)
    vic_fast = rk.head(10)[rk.head(10)["state"] == "Victoria"]
    vic_pos = [int(rk.index.get_loc(i)) + 1 for i in vic_fast.index]
    assert top_tr >= TOP_K // 2, "the text says transport added the most in most of the top LGAs"
    assert ne_top / tot_top > 0.9 and ne_all > tot_chg, "the text relies on these two shares"

    L: list[str] = []
    a = L.append
    a("# Part 3: where new businesses last, and where business numbers are growing")
    a("")
    a("*Generated by `scripts/regions_report.py` from the snapshot in `data/`. Do not edit by hand.*")
    a("")
    a("Part 1's rules apply: survival means \"still actively trading\" at 30 June (an exit isn't a failure); survival "
      "below state level isn't published, so states are compared on survival and local government areas (LGAs) on "
      "growth in business numbers; states are compared within size bands or after allowing for their mix; no rate on "
      f"a base of {SMALL_BASE} businesses or fewer; 'Other Territories/Currently Unknown' is left out of rankings.")
    a("")
    a("## At a glance")
    a("")
    a(f"- **{hi} keeps its new businesses longest, in every cohort.** {rate(st.loc[hi, last])} of its {last} "
      f"entrants were still trading three Junes on, against {rate(nat[last])} nationally; "
      f"{lo} was lowest at {rate(st.loc[lo, last])}.")
    a(f"- **Allowing for mix changes the picture.** Given each state's industry × size mix, {nsw.name} would be "
      f"expected to keep {rate(nsw['expected'])} of its {R.COHORT} entrants; it kept {rate(nsw['actual'])}, "
      f"{abs(nsw['local']):.1f} points fewer, the weakest of the 8 states on that basis. {tas.name} kept "
      f"{tas['local']:.1f} points more than its mix predicts, then {loc_rank.index[-2]} ({pts(loc_rank.iloc[-2]['local'])}) "
      f"and {loc_rank.index[-3]} ({pts(loc_rank.iloc[-3]['local'])}).")
    assert ms.loc["Victoria", "gap"] < 0 and ms.loc["Victoria", "mix"] < 0
    a(f"- **Victoria's weak {R.COHORT} cohort is mostly mix.** Its entrants were "
      f"{abs(ms.loc['Victoria', 'gap']):.1f} points below the national rate; "
      f"{abs(ms.loc['Victoria', 'mix']):.1f} points of that is its industry × size mix. That year "
      f"Victoria had {n(vic_entries[R.COHORT])} entrants ({pct(vic_share_e[R.COHORT])} of Australia's), and was "
      f"over-represented in {ex3.iloc[0]['subdivision']} ({pct(ex3.iloc[0]['share'], 0)} of the 8 states' entrants), "
      f"{ex3.iloc[1]['subdivision']} ({pct(ex3.iloc[1]['share'], 0)}) and {ex3.iloc[2]['subdivision']} "
      f"({pct(ex3.iloc[2]['share'], 0)}).")
    a(f"- **Business numbers grew by {n(tot_chg)} across LGAs from June {R.LGA_FIRST} to June {R.LGA_LAST}, and "
      f"more than all of it was in businesses that employ no one:** non-employing businesses grew by {n(ne_all)} "
      f"and employing businesses fell by {n(-emp_all)}. In the "
      f"{TOP_K} fastest-growing LGAs with {n(R.LGA_FLOOR)}+ businesses, {pct(ne_top / tot_top)} of the net increase "
      f"employed no one and {pct(tr_top['share'])} was in {tr_top.name}.")
    a(f"- **The fastest-growing LGAs** with {n(R.LGA_FLOOR)}+ businesses are {first_lga['lga']} ({first_lga['state_abbr']}, "
      f"{pct(first_lga['growth'])}), {', '.join(f'{r.lga} ({r.state_abbr}, {pct(r.growth)})' for r in rk.iloc[1:4].itertuples())} and "
      f"{rk.iloc[4]['lga']} ({rk.iloc[4]['state_abbr']}, {pct(rk.iloc[4]['growth'])}). "
      f"{len(shrink)} of the {len(rk)} LGAs shrank.")
    a("")

    # 1. four cohorts by state
    a("## 1. Four cohorts by state (data cube 1, not perturbed)")
    a("")
    a(f"Share of each cohort's entrants still trading three Junes after the entry year, and of all businesses "
      f"operating in June still trading four Junes later. Sorted by the {last} cohort; rank 1 = lowest of the 8 states.")
    a("")
    bst = sorted(s[(s.dimension == "state") & (s.cohort == "businesses")]["start"].unique())
    a(f"| State | {' | '.join(COHORTS)} | Change | {last} entrants | Rank {last} | All businesses, {bst[0]} | "
      f"All businesses, {bst[-1]} |")
    a("|---|" + "---|" * (len(COHORTS) + 5))
    for name, r in st.sort_values(last, kind="stable").iterrows():
        a(f"| {name} | {' | '.join(rate(r[c]) for c in COHORTS)} | {sgn(r['change'])} | {n(r['entries_latest'])} | "
          f"{int(r[f'rank_{last}'])} | {rate(r['businesses_first'])} | {rate(r['businesses_latest'])} |")
    a(f"| **Australia** | {' | '.join(rate(nat[c]) for c in COHORTS)} | {sgn(nat['change'])} | "
      f"{n(nat['entries_latest'])} | | {rate(nat['businesses_first'])} | {rate(nat['businesses_latest'])} |")
    a("")
    a("Change is in percentage points, " f"{first} to {last}.")
    a("")
    a(f"- **{' and '.join(top2_states)} are the top two in all four cohorts**"
      f"{f', {always_top[0]} first every time' if len(always_top) == 1 else ''}. "
      f"Their entrants' survival was {rate(st.loc[top2_states, COHORTS].min().min())} or more in every cohort.")
    a(f"- **{vic.name} moves the most:** {rate(vic[first])} for the {first} cohort, {rate(vic['low'])} for "
      f"{R.COHORT} (lowest of any state in any cohort), back to {rate(vic[last])} for {last}. Its {R.COHORT} "
      f"entries ({n(vic_entries[R.COHORT])}) were {n(vic_entries[R.COHORT] - vic_entries['2020-21'])} more than the "
      f"year before and {n(vic_entries[R.COHORT] - vic_entries[last])} more than the year after "
      f"(section 3).")
    a(f"- **Business numbers grew in every state.** Between June 2019 and June 2026, "
      f"{'the ' if fastest.startswith('Australian') else ''}{fastest} grew fastest ({pct(sfs.loc[fastest, 'growth'])}) and {slowest} slowest "
      f"({pct(sfs.loc[slowest, 'growth'])}); Australia {pct(nat_growth := sf.loc[R.NATIONAL, 'growth'])}. "
      f"{slowest} also had the lowest entry rate ({pct(sfs.loc[slowest, 'entry_rate'])} of businesses operating at "
      f"the start of each year, against {pct(sf.loc[R.NATIONAL, 'entry_rate'])} nationally), so high survival there "
      f"comes with fewer entrants.")
    a("")
    a("![Four cohorts by state](charts/10_state_cohorts.png)")
    a("")
    a("| State | Businesses June 2019 | Businesses June 2026 | Growth | Entry rate | Exit rate |")
    a("|---|---|---|---|---|---|")
    for name, r in sf.iterrows():
        bold = "**" if name == R.NATIONAL else ""
        a(f"| {bold}{name}{bold} | {n(r['operating_start'])} | {n(r['operating_end'])} | {pct(r['growth'])} | "
          f"{pct(r['entry_rate'])} | {pct(r['exit_rate'])} |")
    a("")
    a(f"Entry and exit rates: entries (exits) over businesses operating at the start of the year, summed over the "
      f"{int(sf.loc[R.NATIONAL, 'years'])} years 2019-20 to 2025-26, each year from the latest release that has it.")
    a("")

    # 2. mix
    a(f"## 2. Is it the state, or what its new businesses do? ({R.COHORT} entrants, data cube 5)")
    a("")
    a(f"A state's survival depends on which industries its entrants are in and how many employ staff. To separate "
      f"that from the state itself, each state's *expected* rate applies the national survival rate of each "
      f"industry division × size band (non-employing, 1-4, 5+) to the state's own entrants in that cell. Actual "
      f"minus expected is what the mix doesn't explain. This is indirect standardisation, which never needs a "
      f"survival rate from a small state cell.")
    a("")
    a(f"A state's actual rate comes from data cube 5's state-total rows, which match data cube 1 exactly. Summing "
      f"the state's own subdivision × size cells would put small states too low: {worst_bias} comes out at "
      f"{rate(e.loc[worst_bias, 'cells_actual'])} from its cells against {rate(ms.loc[worst_bias, 'actual'])} "
      f"published ({pts(bias.min())}), because hundreds of tiny perturbed cells are summed.")
    a("")
    a("| State | Actual | Expected from mix | Gap to Australia | From the mix | Not explained by mix | Rank (not explained) |")
    a("|---|---|---|---|---|---|---|")
    for name, r in loc_rank.iterrows():
        a(f"| {name} | {rate(r['actual'])} | {rate(r['expected'])} | {pts(r['gap'])} | {pts(r['mix'])} | "
          f"{pts(r['local'])} | {int(r['rank_local'])} |")
    a(f"| **Australia** | {rate(nat_pub)} | | | | | |")
    a("")
    res = float(ms["residual"].iloc[0])
    a(f"The parts add up: gap = from the mix + not explained {'−' if res < 0 else '+'} {abs(res):.2f} points. The "
      f"{abs(res):.2f} is the difference between the national rate on the cells used "
      f"({rate(e['national_cells'].iloc[0])}; they leave out unknown industries and Other Territories) and the "
      f"published {rate(nat_pub)}.")
    a("")
    assert nsw["mix"] > 0 and nsw["gap"] < 0
    a(f"- **{nsw.name} is weaker than its raw rate shows.** Its mix should put it {nsw['mix']:.1f} points above the "
      f"national rate; it ends up {abs(nsw['gap']):.1f} points below it. Within size bands, its non-employing entrants are "
      f"{lowest(int(sb.loc[nsw.name, 'rank_rate_Non-employing']))} of the 8 states and its 1-4 employee entrants "
      f"{lowest(int(sb.loc[nsw.name, 'rank_rate_1-4']))} ({rate(sb.loc[nsw.name, 'rate_1-4'])}).")
    a(f"- **{vic.name}'s gap is {pct(vic_mix_share, 0)} mix.** {pct(sb.loc['Victoria', 'non_employing_share'], 0)} "
      f"of its {R.COHORT} entrants employed no one (Australia {pct(w['Non-employing'], 0)}), the highest share of "
      f"any state, and many were in low-survival subdivisions (section 3). After the mix it is "
      f"{lowest(int(ms.loc['Victoria', 'rank_local']))}, {pts(ms.loc['Victoria', 'local'])}.")
    a(f"- **{tas.name}, {loc_rank.index[-2]} and {loc_rank.index[-3]} keep more of their entrants than their mix "
      f"predicts** ({pts(tas['local'])}, {pts(loc_rank.iloc[-2]['local'])}, {pts(loc_rank.iloc[-3]['local'])}). "
      + (f"They also have the three highest survival rates for 1-4 employee entrants, so the advantage holds within "
         f"size bands too." if top3_14 else "Within size bands their ranks vary (table below)."))
    a(f"- **The method holds up.** With subdivision × 2 size bands, or subdivision × 5 sizes, instead of division × "
      f"3 bands, each state's unexplained part moves by at most {gap_spread:.2f} points and the ranking is "
      f"{'the same' if rank_same else 'the same apart from ' + ' and '.join(R.ABBR[x] for x in swapped) + ', which swap'}.")
    a("")
    a("![Mix vs state](charts/11_state_mix.png)")
    a("")
    a("**Within size bands** (state-total rows, exact; national size-mix weights as in Part 2):")
    a("")
    a("| State | Entrants | Non-employing share | Non-employing | 1-4 | 5+ | Overall | At national size mix |")
    a("|---|---|---|---|---|---|---|---|")
    for name, r in sb.sort_values("std", kind="stable").iterrows():
        a(f"| {name} | {n(r['entries'])} | {pct(r['non_employing_share'], 0)} | {rate(r['rate_Non-employing'])} | "
          f"{rate(r['rate_1-4'])} | {rate(r['rate_5+'])} | {rate(r['rate_all'])} | {rate(r['std'])} |")
    a("")

    # 3. Victoria
    a(f"## 3. Victoria's {R.COHORT} cohort")
    a("")
    a(f"Victoria's share of Australia's entrants was {pct(vic_share_e['2020-21'])} in 2020-21, "
      f"{pct(vic_share_e[R.COHORT])} in {R.COHORT} and {pct(vic_share_e[last])} in {last}. Data cube 5 shows where "
      f"the {R.COHORT} entrants were. Victoria had {pct(ex.attrs['overall_share'])} of the 8 states' entrants "
      f"overall, but far more in a few subdivisions:")
    a("")
    a("| Subdivision | Vic entrants | Vic share | Above Vic's overall share | Still trading, Vic | Still trading, other states |")
    a("|---|---|---|---|---|---|")
    for _, r in ex.head(8).iterrows():
        a(f"| {r['subdivision']} | {n(r['entrants'])} | {pct(r['share'], 0)} | {n(r['excess'])} | "
          f"{rate(r['rate_state'])} | {rate(r['rate_rest'])} |")
    a("")
    a(f"- The top {EXCESS_K} account for {n(ex3['excess'].sum())} entrants above Victoria's overall share. In Part 2 they are "
      f"{', '.join(ordinal(k) for k in p2_pos[:-1])} and {ordinal(p2_pos[-1])} lowest of the {len(p2_big)} "
      f"subdivisions with {MIN_ENTRANTS}+ entrants, at the national size mix, and Victoria's entrants in them did "
      f"{'worse' if vic_lower_all else 'no better'} than other states' ({rate(ex3.iloc[0]['rate_state'])} vs "
      f"{rate(ex3.iloc[0]['rate_rest'])} in {ex3.iloc[0]['subdivision']}).")
    a(f"- Removing those {n(ex3['excess'].sum())} entrants at Victoria's own rate in each subdivision would lift its "
      f"{R.COHORT} rate from {rate(ms.loc['Victoria', 'actual'])} to {rate(vic_wo)}. The rest of the gap is the "
      f"high non-employing share and lower survival within the same subdivisions.")
    a(f"- The data can't say why Victoria's entrants were over-represented there in {R.COHORT}; one cohort of detail is "
      f"published. The {last} cohort ({rate(neighbours[last])}) is back near the national rate.")
    a("")
    a("![Victoria 2021-22](charts/12_victoria_2021_22.png)")
    a("")

    # 4. LGAs
    a(f"## 4. Where business numbers are growing (LGAs, June {R.LGA_FIRST} to June {R.LGA_LAST}, data cube 10)")
    a("")
    a(f"Businesses operating in each of {lga_cells} places (LGAs, plus unincorporated areas; 'No usual address' and "
      f"Other Territories left out; the ACT is one area). Survival isn't published below state level, so this "
      f"section is about growth in business numbers, not survival. League tables use the {len(rk)} LGAs with "
      f"{n(R.LGA_FLOOR)} or more businesses in June {R.LGA_FIRST} ({pct(rk['businesses_2023'].sum() / all_first)} "
      f"of all businesses).")
    a("")
    a(f"**Fastest-growing {TOP_K}**")
    a("")
    a(f"| LGA | State | June {R.LGA_FIRST} | June {R.LGA_LAST} | Growth | Employing growth | Non-employing share of the increase | Industry adding the most |")
    a("|---|---|---|---|---|---|---|---|")
    for _, r in top.iterrows():
        a(f"| {r['lga']} | {r['state_abbr']} | {n(r['businesses_2023'])} | {n(r['businesses_2025'])} | "
          f"{pc(r['growth'])} | {pc(r['employing_growth'])} | {pct(r['non_employing_share_of_change'], 0)} | "
          f"{r['top_division']} (+{n(r['top_division_change'])}) |")
    a("")
    a(f"- **{', '.join(f'{k} {v}' for k, v in top_states.items())}** of the {TOP_K}. {tr_top.name} added the most "
      f"businesses in {top_tr} of them.")
    a(f"- **Across those {TOP_K}, businesses grew by {n(tot_top)} ({pct(tot_top / sz_top['businesses_2023'].sum())})**: "
      f"non-employing {n(ne_top)} ({pct(sz_top.loc['Non employing', 'growth'])}), employing "
      f"{n(tot_top - ne_top)}. {tr_top.name} added {n(tr_top['change'])} ({pct(tr_top['growth'])} growth), "
      f"{n(tr_top['non_employing_change'])} of them non-employing.")
    a(f"- **Counting employers tells a different story.** Total and employing growth are related but far from the "
      f"same (correlation {corr:.2f} across the {len(rk)} LGAs). The fastest employing growth was in "
      f"{', '.join(f'{r.lga} ({r.state_abbr}, {pct(r.employing_growth)})' for r in emp_top.iloc[:-1].itertuples())} "
      f"and {emp_top.iloc[-1]['lga']} ({emp_top.iloc[-1]['state_abbr']}, {pct(emp_top.iloc[-1]['employing_growth'])}). "
      f"{len(emp_fell)} of the {len(rk)} LGAs lost employing businesses even though only {len(shrink)} lost "
      f"businesses overall.")
    a("")
    a("![LGA growth](charts/13_lga_growth.png)")
    a("")
    a(f"**Slowest-growing and shrinking** ({len(shrink)} of {len(rk)} shrank)")
    a("")
    a(f"| LGA | State | June {R.LGA_FIRST} | June {R.LGA_LAST} | Growth | Employing growth |")
    a("|---|---|---|---|---|---|")
    for _, r in rk.tail(10).iloc[::-1].iterrows():
        a(f"| {r['lga']} | {r['state_abbr']} | {n(r['businesses_2023'])} | {n(r['businesses_2025'])} | "
          f"{pc(r['growth'])} | {pc(r['employing_growth'])} |")
    a("")
    a("**By state** (LGAs with " f"{n(R.LGA_FLOOR)}+ businesses)")
    a("")
    a("| State | LGAs | Shrinking | Median growth | Lowest | Highest |")
    a("|---|---|---|---|---|---|")
    for name, r in spread.iterrows():
        a(f"| {name} | {int(r['lgas'])} | {int(r['shrinking'])} | {pc(r['median'])} | {pc(r['low'])} | "
          f"{pc(r['high'])} |")
    a("")
    a(f"- **{wa.name}: none of its {int(wa['lgas'])} LGAs shrank** and its median growth "
      f"({pct(wa['median'])}) is the highest of the states with more than one LGA. {vic_sp.name} has the most "
      f"shrinking LGAs ({int(vic_sp['shrinking'])} of {int(vic_sp['lgas'])}) and the lowest median "
      f"({pct(vic_sp['median'])}), yet {' and '.join(vic_fast['lga'])} are "
      f"{' and '.join(ordinal(k) for k in vic_pos)} fastest-growing: growth is concentrated, not spread.")
    a(f"- {int(above.sum())} of the {len(rk)} LGAs grew faster than all places together ({pct(nat_growth_g)}).")
    a("")
    a("**By industry and size, all places**")
    a("")
    a(f"| Size | June {R.LGA_FIRST} | June {R.LGA_LAST} | Change | Growth |")
    a("|---|---|---|---|---|")
    for name, r in sz_all.iterrows():
        a(f"| {name} | {n(r['businesses_2023'])} | {n(r['businesses_2025'])} | {sn(r['change'])} | "
          f"{pc(r['growth'])} |")
    a("")
    a(f"- **{len(neg_emp_ind)} of {n_ind} industries had fewer employing businesses** in June {R.LGA_LAST} than in "
      f"June {R.LGA_FIRST}. {tr_all.name} added {n(tr_all['change'])} businesses, the most of any industry "
      f"({pct(tr_all['share'])} of the net increase): {n(tr_all['non_employing_change'])} non-employing, "
      f"{sn(tr_all['employing_change'])} employing. {hc.name} added the most employing businesses "
      f"(+{n(hc['employing_change'])}).")
    a(f"- The 1-4 employee band shrank ({sn(sz_all.loc['1-4', 'change'])}) while 20-199 grew "
      f"({pct(sz_all.loc['20-199', 'growth'])}). Size is measured each June, so businesses move between bands as they "
      f"hire or shed staff; a fall in one band isn't the same as businesses closing.")
    a("")
    a("![Growth by industry](charts/14_growth_by_industry.png)")
    a("")

    # 5. so what
    a("## 5. What this means for the business")
    a("")
    a(f"- **Councils and economic-development teams:** don't read a rising business count as a growing local "
      f"economy. In the {TOP_K} fastest-growing LGAs {pct(ne_top / tot_top, 0)} of the increase was businesses "
      f"with no employees, and {pct(tr_top['share'], 0)} was in {tr_top.name}, the industry with the lowest "
      f"survival of 2022-23 entrants in Part 2. Track "
      f"employing businesses (published in the same cube) alongside the total.")
    a(f"- **State agencies:** compare survival after the mix. On raw rates {nsw.name} is "
      f"{abs(nsw['gap']):.1f} points below the national rate; after its mix it is the weakest state ({pts(nsw['local'])}). "
      f"The data can't say why, but it is the gap worth investigating. Victoria's {R.COHORT} dip is "
      f"{pct(vic_mix_share, 0)} mix, so it isn't mainly a Victorian problem.")
    a(f"- **Lenders and investors:** state matters, but less than industry and size. The unexplained state "
      f"effects run from {pts(ms['local'].min())} to {pts(ms['local'].max())}; among non-employing entrants alone, "
      f"industries run from {rate(p2['rate_Non-employing'].min())} to {rate(p2['rate_Non-employing'].max())} "
      f"(Part 2), {p2_span:.1f} points apart. A state adjustment fine-tunes the industry × size rate.")
    a("")
    a("## Caveats")
    a("")
    a(f"- Sections 2 and 3 cover one cohort ({R.COHORT} entrants to June 2025). Data cube 1 (section 1) shows how "
      f"much a single cohort moves, and the 2026 detail is due on 18 December 2026.")
    a("- Expected rates remove the effect of industry division × size band, not of anything else (finer "
      "industry detail, local costs, the owners themselves). The robustness check with subdivisions moves the result little.")
    a("- LGA counts are perturbed (sizes add to the published total within ±4 businesses, industries within ±11), "
      f"so growth is only ranked for LGAs with {n(R.LGA_FLOOR)}+ businesses. For the same reason the net change "
      f"summed by size ({n(tot_chg)}) and by industry ({n(dr_all['change'].sum())}) differ slightly; industry shares "
      "use the industry sum.")
    a("- ABS attributes a business that operates in several places to one area only, so an LGA's count doesn't "
      "capture every business operating there.")
    a("- A change in business numbers is entries minus exits plus businesses moving in or out of an area, so it "
      "isn't the same as start-up activity.")
    a("")
    a("## Output files")
    a("")
    a("- `results/state_cohorts.csv`: states, survival of four entry cohorts and of all businesses, ranks")
    a("- `results/state_flows.csv`: states, businesses June 2019 and June 2026, entries, exits, entry and exit rates")
    a("- `results/state_mix.csv`: states, 2021-22 entrants by size band, expected rate from the mix, the split, "
      "and the unexplained part under the two other cell definitions")
    a("- `results/state_excess_vic.csv`: Victoria's 2021-22 entrants by subdivision vs the other states")
    a("- `results/lga_growth.csv`: every place, businesses and employing businesses in June 2023 and 2025, growth, "
      "the industry adding the most, and whether it is above the floor")
    a("- `results/lga_growth_by_industry.csv`: change by industry, non-employing and employing, all places and the "
      f"{TOP_K} fastest-growing LGAs")
    (RESULTS / "REGIONS.md").write_text("\n".join(L) + "\n")
    print("wrote results/REGIONS.md and 5 charts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
