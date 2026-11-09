"""Part 2 measures on hand-made frames, the real figures the report relies on,
and a byte-for-byte regeneration check of the Part 2 outputs."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from cabee import industries as I, load, profile as P

ROOT = Path(__file__).resolve().parents[1]
PART2 = ["INDUSTRY_SURVIVAL.md", "industry_cohorts.csv", "industry_size_bands.csv", "subdivision_survival.csv",
         "national_size_bands.csv", "charts/06_industry_cohorts.png", "charts/07_common_size_mix.png",
         "charts/08_subdivisions.png", "charts/09_national_size_bands.png"]


def _sub(rows):
    cols = ["cohort", "state", "subdivision_code", "subdivision", "division", "level", "size", "base",
            "years_after", "survived"]
    df = pd.DataFrame(rows, columns=cols)
    for c in ("base", "survived"):
        df[c] = df[c].astype("Int64")
    return df


def _surv(rows):
    """Data cube 1 style rows: (dimension, group, level, start, years_after, base, survived, rate_pub)."""
    cols = ["dimension", "group", "level", "start", "years_after", "base", "survived", "rate_pub"]
    df = pd.DataFrame(rows, columns=cols)
    df["cohort"] = "entries"
    return df


# ------------------------------------------------------- hand-made frames
def test_band_counts_folds_large_sizes_sums_states_and_drops_unknown():
    rows = []
    for st in ("NSW", "Vic"):
        rows += [
            ("entries", st, "45", "Food", "H", "group", "Non employing", 10, 3, 4),
            ("entries", st, "45", "Food", "H", "group", "1-4", 6, 3, 3),
            ("entries", st, "45", "Food", "H", "group", "5-19", 3, 3, 2),
            ("entries", st, "45", "Food", "H", "group", "20-199", 2, 3, 2),
            ("entries", st, "45", "Food", "H", "group", "200+", 1, 3, 1),
            ("entries", st, "45", "Food", "H", "group", "Total", 23, 3, 12),   # perturbed: bands add to 22
            ("entries", st, "99", "Unknown", "X", "group", "Total", 50, 3, 5),
            ("entries", st, "45", "Food", "H", "group", "Total", 23, 2, 15),   # another June: ignored
            ("businesses", st, "45", "Food", "H", "group", "Total", 99, 3, 50),  # other cohort: ignored
        ]
    c = I.band_counts(_sub(rows), ["division"])
    assert list(c.index) == ["H"]
    assert c["base"].loc["H", "Non-employing"] == 20
    assert c["base"].loc["H", "5+"] == 12          # (3 + 2 + 1) x 2 states
    assert c["survived"].loc["H", "5+"] == 10
    assert c["base"].loc["H", "Employing"] == 24   # 1-4 + 5+
    assert c["base"].loc["H", "Total"] == 46       # the published Total, not the sum of bands (44)


def test_rates_floor_is_strictly_above_20():
    counts = pd.concat({"base": pd.DataFrame({"a": [20.0, 21.0]}), "survived": pd.DataFrame({"a": [10.0, 7.0]})},
                       axis=1)
    r = I.rates(counts)["a"]
    assert pd.isna(r.iloc[0])
    assert r.iloc[1] == pytest.approx(100 / 3)


def test_standardise_weights_band_rates_and_blanks_missing_bands():
    r = pd.DataFrame({"Non-employing": [40.0, 40.0], "1-4": [60.0, None], "5+": [80.0, 80.0]})
    w = pd.Series({"Non-employing": 0.5, "1-4": 0.3, "5+": 0.2})
    s = I.standardise(r, w)
    assert s.iloc[0] == pytest.approx(0.5 * 40 + 0.3 * 60 + 0.2 * 80)
    assert pd.isna(s.iloc[1])


def _nb(w_a, r_a, w_b, r_b):
    idx = pd.MultiIndex.from_product([["A", "B"], I.BANDS], names=["start", "band"])
    return pd.DataFrame({"weight": w_a + w_b, "rate": r_a + r_b}, index=idx)


def test_mix_decomposition_parts_add_up_and_isolate_each_effect():
    only_mix = I.mix_decomposition(_nb([0.8, 0.15, 0.05], [40, 60, 70], [0.6, 0.3, 0.1], [40, 60, 70]), "A", "B")
    assert only_mix["within"] == pytest.approx(0)
    assert only_mix["mix"] == pytest.approx(only_mix["total"]) and only_mix["total"] > 0
    only_rates = I.mix_decomposition(_nb([0.7, 0.2, 0.1], [40, 60, 70], [0.7, 0.2, 0.1], [38, 59, 70]), "A", "B")
    assert only_rates["mix"] == pytest.approx(0)
    assert only_rates["within"] == pytest.approx(0.7 * -2 + 0.2 * -1)
    both = I.mix_decomposition(_nb([0.8, 0.15, 0.05], [45, 60, 70], [0.6, 0.3, 0.1], [41, 63, 66]), "A", "B")
    assert both["within"] + both["mix"] == pytest.approx(both["total"])
    assert both["band_change"] == {"Non-employing": -4, "1-4": 3, "5+": -4}


def test_division_trend_ranks_counts_bottom_and_first_june_share():
    rows = []
    rates = {"Alpha": [40, 42, 41, 39], "Beta": [50, 41, 48, 52], "Gamma": [60, 61, 62, 63]}
    for g, rs in rates.items():
        for c, r in zip(I.COHORTS, rs):
            rows.append(("industry", g, "group", c, 3, 100, r, float(r)))
        rows.append(("industry", g, "group", I.COHORTS[-1], 1, 100, 80, 80.0))
    rows.append(("industry", "All Industries", "total", I.COHORTS[-1], 3, 300, 150, 50.0))
    t = I.division_trend(_surv(rows), bottom_k=1)
    assert list(t.index) == ["Alpha", "Beta", "Gamma"]
    assert t.loc["Beta", "change"] == 2
    assert t.loc["Beta", "low"] == 41 and t.loc["Beta", "high"] == 52
    assert t.loc["Alpha", "cohorts_in_bottom"] == 3   # Beta was lowest in 2020-21
    assert t.loc["Beta", "cohorts_in_bottom"] == 1
    assert t["rank_latest"].tolist() == [1, 2, 3]
    assert t.loc["Alpha", "first_june_share_of_loss"] == pytest.approx(20 / 61)
    st = I.rank_stability(t)
    assert st["always_bottom"] == []
    assert len(st["pairs"]) == 6


# ------------------------------------------------------- real figures
@pytest.fixture(scope="module")
def data():
    s, sub = load.read("survival"), load.read("subdivision_survival")
    return {"s": s, "sub": sub, "t": I.division_trend(s), "nb": I.national_bands(s),
            "d": I.division_bands(sub, s), "sd": I.subdivision_bands(sub, s)}


def test_trend_matches_data_cube_1(data):
    t = data["t"]
    assert len(t) == 19 and "Currently Unknown" not in t.index
    assert t.loc["Transport, Postal and Warehousing", "2022-23"] == 37.4
    assert t.loc["Transport, Postal and Warehousing", "entries_latest"] == 55118
    assert t.loc["Retail Trade", I.COHORTS].tolist() == [52.3, 48.5, 44.7, 46.2]
    assert t["change"].idxmin() == "Retail Trade"
    assert int((t["change"] < 0).sum()) == 16
    assert I.rank_stability(t)["always_bottom"] == [
        "Administrative and Support Services", "Public Administration and Safety",
        "Transport, Postal and Warehousing", "Wholesale Trade"]


def test_national_bands_rebuild_the_published_rate(data):
    nb, s = data["nb"], data["s"]
    tot = (nb["weight"] * nb["rate"]).groupby(level="start").sum()
    pub = s[(s.dimension == "industry") & (s.level == "total") & (s.cohort == "entries") & (s.years_after == 3)]
    pub = pub.set_index("start")["rate_pub"]
    assert (tot - pub[tot.index]).abs().max() <= 0.05 + 1e-9
    assert nb["weight"].groupby(level="start").sum().tolist() == pytest.approx([1, 1, 1, 1])
    d = I.mix_decomposition(nb, "2019-20", "2022-23")
    assert round(d["within"], 1) == -1.8 and round(d["mix"], 1) == 0.2
    assert all(v < 0 for v in d["band_change"].values())


def test_division_bands_add_up_to_the_national_detail_total(data):
    sub, d = data["sub"], data["d"]
    x = sub[(sub.cohort == "entries") & (sub.years_after == 3) & (sub["size"] == "Total")]
    nat = int(x[(x.state == "Australia") & (x.level == "total")]["base"].iloc[0])
    unknown = int(x[(x.level == "group") & (x.division == "X")]["base"].sum())
    # perturbed cells: the 19 divisions + unknown miss the national Total by a handful of businesses
    assert abs(d["entries"].sum() + unknown - nat) <= 10


def test_division_overall_rates_equal_part_1(data):
    mix = P.division_size_mix(data["sub"])
    assert (data["d"]["rate_all"] - mix["rate_all"].reindex(data["d"].index)).abs().max() < 1e-9


def test_subdivisions_sum_to_divisions(data):
    sd, d = data["sd"], data["d"]
    assert sd.groupby("division")["entries"].sum().reindex(d.index).tolist() == d["entries"].tolist()


def test_no_rate_on_a_base_of_20_or_fewer(data):
    c = I.band_counts(data["sub"], ["subdivision_code", "subdivision", "division"])
    sd = data["sd"].set_index("subdivision", append=True)
    for band in ("Non-employing", "Employing", "Total"):
        col = "rate_all" if band == "Total" else f"rate_{band}"
        small = c["base"][band].droplevel("division") <= 20
        small = small.reindex(sd.index)
        assert sd.loc[small, col].isna().all(), band
        assert sd.loc[~small, col].notna().all(), band
    assert data["sd"]["std_2"].notna().sum() == 77


def test_common_mix_is_robust_to_the_band_choice(data):
    d = data["d"]
    assert (d["std"] - d["std_2"]).abs().max() < 0.6
    assert (d["std"].rank() == d["std_2"].rank()).all()
    assert d["std"].notna().all()  # every division clears the floor in all three bands


def test_key_division_figures(data):
    d = data["d"]
    w = I.weights(data["s"])
    assert round(w["Non-employing"], 3) == 0.735
    h = d.loc["H"]
    assert (h["rank_rate_all"], h["rank_std"]) == (10, 4)
    assert round(h["rate_all"], 1) == 48.4 and round(h["std"], 1) == 41.9
    assert d["mix_effect"].idxmax() == "H" and d["mix_effect"].idxmin() == "I"
    assert d.loc["I", "rank_rate_all"] == 1
    assert (d["rate_1-4"] > d["rate_Non-employing"]).all()


def test_report_text_matches_the_figures(data):
    rep = (ROOT / "results" / "INDUSTRY_SURVIVAL.md").read_text()
    for phrase in [
        "Accommodation and Food Services falls from 10th to 4th lowest (48.4% → 41.9%)",
        "37.4% of its 55,118 2022-23 entrants were still trading three Junes on, against 49.2% for all industries",
        "−1.8 points inside the size bands and +0.2 points from the size mix",
        "Retail Trade fell the most (52.3% → 46.2%, −6.1 points)",
        "the ranking is identical",
        "45% to 52% of the 2022-23 entrants",
    ]:
        assert phrase in rep, phrase


def _hashes(paths):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_part2_report_regenerates_byte_for_byte():
    outs = [ROOT / "results" / p for p in PART2]
    assert all(p.exists() for p in outs)
    before = _hashes(outs)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "industry_survival.py")], check=True, cwd=ROOT,
                   capture_output=True)
    assert _hashes(outs) == before
