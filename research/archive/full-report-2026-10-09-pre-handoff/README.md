# Frozen snapshot: full report before the handoff cleanup (2026-10-09)

This folder is an exact copy of the work as committed in `7ce4a3e` ("Research: Hawaii Intelligence branding, sales page, reviewer fixes"), saved so nothing is lost while the report is prepared for the Hawaii Intelligence site.

| File | What it is |
|---|---|
| `hawaii-buyer-origins.html` | The full report as built at that commit: all seven chapters, the Why boxes and the original Broker playbook. |
| `hawaii-buyer-origins.src.html` | Its template (the build injects `page_data.json`). |
| `page_data.json` | The report's data payload at that commit. |
| `hawaii-broker-brief.html` | The three-page broker brief. |
| `hawaii-go-to-market.html` | INTERNAL go-to-market plan (pricing, outreach). Not for the public site. |
| `hawaii-intelligence-offer.html` | INTERNAL draft sales page (pricing). Not for the public site. |
| `why_result.json`, `why_curated.json` | The Why-box research, skeptic checks and visible text at that commit. |

This is an archive, not the source of truth. Later commits on this branch hold the corrected report and the handoff (see `research/buyer-origins/HANDOFF.md`). Several figures here were corrected afterwards by the final accuracy audit. Do not port anything from this folder without checking it against the current report.
