"""Part 1 checks: what the CABEE numbers mean and where they can mislead.

Every function takes the tidy tables from ``cabee.load.read`` and returns a
small frame or dict that scripts/profile_source.py turns into the report.
"""
from __future__ import annotations

import pandas as pd

from cabee.load import DIVISIONS

LATEST = "2022-2026"
DETAIL_RELEASE = "2021-2025"  # the release data cubes 4, 5 and 10 come from
SIZES = ["Non employing", "1-4", "5-19", "20-199", "200+"]
SMALL_BASE = 20  # cells with this many businesses or fewer are unreliable


def headline(survival: pd.DataFrame) -> pd.DataFrame:
    """National survival by release: businesses to the 4th June, entries to the 3rd."""
    t = survival[(survival.dimension == "industry") & (survival.level == "total")]
    b = t[(t.cohort == "businesses") & (t.years_after == 4)].set_index("release")
    e = t[(t.cohort == "entries") & (t.years_after == 3)].set_index("release")
    return pd.DataFrame({
        "businesses_start": b["start"], "businesses": b["base"], "businesses_survived": b["survived"],
        "businesses_rate": b["rate_pub"], "businesses_to": b["survived_to"],
        "entries_year": e["start"], "entries": e["base"], "entries_survived": e["survived"],
        "entries_rate": e["rate_pub"], "entries_to": e["survived_to"],
    }).reset_index()


def entry_curves(survival: pd.DataFrame) -> pd.DataFrame:
    """National survival of each entry cohort to the 1st, 2nd and 3rd June."""
    t = survival[(survival.dimension == "industry") & (survival.level == "total") & (survival.cohort == "entries")]
    return t.pivot_table(index="start", columns="years_after", values="rate_pub").sort_index(kind="stable")


def rate_consistency(survival: pd.DataFrame) -> dict:
    """Published rates in data cube 1 vs survived / base (rounded to 1 decimal)."""
    x = survival.dropna(subset=["rate_pub"])
    diff = (100 * x["survived"] / x["base"] - x["rate_pub"]).abs()
    return {"rates": len(x), "max_diff": float(diff.max()), "over_rounding": int((diff > 0.05 + 1e-9).sum())}


def additivity(survival: pd.DataFrame) -> pd.DataFrame:
    """Do the groups (plus 'unknown') add up to the published total in each table?"""
    rows = []
    for dim, g in survival.groupby("dimension"):
        keys = ["release", "cohort", "survived_to"]
        parts = g[g.level.isin(["group", "unknown"])].groupby(keys)[["base", "survived"]].sum()
        tot = g[g.level == "total"].groupby(keys)[["base", "survived"]].sum()
        gap = (parts - tot).abs()
        rows.append({"dimension": dim, "tables": len(tot), "max_gap_base": int(gap["base"].max()),
                     "max_gap_survived": int(gap["survived"].max())})
    return pd.DataFrame(rows)


def flow_series(flows: pd.DataFrame) -> pd.DataFrame:
    """National entries, exits and counts per financial year, each from the latest release that has it."""
    t = flows[(flows.dimension == "industry") & (flows.level == "total")].sort_values("release", kind="stable")
    return t.groupby("fin_year").last().reset_index()[
        ["fin_year", "release", "operating_start", "births", "entries_other", "entries",
         "cancellations", "exits_other", "exits", "operating_end"]]


def revisions(flows: pd.DataFrame) -> dict:
    """How much the same year's figures change between overlapping releases."""
    out = {}
    vals = ["operating_start", "entries", "exits", "operating_end"]
    long = flows.melt(id_vars=["release", "dimension", "fin_year", "group", "level"], value_vars=vals)
    long["value"] = long["value"].astype(float)
    g = long.groupby(["dimension", "fin_year", "group", "level", "variable"])["value"]
    stat = g.agg(["min", "max", "count"]).reset_index()
    stat = stat[stat["count"] > 1]
    stat["range"] = stat["max"] - stat["min"]
    stat["pct"] = 100 * stat["range"] / stat["min"]
    tot = stat[stat.level == "total"]
    named = stat[stat.level == "group"]
    unknown = stat[stat.level == "unknown"]
    out["total_cells"], out["total_changed"] = len(tot), int((tot["range"] > 0).sum())
    out["group_cells"], out["group_changed"] = len(named), int((named["range"] > 0).sum())
    out["group_median_pct"] = float(named["pct"].median())
    big = named.sort_values("pct", ascending=False, kind="stable").iloc[0]
    out["group_max"] = {k: big[k] for k in ("dimension", "fin_year", "group", "variable", "min", "max", "pct")}
    big_abs = named.sort_values("range", ascending=False, kind="stable").iloc[0]
    out["group_max_abs"] = {k: big_abs[k] for k in ("dimension", "fin_year", "group", "variable", "min", "max", "range", "pct")}
    out["unknown_max_pct"] = float(unknown["pct"].max())
    return out


def size_mix(survival: pd.DataFrame, release: str = LATEST) -> pd.DataFrame:
    """Entries and their survival to the 3rd June by employment size (data cube 1)."""
    t = survival[(survival.release == release) & (survival.dimension == "size") & (survival.cohort == "entries")
                 & (survival.years_after == 3)]
    t = t[["group", "level", "base", "survived", "rate_pub"]].set_index("group")
    t["share"] = t["base"] / t.loc["Total", "base"]
    return t


def entries_other_share(flows: pd.DataFrame) -> pd.DataFrame:
    s = flow_series(flows)
    s["other_share"] = s["entries_other"] / s["entries"]
    s["births_share"] = s["births"] / s["entries"]
    return s[["fin_year", "entries", "births", "entries_other", "other_share", "births_share"]]


def division_size_mix(sub: pd.DataFrame) -> pd.DataFrame:
    """Entries by industry division, aggregated from data cube 5's state x subdivision cells.

    Returns each division's non-employing share of entries and its survival
    to the 3rd June overall and for non-employing entries only. Rates are
    recomputed from summed (perturbed) counts.
    """
    x = sub[(sub.cohort == "entries") & (sub.years_after == 3) & (sub.level == "group") & (sub.division != "X")]
    agg = x.groupby(["division", "size"])[["base", "survived"]].sum()
    base = agg["base"].unstack()
    surv = agg["survived"].unstack()
    out = pd.DataFrame({
        "industry": [DIVISIONS[d][0] for d in base.index],
        "entries": base["Total"],
        "non_employing_share": base["Non employing"] / base["Total"],
        "rate_all": 100 * surv["Total"] / base["Total"],
        "rate_non_employing": 100 * surv["Non employing"] / base["Non employing"],
        "rate_employing": 100 * (surv["Total"] - surv["Non employing"]) / (base["Total"] - base["Non employing"]),
    }, index=base.index)
    return out.sort_values("rate_all", kind="stable")


def division_check(sub: pd.DataFrame, survival: pd.DataFrame) -> pd.DataFrame:
    """Division rates rebuilt from data cube 5 vs data cube 1's published division rates."""
    mix = division_size_mix(sub)
    pub = survival[(survival.release == DETAIL_RELEASE) & (survival.dimension == "industry")
                   & (survival.cohort == "entries") & (survival.years_after == 3)].set_index("group")
    mix["rate_pub"] = mix["industry"].map(pub["rate_pub"])
    mix["entries_pub"] = mix["industry"].map(pub["base"])
    mix["diff"] = mix["rate_all"] - mix["rate_pub"]
    return mix


def detail_totals_check(sub: pd.DataFrame, survival: pd.DataFrame) -> dict:
    """State totals in data cubes 4/5 vs data cube 1's state tables (same release)."""
    st = sub[(sub.level == "total") & (sub["size"] == "Total")]
    dc = survival[(survival.release == DETAIL_RELEASE) & (survival.dimension == "state")].copy()
    dc["state"] = dc["group"]
    m = st.merge(dc, on=["cohort", "state", "survived_to"], suffixes=("_d", "_p"))
    return {"pairs": len(m),
            "max_gap_base": int((m.base_d - m.base_p).abs().max()),
            "max_gap_survived": int((m.survived_d - m.survived_p).abs().max()),
            "max_gap_rate": float((m.rate_pub_d - m.rate_pub_p).abs().max())}


def perturbation(sub: pd.DataFrame) -> dict:
    """How far the perturbed detail cells drift from additivity and from their published rates."""
    out = {}
    g = sub[sub.level == "group"]
    w = g.pivot_table(index=["cohort", "state", "subdivision_code", "survived_to"], columns="size",
                      values="base", aggfunc="first")
    gap = w[SIZES].sum(axis=1) - w["Total"]
    out["rows"], out["rows_not_adding"] = len(w), int((gap != 0).sum())
    out["size_gap_min"], out["size_gap_max"] = int(gap.min()), int(gap.max())
    x = g.dropna(subset=["rate_pub"])
    x = x[x["base"] > 0].copy()
    x["diff"] = (100 * x["survived"] / x["base"] - x["rate_pub"]).abs()
    off = x[x["diff"] > 0.05 + 1e-9]
    out["rated_cells"], out["off_cells"] = len(x), len(off)
    out["off_max_base"] = int(off["base"].max()) if len(off) else 0
    out["off_min_diff"] = float(off["diff"].min()) if len(off) else 0.0
    out["off_max_diff"] = float(off["diff"].max()) if len(off) else 0.0
    out["survived_gt_base"] = int((g["survived"] > g["base"]).sum())
    return out


def small_cells(sub: pd.DataFrame) -> pd.DataFrame:
    """Share of rated detail cells whose published rate disagrees with their counts, by base size."""
    g = sub[(sub.level == "group")].dropna(subset=["rate_pub"])
    g = g[g["base"] > 0].copy()
    g["off"] = (100 * g["survived"] / g["base"] - g["rate_pub"]).abs() > 0.05 + 1e-9
    bins = [0, 5, 10, 20, 50, 100, float("inf")]
    labels = ["1-5", "6-10", "11-20", "21-50", "51-100", "101+"]
    g["base_band"] = pd.cut(g["base"].astype(float), bins=bins, labels=labels)
    t = g.groupby("base_band", observed=False)["off"].agg(["count", "sum", "mean"]).reset_index()
    return t.rename(columns={"count": "cells", "sum": "off", "mean": "off_share"})


def lga_checks(lga: pd.DataFrame, flows: pd.DataFrame) -> dict:
    out = {}
    x = lga[lga.lga_code != "TOT"]
    a = x[(x.division == "TOT") & (x["size"] == "Total")].groupby(["june", "state"])["count"].sum()
    b = lga[(lga.lga_code == "TOT") & (lga["size"] == "Total") & (lga.state != "Australia")].set_index(["june", "state"])["count"]
    j = pd.concat([a, b], axis=1, keys=["sum", "total"]).dropna()
    j["pct"] = 100 * (j["sum"] - j["total"]) / j["total"]
    main = j.drop(index="Other Territories/Currently Unknown", level="state")
    out["state_pct_min"], out["state_pct_max"] = float(main["pct"].min()), float(main["pct"].max())
    worst = main["pct"].abs().groupby(level="state").max().sort_values(ascending=False, kind="stable")
    out["worst_states"] = [(s, float(main.xs(s, level="state")["pct"].iloc[main.xs(s, level="state")["pct"].abs().argmax()]))
                           for s in worst.index[:2]]
    out["lgas"] = int(x[x.june == x.june.max()]["lga_code"].nunique())
    nat = lga[(lga.state == "Australia") & (lga["size"] == "Total")].set_index("june")["count"]
    fs = flow_series(flows)
    fs["june"] = fs["fin_year"].str[:4].astype(int) + 1
    end = fs.set_index("june")["operating_end"]
    out["national_matches_dc01"] = bool(all(int(nat[y]) == int(end[y]) for y in nat.index))
    out["national"] = {int(k): int(v) for k, v in nat.items()}
    nua = x[x.lga.str.startswith("No usual address") & (x.division == "TOT") & (x["size"] == "Total")]
    nua_y = nua.groupby("june")["count"].sum()
    out["no_usual_address_share"] = {int(y): float(nua_y[y] / nat[y]) for y in nua_y.index}
    blank = x[x["count"].isna() & (x.division == "TOT") & (x["size"] == "Total")]
    out["blank_lga_rows"] = sorted(set(blank["lga"]))
    w = x[x["size"] == "Total"].pivot_table(index=["june", "lga_code"], columns="division", values="count", aggfunc="first")
    inds = [c for c in w.columns if c != "TOT"]
    gap = (w[inds].sum(axis=1) - w["TOT"])[w["TOT"].notna()]
    out["industry_gap_min"], out["industry_gap_max"] = int(gap.min()), int(gap.max())
    out["industry_gap_share"] = float((gap != 0).mean())
    return out
