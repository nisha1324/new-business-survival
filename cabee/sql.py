"""Part 4: a DuckDB SQL layer over the committed snapshot.

The SQL lives in ``sql/*.sql`` and runs in file order. The views read the
gzipped CSVs in ``data/`` directly (no database file is written), so any SQL
client that can point DuckDB's ``file_search_path`` at ``data/`` gets the same
tables. ``connect()`` does that and runs every file.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from cabee.load import DATA

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
VIEWS = ["entry_cohorts", "division_cohorts", "national_bands", "division_band_counts", "division_bands",
         "state_bands", "state_cells", "national_cells", "state_expected", "state_mix", "lga_places", "lga_growth",
         "perturbation_check", "benchmark", "benchmark_fit"]


def files() -> list[Path]:
    """The SQL files, in the order they run."""
    return sorted(SQL_DIR.glob("[0-9][0-9]_*.sql"))


def connect(data: Path = DATA) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB connection with every view in ``sql/`` defined over ``data``."""
    con = duckdb.connect()
    con.execute("SET threads = 1")   # one thread: floating-point sums add up in the same order every run
    path = str(Path(data).resolve()).replace("'", "''")
    con.execute(f"SET file_search_path = '{path}'")
    for f in files():
        con.execute(f.read_text())
    return con


def table(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    """A whole view as a DataFrame (``name`` must be one of ``VIEWS``)."""
    if name not in VIEWS:
        raise ValueError(f"unknown view {name!r}; expected one of {VIEWS}")
    return con.sql(f"SELECT * FROM {name}").df()


def query(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    """Any query against the views, with optional ``?`` parameters."""
    return con.execute(sql, params or []).df()


# ------------------------------------------------------------------ SQL vs pandas
def _compare(part: str, what: str, sql_df: pd.DataFrame, pd_df: pd.DataFrame, cols: list[str]) -> list[dict]:
    """One row per column: rows compared, rows that differ and the largest numeric difference.

    Both frames are indexed on the same key; a key present in only one of them
    counts as a mismatch. Blank in both counts as equal.
    """
    keys = sql_df.index.union(pd_df.index)
    one_side = pd.Series(~(keys.isin(sql_df.index) & keys.isin(pd_df.index)), index=keys)
    out = []
    for c in cols:
        a, b = sql_df[c].reindex(keys), pd_df[c].reindex(keys)
        both_blank = a.isna() & b.isna() & ~one_side
        if pd.api.types.is_numeric_dtype(a.dtype) and pd.api.types.is_numeric_dtype(b.dtype):
            diff = (a.astype(float) - b.astype(float)).abs()
            bad = ~both_blank & ~(diff <= 1e-9)
            mx = float(diff.max()) if diff.notna().any() else 0.0
        else:
            bad = ~both_blank & (a.astype(object) != b.astype(object))
            mx = None
        out.append({"part": part, "table": what, "column": c, "rows": len(keys), "mismatches": int(bad.sum()),
                    "max_abs_diff": mx})
    return out


def parity_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Rebuild the key Part 1-3 tables in SQL and compare them with the pandas functions."""
    from cabee import industries as I, load, profile as P, regions as R

    s, sub, lga = (load.read(k) for k in ("survival", "subdivision_survival", "lga_counts"))
    rows: list[dict] = []

    # Part 1: national entrants per cohort
    h = P.headline(s).set_index("entries_year")
    q = query(con, "SELECT cohort, entrants, survived, rate_pub FROM entry_cohorts "
                   "WHERE dimension = 'industry' AND level = 'total'").set_index("cohort")
    q.columns = ["entries", "entries_survived", "entries_rate"]
    rows += _compare("1", "headline: national entrants", q, h, list(q.columns))

    # Part 2: division survival across cohorts, size-band weights, divisions within bands
    tr = I.division_trend(s)
    q = query(con, "SELECT industry, cohort, rate_pub, rank_low, change_since_first FROM division_cohorts")
    rq = q.pivot(index="industry", columns="cohort", values="rate_pub")
    rows += _compare("2", "division_trend: rate per cohort", rq, tr, I.COHORTS)
    last = q[q.cohort == I.COHORTS[-1]].set_index("industry")
    rows += _compare("2", "division_trend: latest rank and change",
                     last.rename(columns={"rank_low": "rank_latest", "change_since_first": "change"}), tr,
                     ["rank_latest", "change"])
    nb = I.national_bands(s).reset_index().set_index(["start", "band"])
    q = table(con, "national_bands").rename(columns={"cohort": "start", "entrants": "base"}).set_index(["start", "band"])
    rows += _compare("2", "national_bands", q, nb, ["base", "survived", "weight", "rate"])
    db = I.division_bands(sub, s)
    q = table(con, "division_bands").set_index("division").rename(columns={"entrants": "entries"})
    rows += _compare("2", "division_bands", q, db, ["industry", "entries", "non_employing_share", "rate_all",
                                                    "rate_Non-employing", "rate_1-4", "rate_5+", "base_5+", "std",
                                                    "mix_effect", "rank_std", "rank_rate_all"])

    # Part 3: states across cohorts, within bands, after the mix; LGA growth
    sc = R.state_cohorts(s)
    q = query(con, "SELECT \"group\" AS state, cohort, rate_pub FROM entry_cohorts WHERE dimension = 'state'")
    q = q.pivot(index="state", columns="cohort", values="rate_pub").reindex(sc.index)
    rows += _compare("3", "state_cohorts: rate per cohort", q, sc, I.COHORTS)
    sb = R.state_bands(sub, s)
    q = table(con, "state_bands").set_index("state").rename(columns={"entrants": "entries"})
    rows += _compare("3", "state_bands", q, sb, ["entries", "non_employing_share", "rate_all", "rate_Non-employing",
                                                 "rate_1-4", "rate_5+", "std"])
    e = R.expected(sub)
    q = table(con, "state_expected").set_index("state")
    rows += _compare("3", "expected (division x band)", q, e, ["cell_base", "expected", "cells_actual",
                                                               "national_cells"])
    ms = R.mix_split(sb, e, float(sc.loc[R.NATIONAL, R.COHORT]))
    q = table(con, "state_mix").set_index("state")
    rows += _compare("3", "mix_split", q, ms, ["actual", "expected", "gap", "mix", "local", "residual", "rank_local"])
    g = R.lga_growth(lga).set_index("lga_code")
    q = table(con, "lga_growth").set_index("lga_code")
    rows += _compare("3", "lga_growth", q, g, ["businesses_2023", "businesses_2025", "employing_2023",
                                               "employing_2025", "change", "growth", "employing_change",
                                               "employing_growth", "top_division", "top_division_change"])
    return pd.DataFrame(rows)
