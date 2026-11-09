"""Parsers on hand-made sheets, plus invariants of the committed snapshot."""
import hashlib
import json
import math

import pandas as pd
import pytest

from cabee import load

FOOT = ("(a) footnote",)
COPY = ("© Commonwealth of Australia",)


def test_survival_sheet_businesses():
    rows = [
        ("Australian Bureau of Statistics",),
        ("Table 15 Survival of Businesses by Employment Size Range",),
        (None, "Operating in June 2022", "Survived to June 2023", "Survival rate", "Survived to June 2024", "Survival rate"),
        (None, "no.", "no.", "%", "no.", "%"),
        ("Non-employing", 100, 80, 80.0, 60, 60),
        ("Employing", None, None, None, None, None),
        ("1–4", 50, 45, 90.0, 40, 80.0),
        ("Currently Unknown", 10, 5, None, 2, None),
        ("Total", 160, 130, 81.3, 102, 63.8),
        FOOT, COPY,
    ]
    df = load.parse_survival_sheet(rows)
    assert len(df) == 8
    assert set(df["cohort"]) == {"businesses"}
    assert set(df["cohort_june"]) == {2022}
    one = df[(df.group == "1–4") & (df.survived_to == 2024)].iloc[0]
    assert (one.base, one.survived, one.rate_pub, one.years_after, one.section) == (50, 40, 80.0, 2, "Employing")
    assert df[df.group == "Non-employing"].section.iloc[0] == ""
    unk = df[df.group == "Currently Unknown"]
    assert unk.level.iloc[0] == "unknown" and unk.rate_pub.isna().all()
    assert df[df.group == "Total"].level.iloc[0] == "total"


def test_survival_sheet_entries_counts_from_june_ending_entry_year():
    rows = [
        ("t",),
        (None, "Entries in 2022-23", "Survived to June 2024", "Survival rate", "Survived to June 2026", "Survival rate"),
        (None, "no.", "no.", "%", "no.", "%"),
        ("Mining", 980, 748, 76.3, 517, 52.8),
    ]
    df = load.parse_survival_sheet(rows)
    assert set(df["cohort"]) == {"entries"}
    assert df["start"].iloc[0] == "2022-23"
    assert df["cohort_june"].iloc[0] == 2023
    assert list(df["years_after"]) == [1, 3]


def test_flow_sheet_year_sections():
    hdr = (None, "Operating at start of financial year", "Entries - \nBirths", "Entries - \nOther", "Entries - \nTotal",
           "Exits - \nCancellations", "Exits - \nOther", "Exits - \nTotal", "Operating at end of financial year",
           "Change", "Percentage change")
    rows = [("t",), hdr, ("no.",) * 11,
            ("2022-23",), ("Mining", 10, 2, 1, 3, 1, 1, 2, 11, 1, 10.0), ("All Industries", 10, 2, 1, 3, 1, 1, 2, 11, 1, 10.0),
            ("2023-24",), ("Mining", 11, 1, 0, 1, 2, 0, 2, 10, -1, -9.1), COPY]
    df = load.parse_flow_sheet(rows)
    assert list(df["fin_year"]) == ["2022-23", "2022-23", "2023-24"]
    assert list(df["level"]) == ["group", "total", "group"]
    r = df.iloc[2]
    assert (r.operating_start, r.births, r.entries, r.exits, r.operating_end) == (11, 1, 1, 2, 10)
    assert df["net_movement"].isna().all()


def test_subdivision_sheet():
    top = [None, None, None, "Operating in June 2021", None, None, None, None, None, "Survived to June 2022"] + [None] * 11
    sub = ["State", "ANZSIC Subdivision", "ANZSIC Subdivision", "Non Employing", "1-4 Employees", "5-19 Employees",
           "20-199 Employees", "200+ Employees", "Total"]
    for s in ["Non Employing", "1-4 Employees", "5-19 Employees", "20-199 Employees", "200+ Employees", "Total"]:
        sub += [s, "Survival rate"]
    data = ["Tasmania", 6, "Coal Mining", 4, 2, 0, 0, 0, 7, 3, 66.7, 2, 100, 0, None, 0, None, 0, None, 5, 71.4]
    total = ["Total Tasmania", None, None, 4, 2, 0, 0, 0, 6] + [3, 75.0, 2, 100.0, 0, None, 0, None, 0, None, 5, 83.3]
    rows = [("x",), ("x",), ("x",), ("x",), tuple(top), tuple(sub), ("Label",), tuple(data), tuple(total), FOOT]
    df = load.parse_subdivision_sheet(rows)
    assert len(df) == 12
    c = df[(df.subdivision_code == "06") & (df["size"] == "Non employing")].iloc[0]
    assert (c.division, c.base, c.survived, c.rate_pub, c.years_after) == ("B", 4, 3, 66.7, 1)
    assert df[(df.subdivision_code == "06") & (df["size"] == "Total")].base.iloc[0] == 7  # perturbed: 4+2 != 7
    t = df[df.level == "total"]
    assert set(t.state) == {"Tasmania"} and set(t.subdivision_code) == {"TOT"}
    assert math.isnan(df[(df.subdivision_code == "06") & (df["size"] == "5-19")].rate_pub.iloc[0])


@pytest.mark.parametrize("code,div", [(1, "A"), (5, "A"), (6, "B"), (25, "C"), (46, "I"), (53, "I"), (96, "S"), (99, "X")])
def test_division_of(code, div):
    assert load.division_of(code) == div


@pytest.mark.parametrize("code", [61, 65, 98, 0])
def test_division_of_rejects_unused_codes(code):
    with pytest.raises(ValueError):
        load.division_of(code)


@pytest.mark.parametrize("label,level", [
    ("All Industries", "total"), ("Australia", "total"), ("All Sectors", "total"),
    ("All Organisational Types", "total"), ("Total", "total"), ("Total employing", "subtotal"),
    ("Currently Unknown", "unknown"), ("Other Territories/Currently Unknown", "unknown"),
    ("Mining", "group"), ("Victoria", "group"),
])
def test_level(label, level):
    assert load._level(label) == level


@pytest.mark.skipif(not all((load.RAW / f).exists() for f in [*load.DC01.values(), load.DC04, load.DC05, load.DC10]),
                    reason="raw workbooks not downloaded (run scripts/download_data.py)")
def test_parsers_rebuild_the_committed_snapshot():
    for name, fn in load.TABLES.items():
        pd.testing.assert_frame_equal(fn().reset_index(drop=True), load.read(name).reset_index(drop=True),
                                      check_dtype=False, obj=name)


def test_one_total_row_per_table(snap):
    s = snap["survival"]
    n_tot = s[s.level == "total"].groupby(["release", "dimension", "cohort", "survived_to"]).size()
    assert (n_tot == 1).all() and len(n_tot) == 4 * 5 * 7


# ------------------------------------------------------- the real snapshot
@pytest.fixture(scope="module")
def snap():
    return {name: load.read(name) for name in load.TABLES}


def test_snapshot_hashes_match_manifest():
    meta = json.loads((load.DATA / "SNAPSHOT.json").read_text())
    for name, info in meta["outputs"].items():
        assert hashlib.sha256((load.DATA / name).read_bytes()).hexdigest() == info["sha256"], name


def test_snapshot_shapes(snap):
    assert len(snap["survival"]) == 4 * (84 + 63 + 40 + 30 + 20 + 15 + 24 + 18 + 28 + 21)
    assert len(snap["flows"]) == 4 * (4 * 21 + 4 * 10)
    # 9 states x 86 subdivisions + 10 totals, 6 sizes, 4 + 3 survival dates
    assert len(snap["subdivision_survival"]) == (9 * 86 + 10) * 6 * 7
    assert snap["lga_counts"].groupby("june")["lga_code"].nunique().tolist() == [558] * 3  # 557 LGAs + "TOT"


def test_entry_cohort_base_equals_entries_in_counts_table(snap):
    s, f = snap["survival"], snap["flows"]
    e = s[(s.cohort == "entries") & (s.years_after == 1) & s.dimension.isin(["industry", "state"])]
    m = e.merge(f, left_on=["release", "dimension", "start", "group"],
                right_on=["release", "dimension", "fin_year", "group"], how="left", validate="one_to_one")
    assert m["entries"].notna().all()
    assert (m["base"] == m["entries"]).all()


def test_business_cohort_base_equals_operating_at_start(snap):
    s, f = snap["survival"], snap["flows"]
    b = s[(s.cohort == "businesses") & (s.years_after == 1) & s.dimension.isin(["industry", "state"])].copy()
    b["fin_year"] = b["cohort_june"].astype(str) + "-" + (b["cohort_june"] + 1).astype(str).str[-2:]
    m = b.merge(f, on=["release", "dimension", "fin_year", "group"], how="left", validate="one_to_one")
    assert (m["base"] == m["operating_start"]).all()


def test_flows_balance(snap):
    f = snap["flows"]
    assert (f["births"] + f["entries_other"] == f["entries"]).all()
    assert (f["cancellations"] + f["exits_other"] == f["exits"]).all()
    ind = f[f.dimension == "industry"]
    assert (ind["operating_start"] + ind["entries"] - ind["exits"] == ind["operating_end"]).all()


def test_every_subdivision_maps_to_a_division(snap):
    d = snap["subdivision_survival"]
    g = d[d.level == "group"]
    assert set(g.division) == set(load.DIVISIONS) | {"X"}
    assert g.subdivision_code.str.fullmatch(r"\d{2}").all()


def test_survived_never_exceeds_base(snap):
    for name in ("survival", "subdivision_survival"):
        x = snap[name].dropna(subset=["base", "survived"])
        assert (x["survived"] <= x["base"]).all(), name


def test_lga_national_matches_dc01(snap):
    lga, f = snap["lga_counts"], snap["flows"]
    nat = lga[(lga.state == "Australia") & (lga["size"] == "Total")].set_index("june")["count"]
    t = f[(f.dimension == "industry") & (f.level == "total") & (f.release == "2022-2026")]
    end = t.assign(june=t.fin_year.str[:4].astype(int) + 1).set_index("june")["operating_end"]
    for june in (2023, 2024, 2025):
        assert nat[june] == end[june]


def test_text_codes_survive_round_trip(snap):
    d = snap["subdivision_survival"]
    assert "01" in set(d.subdivision_code)
    assert pd.api.types.is_string_dtype(snap["lga_counts"]["lga_code"])
