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

## Micro-markets

The report's micro-markets chapter (all Hawaiʻi and each island, by price tier, houses versus condos, luxury, ZIP and Maui district) is built by `micro/build_micro.py` from these files:

- `micro/rdc_zip.json`: Realtor.com ZIP core metrics.
- `micro/oahu_tiers.json`: Oʻahu sales by price tier, ZIP and TMK zone, from `oahu-sales.json`.
- `micro/neighbor_sales.json`: Maui assessor sales, FY24–25.
- `micro/luxury.json` and `micro/luxury_buyers.json`: $3M+ and $10M+ counts. Company-reported figures are labelled.
- `micro/district_stats.json`: REALTOR board district statistics.
- `micro/oahu_join.json` and `micro/maui_join.json`: buyer origin from each recent sale joined to the current owner roll.
- `micro/hmda_tiers.json`: HMDA occupancy by price tier, 2025 vs 2019.
- `micro/tg_prices.json`: Title Guaranty price bands.

`owners/oahu_ind.py` builds `owners/oahu_individual.json` from the Honolulu owner roll (data as of 2026-10-05). It counts owner mailing addresses by state, metro and situs ZIP. Any mailing address shared by 10 or more parcels is treated as institutional and kept separate. Only aggregates are published: no names, street addresses or parcel IDs.

- `micro/district_ytd.py` builds `micro/district_ytd.json`, the district scorecards for 2026 to date against the same months of 2025:
  - Oʻahu, Hawaiʻi Island and Kauaʻi, January–August, from the Fidelity National Title August 2026 summaries. These republish HiCentral MLS, Hawaii Information Service and Kauai Board of REALTORS data, and their district rows sum to the island totals.
  - Maui County, January–September, from the REALTORS Association of Maui.
- The Realtor.com ZIP rows that Realtor.com marks as lower quality are flagged † in the report.

- `gap/tg_districts.json` holds Title Guaranty buyer origin for all 26 of its districts: 2024, 2025, Jan–Jun 2025 and Jan–Jun 2026. Each district page's foot-row columns were matched to their district by fill colour, and district rows sum exactly to island totals.
- `gap/hmda_tract.json` holds HMDA 2025 and 2019 purchase loans by census tract, county subdivision, place and ZCTA. Tracts are mapped to county subdivisions through TIGER faces, weighted by block housing units.
- `gap/owner_fields.json` records the search for owner mailing fields for Hawaiʻi County and Kauaʻi. Nothing public was found. It lists what to request from each county.

`hawaii-buyer-origins.src.html` is the page template. The build replaces `__DATA__` with `page_data.json` and inserts the micro-markets chapter.

## Go-to-market plan

`../hawaii-go-to-market.html` is the plan for selling the report to brokerages. It covers:

- the offer, price anchors and revenue scenarios;
- why Hawaii Life is the first target, and who to approach;
- a 90-day pilot;
- RESPA-safe sponsorship and compliance guardrails;
- the checklist to clear before selling.

Its opening figures compare 2024 and 2025 on Title Guaranty's own counts for both years. DBEDT's 2024 count runs about 8% higher.

## Why boxes

Each "Why" box comes from a two-step check, stored in `why/why_result.json`:
1. A researcher gathered evidence for the pattern and proposed drivers.
2. A skeptic re-checked every fact and tried to refute each driver.

Refuted drivers are dropped, and weakened ones are marked down a level. The visible summaries in `why/why_curated.json` are written only from the skeptic's checked answer. `why/build_why.py` renders the boxes, which include the full answer, each driver as checked, factors raised but not yet tested, and every source.
