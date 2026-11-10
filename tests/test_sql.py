"""Part 4: the SQL layer matches the pandas analysis, the benchmark is rebuilt
independently in pandas, the rules sit at the right boundaries, the lookup works,
and the Part 4 outputs regenerate byte for byte."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from cabee import load, regions as R, sql
from cabee.industries import BAND_OF
from scripts import benchmark_lookup as LK
from scripts.benchmark_report import MAX_SMALL_SHARE, RELIABLE_BASE, SMALL_BASE

ROOT = Path(__file__).resolve().parents[1]
PART4 = ["BENCHMARK.md", "benchmark.csv", "benchmark_fit.csv", "perturbation_check.csv", "sql_parity.csv",
         "charts/15_perturbation_bias.png", "charts/16_state_adjustment_fit.png", "charts/17_benchmark_grid.png"]


@pytest.fixture(scope="module")
def con():
    return sql.connect()


@pytest.fixture(scope="module")
def sub():
    return load.read("subdivision_survival")


@pytest.fixture(scope="module")
def bench(con):
    return sql.table(con, "benchmark")


# ------------------------------------------------------- the layer itself
def test_sql_files_run_in_order_and_define_every_view(con):
    names = [f.name for f in sql.files()]
    assert names == sorted(names) and len(names) == 7
    have = set(sql.query(con, "SELECT view_name FROM duckdb_views() WHERE NOT internal").view_name)
    assert set(sql.VIEWS) <= have


def test_unknown_view_is_refused(con):
    with pytest.raises(ValueError):
        sql.table(con, "survival; DROP VIEW benchmark")


def test_lookup_tables_match_python(con):
    d = sql.query(con, "SELECT division, industry FROM divisions").set_index("division")["industry"].to_dict()
    assert d == {k: v[0] for k, v in load.DIVISIONS.items()}
    s = sql.query(con, "SELECT state, abbr FROM states ORDER BY state_order")
    assert list(s.state) == R.STATES and dict(zip(s.state, s.abbr)) == R.ABBR


def test_views_read_another_data_folder(tmp_path):
    # the same files copied elsewhere give the same benchmark: nothing is tied to data/
    for name in ("survival", "flows", "subdivision_survival", "lga_counts"):
        (tmp_path / f"{name}.csv.gz").write_bytes((load.DATA / f"{name}.csv.gz").read_bytes())
    other = sql.connect(tmp_path)
    a = sql.table(other, "benchmark")
    b = sql.table(sql.connect(), "benchmark")
    pd.testing.assert_frame_equal(a, b)


# ------------------------------------------------------- rules at their boundaries
@pytest.mark.parametrize("entrants, share, flag", [
    (0, None, "no rate"), (20, 0.0, "no rate"), (21, 0.0, "use with care"), (99, 0.0, "use with care"),
    (100, 0.0, "reliable"), (100, 0.10, "reliable"), (100, 0.1001, "use with care"), (5000, 0.5, "use with care"),
])
def test_reliability_boundaries(con, entrants, share, flag):
    assert con.execute("SELECT reliability(?, ?)", [entrants, share]).fetchone()[0] == flag


def test_rules_match_the_report_constants(con):
    assert con.execute("SELECT small_base(), reliable_base(), max_small_share()").fetchone() == (
        SMALL_BASE, RELIABLE_BASE, MAX_SMALL_SHARE)


def test_floored_rate_and_size_band(con):
    assert con.execute("SELECT floored_rate(10, 20)").fetchone()[0] is None
    assert con.execute("SELECT floored_rate(11, 21)").fetchone()[0] == pytest.approx(100 * 11 / 21)
    for size, band in {**BAND_OF, "Total": "Total"}.items():
        assert con.execute("SELECT size_band(?)", [size]).fetchone()[0] == band


# ------------------------------------------------------- SQL vs pandas (Parts 1-3)
def test_sql_reproduces_parts_1_to_3_exactly(con):
    p = sql.parity_checks(con)
    assert len(p) >= 50 and p["rows"].min() >= 4
    assert p["mismatches"].sum() == 0, p[p.mismatches > 0]
    assert p["max_abs_diff"].max() < 1e-9


def test_parity_check_catches_a_difference():
    a = pd.DataFrame({"x": [1.0, 2.0, None], "s": ["a", "b", "c"]}, index=[1, 2, 3])
    b = pd.DataFrame({"x": [1.0, 2.1, None], "s": ["a", "B", "c"]}, index=[1, 2, 4])
    out = pd.DataFrame(sql._compare("t", "t", a, b, ["x", "s"])).set_index("column")
    assert out.loc["x", "mismatches"] == 3   # 2.0 vs 2.1, and keys 3 and 4 each on one side only
    assert out.loc["s", "mismatches"] == 3
    assert out.loc["x", "max_abs_diff"] == pytest.approx(0.1)


# ------------------------------------------------------- the benchmark, rebuilt in pandas
def _flag(entrants, share):
    if entrants <= SMALL_BASE:
        return "no rate"
    return "reliable" if entrants >= RELIABLE_BASE and share <= MAX_SMALL_SHARE else "use with care"


def test_benchmark_rebuilt_independently(sub, bench):
    x = sub[(sub.cohort == "entries") & (sub.years_after == 3) & (sub.level == "group") & (sub.division != "X")
            & sub.state.isin(R.STATES) & (sub["size"] != "Total")].copy()
    x["band"] = x["size"].map(BAND_OF)
    x["small"] = x["base"].where(x["base"] <= SMALL_BASE, 0)
    c = x.groupby(["state", "division", "band"])[["base", "survived", "small"]].sum().astype(float)
    nat = c.groupby(level=["division", "band"]).sum()
    s, sb_ = load.read("survival"), None
    sb_ = R.state_bands(sub, s)
    local = R.mix_split(sb_, R.expected(sub), float(R.state_cohorts(s).loc[R.NATIONAL, R.COHORT]))["local"]

    got = bench.set_index(["state", "division", "band"]).sort_index()
    assert len(got) == len(c) == 8 * 19 * 3
    for (st, dv, bd), r in c.iterrows():
        g = got.loc[(st, dv, bd)]
        n = nat.loc[(dv, bd)]
        share = r["small"] / r["base"] if r["base"] else float("nan")
        assert g.entrants == r["base"] and g.survived == r["survived"]
        if r["base"]:
            assert g.small_share == pytest.approx(share)
        obs = 100 * r["survived"] / r["base"] if r["base"] > SMALL_BASE else None
        assert (pd.isna(g.observed) and obs is None) or g.observed == pytest.approx(obs)
        assert g.observed_flag == _flag(r["base"], share)
        nflag = _flag(n["base"], n["small"] / n["base"])
        assert g.national_flag == nflag
        assert g.national_rate == pytest.approx(100 * n["survived"] / n["base"])
        assert g.state_adjustment == pytest.approx(local[st])
        if g.observed_flag == "reliable":
            assert g.benchmark == pytest.approx(obs) and g.benchmark_source == "this state"
        elif nflag == "reliable":
            assert g.benchmark == pytest.approx(100 * n["survived"] / n["base"] + local[st])
            assert g.benchmark_source == "national + state adjustment"
        else:
            assert pd.isna(g.benchmark) and g.benchmark_source == "none"


def test_benchmark_shape(bench):
    assert not bench.duplicated(["state", "division", "band"]).any()
    assert bench.benchmark.dropna().between(0, 100).all()
    assert set(bench.band) == {"Non-employing", "1-4", "5+"}
    # observed and national entrants: the 8 states add up to the national cell
    tot = bench.groupby(["division", "band"]).entrants.sum()
    nat = bench.drop_duplicates(["division", "band"]).set_index(["division", "band"]).national_entrants
    assert (tot == nat.reindex(tot.index)).all()


def test_benchmark_fit_recomputed(bench, con):
    fit = sql.table(con, "benchmark_fit").set_index("state")
    both = bench[(bench.observed_flag == "reliable") & (bench.national_flag == "reliable")]
    e1 = (both.observed - both.national_rate).abs()
    e2 = (both.observed - both.national_rate - both.state_adjustment).abs()
    allr = fit.loc["All states"]
    assert allr.cells == len(both)
    assert allr.mae_national == pytest.approx(e1.mean()) and allr.mae_adjusted == pytest.approx(e2.mean())
    assert allr.wmae_adjusted == pytest.approx((e2 * both.entrants).sum() / both.entrants.sum())
    assert allr.share_closer == pytest.approx((e2 < e1).mean())
    tas = both[both.abbr == "Tas"]
    assert fit.loc["Tas", "mae_adjusted"] == pytest.approx(
        (tas.observed - tas.national_rate - tas.state_adjustment).abs().mean())
    assert len(fit) == 9


# ------------------------------------------------------- perturbation check, rebuilt in pandas
def test_perturbation_check_rebuilt(con, sub):
    pc = sql.table(con, "perturbation_check")
    e = sub[(sub.cohort == "entries") & (sub.years_after == 3) & (sub["size"] != "Total")].copy()
    e["band"] = e["size"].map(BAND_OF)
    cells = e[(e.level == "group") & e.state.isin(R.STATES)].groupby(["state", "band"])[["base", "survived"]].sum()
    tot = e[(e.level == "total") & e.state.isin(R.STATES)].groupby(["state", "band"])[["base", "survived"]].sum()
    want = 100 * cells.survived / cells.base - 100 * tot.survived / tot.base
    got = pc[pc.check_type == "state x size band"].copy()
    got["state"] = got.label.str.split(",").str[0].map({v: k for k, v in R.ABBR.items()})
    got = got.set_index(["state", "band"]).bias
    assert len(got) == 24
    for k, v in want.items():
        assert got[k] == pytest.approx(v)
    # divisions: cells (all states, unknown industry out) vs data cube 1's unperturbed counts
    s = load.read("survival")
    c1 = s[(s.dimension == "industry") & (s.level == "group") & (s.cohort == "entries") & (s.years_after == 3)
           & (s.start == "2021-22")].set_index("group")
    mining = e[(e.level == "group") & (e.division == "B")][["base", "survived"]].sum()
    row = pc[pc.label == "Mining"].iloc[0]
    assert row.bias == pytest.approx(100 * mining.survived / mining.base
                                     - 100 * c1.loc["Mining", "survived"] / c1.loc["Mining", "base"])


def test_known_figures(con, bench):
    pc = sql.table(con, "perturbation_check").set_index("label")
    assert pc.loc["NT, 5+", "bias"] == pytest.approx(-27.09, abs=0.005)
    assert pc.loc["NT, 5+", "small_share"] == 1.0
    r = bench[(bench.abbr == "NT") & (bench.division == "H") & (bench.band == "1-4")].iloc[0]
    assert (int(r.entrants), round(r.observed, 1), r.observed_flag) == (90, 40.0, "use with care")
    assert round(r.benchmark, 1) == 54.5 and r.benchmark_source == "national + state adjustment"
    assert int((bench.benchmark_source != "none").groupby(bench.band).sum()["5+"]) == 15


# ------------------------------------------------------- lookup CLI
def test_lookup_resolves_names_letters_and_abbreviations(con):
    assert LK.resolve(con, "food", "nt", "1-4") == ("H", "Northern Territory", "1-4")
    assert LK.resolve(con, "E", "New South Wales", "Non-employing") == ("E", "New South Wales", "Non-employing")
    assert LK.resolve(con, "mining", "TAS", "0") == ("B", "Tasmania", "Non-employing")
    for bad in [("services", "Vic", "1-4"), ("food", "Victoria State", "1-4"), ("food", "Vic", "3")]:
        with pytest.raises(ValueError):
            LK.resolve(con, *bad)


def test_lookup_answer_matches_the_benchmark(con, bench, capsys):
    r = LK.lookup(con, "food", "NT", "1-4")
    want = bench[(bench.abbr == "NT") & (bench.division == "H") & (bench.band == "1-4")].iloc[0]
    assert r["benchmark"] == pytest.approx(want.benchmark)
    assert LK.main(["food", "NT", "1-4"]) == 0
    out = capsys.readouterr().out
    assert "54.5% (national + state adjustment)" in out and "40.0% (use with care)" in out
    assert LK.main(["services", "Vic", "1-4"]) == 2


# ------------------------------------------------------- regeneration
def _hashes(paths):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_part4_report_regenerates_byte_for_byte():
    outs = [ROOT / "results" / p for p in PART4]
    assert all(p.exists() for p in outs)
    before = _hashes(outs)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "benchmark_report.py")], check=True, cwd=ROOT,
                   capture_output=True)
    assert _hashes(outs) == before


def test_benchmark_fit_on_hand_made_rows():
    # replace the benchmark view with 3 hand-made reliable cells; benchmark_fit binds to it by name
    c = sql.connect()
    c.execute("DROP VIEW benchmark")
    c.execute("""CREATE TABLE benchmark AS SELECT * FROM (VALUES
        (1, 'NSW', 100, 50.0, 'reliable', 48.0, 'reliable', 2.0),   -- adjustment closes the gap exactly
        (1, 'NSW', 300, 40.0, 'reliable', 40.0, 'reliable', 0.0),   -- tie: no adjustment, no gap -> not "closer"
        (2, 'Vic', 100, 60.0, 'reliable', 55.0, 'reliable', -1.0),  -- adjustment makes it worse: 5 -> 6
        (2, 'Vic', 100, 60.0, 'use with care', 55.0, 'reliable', -1.0)  -- not reliable: left out
    ) AS t(state_order, abbr, entrants, observed, observed_flag, national_rate, national_flag, state_adjustment)""")
    f = sql.table(c, "benchmark_fit").set_index("state")
    assert list(f.index) == ["NSW", "Vic", "All states"]
    assert f.loc["NSW", "cells"] == 2 and f.loc["NSW", "share_closer"] == pytest.approx(0.5)
    assert f.loc["NSW", "mae_national"] == pytest.approx(1.0) and f.loc["NSW", "mae_adjusted"] == pytest.approx(0.0)
    assert f.loc["NSW", "wmae_national"] == pytest.approx(200 / 400)
    assert f.loc["Vic", "mae_adjusted"] == pytest.approx(6.0) and f.loc["Vic", "share_closer"] == 0
    assert f.loc["All states", "cells"] == 3 and f.loc["All states", "share_closer"] == pytest.approx(1 / 3)
    assert pd.isna(f.loc["All states", "state_adjustment"]) and f.loc["Vic", "state_adjustment"] == -1.0
