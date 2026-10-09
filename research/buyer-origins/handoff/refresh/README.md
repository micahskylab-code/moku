# DBEDT monthly housing refresh

Checks DBEDT's Monthly Economic Indicators page for a new release, then extracts single-family and condo resale counts and median prices for Hawaiʻi's four counties. It validates them, detects revisions to earlier months, and keeps the last fully validated dataset whenever anything fails.

It uses only the Python standard library (3.8+). Nothing is deployed or scheduled by this package.

## Run it

```sh
cd research/buyer-origins/handoff/refresh
python3 run_refresh.py --state-dir state            # live: reads https://dbedt.hawaii.gov/economic/mei/
python3 -m unittest discover -s tests -v            # 22 tests, offline, about 20 s
```

**Exit codes:**
- `0`: promoted, `promoted_republication`, `staged_for_review` or `no_change`.
- `2`: validation failed, incomplete, or older than last good.
- `3`: fetch or discovery failed.

The last-good dataset is untouched on 2 and 3. Each run prints a one-line JSON summary, and the full record goes to `state/runs/`.

**Options:**
- `--offline-dir DIR`: re-run from saved files.
- `--now`: fix the recorded time for reproducible output.
- `--hold-on-revision`: stage, but don't promote, a release that changes earlier months.
- `--accept-mass-revision`: allow a release that changes more than 1% of earlier values. Without it, such a release fails as a probable layout change.
- `--no-baseline`

A sensible schedule is **daily from about the 25th to the 5th, otherwise weekly**: DBEDT releases about 4–5 weeks after the month ends, and the page states the next date ("on/about October 29th"). A six-hourly check is harmless; a no-change run downloads about 1.3 MB.

## Files

| Path | What it is |
|---|---|
| `run_refresh.py` | Command-line entry point |
| `dbedt_mei.py` | Discovery, fetching, parsing, validation, revision detection, promotion |
| `xlsx_lite.py` | Dependency-free reader for cached .xlsx cell values (matches openpyxl on every cell of the fixtures) |
| `baseline/verified_2026-08.json` | The report's verified monthly series, 2006-01 to 2026-08: 3,968 cells, equal to DBEDT's August 2026 workbooks |
| `tests/` | Unit tests and fixtures: the real July and August 2026 DBEDT workbooks and the publisher page (checksums in `fixtures/SHA256SUMS.txt`) |
| `state/last_good/dbedt_mei_county_housing.json` | **Canonical dataset**: full monthly history per county, YTD, sources, checks, revisions |
| `state/last_good/latest.json` | Small view for the site: latest month, year-ago month, YTD, as-of dates |
| `state/staged/`, `state/rejected/`, `state/runs/` | Every promoted or held candidate, every failed or incomplete candidate, every run record |
| `state/raw/` | Content-addressed downloads with `MANIFEST.tsv`, git-ignored |
| `CAPABILITY_MAP.md` | What updates weekly, monthly and quarterly; what county records can show more often; where MLS access is needed |

The committed `state/` holds one live run (2026-10-09T02:48:49Z, August 2026 edition, all checks passed). Its files were byte-identical to the test fixtures.

## How it works

1. **Discover.** It reads the publisher page and takes the newest month that has all four county workbook links (`YYYY-MM-honolulu|maui|kauai|hawaii.xlsx`) on DBEDT hosts, plus the summary workbook (`mei-MMp-YYYY.xlsx`). It never guesses URLs.
2. **Fetch and checksum.** Each file is stored by SHA-256 with its URL, retrieval time, HTTP status and Last-Modified header. That header is labelled server metadata, not a publication date.
3. **Parse.** Housing columns are found by header text and units, not by position. Dates must form consecutive months. "(NA)" and blanks stay null.
4. **Validate.** Checks include:
   - Each workbook title's "through <month>" matches the file name.
   - All four counties have all four values for the release month; otherwise the run is *incomplete*.
   - The release month equals DBEDT's own summary workbook (a mismatch fails the run).
   - Year-ago month and YTD against the summary (warnings; see below).
   - Statewide counts against DBEDT's state totals.
   - No mass change against the verified baseline or the last-good dataset.
5. **Decide.** The candidate is promoted only if it passes every check and is complete; failed and incomplete candidates go to `rejected/`.
   - A repeat of the same release is `no_change`.
   - A republished file for the same month is `promoted_republication`.
   - A page listing an older month than the last good fails.

## Data rules

- **Monthly vs YTD.** Monthly values are under `counties.<c>.months`. YTD values are separate, in two forms:
  - `ytd_published`: DBEDT's own YTD counts and YTD medians. **Canonical for display.**
  - `ytd_sum_of_monthly_counts`: sums of monthly rows, only when every month is present.

  For the current year these differ on the neighbor islands. DBEDT's YTD includes late-reported sales (August 2026 Hawaiʻi County houses: 1,335 published vs 1,317 summed). The gap is recorded in `ytd_published_vs_sum_of_months`.
- **No derived medians.** No median is averaged, combined or computed; `statewide_median` is always null. DBEDT itself publishes "(NA)".
- **Statewide counts** are the sum of the four counties, only where all four are present. They match DBEDT's state totals.
- **Small samples.** A median from fewer than 20 sales is listed in that month's `small_sample` but kept. An example is Kauaʻi's August 2026 condo median of $999,999 from 15 sales; Title Guaranty shows the same figure.
- **Publication date** is set only when every county workbook title and every summary sheet state the same date (2026-10-01 for August). Otherwise it is null, and all stated dates are kept. July 2026 is such a case: Aug 28 vs Aug 27 / Sep 2.
- **Revisions.** Changed or removed earlier values are listed as old → new, flagged `affects_report_snapshot` when on or before 2026-08, and `review_required` is set.
  - The real July → August 2026 editions changed 5 values: Maui June 2026 condo median, Kauaʻi August 2025 condo count and median, Hawaiʻi County August 2025 house count and median.
  - The package updates data only. It never edits report text, Why boxes, historical explanations or forecasts.

## Wiring into the site (for the integrator)

- Read `state/last_good/latest.json`, or the full dataset, and show "DBEDT, as of <observation_month>, published <publication_date>". Label it publisher-timed monthly data, not live.
- When `revisions.review_required` is true, someone should check any report text that quotes the revised months before it is edited by hand.
- Keep DBEDT canonical for the monthly series. The board figures in the report's `#now` section are a first look until DBEDT publishes the month.
