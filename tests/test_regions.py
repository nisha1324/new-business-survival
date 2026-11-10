"""Part 3 measures on hand-made frames, the real figures the report relies on,
and a byte-for-byte regeneration check of the Part 3 outputs."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from cabee import industries as I, load, regions as R

ROOT = Path(__file__).resolve().parents[1]
PART3 = ["REGIONS.md", "state_cohorts.csv", "state_flows.csv", "state_mix.csv", "state_excess_vic.csv",
         "lga_growth.csv", "lga_growth_by_industry.csv", "charts/10_state_cohorts.png", "charts/11_state_mix.png",
         "charts/12_victoria_2021_22.png", "charts/13_lga_growth.png", "charts/14_growth_by_industry.png"]


def _sub(rows):
    """Data cube 5 style rows: (state, subdivision_code, subdivision, division, level, size, base, survived)."""
    cols = ["state", "subdivision_code", "subdivision", "division", "level", "size", "base", "survived"]
    df = pd.DataFrame(rows, columns=cols)
    df["cohort"], df["years_after"] = "entries", 3
    for c in ("base", "survived"):
        df[c] = df[c].astype("Int64")
    return df


def _lga(rows):
    """Data cube 10 style rows: (june, state, lga_code, lga, division, industry, size, count)."""
    df = pd.DataFrame(rows, columns=["june", "state", "lga_code", "lga", "division", "industry", "size", "count"])
    df["count"] = df["count"].astype("Int64")
    return df


# ------------------------------------------------------- hand-made frames
def _two_states():
    # NSW: 100 non-employing in sub 01 (div A), 50 1-4 in sub 45 (div H). Vic: 300 / 10. Rates differ by state.
    rows = [
        ("New South Wales", "01", "Agri", "A", "group", "Non employing", 100, 40),
        ("New South Wales", "45", "Food", "H", "group", "1-4", 50, 35),
        ("Victoria", "01", "Agri", "A", "group", "Non employing", 300, 150),
        ("Victoria", "45", "Food", "H", "group", "1-4", 10, 5),
        # left out of the cells: unknown industry, Other Territories, Total rows, state-total rows
        ("Victoria", "99", "Unknown", "X", "group", "Non employing", 500, 0),
        ("Other Territories/Currently Unknown", "01", "Agri", "A", "group", "Non employing", 500, 0),
        ("Victoria", "01", "Agri", "A", "group", "Total", 999, 0),
        ("Victoria", "TOT", "All industries", "TOT", "total", "Non employing", 999, 0),
    ]
    return _sub(rows)


def test_expected_is_indirect_standardisation_on_national_cell_rates():
    e = R.expected(_two_states(), ("division", "band")).dropna(how="all")
    nat_a, nat_h = 190 / 400, 40 / 60      # national rate per cell, over the two states only
    assert e.loc["New South Wales", "expected"] == pytest.approx(100 * (100 * nat_a + 50 * nat_h) / 150)
    assert e.loc["Victoria", "expected"] == pytest.approx(100 * (300 * nat_a + 10 * nat_h) / 310)
    assert e.loc["Victoria", "cells_actual"] == pytest.approx(100 * 155 / 310)
    assert e.loc["Victoria", "cell_base"] == 310
    assert e["national_cells"].unique().tolist() == pytest.approx([100 * 230 / 460])


def test_expected_equals_actual_when_states_share_the_same_rates():
    rows = [(st, "01", "Agri", "A", "group", sz, b, b // 2) for st, sz, b in
            [("New South Wales", "Non employing", 100), ("New South Wales", "1-4", 40),
             ("Victoria", "Non employing", 60), ("Victoria", "1-4", 200)]]
    e = R.expected(_sub(rows), ("division", "band")).dropna(how="all")
    assert (e["expected"] - e["cells_actual"]).abs().max() == pytest.approx(0)


def test_mix_split_parts_add_up_exactly():
    bands = pd.DataFrame({"rate_all": [47.0, 52.0]}, index=["New South Wales", "Victoria"])
    exp = pd.DataFrame({"expected": [49.0, 48.5], "national_cells": [47.9, 47.9]}, index=bands.index)
    m = R.mix_split(bands, exp, 48.0)
    assert m.loc["New South Wales", "mix"] == pytest.approx(1.1)
    assert m.loc["New South Wales", "local"] == pytest.approx(-2.0)
    assert m["residual"].tolist() == pytest.approx([-0.1, -0.1])
    assert (m["mix"] + m["local"] + m["residual"] - m["gap"]).abs().max() == pytest.approx(0)
    assert m["rank_local"].tolist() == [1, 2]


def test_state_bands_use_state_total_rows_floor_and_national_weights():
    rows = []
    for st, (ne, one4, five) in {"New South Wales": ((100, 40), (21, 14), (20, 15)),
                                 "Victoria": ((200, 80), (50, 30), (30, 24))}.items():
        rows += [(st, "TOT", "All", "TOT", "total", "Non employing", *ne), (st, "TOT", "All", "TOT", "total", "1-4", *one4),
                 (st, "TOT", "All", "TOT", "total", "5-19", five[0] - 5, five[1] - 4),
                 (st, "TOT", "All", "TOT", "total", "20-199", 5, 4),
                 (st, "TOT", "All", "TOT", "total", "Total", 999, 999),        # ignored: bands are summed
                 (st, "01", "Agri", "A", "group", "Non employing", 7, 7)]      # ignored: not a state-total row
    # national weights from data cube 1 style size rows (2021-22 entrants)
    surv = pd.DataFrame([("size", g, "group", "2021-22", 3, b, b // 2, 50.0) for g, b in
                         [("Non employing", 700), ("1-4", 200), ("5-19", 80), ("20-199", 15), ("200+", 5)]],
                        columns=["dimension", "group", "level", "start", "years_after", "base", "survived", "rate_pub"])
    surv["cohort"] = "entries"
    b = R.state_bands(_sub(rows), surv).dropna(how="all")
    nsw, vic = b.loc["New South Wales"], b.loc["Victoria"]
    assert nsw["entries"] == 141 and nsw["rate_all"] == pytest.approx(100 * 69 / 141)
    assert nsw["rate_1-4"] == pytest.approx(100 * 14 / 21)       # base 21: rated
    assert pd.isna(nsw["rate_5+"]) and pd.isna(nsw["std"])        # base 20: blank, so no common-mix rate
    assert vic["std"] == pytest.approx(0.7 * 40 + 0.2 * 60 + 0.1 * 80)
    assert vic["non_employing_share"] == pytest.approx(200 / 280)


def test_excess_entrants_and_the_counterfactual():
    rows = [("Victoria", "52", "Transport support", "I", "group", "Non employing", 60, 15),
            ("Victoria", "01", "Agri", "A", "group", "Non employing", 40, 20),
            ("New South Wales", "52", "Transport support", "I", "group", "Non employing", 40, 16),
            ("New South Wales", "01", "Agri", "A", "group", "Non employing", 160, 96),
            ("Queensland", "52", "Transport support", "I", "group", "Non employing", 10, 1)]   # rest base 50
    ex = R.excess_entrants(_sub(rows), "Victoria")
    share = 100 / 310
    assert ex.attrs["overall_share"] == pytest.approx(share)
    t = ex.loc["52"]
    assert t["share"] == pytest.approx(60 / 110)
    assert t["excess"] == pytest.approx(60 - share * 110)
    assert t["rate_state"] == pytest.approx(25.0) and t["rate_rest"] == pytest.approx(100 * 17 / 50)
    assert ex["excess"].sum() == pytest.approx(0)
    assert ex.index[0] == "52"
    # removing the excess at the state's own rate: (35 - x * 0.25) / (100 - x)
    x = t["excess"]
    assert R.without(100, 35, ex.head(1)) == pytest.approx(100 * (35 - x * 0.25) / (100 - x))
    assert R.without(100, 35, ex.tail(1)) == pytest.approx(35.0)  # a negative excess removes nothing


def _lga_rows(code, name, state, sizes_23, sizes_25, inds):
    rows = []
    for june, sizes in ((2023, sizes_23), (2025, sizes_25)):
        for sz, c in sizes.items():
            rows.append((june, state, code, name, "TOT", "All industries", sz, c))
        rows.append((june, state, code, name, "TOT", "All industries", "Total", sum(sizes.values())))
        for (div, ind), (c23, c25) in inds.items():
            rows.append((june, state, code, name, div, ind, "Total", c23 if june == 2023 else c25))
    return rows


def test_lga_growth_measures_floor_and_exclusions():
    rows = (_lga_rows("1", "Fringe", "Victoria", {"Non employing": 900, "1-4": 80, "5-19": 20},
                      {"Non employing": 1200, "1-4": 85, "5-19": 20},
                      {("I", "Transport"): (100, 350), ("E", "Construction"): (200, 255), ("A", "Agri"): (700, 700)})
            + _lga_rows("2", "Town", "Victoria", {"Non employing": 990, "1-4": 15, "5-19": 4},
                        {"Non employing": 990, "1-4": 10, "5-19": 9},
                        {("A", "Agri"): (509, 509), ("E", "Construction"): (500, 500)})
            + _lga_rows("3", "No usual address", "Victoria", {"Non employing": 50}, {"Non employing": 90}, {})
            + _lga_rows("4", "Island", "Other Territories/Currently Unknown", {"Non employing": 50},
                        {"Non employing": 90}, {})
            + _lga_rows("TOT", "All LGAs", "Victoria", {"Non employing": 1}, {"Non employing": 2}, {}))
    g = R.lga_growth(_lga(rows)).set_index("lga")
    assert list(g.index) == ["Fringe", "Town"]
    f, t = g.loc["Fringe"], g.loc["Town"]
    assert f["change"] == 305 and f["growth"] == pytest.approx(305 / 1000)
    assert f["employing_2023"] == 100 and f["employing_growth"] == pytest.approx(0.05)
    assert f["non_employing_share_of_change"] == pytest.approx(300 / 305)
    assert f["top_division"] == "Transport" and f["top_division_change"] == 250
    assert f["state_abbr"] == "Vic"
    assert t["change"] == 0 and pd.isna(t["non_employing_share_of_change"])
    assert pd.isna(t["employing_growth"])                 # 19 employing businesses: at or under the floor
    assert t["top_division"] == "Agri"                    # a tie (0 and 0) is broken alphabetically
    r = R.ranked(g.reset_index(), floor=1000)
    assert r["lga"].tolist() == ["Fringe", "Town"]        # Fringe has exactly 1,000: in
    assert R.ranked(g.reset_index(), floor=1001)["lga"].tolist() == ["Town"]   # 1,009
    assert R.ranked(g.reset_index(), floor=1010).empty


def test_growth_drivers_split_non_employing_and_employing():
    rows = []
    for june, ne, emp in ((2023, 10, 5), (2025, 30, 2)):
        for code in ("1", "2"):
            rows += [(june, "Victoria", code, f"L{code}", "I", "Transport", "Non employing", ne),
                     (june, "Victoria", code, f"L{code}", "I", "Transport", "1-4", emp),
                     (june, "Victoria", code, f"L{code}", "I", "Transport", "Total", ne + emp)]
    d = R.growth_drivers(_lga(rows), ["1"])
    assert d.loc["Transport", "non_employing_change"] == 20 and d.loc["Transport", "employing_change"] == -3
    assert d.loc["Transport", "growth"] == pytest.approx(17 / 15)
    assert R.growth_drivers(_lga(rows)).loc["Transport", "change"] == 34
    assert R.growth_drivers(_lga(rows))["share"].sum() == pytest.approx(1)


# ------------------------------------------------------- real figures
@pytest.fixture(scope="module")
def data():
    s, f, sub, lga = (load.read(k) for k in ("survival", "flows", "subdivision_survival", "lga_counts"))
    sb = R.state_bands(sub, s)
    sc = R.state_cohorts(s)
    nat = float(sc.loc["Australia", "2021-22"])
    splits = {k: R.mix_split(sb, R.expected(sub, k), nat) for k in
              [("division", "band"), ("subdivision_code", "band"), ("subdivision_code", "size")]}
    g = R.lga_growth(lga)
    return {"s": s, "f": f, "sub": sub, "lga": lga, "sb": sb, "sc": sc, "nat": nat, "splits": splits, "g": g,
            "rk": R.ranked(g), "e": R.expected(sub)}


def test_state_cohorts_match_data_cube_1(data):
    sc, s = data["sc"], data["s"]
    pub = s[(s.dimension == "state") & (s.cohort == "entries") & (s.years_after == 3)]
    pub = pub.pivot_table(index="group", columns="start", values="rate_pub")
    for st in R.STATES + ["Australia"]:
        assert sc.loc[st, I.COHORTS].tolist() == pub.loc[st, I.COHORTS].tolist(), st
    assert "Other Territories/Currently Unknown" not in sc.index
    assert (sc.loc[R.STATES, "rank_2022-23"].sort_values().tolist() == list(range(1, 9)))
    assert (sc.loc["Tasmania", [f"rank_{c}" for c in I.COHORTS]] == 8).all()
    assert sc.loc["Victoria", "2021-22"] == 44.9 and sc.loc["New South Wales", "2022-23"] == 48.0


def test_state_flows_match_part_1_and_add_up(data):
    sf = R.state_flows(data["f"])
    assert sf.loc["Australia", "operating_start"] == 2268998 and sf.loc["Australia", "operating_end"] == 2814778
    assert round(sf.loc["Australia", "growth"], 3) == 0.241
    assert (sf["years"] == 7).all()
    other = data["f"][(data["f"].dimension == "state") & (data["f"].group.str.startswith("Other"))
                      & (data["f"].fin_year == "2025-26")]["operating_end"].iloc[0]
    assert sf.loc[R.STATES, "operating_end"].sum() + other == sf.loc["Australia", "operating_end"]
    assert sf.loc[R.STATES, "growth"].idxmin() == "Tasmania" and sf.loc[R.STATES, "entry_rate"].idxmin() == "Tasmania"


def test_state_total_rows_equal_data_cube_1_counts(data):
    s, sub = data["s"], data["sub"]
    pub = s[(s.dimension == "state") & (s.cohort == "entries") & (s.years_after == 3) & (s.start == "2021-22")]
    pub = pub.set_index("group")
    x = sub[(sub.cohort == "entries") & (sub.years_after == 3) & (sub.level == "total") & (sub["size"] == "Total")]
    x = x.set_index("state")
    for st in R.STATES:
        assert int(x.loc[st, "base"]) == int(pub.loc[st, "base"]), st
        assert int(x.loc[st, "survived"]) == int(pub.loc[st, "survived"]), st
    # the size rows behind state_bands rebuild the published rate to rounding
    assert (data["sb"]["rate_all"] - pub.loc[R.STATES, "rate_pub"]).abs().max() <= 0.05 + 1e-9


def test_summing_small_cells_biases_small_states_down(data):
    bias = data["e"]["cells_actual"] - data["sb"]["rate_all"]
    assert bias.idxmin() == "Northern Territory" and round(bias.min(), 1) == -2.3
    assert bias[["New South Wales", "Victoria"]].abs().max() < 0.1   # large states: negligible


def test_mix_split_real_figures_and_robustness(data):
    sp = data["splits"]
    m = sp[("division", "band")]
    assert (m["mix"] + m["local"] + m["residual"] - m["gap"]).abs().max() < 1e-9
    assert m["residual"].nunique() == 1 and abs(m["residual"].iloc[0]) < 0.1
    assert m["local"].idxmin() == "New South Wales" and m["local"].idxmax() == "Tasmania"
    assert round(m.loc["Victoria", "gap"], 1) == -3.1 and round(m.loc["Victoria", "mix"], 1) == -2.0
    assert round(m.loc["New South Wales", "local"], 1) == -1.4 and round(m.loc["Tasmania", "local"], 1) == 6.0
    for other in sp.values():
        assert (other["local"] - m["local"]).abs().max() < 0.2
        assert other["local"].rank()[["New South Wales", "Tasmania", "South Australia", "Western Australia"]].tolist() \
            == m["local"].rank()[["New South Wales", "Tasmania", "South Australia", "Western Australia"]].tolist()


def test_victoria_excess(data):
    ex = R.excess_entrants(data["sub"], "Victoria")
    assert ex.index[:3].tolist() == ["52", "46", "73"]
    assert round(ex["excess"].head(3).sum()) == 8551
    assert abs(ex["excess"].sum()) < 1e-6
    assert (ex.head(3)["rate_state"] < ex.head(3)["rate_rest"]).all()
    small = ex["entrants"] <= 20
    assert ex.loc[small, "rate_state"].isna().all() and ex.loc[~small, "rate_state"].notna().all()


def test_lga_totals_and_floor(data):
    g, rk, lga = data["g"], data["rk"], data["lga"]
    assert len(g) == 547 and len(rk) == 303
    assert rk["businesses_2023"].min() >= 1000
    assert g["lga"].isin(["No usual address"]).sum() == 0
    assert (g["state"].isin(R.STATES)).all()
    sz = R.size_change(lga)
    assert sz.loc["Non employing", "change"] == 149180 and sz["change"].sum() == 139482
    # employing = the four employing bands
    assert g["employing_2023"].sum() == sz.loc[["1-4", "5-19", "20-199", "200+"], "businesses_2023"].sum()
    small = g["employing_2023"] <= 20
    assert g.loc[small, "employing_growth"].isna().all() and g.loc[~small, "employing_growth"].notna().all()


def test_fastest_growing_lgas(data):
    rk = data["rk"]
    top = rk.head(20)
    assert rk.iloc[0]["lga"] == "Kwinana" and rk.iloc[1]["lga"] == "Melton"
    sz = R.size_change(data["lga"], top["lga_code"])
    assert round(sz.loc["Non employing", "change"] / sz["change"].sum(), 3) == 0.918
    d = R.growth_drivers(data["lga"], top["lga_code"])
    assert d.index[0] == "Transport, Postal and Warehousing" and round(d["share"].iloc[0], 3) == 0.395
    assert int((top["top_division"] == "Transport, Postal and Warehousing").sum()) == 17
    assert int((rk["growth"] < 0).sum()) == 31 and int((rk["employing_growth"] < 0).sum()) == 199


def test_report_text_matches_the_figures():
    rep = (ROOT / "results" / "REGIONS.md").read_text()
    for phrase in [
        "it kept 47.6%, 1.4 points fewer, the weakest of the 8 states on that basis",
        "Its entrants were 3.1 points below the national rate; 2.0 points of that is its industry × size mix",
        "non-employing businesses grew by 149,180 and employing businesses fell by 9,698",
        "91.8% of the net increase employed no one and 39.5% was in Transport, Postal and Warehousing",
        "Northern Territory comes out at 46.9% from its cells against 49.2% published (−2.3 points)",
        "lift its 2021-22 rate from 44.9% to 45.7%",
        "the ranking is the same apart from NT and ACT, which swap",
    ]:
        assert phrase in rep, phrase


def _hashes(paths):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_part3_report_regenerates_byte_for_byte():
    outs = [ROOT / "results" / p for p in PART3]
    assert all(p.exists() for p in outs)
    before = _hashes(outs)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "regions_report.py")], check=True, cwd=ROOT,
                   capture_output=True)
    assert _hashes(outs) == before
