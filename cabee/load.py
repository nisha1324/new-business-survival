"""Parse the ABS CABEE data cubes (data/raw/*.xlsx) into tidy tables.

Four tidy tables come out of seven workbooks:

- ``survival``: data cube 1 survival tables from four releases. One row per
  release x cohort ("businesses" operating in June of the first year, or
  "entries" during the first financial year) x dimension x group x survival
  date.
- ``flows``: data cube 1 counts tables by industry division and by state from
  the same four releases: operating at start, entries (births, other), exits
  (cancellations, other) and operating at end, per financial year.
- ``subdivision_survival``: data cubes 4 and 5 of the June 2021 - June 2025
  release: survival by state x ANZSIC subdivision x employment size.
- ``lga_counts``: data cube 10 of the same release: businesses operating in
  June 2023, 2024 and 2025 by LGA x industry division x employment size.

Published survival rates are kept as published (``rate_pub``). The counts in
the detailed cubes are perturbed by ABS for confidentiality, so a rate
recomputed from them can differ from the published one; Part 1's profile
measures by how much.
"""
from __future__ import annotations

from pathlib import Path
import re

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# release label -> data cube 1 file. The label is the span of June dates covered.
DC01 = {
    "2019-2023": "cabee_dc01_jun2019_jun2023.xlsx",
    "2020-2024": "cabee_dc01_jun2020_jun2024.xlsx",
    "2021-2025": "cabee_dc01_jun2021_jun2025.xlsx",
    "2022-2026": "cabee_dc01_jun2022_jun2026.xlsx",
}
DC04 = "cabee_dc04_jun2021_jun2025.xlsx"
DC05 = "cabee_dc05_jun2021_jun2025.xlsx"
DC10 = "cabee_dc10_jun2021_jun2025.xlsx"

# Sheet numbers are the same in all four releases (checked in Part 1).
SURVIVAL_SHEETS = {
    "industry": ("Table 2", "Table 3"),
    "state": ("Table 5", "Table 6"),
    "sector": ("Table 8", "Table 9"),
    "legal_form": ("Table 11", "Table 12"),
    "size": ("Table 15", "Table 16"),
}
FLOW_SHEETS = {"industry": "Table 1", "state": "Table 4"}

TOTAL_LABELS = {"All Industries", "Australia", "All Sectors", "All Organisational Types", "Total"}
SUBTOTAL_LABELS = {"Total employing"}
UNKNOWN_LABELS = {"Currently Unknown", "Other Territories/Currently Unknown"}

SIZE_BANDS = ["Non employing", "1-4", "5-19", "20-199", "200+", "Total"]

# ANZSIC 2006 subdivision code ranges for each industry division.
DIVISIONS = {
    "A": ("Agriculture, Forestry and Fishing", 1, 5),
    "B": ("Mining", 6, 10),
    "C": ("Manufacturing", 11, 25),
    "D": ("Electricity, Gas, Water and Waste Services", 26, 29),
    "E": ("Construction", 30, 32),
    "F": ("Wholesale Trade", 33, 38),
    "G": ("Retail Trade", 39, 43),
    "H": ("Accommodation and Food Services", 44, 45),
    "I": ("Transport, Postal and Warehousing", 46, 53),
    "J": ("Information Media and Telecommunications", 54, 60),
    "K": ("Financial and Insurance Services", 62, 64),
    "L": ("Rental, Hiring and Real Estate Services", 66, 67),
    "M": ("Professional, Scientific and Technical Services", 69, 70),
    "N": ("Administrative and Support Services", 72, 73),
    "O": ("Public Administration and Safety", 75, 77),
    "P": ("Education and Training", 80, 82),
    "Q": ("Health Care and Social Assistance", 84, 87),
    "R": ("Arts and Recreation Services", 89, 92),
    "S": ("Other Services", 94, 96),
}


def division_of(subdivision_code: int) -> str:
    """ANZSIC division letter for a 2-digit subdivision code ("X" for 99, unknown)."""
    for letter, (_, lo, hi) in DIVISIONS.items():
        if lo <= subdivision_code <= hi:
            return letter
    if subdivision_code == 99:
        return "X"
    raise ValueError(f"subdivision {subdivision_code} is not in any ANZSIC division")


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _rows(path: Path, sheet: str) -> list[tuple]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list(wb[sheet].iter_rows(values_only=True))
    finally:
        wb.close()


def _level(label: str) -> str:
    if label in TOTAL_LABELS:
        return "total"
    if label in SUBTOTAL_LABELS:
        return "subtotal"
    if label in UNKNOWN_LABELS:
        return "unknown"
    return "group"


def _norm_size(label: str) -> str:
    s = _clean(label).replace("–", "-").replace("Employees", "").strip()
    return {"Non-employing": "Non employing", "Non Employing": "Non employing"}.get(s, s)


# ---------------------------------------------------------------- data cube 1
def parse_survival_sheet(rows: list[tuple]) -> pd.DataFrame:
    """One data cube 1 survival sheet -> tidy rows.

    The header row holds "Operating in June YYYY" (businesses) or
    "Entries in YYYY-YY" (entries) followed by pairs of
    "Survived to June YYYY" / "Survival rate" columns.
    """
    h = next(
        i for i, r in enumerate(rows)
        if any(isinstance(c, str) and re.match(r"(Operating in June|Entries in) ", _clean(c)) for c in r)
    )
    hdr = [_clean(c) if c is not None else None for c in rows[h]]
    base_col = next(i for i, c in enumerate(hdr) if c and re.match(r"(Operating in June|Entries in) ", c))
    base_label = hdr[base_col]
    if base_label.startswith("Operating"):
        cohort = "businesses"
        cohort_june = int(re.search(r"June (\d{4})", base_label).group(1))
        start = f"June {cohort_june}"
    else:
        cohort = "entries"
        y0 = int(re.search(r"Entries in (\d{4})", base_label).group(1))
        cohort_june = y0 + 1  # entries during 2022-23 are first counted at June 2023
        start = f"{y0}-{str(y0 + 1)[-2:]}"
    survived_cols = [
        (i, int(re.search(r"June (\d{4})", c).group(1)))
        for i, c in enumerate(hdr) if c and c.startswith("Survived to June")
    ]
    out, section = [], ""
    for r in rows[h + 2:]:
        if not r or r[0] is None:
            continue
        label = _clean(r[0])
        if label.startswith(("(", "©")):
            continue
        base = _num(r[base_col])
        if base is None:
            section = label  # "Employing", "Private Sector", "Public Sector"
            continue
        for col, june in survived_cols:
            rate = _num(r[col + 1]) if col + 1 < len(r) else None
            out.append({
                "cohort": cohort, "start": start, "cohort_june": cohort_june,
                "section": section, "group": label, "level": _level(label),
                "base": int(base), "survived_to": june, "years_after": june - cohort_june,
                "survived": int(_num(r[col])), "rate_pub": float(rate) if rate is not None else float("nan"),
            })
    return pd.DataFrame(out)


def load_survival(raw: Path = RAW) -> pd.DataFrame:
    frames = []
    for release, fname in DC01.items():
        for dim, sheets in SURVIVAL_SHEETS.items():
            for sheet in sheets:
                df = parse_survival_sheet(_rows(raw / fname, sheet))
                df.insert(0, "dimension", dim)
                df.insert(0, "release", release)
                frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["group"] = df.apply(lambda r: _norm_size(r["group"]) if r["dimension"] == "size" else r["group"], axis=1)
    return df


FLOW_COLS = {
    "Operating at start of financial year": "operating_start",
    "Entries - Births": "births",
    "Entries - Other": "entries_other",
    "Entries - Total": "entries",
    "Exits - Cancellations": "cancellations",
    "Exits - Other": "exits_other",
    "Exits - Total": "exits",
    "Net movement of surviving businesses": "net_movement",
    "Operating at end of financial year": "operating_end",
}


def parse_flow_sheet(rows: list[tuple]) -> pd.DataFrame:
    """A data cube 1 counts sheet (Table 1 or 4) -> one row per year x group."""
    h = next(i for i, r in enumerate(rows) if any(isinstance(c, str) and c.startswith("Operating at start") for c in r))
    cols = {i: FLOW_COLS[_clean(c)] for i, c in enumerate(rows[h]) if isinstance(c, str) and _clean(c) in FLOW_COLS}
    out, year = [], None
    for r in rows[h + 2:]:
        if not r or r[0] is None:
            continue
        label = _clean(r[0])
        if re.fullmatch(r"\d{4}-\d{2}", label):
            year = label
            continue
        if label.startswith(("(", "©")) or year is None:
            continue
        rec = {"fin_year": year, "group": label, "level": _level(label)}
        for i, name in cols.items():
            v = _num(r[i])
            rec[name] = int(v) if v is not None else None
        out.append(rec)
    df = pd.DataFrame(out)
    if "net_movement" not in df:
        df["net_movement"] = None
    return df[["fin_year", "group", "level", *FLOW_COLS.values()]]


def load_flows(raw: Path = RAW) -> pd.DataFrame:
    frames = []
    for release, fname in DC01.items():
        for dim, sheet in FLOW_SHEETS.items():
            df = parse_flow_sheet(_rows(raw / fname, sheet))
            df.insert(0, "dimension", dim)
            df.insert(0, "release", release)
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    for c in FLOW_COLS.values():
        df[c] = df[c].astype("Int64")
    return df


# ------------------------------------------------------- data cubes 4 and 5
def parse_subdivision_sheet(rows: list[tuple]) -> pd.DataFrame:
    """Data cube 4 or 5, Table 1 -> state x subdivision x size x survival date.

    Row 4 holds the period groups ("Operating in June 2021" / "Entries in
    2021-2022", then "Survived to June YYYY"); row 5 the size bands, each
    survived band followed by its "Survival rate" column.
    """
    top = [_clean(c) if c is not None else None for c in rows[4]]
    sub = [_clean(c) if c is not None else None for c in rows[5]]
    period, periods = None, []
    for i, c in enumerate(top):
        period = c or period
        periods.append(period if i >= 3 else None)
    base_label = next(p for p in periods if p)
    if base_label.startswith("Operating"):
        cohort, cohort_june = "businesses", int(re.search(r"June (\d{4})", base_label).group(1))
    else:
        cohort, cohort_june = "entries", int(re.search(r"Entries in (\d{4})", base_label).group(1)) + 1
    base_cols, surv_cols = {}, []
    for i in range(3, len(sub)):
        if sub[i] is None or sub[i].lower() == "survival rate":
            continue
        size = _norm_size(sub[i])
        if periods[i] == base_label:
            base_cols[size] = i
        elif periods[i] and periods[i].startswith("Survived to June"):
            surv_cols.append((size, int(periods[i][-4:]), i))
    out = []
    for r in rows[7:]:
        if not r or r[0] is None:
            continue
        state = _clean(r[0])
        if state.startswith(("(", "©")):
            continue
        if r[1] is None:  # "Total New South Wales", ..., "Total Australia"
            code, label = "TOT", "All industries"
            state = state.removeprefix("Total ").strip()
            level = "total"
        else:
            code, label, level = f"{int(r[1]):02d}", _clean(r[2]), "group"
        for size, june, col in surv_cols:
            base, surv, rate = _num(r[base_cols[size]]), _num(r[col]), _num(r[col + 1])
            out.append({
                "cohort": cohort, "cohort_june": cohort_june, "state": state,
                "subdivision_code": code, "subdivision": label,
                "division": division_of(int(code)) if code != "TOT" else "TOT",
                "level": level, "size": size,
                "base": int(base) if base is not None else None,
                "survived_to": june, "years_after": june - cohort_june,
                "survived": int(surv) if surv is not None else None,
                "rate_pub": float(rate) if rate is not None else float("nan"),
            })
    df = pd.DataFrame(out)
    for c in ("base", "survived"):
        df[c] = df[c].astype("Int64")
    return df


def load_subdivision_survival(raw: Path = RAW) -> pd.DataFrame:
    return pd.concat(
        [parse_subdivision_sheet(_rows(raw / f, "Table 1")) for f in (DC04, DC05)],
        ignore_index=True,
    )


# ------------------------------------------------------------ data cube 10
def _lga_table_years(raw: Path) -> dict[str, int]:
    """Map each table sheet to its June year using the Contents sheet."""
    years = {}
    for r in _rows(raw / DC10, "Contents"):
        if r and isinstance(r[1] if len(r) > 1 else None, int) and len(r) > 2 and isinstance(r[2], str):
            m = re.search(r"June (\d{4})", r[2])
            if m:
                years[f"Table {r[1]}"] = int(m.group(1))
    return years


def load_lga_counts(raw: Path = RAW) -> pd.DataFrame:
    wb = openpyxl.load_workbook(raw / DC10, read_only=True, data_only=True)
    sheets = {s.strip(): s for s in wb.sheetnames}
    wb.close()
    frames = []
    for table, june in _lga_table_years(raw).items():
        rows = _rows(raw / DC10, sheets[table])
        sub = [_norm_size(c) if c is not None else None for c in rows[5]]
        size_cols = {sub[i]: i for i in range(5, 11)}
        out = []
        for r in rows[7:]:
            if not r or r[0] is None:
                continue
            state = _clean(r[0])
            if state.startswith(("(", "©")):
                continue
            if r[1] is None:  # state and national totals
                rec = {"state": state.removeprefix("Total ").strip(), "lga_code": "TOT", "lga": "All LGAs",
                       "division": "TOT", "industry": "All industries"}
            else:
                rec = {"state": state, "lga_code": str(int(r[1])), "lga": _clean(r[2]),
                       "division": r[3] if r[3] is not None else "TOT", "industry": _clean(r[4])}
            for size, i in size_cols.items():
                v = _num(r[i])
                out.append({"june": june, **rec, "size": size, "count": int(v) if v is not None else None})
        frames.append(pd.DataFrame(out))
    df = pd.concat(frames, ignore_index=True)
    df["count"] = df["count"].astype("Int64")
    df["industry"] = df["industry"].replace({"Total": "All industries"})
    return df.sort_values(["june", "state", "lga_code", "division", "size"], kind="stable").reset_index(drop=True)


# ------------------------------------------------------------- the snapshot
DATA = ROOT / "data"
TABLES = {
    "survival": load_survival,
    "flows": load_flows,
    "subdivision_survival": load_subdivision_survival,
    "lga_counts": load_lga_counts,
}
# text columns that must not be read back as numbers ("01", "TOT", LGA codes)
_TEXT = {"subdivision_code": str, "lga_code": str, "division": str, "section": str, "start": str}


def read(name: str, data: Path = DATA) -> pd.DataFrame:
    """Read one tidy table from the committed snapshot (data/<name>.csv.gz)."""
    df = pd.read_csv(data / f"{name}.csv.gz", dtype=_TEXT, keep_default_na=False, na_values=[""])
    if "section" in df:
        df["section"] = df["section"].fillna("")
    for c in ("base", "survived", "count", *FLOW_COLS.values()):
        if c in df:
            df[c] = df[c].astype("Int64")
    return df
