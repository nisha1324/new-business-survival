"""The committed outputs must not depend on which CPU makes them.

NumPy's default sort is unstable and picks a SIMD code path at run time (AVX2, AVX-512, ...),
so rows with equal sort keys could come out in a different order on another machine. The first
CI run on GitHub caught exactly that: tied LGAs in lga_growth.csv, tied industries in Part 2 and
the label of a tied revision in the source profile came out in a different order there. Every
sort is now stable, so ties keep the (deterministic) input order.
"""
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = sorted((ROOT / "cabee").glob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
REPORTS = ["profile_source.py", "industry_survival.py", "regions_report.py", "benchmark_report.py"]


def _calls(text, name):
    """The argument text of every ``.name(...)`` call, matching nested brackets."""
    out = []
    for m in re.finditer(rf"\.{name}\(", text):
        j, depth = m.end(), 1
        while depth:
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            j += 1
        out.append(text[m.end():j - 1])
    return out


def test_every_sort_is_stable():
    unstable = [(p.name, args) for p in CODE for name in ("sort_values", "sort_index")
                for args in _calls(p.read_text(), name) if 'kind="stable"' not in args]
    assert not unstable, unstable


def test_call_finder_on_a_hand_made_line():
    text = 'a.sort_values(["x", f(y)], ascending=False).head(); b.sort_index(kind="stable")'
    assert _calls(text, "sort_values") == ['["x", f(y)], ascending=False']
    assert _calls(text, "sort_index") == ['kind="stable"']


def _hashes():
    files = sorted(p for p in (ROOT / "results").rglob("*") if p.is_file())
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def test_reports_are_identical_on_numpys_baseline_code_path():
    # Switch off every optional SIMD extension this CPU has, so NumPy runs its baseline code,
    # and check that all four reports still write exactly the committed bytes.
    from numpy._core import _multiarray_umath as m
    extra = [f for f in m.__cpu_dispatch__ if m.__cpu_features__.get(f)]
    env = {**os.environ, "NPY_DISABLE_CPU_FEATURES": " ".join(extra)}
    before = _hashes()
    for script in REPORTS:
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True, cwd=ROOT,
                       env=env, capture_output=True)
    after = _hashes()
    changed = sorted(k for k in before if before[k] != after.get(k))
    assert not changed, (extra, changed)
    assert after.keys() == before.keys()
