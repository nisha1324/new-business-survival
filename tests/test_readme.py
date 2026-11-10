"""The README's Part 1 figures must come from the generated report."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
REPORT = (ROOT / "results" / "SOURCE_PROFILE.md").read_text()
NUM = re.compile(r"(?<![\w.,])\d[\d,]*(?:\.\d+)?(?:%|st|nd|rd|th)?(?![\w])")


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end != -1 else None]


def figures(text: str) -> set[str]:
    text = re.sub(r"(?m)^\s*\d+\.\s", "", text)          # list numbering
    text = re.sub(r"\(results/[^)]*\)|`[^`]*`", "", text)  # links and code
    return {m.group(0).rstrip(".,") for m in NUM.finditer(text)}


def in_report(fig: str) -> bool:
    tail = r"(?![\w%]|[.,]\d)" if not fig.endswith("%") else ""
    return re.search(r"(?<![\w.,])" + re.escape(fig) + tail, REPORT) is not None


def test_every_part1_figure_is_in_the_report():
    part1 = section(README, "## Part 1")
    missing = sorted(f for f in figures(part1) if not in_report(f))
    assert not missing, f"README Part 1 figures not in SOURCE_PROFILE.md: {missing}"


def _sentence_with(text: str, *phrases: str) -> bool:
    text = re.sub(r"\s+", " ", text)  # README lines are wrapped
    sentences = re.split(r"(?<=[.|])\s+|\s(?=- )|\s(?=\d\. )", text)
    return any(all(p in s for p in phrases) for s in sentences)


PAIRS = [
    ("406,365", "2022-23"),
    ("199,742", "49.2%"),
    ("50.8%", "2019-20"),
    ("48.0%", "2021-22"),
    ("73.2%", "employed no one"),
    ("44.6%", "61.5%"),
    ("2,814,778", "June 2026"),
    ("Accommodation and Food Services", "10th lowest of 19"),
    ("1,575 of 20,864", "15 businesses or fewer"),
]


def test_figures_stay_with_their_subject():
    for pair in PAIRS:
        assert _sentence_with(section(README, "## Part 1"), *pair), f"README: {pair}"
        assert _sentence_with(REPORT, *pair), f"report: {pair}"


def test_test_count_in_readme_is_current():
    import subprocess, sys
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    n = int(re.search(r"(\d+) tests? collected", out).group(1))
    assert f"{n} tests:" in section(README, "## Tests"), n


# phrases that must read the same in the README and the report (word order matters)
PHRASES = [
    "44.6% of them were still trading at June 2026, against 61.5% of employing entrants",
    "199,742 (49.2%) were still trading at June 2026",
    "up 24.1% from 2,268,998 at June 2019",
    "its overall rate is 10th lowest of 19, but its employing entrants' rate is 5th lowest",
    "all with a base of 15 businesses or fewer",
]


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_phrases_match_the_report():
    for p in PHRASES:
        assert p in _flat(README), f"README: {p}"
        assert p in _flat(REPORT), f"report: {p}"


def test_overlapping_cells_figure():
    m = re.search(r"\(0 of (\d+) overlapping cells\)", _flat(README))
    assert m and f"{m.group(1)} overlapping cells, 0 revised" in REPORT


# ------------------------------------------------------------------ Part 2
REPORT2 = (ROOT / "results" / "INDUSTRY_SURVIVAL.md").read_text()


def in_report2(fig: str) -> bool:
    tail = r"(?![\w%]|[.,]\d)" if not fig.endswith("%") else ""
    return re.search(r"(?<![\w.,])" + re.escape(fig) + tail, REPORT2) is not None


def test_every_part2_figure_is_in_the_report():
    part2 = section(README, "## Part 2")
    missing = sorted(f for f in figures(part2) if not in_report2(f))
    assert not missing, f"README Part 2 figures not in INDUSTRY_SURVIVAL.md: {missing}"


PAIRS2 = [
    ("37.4%", "55,118", "Transport, Postal and Warehousing"),
    ("16 of 19", "fell"),
    ("Retail Trade", "52.3% → 46.2%", "−6.1 points"),
    ("−1.8 points", "inside the size bands", "+0.2 points", "size mix"),
    ("Accommodation and Food Services", "10th", "4th lowest", "48.4% → 41.9%"),
    ("35.2%", "non-employing", "54.7%", "employing"),
    ("34.6%", "Public Order, Safety and Regulatory Services", "65.2%", "Agriculture"),
    ("45% to 52%", "first"),
    ("4.4 to 22.0 points", "non-employing", "1-4 employee"),
    ("7.7", "cohorts"),
]


def test_part2_figures_stay_with_their_subject():
    for pair in PAIRS2:
        assert _sentence_with(section(README, "## Part 2"), *pair), f"README: {pair}"
        assert _sentence_with(REPORT2, *pair), f"report: {pair}"


PHRASES2 = [
    "Accommodation and Food Services falls from 10th to 4th lowest (48.4% → 41.9%)",
    "37.4% of its 55,118 2022-23 entrants were still trading three Junes on, against 49.2% for all industries",
    "Retail Trade fell the most (52.3% → 46.2%, −6.1 points)",
    "−1.8 points inside the size bands and +0.2 points from the size mix",
    "Administrative and Support Services; Public Administration and Safety; Transport, Postal and Warehousing; and "
    "Wholesale Trade are among the 5 industries with the lowest survival in all",
    "survival at the national size mix runs from 34.6% (Public Order, Safety and Regulatory Services) to 65.2% "
    "(Agriculture)",
    "45% to 52% of the 2022-23 entrants that had stopped trading by the third June had already stopped by the first",
    "About half of the three-year loss happens by the first June",
]


def test_part2_phrases_match_the_report():
    for p in PHRASES2:
        assert p in _flat(README), f"README: {p}"
        assert p in _flat(REPORT2), f"report: {p}"


def test_part2_weights_and_method_claims():
    flat = _flat(README)
    for band, w in (("non-employing", "73.5%"), ("1-4", "24.1%"), ("5+", "2.4%")):
        assert f"{band.capitalize() if band == 'non-employing' else band} {w}" in REPORT2, band
    assert "non-employing 73.5%, 1-4 employees 24.1%, 5 or more 2.4%" in flat
    assert "to within 0.05 points" in REPORT2 and "to within 0.05 points" in flat
    assert "the ranking is identical" in REPORT2 and "identical ranking" in flat


# ------------------------------------------------------------------ Part 3
REPORT3 = (ROOT / "results" / "REGIONS.md").read_text()


def in_report3(fig: str) -> bool:
    tail = r"(?![\w%]|[.,]\d)" if not fig.endswith("%") else ""
    return re.search(r"(?<![\w.,])" + re.escape(fig) + tail, REPORT3) is not None


def test_every_part3_figure_is_in_the_report():
    part3 = section(README, "## Part 3")
    missing = sorted(f for f in figures(part3) if not in_report3(f))
    assert not missing, f"README Part 3 figures not in REGIONS.md: {missing}"


PAIRS3 = [
    ("Tasmania", "54.7%", "49.2%"),
    ("New South Wales", "lowest", "48.0%"),
    ("New South Wales", "49.0%", "47.6%", "1.4 points fewer"),
    ("Tasmania", "6.0 points"),
    ("South Australia", "+4.2 points", "Western Australia", "+3.7 points"),
    ("Victoria", "3.1 points below", "2.0"),
    ("79%", "employed no one", "highest share of any state"),
    ("53%", "Transport Support Services"),
    ("32.1%",),
    ("139,482",),
    ("non-employing", "149,180", "employing", "9,698"),
    ("91.8%", "employed no one", "39.5%", "Transport, Postal and Warehousing"),
    ("Kwinana", "22.2%"),
    ("199 of the 303", "lost employing businesses", "31"),
    ("Northern Territory", "46.9%", "49.2%"),
    ("0.18 points",),
    ("65% mix",),
    ("−1.4 points", "+6.0 points"),
]


def test_part3_figures_stay_with_their_subject():
    for pair in PAIRS3:
        assert _sentence_with(section(README, "## Part 3"), *pair), f"README: {pair}"
        assert _sentence_with(REPORT3, *pair), f"report: {pair}"


PHRASES3 = [
    "Tasmania keeps its new businesses longest, in every cohort",
    "54.7% of its 2022-23 entrants were still trading three Junes on, against 49.2% nationally; New South Wales was "
    "lowest at 48.0%",
    "New South Wales would be expected to keep 49.0% of its 2021-22 entrants; it kept 47.6%, 1.4 points fewer, the "
    "weakest of the 8 states on that basis",
    "Tasmania kept 6.0 points more than its mix predicts, then South Australia (+4.2 points) and Western Australia "
    "(+3.7 points)",
    "Its entrants were 3.1 points below the national rate; 2.0 points of that is its industry × size mix",
    "non-employing businesses grew by 149,180 and employing businesses fell by 9,698",
    "91.8% of the net increase employed no one and 39.5% was in Transport, Postal and Warehousing",
    "199 of the 303 LGAs lost employing businesses even though only 31 lost businesses overall",
]


def test_part3_phrases_match_the_report():
    for p in PHRASES3:
        assert p in _flat(README), f"README: {p}"
        assert p in _flat(REPORT3), f"report: {p}"


def test_part3_method_claims():
    flat = _flat(README)
    assert "WA 8," in REPORT3 and "(8 of them in WA" in flat
    assert "Victoria had 32.1% of the 8 states' entrants overall" in _flat(REPORT3)
    assert "Victoria's 2021-22 dip is 65% mix" in _flat(REPORT3) and "Victoria's 2021-22 dip is 65% mix" in flat
    assert "on raw rates New South Wales is 0.4 points below" in _flat(REPORT3).replace("On raw", "on raw")
    assert "New South Wales is 0.4 points below the national rate on raw figures" in flat
    assert "at most 0.18 points" in REPORT3 and "at most 0.18 points" in flat
    assert "after its mix it is the weakest state" in _flat(REPORT3)
    assert "the weakest state once its mix is allowed for" in flat
    assert "the 303 LGAs with 1,000 or more businesses" in flat and "303 LGAs with 1,000 or more businesses" in REPORT3


# ------------------------------------------------------- Part 4
REPORT4 = (ROOT / "results" / "BENCHMARK.md").read_text()


def in_report4(fig: str) -> bool:
    tail = r"(?![\w%]|[.,]\d)" if not fig.endswith("%") else ""
    return re.search(r"(?<![\w.,])" + re.escape(fig) + tail, REPORT4) is not None


def _part4_text() -> str:
    # the lookup's printed output is checked separately, against the script itself
    return re.sub(r"```.*?```", "", section(README, "## Part 4"), flags=re.S)


def test_every_part4_figure_is_in_the_report():
    missing = sorted(f for f in figures(_part4_text()) if not in_report4(f))
    assert not missing, f"README Part 4 figures not in BENCHMARK.md: {missing}"


PAIRS4 = [
    ("57 columns", "10", "6,052", "0 mismatches"),
    ("32,508", "1 or 2"),
    ("NT, 5+", "48.1%", "75.2%", "−27.1 points"),
    ("10%", "0.86 points"),
    ("4 small industries", "more than a point low"),
    ("no industry more than 2 places", "bottom five are unchanged"),
    ("97.9%", "441,808"),
    ("15 of 152",),
    ("Where both", "192 cells"),
    ("3.19", "2.33"),
    ("Tas", "5.42 → 3.05"),
    ("all 85", "+16.6 points"),
    ("50.2% (ACT)", "58.3% (WA)"),
    ("30.3%", "70.9%"),
    ("−1.4 points", "+6.0 points"),
]


def test_part4_figures_stay_with_their_subject():
    for pair in PAIRS4:
        readme = tuple(p.replace("Tas", "Tasmania") if p == "Tas" else p for p in pair)
        assert _sentence_with(_part4_text(), *readme), f"README: {readme}"
        assert _sentence_with(REPORT4, *pair), f"report: {pair}"


PHRASES4 = [
    "48.1% from the cells against 75.2% exact (−27.1 points)",
    "the sum is within 0.86 points of the exact rate",
    "moves no industry more than 2 places, and the bottom five are unchanged",
    "cuts the average gap from 3.19 to 2.33 points",
    "entrants with 1-4 employees out-survived non-employing ones in all 85",
    "it runs from 50.2% (ACT) to 58.3% (WA)",
    "run from 30.3% to 70.9%",
]


def test_part4_phrases_match_the_report():
    flat = _flat(README).replace("Overall the adjustment cuts", "cuts").replace(
        "Entrants with 1-4", "entrants with 1-4")
    rep = _flat(REPORT4).replace("Entrants with 1-4", "entrants with 1-4")
    for p in PHRASES4:
        assert p in rep, f"report: {p}"
        assert p in flat or p.replace("cuts the average gap from", "it cuts the average gap to the state's own rate "
                                      "from") in flat, f"README: {p}"


def test_part4_rules_and_method_claims():
    flat = _flat(README)
    from scripts.benchmark_report import MAX_SMALL_SHARE, RELIABLE_BASE, SMALL_BASE
    assert (SMALL_BASE, RELIABLE_BASE, MAX_SMALL_SHARE) == (20, 100, 0.10)
    assert "needs 100+ entrants and at most 10% of them in small cells" in flat
    assert "cells of 20 or fewer" in flat
    assert "doesn't help in Victoria or the Northern Territory" in flat
    assert "doesn't help in Vic or NT" in _flat(REPORT4)
    assert "It helps most where the state effect is largest: Tas (5.42 → 3.05)" in _flat(REPORT4)
    assert "**Sums of small perturbed cells read low.**" in flat and "Summed cells read low" in REPORT4
    assert "read high" not in _part4_text()
    assert "Seven SQL files" in flat and len(list((ROOT / "sql").glob("[0-9][0-9]_*.sql"))) == 7


def test_part4_lookup_example_is_the_real_output():
    import subprocess, sys
    block = re.search(r"```\n\$ (python scripts/benchmark_lookup\.py [^\n]+)\n(.*?)```", README, re.S)
    assert block, "lookup example missing"
    args = block.group(1).split()[2:]
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "benchmark_lookup.py"), *args], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert out == block.group(2)
