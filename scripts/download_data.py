"""Download the ABS "Counts of Australian Businesses, including Entries and Exits"
(CABEE, cat. no. 8165.0) data cubes into data/raw/.

Source: Australian Bureau of Statistics,
https://www.abs.gov.au/statistics/economy/business-indicators/counts-australian-businesses-including-entries-and-exits
Licence: Creative Commons Attribution 4.0 International (ABS copyright page:
"All material presented on this website is provided under a Creative Commons
Attribution 4.0 International licence"). Attribution: (c) Commonwealth of
Australia, Australian Bureau of Statistics.

Seven workbooks are used:
- Data cube 1 (national and state counts, entries, exits and survival) from the
  four releases that cover June 2019 - June 2023, June 2020 - June 2024,
  June 2021 - June 2025 and June 2022 - June 2026. Each release follows one
  cohort of businesses and one cohort of new entries, so four releases give
  four cohorts to compare.
- Data cubes 4 and 5 of the June 2021 - June 2025 release: survival of all
  businesses and of new entries by state x ANZSIC subdivision x employment
  size. The June 2022 - June 2026 versions are due on 18 December 2026; in
  August ABS only publishes data cube 1, tables 1-16.
- Data cube 10 of the June 2021 - June 2025 release: business counts by local
  government area (LGA) x industry division x employment size, June 2023-2025.

Every file's SHA-256 is pinned: a file that differs (for example a revision
by ABS) stops the download instead of silently changing the analysis.
"""
from pathlib import Path
import hashlib
import sys
import time
import urllib.request

BASE = (
    "https://www.abs.gov.au/statistics/economy/business-indicators/"
    "counts-australian-businesses-including-entries-and-exits"
)

# local name -> (expected SHA-256, release slug, file name on the ABS site)
FILES = {
    "cabee_dc01_jun2019_jun2023.xlsx": (
        "60f05fc92e352c6121112bc241d518ec07975a17b226674a07b404c95214f035",
        "jul2019-jun2023",
        "8165DC01_revised.xlsx",
    ),
    "cabee_dc01_jun2020_jun2024.xlsx": (
        "ceaa3012b99382994d3a76a0c85eba941654ad85ec0719221d32aea6e89f77a9",
        "jul2020-jun2024",
        "8165DC01.xlsx",
    ),
    "cabee_dc01_jun2021_jun2025.xlsx": (
        "eb18f5df2f1df390122db9921df7e3c4a6098d29fec40529cd164537b3ab1746",
        "jul2021-jun2025",
        "8165DC01.xlsx",
    ),
    "cabee_dc01_jun2022_jun2026.xlsx": (
        "477690c133eaf70e5671643be4e255ac22bca46b7db6d236f91744b3a40d2d79",
        "jul2022-jun2026",
        "8165DC01.xlsx",
    ),
    "cabee_dc04_jun2021_jun2025.xlsx": (
        "f68901ea85e87619d68fd9dbc23e1f896b3986e73a8f7e8b24c775d7c0ec71a0",
        "jul2021-jun2025",
        "8165DC04.xlsx",
    ),
    "cabee_dc05_jun2021_jun2025.xlsx": (
        "554a74698c57614109f874292d367daa2aa6387f4b5c629ddd6edc070adc53ee",
        "jul2021-jun2025",
        "8165DC05.xlsx",
    ),
    "cabee_dc10_jun2021_jun2025.xlsx": (
        "69b73851ab31a3553092254b80509958692b613756436a1efb8629e74adb1d75",
        "jul2021-jun2025",
        "8165DC10.xlsx",
    ),
}
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
USER_AGENT = "Mozilla/5.0 (new-business-survival; +https://github.com/nisha1324)"


def url_for(name: str) -> str:
    _, slug, remote = FILES[name]
    return f"{BASE}/{slug}/{remote}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path, tries: int = 3) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
            part.replace(dest)
            return
        except OSError as e:  # URLError, timeouts, resets
            print(f"  attempt {attempt} failed: {e}")
            if attempt == tries:
                part.unlink(missing_ok=True)
                raise
            time.sleep(5 * attempt)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (expected, _, _) in FILES.items():
        dest = RAW / name
        if dest.exists() and sha256(dest) == expected:
            print(f"ok      {name} (already downloaded)")
            continue
        print(f"fetch   {name} <- {url_for(name)}")
        fetch(url_for(name), dest)
        got = sha256(dest)
        if got != expected:
            print(f"HASH MISMATCH for {name}: expected {expected}, got {got}")
            print("ABS may have revised the file. Check the release page before updating the hash.")
            return 1
        print(f"ok      {name} ({dest.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
