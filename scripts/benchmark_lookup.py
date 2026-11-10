"""Look up the survival benchmark for one industry, state and size band.

    python scripts/benchmark_lookup.py "food" Vic 1-4
    python scripts/benchmark_lookup.py construction "New South Wales" non-employing

Industry: part of the ANZSIC division name, or its letter (e.g. H). State: name or
abbreviation. Size band: non-employing (or 0), 1-4, 5+. Runs the SQL in sql/ over
the committed snapshot; nothing is downloaded.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cabee import sql  # noqa: E402

BAND_ALIASES = {"non-employing": "Non-employing", "nonemploying": "Non-employing", "0": "Non-employing",
                "none": "Non-employing", "1-4": "1-4", "5+": "5+", "5-19": "5+", "20+": "5+"}


def resolve(con, industry: str, state: str, band: str) -> tuple[str, str, str]:
    """Turn user input into (division letter, state name, band); raise ValueError with the options if unclear."""
    divs = sql.query(con, "SELECT division, industry FROM divisions")
    q = industry.strip().lower()
    hit = divs[(divs.division.str.lower() == q) | (divs.industry.str.lower() == q)]   # exact letter or name first
    if hit.empty:
        hit = divs[divs.industry.str.lower().str.contains(q, regex=False)]
    if len(hit) != 1:
        raise ValueError(f"industry {industry!r} matches {len(hit)} divisions; choose one of: "
                         + "; ".join(f"{d} {i}" for d, i in divs.itertuples(index=False)))
    sts = sql.query(con, "SELECT state, abbr FROM states ORDER BY state_order")
    s = sts[(sts.state.str.lower() == state.strip().lower()) | (sts.abbr.str.lower() == state.strip().lower())]
    if len(s) != 1:
        raise ValueError(f"state {state!r} not recognised; choose one of: " + ", ".join(sts.abbr))
    b = BAND_ALIASES.get(band.strip().lower().replace(" ", ""))
    if b is None:
        raise ValueError(f"size band {band!r} not recognised; use non-employing, 1-4 or 5+")
    return hit.division.iloc[0], s.state.iloc[0], b


def lookup(con, industry: str, state: str, band: str) -> dict:
    """The benchmark row for one cell, as a dict."""
    d, s, b = resolve(con, industry, state, band)
    rows = sql.query(con, "SELECT * FROM benchmark WHERE division = ? AND state = ? AND band = ?", [d, s, b])
    assert len(rows) == 1
    return rows.iloc[0].to_dict()


def describe(r: dict) -> str:
    """A short plain-English answer for one benchmark row."""
    def pc(x):
        return "–" if x != x or x is None else f"{x:.1f}%"   # x != x is NaN
    band = {"Non-employing": "non-employing", "1-4": "1-4 employees", "5+": "5+ employees"}[r["band"]]
    lines = [f"{r['industry']}, {band}, {r['state']}: businesses that entered in 2021-22",
             f"  entrants here:         {int(r['entrants']):,}",
             f"  own rate:              {pc(r['observed'])} ({r['observed_flag']})",
             f"  national rate:         {pc(r['national_rate'])} ({r['national_flag']}, "
             f"{int(r['national_entrants']):,} entrants)",
             f"  state adjustment:      {r['state_adjustment']:+.1f} points".replace("-", "−"),
             f"  benchmark:             {pc(r['benchmark'])} ({r['benchmark_source']})"]
    if r["benchmark_source"] == "none":
        lines.append("  Too few entrants, or too many in perturbed small cells, to benchmark."
                     + (" For 5+ employees use the state's exact all-industry rate in results/BENCHMARK.md."
                        if r["band"] == "5+" else ""))
    lines.append("  = share still trading in June 2025, three Junes after entry. Still trading isn't the same as "
                 "profitable.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("industry")
    ap.add_argument("state")
    ap.add_argument("band")
    args = ap.parse_args(argv)
    con = sql.connect()
    try:
        r = lookup(con, args.industry, args.state, args.band)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print(describe(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
