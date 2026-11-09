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
