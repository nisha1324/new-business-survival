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
