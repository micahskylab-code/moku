# Hawaiʻi report: handoff for the Hawaii Intelligence site

**Prepared:** 2026-10-09.
**Branch:** `claude/hawaii-home-buyer-analysis-prhdoc` (PR #1). Nothing has been merged, deployed or published to the site.

**Purpose:** let Codex port the full Hawaiʻi report onto Hawaii Intelligence. This covers its 2006–2026 history, buyer-origin evidence, micro-markets and market-influence context, using only figures this branch has verified.

**Before you start:**
- The public report is evidence-only: it has no pricing, sales pitches, outreach or owner-level data.
- Monetization ideas are kept internally in [`INTERNAL_monetization_appendix.md`](INTERNAL_monetization_appendix.md).

---

## 1. Files to port (exact paths)

| What | Path |
|---|---|
| **Built report** (self-contained HTML; source of truth for the text) | `research/hawaii-buyer-origins.html` |
| Report template (text + layout; `__DATA__` is replaced by `page_data.json`) | `research/buyer-origins/hawaii-buyer-origins.src.html` |
| Chart and table data used by the report | `research/buyer-origins/page_data.json` |
| Micro-markets chapter (generated) and its builder | `research/buyer-origins/micro/micro_chapter.html`, `micro/build_micro.py` |
| Why boxes: checked research, visible text, rendered HTML | `research/buyer-origins/why/why_result.json`, `why/why_curated.json`, `why/why_boxes.json` (built by `why/build_why.py`) |
| Assembler (inserts chapter + Why boxes, injects data) | `research/buyer-origins/micro/assemble.py` |
| **Source registry** (one row per source) | `research/buyer-origins/handoff/source_registry.json` (+ `.csv`) |
| **Metric catalog** (one canonical dataset per metric) | `research/buyer-origins/handoff/metric_catalog.json` (+ `.csv`) |
| Data-layer map (raw → normalized → calculated → narrative) | `research/buyer-origins/handoff/data_layers.json` |
| Raw-download manifests (URL, UTC time, bytes, sha256) | `research/buyer-origins/handoff/raw_manifests/*.MANIFEST.txt` |
| Verification records | `research/buyer-origins/handoff/verification_*.json` |
| Frozen pre-cleanup snapshot (archive only; not source of truth) | `research/archive/full-report-2026-10-09-pre-handoff/` (commit `5423687`, copied from `7ce4a3e`) |

**Not for port:** `research/hawaii-broker-brief.html`. It is broker-targeting oriented and duplicates report figures.

**About the scripts:** the Python builders in `research/buyer-origins/` hard-code this session's scratch paths. Port the JSON outputs and the template; do not run the scripts as-is.

---

## 2. Report outline

Each section is tagged by content class:
- **E** = historical transaction or buyer-origin evidence.
- **I** = market-influence indicator: context, correlation rather than causation.
- **F** = forecast or model.
- **N** = narrative explanation (Why box).

1. **The story** (`#story`)
   - `#glance` Twenty years at a glance: E + I.
   - `#eras` What happened, and why, 2006–2026 in nine periods: E, with "Our read" interpretation (I/N).
2. **Who buys, who leaves** (`#flows`)
   - `#corridors` Where departing households go (IRS 2004–05 → 2022–23): I. Households, not sellers.
   - `#owners` Off-island ownership on Oʻahu (owner-roll aggregates): E (stock, not purchases).
   - `#decade` Buyer origin 2008 → June 2026: E.
   - `#islands` Island by island: E.
   - `#buyers` Buyer states, countries and visitor metros: E + I. Why boxes for California, the western states, Japan/Korea and Canada: N.
3. **Micro-markets** (`#micro`), all E unless noted:
   - `#mm-glance` (+ investors/VA Why box).
   - `#mm-tiers`, `#mm-type`, `#mm-luxury` (luxury counts are company-reported).
   - `#mm-districts` (26 Title Guaranty districts) and `#mm-loans` (HMDA by county subdivision).
   - ZIP and district sections `#mm-oahu` (+ hotspots Why box), `#mm-maui`, `#mm-kauai`, `#mm-hawaii`, each with 2026 board-district scorecards.
4. **Locals and housing** (`#locals`)
   - `#squeeze` Payment share of income: I (calculated), + affordability Why box.
   - `#empty` Seasonal and occasional-use homes: I.
   - `#oahu` Oʻahu repeat-sales index by district: E.
5. **The market now** (`#market`)
   - `#now`, `#thermo` (months of supply), `#pulse` (monthly record): E + I.
   - `#next` 2027 scenarios: F.
6. **Feeder and landing markets** (`#feeders`)
   - `#targets` The evidence by market: buyer counts (E), visitor metros (I), IRS landing markets (I) and seasonal timing (I).
   - `#firezips` Legal context: Lahaina and Kula unsolicited-offer ban.
7. **Sources and checks** (`#checks`): `#method`, `#sources`.

**Changes made in this PR for the public focus:**
- Removed all "For brokers" advice and "Do now" lines. They are replaced by neutral "What it means" or "Reading the data" notes, or removed where they were prospecting.
- Removed the targeting tiers, ad and campaign rules, and owner-prospecting text.
- Kept every data table from the former playbook (now Chapter 6).
- Removed any inference that a missing homeowner exemption proves a second home or a listing lead.
- Describe buyers by the country of their address, not nationality.

---

## 3. Data architecture and the canonical-dataset rule

The four layers are listed in `data_layers.json`:
1. **Raw, immutable.** Downloads are never edited. The repo keeps their manifests (URL, time, sha256). Large and owner-level raw files are not committed.
2. **Normalized observations.** `sources/*.json`, `gap/tg_districts.json`, `micro/rdc_zip.json`, `micro/district_*.json`, `micro/luxury.json`.
3. **Calculated comparisons.** `page_data.json`, `moku_index.json`, `irs_instate.json`, `vis_cbsa.json`, `owners/oahu_individual.json`, `micro/*_join.json`, `micro/hmda_tiers.json`, `gap/hmda_tract.json`.
4. **Report narrative.** The template, the micro chapter and the Why boxes.

**One canonical dataset per metric:** `metric_catalog.json` names it for each metric. Its `do_not_mix` field lists the competing figures that must not be shown side by side without a label. The main cases:
- **2024 sales counts.** DBEDT (18,007) and Title Guaranty (16,709 restated, 16,716 originally) disagree. Compare 2024 by share, or use Title Guaranty for both years.
- **Maui months of supply.** The report's method (Realtor.com ÷ DBEDT) gives 9.6 for August 2026. The Maui board gives 11.0 (houses 7.8, condos 12.1). Label the method; prefer board data for Maui.
- **Maui buyer origin.** Title Guaranty's deed-address mainland share is 25% (2025). The county's non-homeowner conveyance share is about 57% (FY2025–26) and includes local landlords. UHERO counts 55–59% of condo buyers as out-of-state. These measure different things; show them with definitions.
- **Recorded vs MLS counts.** Developer closings move recorded counts: The Park Ward Village closed 527 units in Q2 2026. Quote them separately.

---

## 4. Live vs publisher-timed data (product requirement)

**(a) Live, high-frequency.** Use only the feeds Hawaii Intelligence already runs:
- **Inventory** (active listings, days on market, price cuts): the site's existing inventory feed.
- **Mortgage rate** (30-year fixed): the site's existing rate feed.

For both:
- Show each feed's last successful refresh time and a status if a refresh failed.
- The report's own values are dated snapshots, not live data: Realtor.com September 2026 inventory, and PMMS 7.40% on Oct 8, 2026, verified against Freddie Mac's file on 2026-10-09.
- Do not add a competing live dataset from this report.
- In `page_data.json`, the October 2026 point of the monthly `mortgage` series (7.28%) covers only the first week. Recompute it when the month closes, or drop it in favor of the live feed.

**(b) Publisher-timed.** Never label these live:

| Cadence | Metrics |
|---|---|
| Monthly | DBEDT MLS sales and medians; board district scorecards; DBEDT visitor arrivals; building permits |
| Derived, mixed cadence | Months of supply (live inventory ÷ monthly DBEDT sales): show both as-of dates |
| Quarterly | Title Guaranty buyer origin (cumulative editions); DBEDT QSER county origin; district buyer origin |
| Semiannual | Luxury counts (company-reported) |
| Annual / historical | DBEDT Data Book; IRS migration; ACS and PUMS; HMDA; UHERO Factbook; annual visitor metros; owner rolls; Maui conveyance FY series; Oʻahu repeat-sales index; 2027 model |

**Recommended surfaces:**
- **Weekly brief:**
  - The two live metrics, with their refresh times.
  - Any publisher release that landed that week (use `next_expected` in the registry).
  - Re-checking the Lahaina and Kula proclamation status about every 60 days.

  Do not invent weekly values for monthly or slower data. Show "latest available: <period>".
- **Monthly page:** sales and medians, board scorecards, visitor arrivals and months of supply, each with its as-of month.
- **Quarterly:** buyer origin by island and district, and buyer states and countries.
- **Historical context:** everything else, plus the Chapter 1 story.

---

## 5. Evidence vs influence (correlation, not causation)

- **Historical evidence** (what happened):
  - Recorded sales and prices by buyer origin.
  - District origin.
  - MLS sales and medians.
  - The repeat-sales index.
  - Mortgaged-purchase occupancy (financed buyers only).
  - Off-island ownership stock.
- **Market-influence indicators:** rates, payment share of income, ACS income and rents, permits, visitor arrivals and metro over-index, IRS household migration, tourism and policy (Bill 9, Bill 88, the proclamation).

  The report presents these as context. Where it explains a pattern (Why boxes, "Our read"), the driver strength is labelled. Associations are marked "an association, not proof", for example vacation-rental share vs investor loans, and visitor rates vs buyer rates.

  Keep these labels when porting. Do not convert "consistent with" or "fits" into causal claims.

---

## 6. Sources: summary (full detail in `source_registry.json`)

| Source id | Publisher | Cadence | Newest in report | Next expected |
|---|---|---|---|---|
| TG_BUYER | Title Guaranty of Hawaiʻi | Quarterly, cumulative | Jan–Jun 2026 (posted 2026-08-31) | Q3 2026 edition: not posted as of 2026-10-08 |
| DBEDT_DATABOOK | Hawaiʻi DBEDT | Annual | 2025 | Data Book 2026: not announced |
| DBEDT_QSER | Hawaiʻi DBEDT | Quarterly | Q2 2026 | Next QSER: not announced |
| DBEDT_MEI | Hawaiʻi DBEDT | Monthly | Aug 2026 | Sep 2026 data, about early to mid November |
| DBEDT_VISITOR_ANNUAL | Hawaiʻi DBEDT | Annual | 2024 | 2025 published 2026-09-28; not integrated |
| IRS_SOI_MIGRATION | IRS SOI | Annual | 2022–23 | 2023–24 on 2026-11-20 (tentative) |
| FFIEC_HMDA | FFIEC/CFPB | Annual | 2025 | 2026 data, about spring–summer 2027 |
| CENSUS_ACS | Census | Annual | 2024 | ACS 2025: not integrated |
| FREDDIE_PMMS | Freddie Mac | Weekly | 2026-10-08 (7.40%) | Thursdays |
| CENSUS_BPS | Census via FRED | Monthly | 2026 year to date | Monthly |
| REALTOR_COM | Realtor.com | Monthly | Sep 2026 | Oct 2026 data, early November |
| UHERO_FACTBOOK | UHERO | Annual | 2026 edition (2025 sales) | About May 2027 |
| HNL_OWNER_ROLL | City & County of Honolulu | Continuous | 2026-10-05 | Ongoing |
| MAUI_PARCEL_FABRIC | County of Maui | Continuous | 2026-10-04 | Ongoing |
| MAUI_RPT_SALES | County of Maui (via Hawaiʻi Appleseed) | Fiscal year | FY2026 | FY2027 |
| HNL_SALES_EXTRACT | City & County of Honolulu (repo `oahu-sales.json`) | Ad hoc | Sales to 2025-09-26 | Re-export needed |
| BOARD_MLS_STATS | HBR/HiCentral, HIS, KBR (via Fidelity), RAM | Monthly | Jan–Aug 2026 (Maui Jan–Sep) | September/October editions |
| HL_LUXURY | Hawaiʻi Life (company-reported) | Semiannual | Jan–Jun 2026 | 2026 year-end |
| GOV_WILDFIRE_PROCLAMATION | Office of the Governor | About every 60 days | 32nd, 2026-08-24 | Check about 2026-10-23 |

---

## 7. Verification results (key outcomes)

- **Primary sources** (`verification_primary_sources.json`): Title Guaranty, Data Book, Oʻahu and Maui owner rolls, HMDA, UHERO, market and visitors were each independently re-derived, with 0 numeric errors in the data files. Three summary-wording issues were found:
  - The IRS release date: corrected in the report to 2026-11-20.
  - A Kīhei "most out-of-state condo buyers" ranking: not used in the report.
  - Title Guaranty's neighbor-island "average" vs "median" days on market: not used; the report's days on market come from Realtor.com.
- **Micro-market data** (`verification_micro_data.json`):
  - Realtor.com ZIP data: 20/20 checks passed. Quality flags are now shown for either month.
  - Board district stats: newer August editions found and used. Every scorecard row re-parsed with 0 mismatches.
  - Oʻahu tiers: non-residential deals excluded from home-buyer figures.
- **Who-buys data** (`verification_who_buys.json`):
  - Oʻahu join calibrated to Title Guaranty within about 1–4 points.
  - HMDA trend now compares only the combined second-home + investment share.
  - Small cells are flagged and not quoted as rates.
- **District and tract data** (`verification_gap_data.json`): Title Guaranty districts sum exactly to island totals. HMDA tract-to-subdivision mapping recomputed with 0 mismatches.
- **Final accuracy audit** (`verification_final_audit.json`): 73 confirmed findings.
  - 59 applied to the report. Examples:
    - The "Lahaina" row is now labelled "West Maui (Lahaina subdivision)", with Lahaina-town counts stated.
    - Kula and ʻEwa rows are relabelled.
    - "Won't live there" becomes "Not a main home".
    - Rounding is now half-up.
    - Rates corrected to Oct 8 7.40%.
    - Canadian closings given as 11–18 per half-year.
    - Kahuku now ranks second, not first.
    - Resort-area luxury shares are now stated by region.
    - The South Maui 179 → 113 restated count is used.
    - Periods added to IRS and Zillow figures.
  - The other 14 findings concerned the internal go-to-market page, which is archived and not ported.
- **Checks run on the final build (2026-10-09):**
  - Headless render at 1280px and 400px: no horizontal overflow, no script errors.
  - Text scans of the built page: 0 hits for pricing or sales terms, outreach or prospecting phrases, "exemption proves second home" wording, process leaks (tool notes, file paths), nationality-style buyer labels, or the superseded figures.
  - Freddie Mac PMMS history re-downloaded: Oct 1 7.28%, Oct 8 7.40%, 2026 low 5.98% (Feb 26).

---

## 8. Known gaps: unverified future work (not in the public report)

None of the following claims appear in the report:
- **Kauaʻi and Hawaiʻi County ownership:** owner mailing addresses are not public. An occupancy (homeowner-exemption) build was started but stopped before verification. Not used.
- **Oʻahu and Maui luxury ownership** ($3M+ assessed): stopped. Not used.
- **2025 visitor-metro data** (published 2026-09-28): not integrated. The report uses 2024.
- **IRS 2023–24 migration** (due 2026-11-20). Also a re-download of the pre-2013 IRS files from irs.gov to replace mirror copies that were not independently checksummed.
- **October market reports:** HBR September 2026, RAM October, KBR and HIS monthly, Title Guaranty September Residential Sales Reports, and the Title Guaranty Q3 2026 buyer statistics.
- **ACS 2025 1-year.**
- **Oʻahu recorded sales after 2025-09-26, and Maui sales after June 2025.** Needs a re-export of `oahu-sales.json` and a Maui sales extract.
- **$3M+ counts rebuilt from public records,** replacing company-reported luxury figures.
- **HMDA 2026:** not released.

**Included and verified, but owner-roll or HMDA based.** Micah can hold these if he prefers:
- `#owners`.
- The Maui district table in `#mm-maui`.
- The "Owned from off-island" ZIP column.
- The glance-table rows "Homes owned from outside Hawaiʻi" and "Mortgaged buyers not buying a main home".
- The HMDA column in `#mm-tiers`.
- `#mm-loans`.
- The investors/VA Why box.

All of these are aggregates, with small cells flagged.

---

## 9. Source and reuse caveats

- **Title Guaranty:**
  - Its publications read "all rights reserved; no reproduction without prior written consent". Micah reports permission received. Keep it on file, confirm it covers web republication of tables, and credit Title Guaranty on every page that uses its data.
  - Its buyer-origin method (deed address) is not published.
- **REALTOR board statistics** (via Fidelity National Title) and **Realtor.com research data:** confirm republication terms before porting tables. Attribute them.
- **UHERO Factbook:** cite. Confirm reuse terms for its tables.
- **Hawaiʻi Life luxury reports:** a competitor's company-reported marketing. Label them "Reported" and do not republish its charts.
- **Owner rolls:**
  - Owner mailing addresses are public records (OIP Op. Ltr. 11-01), but portal terms for bulk or commercial reuse were not verified.
  - Publish aggregates only. No owner names, addresses, parcel IDs or sale-level lists. Sale-level "top sales" lists were removed from the repo copies in this PR.
- **Fair housing:**
  - "Local, mainland, foreign" describes where buyers live, never nationality or ancestry. The text uses "buyers from Japan" and similar wording.
  - Do not add targeting or steering language.
- **Lahaina and Kula** (96761, 96767, 96790): keep the legal-context note, and re-check the proclamation around 2026-10-23.
