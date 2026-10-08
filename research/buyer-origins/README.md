# Hawaiʻi buyer-origin report — data and build scripts

`../hawaii-buyer-origins.html` is generated from `page_data.json`, which these scripts build:

- `irs_decade.py` — IRS SOI county-to-county inflow (2014–15 … 2022–23) into the four Hawaiʻi counties: different-state totals, top origin counties, metro roll-ups. Input CSVs: IRS SOI `countyinflowYYYY.csv`; their SHA-256 are in `irs_sha256.txt` and match an independent record of direct irs.gov downloads.
- `build.py` — merges DBEDT Monthly Economic Indicators (via Hawaiʻi Appleseed `macro_monthly.json`), Realtor.com county inventory history, Title Guaranty county buyer-origin 2015–2025 (via Hawaiʻi Appleseed, published with Title Guaranty's permission) and Maui RPT sales categories.
- `prep.py` — trims the merged dataset to what the page charts.

Known source issue: the HTA island visitor series repeats Maui 2021 as 2022; the report uses DBEDT's arrivals series instead.
- `locals.py` — ACS 2024 PUMS (Hawaiʻi housing + person files, via Hawaiʻi Appleseed; weights sum to Census's 1,446,146 population) for movers, vacancy and rent burden, plus IRS county **outflows** 2014–15 … 2022–23 (SHA-256 in `irs_outflow_sha256.txt`).
- Oʻahu district figures use Moku's own `oahu-sales.json` (repeat-sale pairs by TMK zone); the zone→district names follow the Oʻahu TMK zone map.
- ACS county series (income, value, rent, tenure, vacancy, 2015–2024) come from Hawaiʻi Appleseed's `acs_panel.json`.
- `irs_20yr.py` — IRS county inflow/outflow 2004–05 … 2022–23 (old Hawaiʻi workbooks for 2004–05 … 2010–11; national CSVs after). Totals use IRS row codes (state 97 / county 003 = different state). 2013–14 onward match an independent irs.gov SHA-256 record; earlier files are mirror copies not independently checksummed.
- `irs_states.py` — IRS state-to-state flows 2011–12 … 2022–23 from the Hawaiʻi state workbooks.
- `moku_index.py` — Oʻahu weighted repeat-sales index (2000–2025, 2015 = 100) from `oahu-sales.json`, island-wide and by TMK zone; year-over-year changes correlate 0.94 with Zillow ZHVI Honolulu.
- `rate_model.py` — log-linear fit of annual recorded sales (DBEDT buyer-origin series, as published) on the Freddie Mac annual average rate, 2015–2025, with a 2008–2025 robustness check.
- `irs_instate.py` — IRS same-state county flows (Oʻahu → each neighbor island), 2019–20 … 2022–23.
- `vis_cbsa.py` — DBEDT 2024 Annual Visitor Research, Table 55 (domestic air arrivals by island and metro): each metro's over-index by island, Utah's three metros combined. Workbook SHA-256 `86bf9ca5711671f3a4333bba15a0da06d70df361269c68d8951cf94acad0a35c`.
- Statewide buyer origin 2008–2014 comes from State Data Book Tables 21.37–21.38 (read from search extracts); every year closes to the published totals and average prices, and the 2008–2015 sums equal DBEDT's May 2016 home-sales report.

## Broker brief

`../hawaii-broker-brief.html` is a one-page summary for brokers, built by `brief/build_brief.py` from `brief/brief.tpl.html`, `brief/brief_data.json` (IRS metros by island, seasonal factors), `irs_instate.json`, `vis_cbsa.json` and `page_data.json`. Every figure was re-checked against the raw files by an independent audit before release.
