"""Part 2: which industries new businesses last in, compared fairly.

Part 1 set the rules this module follows:

- industries are compared within employment-size bands, or at a common size
  mix, not on the overall rate alone (rule 4);
- no rate on a base of ``SMALL_BASE`` businesses or fewer, and perturbed detail
  cells are summed before a rate is computed (rule 6);
- each cohort's figures come from the one release that publishes them (rule 5);
- "Currently Unknown" is left out of rankings (rule 8).

Two sources feed it. Data cube 1 (not perturbed) gives each industry
division's survival for four entry cohorts, 2019-20 to 2022-23. Data cube 5
(perturbed, one cohort: 2021-22 entrants, to June 2025) gives state x
subdivision x size, which is summed over states here, because no national
subdivision rows are published.

The common size mix is a direct standardisation: each industry's rate in each
size band, weighted by the national share of entrants in that band (data cube
1, same cohort). It answers "what would this industry's survival be if its
entrants had the national size mix?".
"""
from __future__ import annotations

import pandas as pd

from cabee.load import DIVISIONS
from cabee.profile import DETAIL_RELEASE, SMALL_BASE

# Employment-size bands used for comparisons. 20-199 and 200+ are folded into
# "5+" because, by division, they fall under the floor (e.g. Mining 15, Other
# Services 16 entrants with 20 or more employees).
BAND_OF = {"Non employing": "Non-employing", "1-4": "1-4", "5-19": "5+", "20-199": "5+", "200+": "5+"}
BANDS = ["Non-employing", "1-4", "5+"]
BANDS_2 = ["Non-employing", "Employing"]
COHORTS = ["2019-20", "2020-21", "2021-22", "2022-23"]
DIVISION_NAMES = {code: name for code, (name, _, _) in DIVISIONS.items()}


# ------------------------------------------------------------------ data cube 1: four cohorts
def division_trend(survival: pd.DataFrame, bottom_k: int = 5) -> pd.DataFrame:
    """Each division's survival to the 3rd June for the four entry cohorts (data cube 1).

    Columns: one rate per cohort, the latest cohort's entries, its change since
    the first cohort (points), the lowest and highest rate across cohorts, its
    rank among divisions in the latest cohort (1 = lowest survival), how many
    cohorts it sat in the bottom ``bottom_k``, and the share of the latest
    cohort's 3-year loss that had already happened by the 1st June.
    """
    t = survival[(survival.dimension == "industry") & (survival.cohort == "entries") & (survival.level == "group")]
    r3 = t[t.years_after == 3].pivot_table(index="group", columns="start", values="rate_pub")[COHORTS]
    base = t[t.years_after == 3].pivot_table(index="group", columns="start", values="base")[COHORTS]
    last = COHORTS[-1]
    r1 = t[(t.years_after == 1) & (t.start == last)].set_index("group")["rate_pub"]
    out = r3.copy()
    out["entries_latest"] = base[last].astype(int)
    out["change"] = r3[last] - r3[COHORTS[0]]
    out["low"] = r3.min(axis=1)
    out["high"] = r3.max(axis=1)
    ranks = r3.rank(method="min")
    out["rank_latest"] = ranks[last].astype(int)
    out["cohorts_in_bottom"] = (ranks <= bottom_k).sum(axis=1)
    out["first_june_share_of_loss"] = (100 - r1) / (100 - r3[last])
    out.index.name = "industry"
    return out.sort_values(last)


def rank_stability(trend: pd.DataFrame) -> dict:
    """How much the industry ranking moves between cohorts (rank correlations)."""
    rho = trend[COHORTS].rank().corr()
    pairs = [(a, b, float(rho.loc[a, b])) for i, a in enumerate(COHORTS) for b in COHORTS[i + 1:]]
    vals = [p[2] for p in pairs]
    return {"pairs": pairs, "min": min(vals), "max": max(vals),
            "always_bottom": sorted(trend.index[trend["cohorts_in_bottom"] == len(COHORTS)])}


def national_bands(survival: pd.DataFrame) -> pd.DataFrame:
    """National entrants by size band for each cohort (data cube 1): base, survived, weight, rate."""
    t = survival[(survival.dimension == "size") & (survival.cohort == "entries") & (survival.years_after == 3)
                 & survival.group.isin(BAND_OF.keys())].copy()
    t["band"] = t["group"].map(BAND_OF)
    g = t.groupby(["start", "band"])[["base", "survived"]].sum().astype(float)
    g["weight"] = g["base"] / g.groupby(level="start")["base"].transform("sum")
    g["rate"] = 100 * g["survived"] / g["base"]
    return g


def mix_decomposition(nb: pd.DataFrame, a: str, b: str) -> dict:
    """Split the change in the national rate between two cohorts into within-band and mix parts.

    Shift-share with average weights and average rates, so the two parts add
    exactly to the total change.
    """
    w, r = nb["weight"].unstack(), nb["rate"].unstack()
    within = float((((w.loc[a] + w.loc[b]) / 2) * (r.loc[b] - r.loc[a])).sum())
    mix = float(((w.loc[b] - w.loc[a]) * ((r.loc[a] + r.loc[b]) / 2)).sum())
    total = float((w.loc[b] * r.loc[b]).sum() - (w.loc[a] * r.loc[a]).sum())
    return {"from": a, "to": b, "total": total, "within": within, "mix": mix,
            "band_change": {k: float(r.loc[b, k] - r.loc[a, k]) for k in BANDS}}


def weights(survival: pd.DataFrame, start: str = "2021-22") -> pd.Series:
    """National size-band weights of one entry cohort (data cube 1)."""
    return national_bands(survival)["weight"].xs(start, level="start")[BANDS]


# ------------------------------------------------------------------ data cube 5: size bands
def band_counts(sub: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """2021-22 entrants to June 2025, summed over states, by ``by`` x band.

    Bands come from summing the size cells; "Total" comes from the published
    Total cells. Because cells are perturbed, the bands need not add exactly to
    the Total. "Currently Unknown" (division X) is dropped.
    """
    x = sub[(sub.cohort == "entries") & (sub.years_after == 3) & (sub.level == "group") & (sub.division != "X")].copy()
    x["band"] = x["size"].map(BAND_OF).fillna(x["size"])
    g = x.groupby(by + ["band"])[["base", "survived"]].sum()
    base, surv = g["base"].unstack().astype(float), g["survived"].unstack().astype(float)
    base["Employing"] = base[["1-4", "5+"]].sum(axis=1)
    surv["Employing"] = surv[["1-4", "5+"]].sum(axis=1)
    return pd.concat({"base": base, "survived": surv}, axis=1)


def rates(counts: pd.DataFrame, floor: int = SMALL_BASE) -> pd.DataFrame:
    """Survival (%) per column of ``counts``; blank where the base is ``floor`` or fewer."""
    base, surv = counts["base"], counts["survived"]
    return (100 * surv / base).where(base > floor)


def standardise(r: pd.DataFrame, w: pd.Series) -> pd.Series:
    """Rate at the common size mix ``w``; blank if any band's rate is blank."""
    return (r[w.index] * w).sum(axis=1, min_count=len(w))


def division_bands(sub: pd.DataFrame, survival: pd.DataFrame) -> pd.DataFrame:
    """Divisions: overall rate, rate in each size band, and rates at the national size mix.

    ``std`` uses three bands (non-employing, 1-4, 5+); ``std_2`` uses two
    (non-employing, employing) as a robustness check. ``mix_effect`` is the
    overall rate minus ``std``: positive means the industry's size mix flatters
    its overall rate. Ranks: 1 = lowest survival.
    """
    c = band_counts(sub, ["division"])
    r = rates(c)
    w3 = weights(survival)
    w2 = pd.Series({"Non-employing": w3["Non-employing"], "Employing": 1 - w3["Non-employing"]})
    out = pd.DataFrame({
        "industry": [DIVISION_NAMES[d] for d in c.index],
        "entries": c["base"]["Total"].astype(int),
        "non_employing_share": c["base"]["Non-employing"] / c["base"][BANDS].sum(axis=1),
        "rate_all": r["Total"],
        **{f"rate_{b}": r[b] for b in BANDS},
        "rate_Employing": r["Employing"],
        "base_5+": c["base"]["5+"].astype(int),
        "std": standardise(r, w3),
        "std_2": standardise(r, w2),
    }, index=c.index)
    out["mix_effect"] = out["rate_all"] - out["std"]
    for col in ["rate_all", "std", *[f"rate_{b}" for b in BANDS]]:
        out[f"rank_{col}"] = out[col].rank(method="min").astype(int)
    out.index.name = "division"
    return out.sort_values("std")


def subdivision_bands(sub: pd.DataFrame, survival: pd.DataFrame) -> pd.DataFrame:
    """Subdivisions: overall rate and the two-band common-mix rate, where the floor allows.

    Two bands only (non-employing, employing): with three, 32 of 85
    subdivisions have 20 or fewer entrants in the 5+ band.
    """
    c = band_counts(sub, ["subdivision_code", "subdivision", "division"])
    r = rates(c)
    w3 = weights(survival)
    w2 = pd.Series({"Non-employing": w3["Non-employing"], "Employing": 1 - w3["Non-employing"]})
    out = pd.DataFrame({
        "entries": c["base"]["Total"].astype(int),
        "non_employing_share": c["base"]["Non-employing"] / c["base"][BANDS].sum(axis=1),
        "rate_all": r["Total"],
        "rate_Non-employing": r["Non-employing"],
        "rate_Employing": r["Employing"],
        "std_2": standardise(r, w2),
    })
    out = out.reset_index(["subdivision", "division"])
    out["industry"] = out["division"].map(DIVISION_NAMES)
    out["rank_std_2"] = out["std_2"].rank(method="min")
    return out.sort_values(["std_2", "rate_all"])
