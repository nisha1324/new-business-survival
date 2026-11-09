"""Profile measures on hand-made frames, the real figures the report relies on,
and a byte-for-byte regeneration check of the Part 1 outputs."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from cabee import load, profile as P

ROOT = Path(__file__).resolve().parents[1]


def _sub(rows):
    cols = ["cohort", "state", "subdivision_code", "division", "level", "size", "base", "survived_to",
            "years_after", "survived", "rate_pub"]
    df = pd.DataFrame(rows, columns=cols)
    for c in ("base", "survived"):
        df[c] = df[c].astype("Int64")
    return df


def test_small_cells_flags_rates_that_disagree_with_counts():
    df = _sub([
        ("entries", "Tas", "06", "B", "group", "Total", 3, 2025, 3, 0, 66.7),     # off by 66.7
        ("entries", "Tas", "07", "B", "group", "Total", 3, 2025, 3, 2, 66.7),     # 66.67 rounds to 66.7: fine
        ("entries", "Tas", "08", "B", "group", "Total", 40, 2025, 3, 20, 50.0),   # fine
        ("entries", "Tas", "09", "B", "group", "Total", 0, 2025, 3, 0, None),     # no base: not rated
        ("entries", "Tas", "10", "B", "group", "Total", 30, 2025, 3, 20, 66.5),   # 66.67 vs 66.5: beyond rounding
    ])
    sc = P.small_cells(df).set_index("base_band")
    assert (sc.loc["1-5", "cells"], sc.loc["1-5", "off"]) == (2, 1)
    assert (sc.loc["21-50", "cells"], sc.loc["21-50", "off"]) == (2, 1)
    assert sc["cells"].sum() == 4


def test_small_cell_bands_are_inclusive_at_the_top():
    df = _sub([("entries", "T", "06", "B", "group", "Total", b, 2025, 3, b, 100.0) for b in (5, 10, 20, 21)])
    sc = P.small_cells(df).set_index("base_band")["cells"]
    assert (sc["1-5"], sc["6-10"], sc["11-20"], sc["21-50"]) == (1, 1, 1, 1)


def test_perturbation_counts_rows_whose_sizes_do_not_add():
    rows = []
    for code, total in (("06", 10), ("07", 12)):
        for size, base in zip(P.SIZES + ["Total"], [5, 3, 2, 0, 0, total]):
            rows.append(("businesses", "Tas", code, "B", "group", size, base, 2022, 1, base, 100.0))
    pt = P.perturbation(_sub(rows))
    assert (pt["rows"], pt["rows_not_adding"], pt["size_gap_min"]) == (2, 1, -2)


def test_flow_series_takes_each_year_from_the_latest_release():
    f = pd.DataFrame({
        "release": ["2019-2023", "2020-2024", "2020-2024"], "dimension": "industry",
        "fin_year": ["2020-21", "2020-21", "2021-22"], "group": "All Industries", "level": "total",
        "operating_start": [1, 2, 3], "births": 0, "entries_other": 0, "entries": 0,
        "cancellations": 0, "exits_other": 0, "exits": 0, "operating_end": 0,
    })
    fs = P.flow_series(f)
    assert list(fs["fin_year"]) == ["2020-21", "2021-22"]
    assert list(fs["operating_start"]) == [2, 3]


def test_division_size_mix_recomputes_rates_from_summed_counts():
    rows = []
    for state, (ne, ne_s, e, e_s) in {"NSW": (8, 4, 2, 2), "Vic": (2, 0, 8, 4)}.items():
        for size, base, surv in (("Non employing", ne, ne_s), ("1-4", e, e_s), ("Total", ne + e, ne_s + e_s)):
            rows.append(("entries", state, "06", "B", "group", size, base, 2025, 3, surv, None))
    m = P.division_size_mix(_sub(rows)).loc["B"]
    assert m["entries"] == 20
    assert m["non_employing_share"] == pytest.approx(0.5)
    assert m["rate_non_employing"] == pytest.approx(40.0)
    assert m["rate_employing"] == pytest.approx(60.0)
    assert m["rate_all"] == pytest.approx(50.0)


# ------------------------------------------------------- real figures
@pytest.fixture(scope="module")
def data():
    return {name: load.read(name) for name in load.TABLES}


def test_headline_figures(data):
    h = P.headline(data["survival"]).set_index("release")
    assert h.loc["2022-2026", "entries"] == 406365
    assert h.loc["2022-2026", "entries_survived"] == 199742
    assert h.loc["2022-2026", "entries_rate"] == 49.2
    assert h["entries_rate"].tolist() == [50.8, 50.1, 48.0, 49.2]
    assert h["businesses_rate"].tolist() == [64.5, 64.1, 63.1, 61.9]


def test_data_cube_1_is_exact(data):
    assert P.rate_consistency(data["survival"])["over_rounding"] == 0
    add = P.additivity(data["survival"])
    assert add[["max_gap_base", "max_gap_survived"]].max().max() == 0


def test_revisions_never_touch_national_totals(data):
    rev = P.revisions(data["flows"])
    assert rev["total_cells"] == 40 and rev["total_changed"] == 0
    assert rev["group_changed"] > 0


def test_detail_cubes_match_data_cube_1_at_state_level(data):
    dt = P.detail_totals_check(data["subdivision_survival"], data["survival"])
    assert dt["pairs"] == 70
    assert (dt["max_gap_base"], dt["max_gap_survived"], dt["max_gap_rate"]) == (0, 0, 0.0)


def test_mismatched_rates_only_on_small_bases(data):
    pt = P.perturbation(data["subdivision_survival"])
    assert pt["off_cells"] > 0
    assert pt["off_max_base"] <= P.SMALL_BASE
    assert pt["survived_gt_base"] == 0


def test_rebuilt_division_rates_close_to_published(data):
    m = P.division_check(data["subdivision_survival"], data["survival"])
    assert len(m) == 19
    assert m["diff"].abs().max() < 1.0


def test_lga_checks(data):
    lc = P.lga_checks(data["lga_counts"], data["flows"])
    assert lc["national_matches_dc01"]
    assert lc["lgas"] == 557
    assert -1 < lc["state_pct_min"] <= lc["state_pct_max"] < 1


def _hashes(paths):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_profile_report_regenerates_byte_for_byte():
    outs = sorted((ROOT / "results").rglob("*.*"))
    outs = [p for p in outs if p.suffix in {".md", ".csv", ".png"}]
    assert any(p.name == "SOURCE_PROFILE.md" for p in outs)
    before = _hashes(outs)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "profile_source.py")], check=True, cwd=ROOT,
                   capture_output=True)
    assert _hashes(outs) == before
