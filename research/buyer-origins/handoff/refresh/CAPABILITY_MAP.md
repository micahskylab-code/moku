# Capability map: how current each source can be

Built from this branch's existing research: the source registry, raw manifests and verification files. No new sources were tested for this map, except DBEDT's monthly workbooks for the refresh package (2026-10-09).

**Checking a source often is not the same as the data being current.** A six-hourly check of a monthly source still returns monthly data. None of the sources below is a real-time transaction feed.

## 1. What updates when

| Cadence of the data | Source | Typical lag after the period | Access status |
|---|---|---|---|
| **Weekly** | Freddie Mac PMMS 30-year rate | Released Thursdays | On the site already (existing Worker, checked every 6 hours). |
| **Monthly** | Realtor.com inventory: state, county, ZIP; listings, days on market, price cuts | Early in the following month | County data on the site already. ZIP file used in the report. Maui County quality-flagged since Dec 2025. Listing data, not sales. |
| Monthly | **DBEDT county resales and medians** (MEI workbooks) | About 4–5 weeks: August 2026 was released Oct 1; September is due "on/about October 29" | **Automated by this package** (`run_refresh.py`). Verified against the report baseline, and July → August revisions tested on real files. |
| Monthly | Island board reports (HBR Oʻahu; RAM Maui; Kauaʻi Board and Hawaiʻi Island REALTORS via Hawaiʻi Information Service) | Oʻahu about the 6th; Maui about the 1st; Kauaʻi and Hawaiʻi Island about the 8th | Read by hand. HBR had not posted September on its own site as of Oct 9. Kauaʻi and Hawaiʻi Island sites refused a custom user agent but served a standard one. Republication terms not confirmed. |
| Monthly | Title Guaranty Residential Sales Reports (MLS republished) | Early the following month | Read by hand. First prints are revised in later charts. Permission scope to confirm. |
| Monthly | Census building permits (FRED) | Lag not measured in this project | Public domain. Not automated here. |
| **Quarterly** | Title Guaranty buyer statistics (buyer origin) | About 1.5–3+ months: Q2 2026 posted Aug 31; past Q3 editions late Oct to early Jan | Read by hand. Not posted for Q3 2026 as of Oct 9. |
| Quarterly | DBEDT QSER county origin tables | The 3rd-quarter 2026 report carries data through June 2026 | Public. |
| **Semiannual** | Hawaiʻi Life luxury counts | Company-reported | Read by hand. Label "Reported". |
| **Annual** | DBEDT Data Book; IRS migration (2023–24 due Nov 20, 2026); HMDA (spring–summer); ACS (September); UHERO Factbook (about May); DBEDT annual visitor report (2025 posted Sep 28, 2026); county certified rolls | Months to over a year | Public. |

**The DBEDT monthly data has two properties the site must respect** (both measured on the real files):

1. **Current-year months are first prints.** For Maui, Kauaʻi and Hawaiʻi County, DBEDT's published YTD counts already include late-reported sales, so they exceed the sum of the monthly rows. In August 2026 YTD, Hawaiʻi County houses were 1,335 published vs 1,317 summed. Last year's rows have been updated and match. The package keeps the published YTD as canonical and records the gap.
2. **DBEDT revises earlier months between editions.** Between July and August 2026 it changed 5 values, mostly the year-ago month (August 2025). It also re-posts a release under the same name: the July summary was re-posted Sep 2, and its sheets carry different dates. Each release lists these changes; nothing in the report text changes automatically.

## 2. Public records that change more often than monthly

These come from county records and show **owner changes after a deed is recorded and the assessor processes it**. They are not sales feeds, and the lag from closing to the record changing has **not been measured**.

| Source (as used in this project) | Last edit seen | What a frequent check could show | Limits |
|---|---|---|---|
| Honolulu OWNINFO and OWNDAT owner tables (HoLIS ArcGIS) | 2026-10-05 (tax-class table 2026-10-02) | Weekly changes in owner and tax-bill mailing address by parcel. Off-island-owner share moves as aggregates. | One snapshot only, so the update frequency is inferred from edit timestamps, not observed. The situs-address table was last edited 2023-10-27. Bulk-reuse terms not verified. Aggregates only, never parcel-level. |
| Maui County parcel fabric (owner and mailing) and PARCELINFO ("Updated Weekly", per its own description) | 2026-10-04 | Weekly "recent owner change" counts by district. Already used once: April roll vs October fabric. | An owner change is a proxy for a sale, not a recorded-sale count. The origin mix depends on address filtering. Aggregates only. |
| Kauaʻi tax-year layer | 2026-02-11 | Effectively an annual snapshot. | No owner mailing addresses. |
| Hawaiʻi County certified roll | 2026-04-28 | Annual (April). | No owner mailing addresses. |
| Honolulu recorded-sales extract (`oahu-sales.json`) | Last sale 2025-09-26 | Sale prices and dates by parcel. | From a one-off public-records request; not a feed. A new request would be needed (none submitted). |
| Maui conveyance-tax sales (via Hawaiʻi Appleseed) | FY2026 | Price and homeowner-rate status by sale. | Fiscal-year file processed by a third party. |
| State Bureau of Conveyances (recorded deeds; Title Guaranty's source) | Not accessed | The authoritative record of each recorded transfer. | Bulk or feed access, its cost and terms were **not checked** in this project. |

**What is realistically possible without MLS access:** weekly aggregate owner-change counts for Oʻahu and Maui, each labelled "county records, owner changes recorded through <date>". Monthly DBEDT and board aggregates for all four counties. Quarterly buyer origin from Title Guaranty.

## 3. What still needs MLS permission or access

| Need | Why public sources can't supply it | What is required |
|---|---|---|
| Individual **new listings, price changes, pending and sold events** with dates and prices | Board reports, Realtor.com research files and DBEDT are monthly aggregates. County records show only recorded transfers, after a lag, with no listing history. | MLS data access under each board's rules (IDX, VOW or a data license): HiCentral MLS (Oʻahu), Hawaiʻi Information Service (Hawaiʻi Island and Kauaʻi), and RAM's MLS (Maui). Whether Micah's membership allows this display, and on what terms, is **not verified**. |
| Faster or district-level **pending and active counts** than the boards publish | Not in public files. | The same MLS access. |
| Republishing board statistics tables on the site | Terms not confirmed. | Written permission from each board, or from Fidelity / Title Guaranty for their republications. |

## 4. Verification gaps to keep visible

- The DBEDT link pattern and workbook layout were verified for the July and August 2026 editions only. Older editions are removed from DBEDT's server: a 2025-08 file returned 404.
- The package's dependency-free reader matched openpyxl on every cell of the ten fixture workbooks. A future DBEDT format change is caught by the layout checks; it is not silently accepted.
- How often DBEDT revises months beyond the year-ago month has been observed for one edition pair only.
- County-layer update frequency is inferred from last-edit timestamps, not from repeated observation.
- Board-site access worked on Oct 9 with a standard client. It may change.
