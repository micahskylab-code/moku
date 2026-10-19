# Handoff: community view, round 8 done (aerial photo)

This branch carries the whole Nā Hiku walkthrough project, so a new session can pick it up. Start with `docs/project-overview.md`, then `docs/community-view.md`.

## Where it stands (19 Oct 2026, round 8)
- **Live copy:** the owner's private artifact https://claude.ai/artifact/NEjN2ZRGqzKS4LPEHoFTE2, version 5 ("Community round 8: NAIP 2022 photo"). It opens on the Kukuiʻula community fly-in, with the model view under ⋯ → Model. In a new conversation, read the artifact first (Artifact `read`), list its files (`list`, `scope: files`), then publish to the same `url`.
- **Build the hosted copy:** `python3 scripts/build_artifact.py <out-dir>` (174 files, about 46 MB). Publish `<out-dir>/index.html` with `root` set to `<out-dir>` and every other file listed in `files`. `data/LICENSE-d3-celestial` needs `contentType: text/plain`.
- **Round 8: the land is now the USDA NAIP aerial photo** (flown 11 Feb 2022, 0.6 m, 4-band). Licence checked on the InPort record (item 69406): "Use Constraints: None. The USDA-FSA Aerial Photography Field office asks to be credited in derived products." It is credited "Aerial photo: USDA NAIP 2022" in the short credits line (desktop "Aerial photo: …", phones "Photo: …"), the card note, "How this was made", `community.json` attribution, `geodata/SOURCES.txt` and `docs/community-view.md`. The Nā Hiku row stays drawn and labelled modeled. The NAIP hosts and `www.fisheries.noaa.gov` were reachable from this environment (HTTP 200); the earlier "still blocked" note no longer applies.
  - `scripts/geo_naip.py` fetches the three quarter quads over the box and mosaics them onto the bake's 0.488 m grid in EPSG:32604 (`<cache>/naip_comm.npy`; tiles in `<cache>/../naip`).
  - `scripts/geo_community.py` (`Inputs._photo`) matches the photo to Sentinel-2 (per-band curve, a 250 m gain field, saturation), keeps the photo's detail on the satellite's colour under thin cloud (about 3 ha), eases the baked occlusion on photo pixels and writes the photo's weight in `w_*.png` G on land. `COMM_NO_PHOTO=1` bakes the old drawn ground; `COMM_OUT` bakes elsewhere; `--only none` rewrites only `h.bin` and `community.json`.
  - `src/community.js` eases the live relief (to 30%), the traced shadows (to 25%), the crowns' relief, the grain and the mottle on photo pixels, grades the photo warmer and brighter, and warms pale sand.
  - The cache was rebuilt into `../geo-test/cache` this session; the drawn tiles from it differ slightly from round 7's (newer Sentinel-2 scenes).
- **Community view blind score (round 8, `docs/critique-community-r8.json`):** overall 6, land 5, sea 7, UI 7, phone 6 (medians; means 6.0 / 5.0 / 6.67 / 7.33 / 6.0). Round 7 was 6 / 5 / 6 / 7 / 6 (means 5.67 / 5.0 / 6.33 / 6.67 / 6.0). The before/after judge preferred round 8 in 10 of 12 views (one tie; round 7 won the desktop home close-up, where the photo goes soft). The target is still 7–8.
  - Fixed after the critique: the landscape-phone notice ran under "The home" (now on one line, clear of the toolbar); the photo's bunkers read grey-green (pale photo ground is now warmed, only a little).
  - **Still weak (verified):** the photo is soft up close (0.5 m magnified; no detail layer over it yet); the context buildings are untextured boxes; the 3D trees are blobs; the bunkers are flat pale decals; the modelled access road ends square in grass; sprite clouds and a hard sea horizon; the open ocean is flat; the harbour basin is a milky wash with a white rim; place pills are under 44 px to tap; the phone credits are small.
  - Ideas: a close-range detail layer by land cover over the photo (the class is already in `w_*.png` B), the NIR band to sharpen the classes, roof colours from the photo for the context buildings, and bunkers from the photo's own bright sand.
  - Note on the evidence: the round 7 phone and landscape "before" shots were taken after the credits text had changed, so their credits line already names the photo (the tiles are round 7's).
- **Renders (round 6):** the front and back stills scored 8/8/7/8 (`docs/critique-preview6-*.json`).

## Checks (software WebGL is slow: about 5 min per 1600×900 shot)
- `node scripts/community_qa.mjs <out>`: poses 0–6 and the checks (notice, credits, trees on the tiles, exit and re-entry). The phone run uses `W=390 H=844 Q=low SHOTS=0,1,3`, and landscape uses `W=844 H=390 Q=low SHOTS=0,1`.
- `node scripts/inspect_qa.mjs <out>`: the model and walk regression. It must pass 24/24, and no request may leave localhost.
- **Hosted test:** serve the built copy wrapped in a bare skeleton with no query string. Open the community view, then ⋯ → Model.

## Rules the owner set (keep them)
- **Labelling:** label everything an independent concept visualization. Make no buyer-ready, as-built or construction-accuracy claims, no view claims, and draw no lot lines or parcel boundaries.
- **Developer material:** do not copy the developer's map art, branding or sales status. Keep the brochure images out of the repo. Never request or store parcel owner names.
- **Purchases and accounts:** no paid services or purchases, no new accounts or credentials, no deployment or outreach. Updating the owner's private artifact link is approved.
- **Git:** push only when asked. Commit as `-c user.email=micahskylab@gmail.com -c user.name=micahskylab`, ending the message with the session's attribution lines. Keep model names out of code, docs and commits.
- **Processes:** do not kill processes you did not start.
