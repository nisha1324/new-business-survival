# New-business survival in Australia: which industries and regions new businesses last in

**Status: work in progress (Part 1 of 5 done: source, snapshot and profile).**

About half of the businesses that start trading in Australia in a given year are no longer trading three
Junes later. That rate is
not the same everywhere. It depends on the industry, the state and, above all, on whether the business employs
anyone. This project uses the Australian Bureau of Statistics' official business counts to answer three
questions for people who back, plan for or advise new businesses:

- **A lender or investor:** how likely is a new business in this industry, state and size band to still be
  trading after three years, and how sure can we be of that figure?
- **A council or state agency:** where is the number of businesses growing or shrinking, and in which industries?
- **A small-business adviser:** which industries have the weakest early survival, once you compare businesses of
  the same size?

## Data

Australian Bureau of Statistics, [*Counts of Australian Businesses, including Entries and Exits*](https://www.abs.gov.au/statistics/economy/business-indicators/counts-australian-businesses-including-entries-and-exits)
(CABEE, cat. no. 8165.0). Licence: [CC BY 4.0](https://www.abs.gov.au/website-privacy-copyright-and-disclaimer),
© Commonwealth of Australia. No key or sign-up is needed.

- Data cube 1 from the four releases covering June 2019 – June 2023 through June 2022 – June 2026 (the latest,
  released 18 August 2026): national and state counts, entries, exits and survival. Four releases give four
  cohorts to compare.
- Data cubes 4, 5 and 10 from the June 2021 – June 2025 release: survival by state × ANZSIC subdivision ×
  employment size, and business counts for 557 local government areas. The 2026 versions are due on
  18 December 2026.

`scripts/download_data.py` fetches the 7 workbooks (about 4 MB) from abs.gov.au, with each file's SHA-256 pinned.
`scripts/build_snapshot.py` turns them into four tidy, gzipped CSVs in `data/` (about 1.2 MB, committed), so
every analysis runs without downloading anything.

## Part 1: what the numbers mean (`results/SOURCE_PROFILE.md`)

- **2,814,778 businesses** were actively trading at June 2026, up 24.1% from 2,268,998 at June 2019. Entries
  outnumbered exits in every one of the 7 years from 2019-20 to 2025-26.
- Of the **406,365 businesses that entered in 2022-23**, 199,742 (49.2%) were still trading at June 2026. The
  same figure was 50.8% for the 2019-20 entrants and 48.0% for the 2021-22 entrants, the lowest of the four
  cohorts.
- 73.2% of 2022-23 entrants employed no one. 44.6% of them were still trading at June 2026, against 61.5% of
  employing entrants.

![Survival by cohort](results/charts/02_cohort_survival.png)

Before any ranking, the profile checks the data and sets eight rules. The main ones:

1. **An exit isn't a failure.** It can be a sale, a restructure or a business that stopped remitting GST, so the
   project says "still trading" or "exited", never "failed".
2. **Not every entry is a start-up.** 28.5% to 31.7% of entries each year are re-activations or businesses
   coming into scope, and a business that opens and closes between two 30 Junes is never counted.
3. **Size mix drives industry rankings.** The non-employing share of entries ranges from 40% to 89% by industry.
   Accommodation and Food Services has the lowest share, so its overall rate is 10th lowest of 19, but its
   employing entrants' rate is 5th lowest. Industries are compared within a size band.
4. **Tiny cells mislead.** The detailed cubes are perturbed for confidentiality. 1,575 of 20,864 published rates
   don't match their own counts, all with a base of 15 businesses or fewer, so no rate is reported on a base of
   20 or fewer.
5. **Releases revise groups, not totals.** National totals never changed between releases (0 of 40 overlapping
   cells); industry and state groups moved by a median of 0.10%. A time series takes each year from the latest
   release.
6. **Survival below state level isn't published.** LGAs have counts only, so regional survival is a state
   comparison and LGAs are compared on growth in business numbers.

![Industry size mix](results/charts/04_industry_size_mix.png)

The data reconciles where it should: data cube 1's 1,288 published rates all match survived ÷ base to rounding,
its groups add exactly to its totals, the detailed cubes' state totals match data cube 1 exactly, and the LGA
cube's national totals match data cube 1's June counts for 2023, 2024 and 2025.

## Plan

| Part | What | Status |
|---|---|---|
| 1 | Source, download with pinned hashes, tidy snapshot, profile and rules | done |
| 2 | Industries: survival within size bands, a common-size-mix comparison, subdivisions above the floor, cohort trends | next |
| 3 | Regions: state survival across four cohorts, state × industry, LGA growth in business numbers | |
| 4 | A DuckDB SQL layer and a benchmark table for lenders and advisers (industry × state × size, with reliability flags) | |
| 5 | CI, recommendations, limitations and write-up | |

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/profile_source.py      # Part 1 report and charts from the committed snapshot
python -m pytest                      # tests

# optional: rebuild the snapshot from the ABS files
python scripts/download_data.py       # 7 workbooks into data/raw/ (hash-checked)
python scripts/build_snapshot.py      # data/*.csv.gz and data/SNAPSHOT.json (byte-identical rebuild)
```

## Layout

```
cabee/load.py               parse the ABS workbooks into tidy tables; read the snapshot
cabee/profile.py            Part 1 checks and measures
scripts/download_data.py    fetch the workbooks, check SHA-256
scripts/build_snapshot.py   write data/*.csv.gz and data/SNAPSHOT.json
scripts/profile_source.py   write results/SOURCE_PROFILE.md, CSVs and charts 01-05
data/                       the tidy snapshot (survival, flows, subdivision_survival, lga_counts)
results/                    reports, CSVs and charts
tests/                      parser tests on hand-made sheets, snapshot invariants, report checks
```

## Tests

55 tests: the parsers on hand-made sheets (including a perturbed row whose sizes don't add up), the snapshot's
invariants (entry cohorts equal that year's entries, start + entries − exits = end for every industry, every
subdivision maps to an ANZSIC division, LGA totals equal the national count), the profile measures on hand-made
frames, the real figures the report relies on, and a byte-for-byte regeneration of the Part 1 report, CSVs and
charts. If the raw workbooks are present, a test also rebuilds the snapshot from them and compares. 16 planted
bugs were tried on a scratch copy: 14 were caught at first, and the 2 that survived (a mislabelled state total,
a looser mismatch threshold) now have tests. README tests check that every Part 1 figure here appears in the
generated report and stays with its subject; 14 planted errors in this README (changed figures, swapped subjects)
were tried, 12 were caught at first, and the 2 survivors now have exact checks.

## Credit

Data: Australian Bureau of Statistics, CC BY 4.0, © Commonwealth of Australia.
