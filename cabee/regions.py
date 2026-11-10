"""Part 3: where new businesses last, and where business numbers are growing.

Part 1's rules apply:

- survival below state level isn't published, so survival is compared between
  states; local government areas (LGAs) are compared on growth in business
  numbers (rule 6);
- states are compared within size bands, or after allowing for their industry
  and size mix (rule 3);
- no rate on a base of ``SMALL_BASE`` businesses or fewer, and "Other
  Territories/Currently Unknown" is left out of rankings (rules 4 and 8);
- each year's figures come from the latest release that has them (rule 5).

Three sources feed it:

- data cube 1 (not perturbed): each state's survival for four entry cohorts,
  and its business counts, entries and exits for 2019-20 to 2025-26;
- data cube 5 (one cohort: 2021-22 entrants, to June 2025): state x
  subdivision x size. Its state-total rows match data cube 1 exactly, but
  summing its hundreds of small perturbed cells puts small states' survival too
  low (Northern Territory: 46.9% from the cells, 49.2% published). So a state's
  actual rate always comes from the state-total rows; the cells are used only
  for each state's industry x size *mix*, and for national rates per cell;
- data cube 10: businesses operating in each LGA in June 2023, 2024 and 2025,
  by industry division and size.

The mix comparison is an indirect standardisation: a state's *expected* rate
is the rate it would have if each of its industry x size cells survived at the
national rate for that cell. Actual minus expected is the part of the state's
gap that its mix doesn't explain; expected minus national is the part it does.
Indirect standardisation suits small states because it never needs a rate from
a small state cell, only national ones.
"""
from __future__ import annotations

import pandas as pd

from cabee.industries import BAND_OF, BANDS, COHORTS, weights
from cabee.profile import SMALL_BASE

STATES = ["New South Wales", "Victoria", "Queensland", "South Australia", "Western Australia", "Tasmania",
          "Northern Territory", "Australian Capital Territory"]
ABBR = {"New South Wales": "NSW", "Victoria": "Vic", "Queensland": "Qld", "South Australia": "SA",
        "Western Australia": "WA", "Tasmania": "Tas", "Northern Territory": "NT",
        "Australian Capital Territory": "ACT"}
NATIONAL = "Australia"
COHORT = "2021-22"          # the one entry cohort data cube 5 covers
LGA_FLOOR = 1000            # LGA league tables: at least this many businesses in June 2023
LGA_FIRST, LGA_LAST = 2023, 2025
NOT_PLACES = {"No usual address"}  # LGA-cube rows that aren't places


def _order(df: pd.DataFrame, national: bool = False) -> pd.DataFrame:
    """The states present in ``df``, in the standard order (then Australia if asked for)."""
    keep = [s for s in STATES + ([NATIONAL] if national else []) if s in df.index]
    return df.loc[keep]


# ------------------------------------------------------------------ data cube 1: four cohorts, counts
def state_cohorts(survival: pd.DataFrame) -> pd.DataFrame:
    """Each state's entrants still trading at the 3rd June, four cohorts (data cube 1).

    Also the latest cohort's entries, the change since the first cohort
    (points), the range across cohorts, the rank among the 8 states in each
    cohort (1 = lowest survival) and businesses' survival to the 4th June for
    the first and latest cohorts of operating businesses. The last row is
    Australia.
    """
    t = survival[(survival.dimension == "state") & survival.group.isin(STATES + [NATIONAL])]
    e = t[(t.cohort == "entries") & (t.years_after == 3)]
    r = e.pivot_table(index="group", columns="start", values="rate_pub")[COHORTS]
    base = e.pivot_table(index="group", columns="start", values="base")[COHORTS]
    b = t[(t.cohort == "businesses") & (t.years_after == 4)]
    rb = b.pivot_table(index="group", columns="start", values="rate_pub")
    first, last = COHORTS[0], COHORTS[-1]
    out = r.copy()
    out["entries_latest"] = base[last].astype(int)
    out["change"] = r[last] - r[first]
    out["low"], out["high"] = r.min(axis=1), r.max(axis=1)
    ranks = _order(r).rank(method="min")
    for c in COHORTS:
        out[f"rank_{c}"] = ranks[c]
    out["businesses_first"] = rb[rb.columns[0]]
    out["businesses_latest"] = rb[rb.columns[-1]]
    out = _order(out, national=True)
    out.index.name = "state"
    return out


def state_flows(flows: pd.DataFrame) -> pd.DataFrame:
    """Businesses operating, entries and exits by state, each year from the latest release that has it.

    ``growth`` is June 2019 to the latest June; ``entry_rate`` and
    ``exit_rate`` are entries (exits) over businesses operating at the start
    of the year, summed over all years. The last row is Australia.
    """
    t = flows[(flows.dimension == "state") & flows.group.isin(STATES + [NATIONAL])].sort_values("release")
    t = t.groupby(["group", "fin_year"]).last().reset_index().sort_values("fin_year")
    g = t.groupby("group")
    out = pd.DataFrame({
        "start_year": g["fin_year"].first(),
        "operating_start": g["operating_start"].first().astype(float),
        "end_year": g["fin_year"].last(),
        "operating_end": g["operating_end"].last().astype(float),
        "entries": g["entries"].sum().astype(float),
        "exits": g["exits"].sum().astype(float),
        "opening_sum": g["operating_start"].sum().astype(float),
        "years": g.size(),
    })
    out["growth"] = out["operating_end"] / out["operating_start"] - 1
    out["entry_rate"] = out["entries"] / out["opening_sum"]
    out["exit_rate"] = out["exits"] / out["opening_sum"]
    out = _order(out, national=True)
    out.index.name = "state"
    return out


# ------------------------------------------------------------------ data cube 5: one cohort, mix
def _entries(sub: pd.DataFrame) -> pd.DataFrame:
    return sub[(sub.cohort == "entries") & (sub.years_after == 3)]


def state_bands(sub: pd.DataFrame, survival: pd.DataFrame) -> pd.DataFrame:
    """2021-22 entrants by state x size band, from data cube 5's state-total rows (they match data cube 1).

    Rates per band (blank on a base of ``SMALL_BASE`` or fewer), the overall
    rate, and the rate at the national size mix of 2021-22 entrants (data cube
    1), as in Part 2. Ranks among the 8 states: 1 = lowest.
    """
    x = _entries(sub)
    x = x[(x.level == "total") & x.state.isin(STATES) & (x["size"] != "Total")].copy()
    x["band"] = x["size"].map(BAND_OF)
    g = x.groupby(["state", "band"])[["base", "survived"]].sum().astype(float)
    base, surv = g["base"].unstack()[BANDS], g["survived"].unstack()[BANDS]
    r = (100 * surv / base).where(base > SMALL_BASE)
    w = weights(survival, COHORT)
    out = pd.DataFrame({
        "entries": base.sum(axis=1).astype(int),
        "non_employing_share": base["Non-employing"] / base.sum(axis=1),
        "rate_all": 100 * surv.sum(axis=1) / base.sum(axis=1),
        **{f"rate_{b}": r[b] for b in BANDS},
        "base_5+": base["5+"].astype(int),
        "std": (r[BANDS] * w).sum(axis=1, min_count=len(BANDS)),
    })
    out["mix_effect"] = out["rate_all"] - out["std"]
    for col in ["rate_all", "std", *[f"rate_{b}" for b in BANDS]]:
        out[f"rank_{col}"] = out[col].rank(method="min")
    out = _order(out)
    out.index.name = "state"
    return out


def cells(sub: pd.DataFrame, key: tuple[str, ...]) -> pd.DataFrame:
    """2021-22 entrants per state x cell, where a cell is ``key`` (e.g. division x band).

    Built from the subdivision x size cells of the 8 states; 'Currently
    Unknown' industry (division X) and 'Other Territories' are left out.
    ``key`` may use 'division', 'subdivision_code', 'band' (size folded as in
    Part 2) or 'size' (the five published sizes).
    """
    x = _entries(sub)
    x = x[(x.level == "group") & (x.division != "X") & x.state.isin(STATES) & (x["size"] != "Total")].copy()
    x["band"] = x["size"].map(BAND_OF)
    return x.groupby(["state", *key])[["base", "survived"]].sum().astype(float)


def expected(sub: pd.DataFrame, key: tuple[str, ...] = ("division", "band")) -> pd.DataFrame:
    """Each state's expected survival if its cells survived at the national rate per cell.

    Columns: ``cell_base`` (entrants in the cells), ``expected`` (%),
    ``cells_actual`` (% from summing the state's own perturbed cells; shown
    only to measure the small-cell bias) and ``national_cells`` (the national
    rate on the same cells).
    """
    c = cells(sub, key)
    nat = c.groupby(level=list(key)).sum()
    nat_rate = nat["survived"] / nat["base"]
    exp = c["base"] * nat_rate.reindex(c.index.droplevel("state")).to_numpy()
    s = c.groupby(level="state").sum()
    out = pd.DataFrame({
        "cell_base": s["base"],
        "expected": 100 * exp.groupby(level="state").sum() / s["base"],
        "cells_actual": 100 * s["survived"] / s["base"],
    })
    out["national_cells"] = 100 * nat["survived"].sum() / nat["base"].sum()
    return _order(out)


def mix_split(bands: pd.DataFrame, exp: pd.DataFrame, national: float) -> pd.DataFrame:
    """Split each state's gap to the national rate into a mix part and a local part.

    ``actual`` is the state's exact rate (state-total rows); ``national`` the
    published national rate for the cohort. ``mix`` = expected − national
    cells rate (what the state's industry x size mix alone would do);
    ``local`` = actual − expected (what the mix doesn't explain).
    ``residual`` = national cells rate − published national rate (the cells
    leave out unknown industries and Other Territories), so that
    gap = mix + local + residual exactly.
    """
    out = pd.DataFrame({"actual": bands["rate_all"], "expected": exp["expected"]})
    out["gap"] = out["actual"] - national
    out["mix"] = exp["expected"] - exp["national_cells"]
    out["local"] = out["actual"] - out["expected"]
    out["residual"] = out["gap"] - out["mix"] - out["local"]
    out["rank_actual"] = out["actual"].rank(method="min")
    out["rank_local"] = out["local"].rank(method="min")
    return out


def excess_entrants(sub: pd.DataFrame, state: str = "Victoria") -> pd.DataFrame:
    """Where one state's 2021-22 entrants were over-represented, by subdivision.

    ``share`` is the state's share of the 8 states' entrants in the
    subdivision; ``excess`` is its entrants minus what it would have at its
    overall share; rates are survival in the state and in the other states
    (blank on a base of ``SMALL_BASE`` or fewer).
    """
    c = cells(sub, ("subdivision_code", "subdivision"))
    st = c.xs(state, level="state")
    rest = c.drop(index=state, level="state").groupby(level=["subdivision_code", "subdivision"]).sum()
    total = st["base"] + rest["base"]
    overall = st["base"].sum() / total.sum()
    out = pd.DataFrame({
        "entrants": st["base"],
        "entrants_all": total,
        "share": st["base"] / total,
        "excess": st["base"] - overall * total,
        "rate_state": (100 * st["survived"] / st["base"]).where(st["base"] > SMALL_BASE),
        "rate_rest": (100 * rest["survived"] / rest["base"]).where(rest["base"] > SMALL_BASE),
    }).reset_index("subdivision")
    out.attrs["overall_share"] = overall
    return out.sort_values("excess", ascending=False)


def without(actual_base: float, actual_survived: float, rows: pd.DataFrame) -> float:
    """A state's rate (%) with the ``excess`` entrants in ``rows`` removed at the state's own rate there."""
    gone = rows["excess"].clip(lower=0)
    return 100 * (actual_survived - (gone * rows["rate_state"] / 100).sum()) / (actual_base - gone.sum())


# ------------------------------------------------------------------ data cube 10: LGA counts
def _places(lga: pd.DataFrame) -> pd.DataFrame:
    return lga[(lga.lga_code != "TOT") & ~lga.lga.isin(NOT_PLACES) & lga.state.isin(STATES)]


def lga_growth(lga: pd.DataFrame, first: int = LGA_FIRST, last: int = LGA_LAST) -> pd.DataFrame:
    """Businesses operating in each LGA in June ``first`` and ``last``, all and employing.

    "No usual address" rows and 'Other Territories' are left out. The ACT is
    one LGA ("Unincorporated ACT"). ``top_division`` is the industry that
    added the most businesses; ``non_employing_share_of_change`` is the share
    of the net change that came from non-employing businesses (blank if the
    net change is zero).
    """
    p = _places(lga)
    tot = p[(p.division == "TOT")]
    by_size = tot.pivot_table(index=["state", "lga_code", "lga"], columns=["size", "june"], values="count",
                              aggfunc="sum")
    full = pd.MultiIndex.from_product([["Non employing", "1-4", "5-19", "20-199", "200+", "Total"], [first, last]])
    by_size = by_size.reindex(columns=full, fill_value=0).fillna(0)  # a size with no businesses can be absent
    t = lambda s, j: by_size[(s, j)].astype(float)  # noqa: E731
    emp = lambda j: sum(t(s, j) for s in ["1-4", "5-19", "20-199", "200+"])  # noqa: E731
    out = pd.DataFrame({
        f"businesses_{first}": t("Total", first),
        f"businesses_{last}": t("Total", last),
        f"employing_{first}": emp(first),
        f"employing_{last}": emp(last),
        f"non_employing_{first}": t("Non employing", first),
        f"non_employing_{last}": t("Non employing", last),
    })
    out["change"] = out[f"businesses_{last}"] - out[f"businesses_{first}"]
    out["growth"] = out["change"] / out[f"businesses_{first}"]
    out["employing_change"] = out[f"employing_{last}"] - out[f"employing_{first}"]
    out["employing_growth"] = (out["employing_change"] / out[f"employing_{first}"]).where(
        out[f"employing_{first}"] > SMALL_BASE)
    ne_change = out[f"non_employing_{last}"] - out[f"non_employing_{first}"]
    out["non_employing_change"] = ne_change
    out["non_employing_share_of_change"] = (ne_change / out["change"]).where(out["change"] != 0)
    d = p[(p.division != "TOT") & (p["size"] == "Total") & p.june.isin([first, last])]
    dc = d.pivot_table(index=["state", "lga_code", "lga", "industry"], columns="june", values="count",
                       aggfunc="sum").fillna(0)
    dc = (dc[last] - dc[first]).rename("chg").reset_index()
    top = dc.sort_values(["chg", "industry"], ascending=[False, True]).groupby(["state", "lga_code", "lga"]).head(1)
    top = top.set_index(["state", "lga_code", "lga"])
    out["top_division"] = top["industry"]
    out["top_division_change"] = top["chg"]
    out = out.reset_index()
    out["state_abbr"] = out["state"].map(ABBR)
    return out.sort_values("growth", ascending=False).reset_index(drop=True)


def ranked(g: pd.DataFrame, floor: int = LGA_FLOOR, first: int = LGA_FIRST) -> pd.DataFrame:
    """LGAs with at least ``floor`` businesses in June ``first``, fastest-growing first."""
    return g[g[f"businesses_{first}"] >= floor].sort_values(["growth", "lga"], ascending=[False, True])


def growth_drivers(lga: pd.DataFrame, codes=None, first: int = LGA_FIRST, last: int = LGA_LAST) -> pd.DataFrame:
    """Change in businesses by industry, split into non-employing and employing, for a set of LGAs.

    ``codes`` is a list of LGA codes; None means every place in the cube.
    Rows are sorted by total change; ``share`` is each industry's share of
    the net change.
    """
    p = _places(lga)
    if codes is not None:
        p = p[p.lga_code.isin(list(codes))]
    p = p[(p.division != "TOT") & (p["size"] != "Total") & p.june.isin([first, last])].copy()
    p["band"] = (p["size"] == "Non employing").map({True: "non_employing", False: "employing"})
    g = p.pivot_table(index=["industry"], columns=["band", "june"], values="count", aggfunc="sum")
    full = pd.MultiIndex.from_product([["non_employing", "employing"], [first, last]])
    g = g.reindex(columns=full, fill_value=0).fillna(0)
    out = pd.DataFrame({
        f"businesses_{first}": g["non_employing"][first] + g["employing"][first],
        "non_employing_change": g["non_employing"][last] - g["non_employing"][first],
        "employing_change": g["employing"][last] - g["employing"][first],
    })
    out["change"] = out["non_employing_change"] + out["employing_change"]
    out["growth"] = out["change"] / out[f"businesses_{first}"]
    out["share"] = out["change"] / out["change"].sum()
    return out.sort_values("change", ascending=False)


def size_change(lga: pd.DataFrame, codes=None, first: int = LGA_FIRST, last: int = LGA_LAST) -> pd.DataFrame:
    """Businesses by employment size in June ``first`` and ``last`` for a set of LGAs (None = all places)."""
    p = _places(lga)
    if codes is not None:
        p = p[p.lga_code.isin(list(codes))]
    p = p[(p.division == "TOT") & (p["size"] != "Total") & p.june.isin([first, last])]
    g = p.pivot_table(index="size", columns="june", values="count", aggfunc="sum").astype(float)
    g = g.loc[["Non employing", "1-4", "5-19", "20-199", "200+"]]
    out = pd.DataFrame({f"businesses_{first}": g[first], f"businesses_{last}": g[last]})
    out["change"] = out[f"businesses_{last}"] - out[f"businesses_{first}"]
    out["growth"] = out["change"] / out[f"businesses_{first}"]
    return out


def state_lga_spread(g: pd.DataFrame, floor: int = LGA_FLOOR, first: int = LGA_FIRST) -> pd.DataFrame:
    """Per state: LGAs above the floor, how many shrank, the median and range of growth."""
    r = g[g[f"businesses_{first}"] >= floor]
    out = r.groupby("state").agg(lgas=("growth", "size"), shrinking=("growth", lambda s: int((s < 0).sum())),
                                 median=("growth", "median"), low=("growth", "min"), high=("growth", "max"))
    return _order(out)
