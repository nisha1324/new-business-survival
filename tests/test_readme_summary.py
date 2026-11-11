"""The TL;DR, Part 5, recommendations and limitations of the README.

These sections may only repeat figures that the Data section or Parts 1-4 already state (and
those are tied to the generated reports by tests/test_readme.py), and each repeated figure must
sit next to the same subject it has there.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

NUMBER = re.compile(r"[−+]?\d+(?:,\d{3})*(?:\.\d+)?[%×]?")


def flat(text):
    return re.sub(r"\s+", " ", text.replace("**", ""))


def section(heading, end="\n## "):
    assert README.count(heading) == 1, heading
    return README.split(heading, 1)[1].split(end, 1)[0]


def tokens(text):
    # Whole figures only, so "1.4%" can't hide inside "31.4%". A leading "+" is dropped
    # because the parts write both "+6.0 points" and "6.0 points more".
    return {t.lstrip("+") for t in NUMBER.findall(text)}


SOURCE = section("\n## Data\n", "\n## Part 5:")  # the Data section and Parts 1-4
SUMMARIES = {
    "TL;DR": section("\n## TL;DR\n"),
    "Part 5": section("\n## Part 5:"),
    "Recommendations": section("\n## Recommendations\n"),
    "Limitations": section("\n## Limitations\n"),
}


@pytest.mark.parametrize("name", SUMMARIES)
def test_summary_figures_repeat_figures_from_parts_1_to_4(name):
    # Part 4 gives the worst small-cell gap as "−27.1 points"; the recommendation says
    # "up to 27.1 points low", which is the same figure without the sign.
    worded_differently = {"27.1"}
    missing = tokens(SUMMARIES[name]) - tokens(SOURCE) - worded_differently
    assert not missing, (name, sorted(missing))
    assert "(−27.1 points)" in flat(SOURCE)


# (summary section, phrase there, phrase in the Data section or Parts 1-4 with the same figure and subject)
SAME_SUBJECT = [
    ("TL;DR", "406,365 businesses that entered in 2022-23, 49.2% were still trading at June 2026",
     "406,365 businesses that entered in 2022-23, 199,742 (49.2%) were still trading at June 2026"),
    ("TL;DR", "against 50.8% for the 2019-20 entrants", "50.8% for the 2019-20 entrants"),
    ("TL;DR", "Survival fell in 16 of 19 industries", "Survival fell in 16 of 19 industries"),
    ("TL;DR", "−1.8 points of the fall happened inside the size bands", "−1.8 points inside the size bands"),
    ("TL;DR", "44.6% of non-employing entrants were still trading at June 2026, against 61.5% of employing entrants",
     "44.6% of them were still trading at June 2026, against 61.5% of employing entrants"),
    ("TL;DR", "Entrants with 1-4 employees out-survived non-employing ones in all 85 state × industry pairs where "
              "both are reliable (median gap +16.6 points)",
     "Entrants with 1-4 employees out-survived non-employing ones in all 85 state × industry pairs where both are "
     "reliable (median gap +16.6 points)"),
    ("TL;DR", "national rates for an industry and size band run from 30.3% to 70.9%",
     "national rates for an industry and size band run from 30.3% to 70.9%"),
    ("TL;DR", "Transport, Postal and Warehousing is lowest in the latest cohort (37.4%)",
     "Transport, Postal and Warehousing is lowest in the latest: 37.4%"),
    ("TL;DR", "Accommodation and Food Services falls from 10th to 4th lowest (48.4% → 41.9%)",
     "Accommodation and Food Services falls from 10th to 4th lowest (48.4% → 41.9%)"),
    ("TL;DR", "Tasmania kept 6.0 points more of its 2021-22 entrants than its mix predicts",
     "Tasmania kept 6.0 points more than its mix predicts"),
    ("TL;DR", "New South Wales kept 1.4 points fewer, the weakest of the 8 states on that basis",
     "1.4 points fewer, the weakest of the 8 states on that basis"),
    ("TL;DR", "Victoria's weak 2021-22 cohort is mostly mix", "Victoria's weak 2021-22 cohort is mostly mix"),
    ("TL;DR", "Business numbers grew by 139,482 across LGAs", "Business numbers grew by 139,482 across LGAs"),
    ("TL;DR", "non-employing businesses grew by 149,180 and employing businesses fell by 9,698",
     "non-employing businesses grew by 149,180 and employing businesses fell by 9,698"),
    ("TL;DR", "199 of the 303 LGAs lost employing businesses even though only 31 lost businesses overall",
     "199 of the 303 LGAs lost employing businesses even though only 31 lost businesses overall"),
    ("TL;DR", "covers 97.9% of the 441,808 entrants", "covers 97.9% of the 441,808 entrants"),
    ("Recommendations", "national rates for an industry and size band run from 30.3% to 70.9%",
     "national rates for an industry and size band run from 30.3% to 70.9%"),
    ("Recommendations", "the state adjustment then moves them by −1.4 points to +6.0 points",
     "the state adjustment moves them by −1.4 points to +6.0 points"),
    ("Recommendations", "For entrants with 5+ employees there is a benchmark in only 15 of 152 cells",
     "For businesses with 5+ employees there is a benchmark in only 15 of 152 cells"),
    ("Recommendations", "45% to 52% of the 2022-23 entrants that had stopped trading by the third June had already "
                        "stopped by the first",
     "45% to 52% of the 2022-23 entrants that had stopped trading by the third June had already stopped by the first"),
    ("Recommendations", "(44.6% against 61.5% for employing entrants)",
     "44.6% of them were still trading at June 2026, against 61.5% of employing entrants"),
    ("Recommendations", "Transport, Postal and Warehousing (37.4% of all its 2022-23 entrants)",
     "Transport, Postal and Warehousing is lowest in the latest: 37.4% of its 55,118 2022-23 entrants"),
    ("Recommendations", "non-employing entrants in Food and Beverage Services (35.2%)",
     "Food and Beverage Services subdivision (cafés, restaurants, takeaways, pubs and clubs), 35.2% of "
     "non-employing entrants"),
    ("Recommendations", "199 of the 303 LGAs lost employing businesses even though only 31 lost businesses overall",
     "199 of the 303 LGAs lost employing businesses even though only 31 lost businesses overall"),
    ("Recommendations", "in the 20 fastest-growing LGAs 91.8% of the net increase employed no one",
     "In the 20 fastest-growing LGAs (8 of them in WA, led by Kwinana at 22.2%), 91.8% of the net increase "
     "employed no one"),
    ("Recommendations", "New South Wales is the weakest state (1.4 points below what its mix predicts)",
     "1.4 points fewer, the weakest of the 8 states on that basis"),
    ("Recommendations", "Victoria's 2021-22 dip is 65% mix", "Victoria's 2021-22 dip is 65% mix"),
    ("Recommendations", "Tasmania's +6.0 points", "Tasmania kept 6.0 points more than its mix predicts"),
    ("Recommendations", "Its survival fell from 52.3% to 46.2% (−6.1 points) between the 2019-20 and 2022-23 cohorts, "
                        "the largest fall of any industry",
     "Survival fell in 16 of 19 industries from the 2019-20 to the 2022-23 cohort. Retail Trade fell the most "
     "(52.3% → 46.2%, −6.1 points)"),
    ("Recommendations", "The 2026 detail is due on 18 December 2026", "The 2026 versions are due on 18 December 2026"),
    ("Recommendations", "Summing perturbed cells read up to 27.1 points low (NT, 5+)",
     "worst for NT, 5+: 48.1% from the cells against 75.2% exact (−27.1 points)"),
    ("Recommendations", "where at most 10% of entrants are in cells of 20 or fewer, the sum is within 0.86 points",
     "Where at most 10% of entrants are in cells of 20 or fewer, the sum is within 0.86 points"),
    ("Limitations", "28.5% to 31.7% of entries each year are re-activations or businesses coming into scope",
     "28.5% to 31.7% of entries each year are re-activations or businesses coming into scope"),
    ("Limitations", "a business that opens and closes between two 30 Junes is never counted",
     "a business that opens and closes between two 30 Junes is never counted"),
    ("Limitations", "an industry's rate moved by up to 7.7 points across the four cohorts",
     "an industry's rate moved by up to 7.7 points across the four cohorts"),
    ("Limitations", "Even reliable rates are sums of perturbed cells, read up to 0.86 points low",
     "Where at most 10% of entrants are in cells of 20 or fewer, the sum is within 0.86 points"),
    ("Limitations", "Its fit over the 192 reliable cells is in-sample", "Where both rates are reliable (192 cells)"),
    ("Limitations", "Industry and state figures moved by a median of 0.10% between releases",
     "industry and state groups moved by a median of 0.10%"),
]


@pytest.mark.parametrize("name, summary, part", SAME_SUBJECT)
def test_summary_figures_keep_their_subject(name, summary, part):
    assert flat(summary) in flat(SUMMARIES[name])
    assert flat(part) in flat(SOURCE)


def test_every_summary_figure_is_tied_to_a_subject():
    # every figure in the TL;DR, recommendations and limitations appears in at least one
    # SAME_SUBJECT phrase, so a new figure can't be added without being tied to its subject
    tied = {name: set() for name in SUMMARIES}
    for name, summary, _ in SAME_SUBJECT:
        tied[name] |= tokens(summary)
    # cohort labels, size bands, list numbering and the 20/10% rule are checked elsewhere
    labels = {"2019", "2020", "2021", "2022", "20", "21", "22", "23", "1", "4", "5", "6", "7", "8", "10%",
              "2025", "2026", "2", "3"}
    for name in ("TL;DR", "Recommendations", "Limitations"):
        loose = tokens(SUMMARIES[name]) - tied[name] - labels
        assert not loose, (name, sorted(loose))


def test_recommendations_are_ranked_and_owned():
    recs = re.findall(r"(?m)^(\d+)\. (.*?)(?=^\d+\. |\Z)", SUMMARIES["Recommendations"], flags=re.S)
    assert [int(n) for n, _ in recs] == list(range(1, len(recs) + 1)) and len(recs) == 7
    assert all("*Owner:" in body for _, body in recs)
    lims = re.findall(r"(?m)^(\d+)\. ", SUMMARIES["Limitations"])
    assert [int(n) for n in lims] == list(range(1, 9))


def test_rules_stated_in_the_summary_match_the_code():
    from cabee import profile, sql
    c = sql.connect()
    floor, base, share = c.execute("SELECT small_base(), reliable_base(), max_small_share()").fetchone()
    assert floor == profile.SMALL_BASE == 20 and base == 100 and share == pytest.approx(0.10)
    assert "at most 10% of entrants are in cells of 20 or fewer" in flat(SUMMARIES["Recommendations"])
    assert "100+ entrants and at most 10% of them in small cells" in flat(SOURCE)


def test_ci_reruns_every_report_in_how_to_run():
    how_to_run = section("\n## How to run\n")
    reports = re.findall(r"python (scripts/\w+\.py)\s+# Part \d", how_to_run)
    assert len(reports) == 4
    for script in reports:
        assert f"python {script}\n" in CI
    assert 'test -z "$(git status --porcelain)"' in CI and "pytest -q" in CI
    assert "pip install -r requirements-lock.txt" in CI
    assert "actions/workflows/ci.yml/badge.svg" in README


def test_lock_file_pins_every_requirement():
    def names(path, sep):
        out = set()
        for line in (ROOT / path).read_text().splitlines():
            line = line.split("#")[0].strip()
            if line:
                out.add(re.split(sep, line)[0].strip().lower().replace("_", "-"))
        return out
    lock = (ROOT / "requirements-lock.txt").read_text()
    assert all("==" in l for l in lock.splitlines() if l and not l.startswith("#"))
    assert names("requirements.txt", r"[<>=!~]") <= names("requirements-lock.txt", "==")
