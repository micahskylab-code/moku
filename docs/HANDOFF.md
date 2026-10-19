# Handoff: community view, next step aerial photos

This branch carries the whole Nā Hiku walkthrough project, so a new session can pick it up. Start with `docs/project-overview.md`, then `docs/community-view.md`.

## Where it stands (19 Oct 2026)
- **Live copy:** the owner's private artifact https://claude.ai/artifact/NEjN2ZRGqzKS4LPEHoFTE2, version 4 ("Community round 7"). It opens on the Kukuiʻula community fly-in, with the model view under ⋯ → Model. In a new conversation, read the artifact first (Artifact `read`), then publish to the same `url`.
- **Build the hosted copy:** `python3 scripts/build_artifact.py <out-dir>`, which writes about 174 files and 44 MB. Publish `<out-dir>/index.html` with `root` set to `<out-dir>` and every other file listed in `files`. `data/LICENSE-d3-celestial` needs `contentType: text/plain`.
- **Community view blind score (round 7):** overall 6, land 5, sea 6, UI 7, phone 6, out of 10. The target is 7–8. `docs/critique-community-r7.json` has the confirmed flaws.
  - Biggest remaining gaps: the land reads as a game map (uniform green, brown blotches, soft ground up close); the context buildings are boxes; the trees are uniform; the sea horizon is a hard line; the hero frame has about 30% sky with simple clouds.
- **Renders (round 6):** the front and back stills scored 8/8/7/8 (`docs/critique-preview6-*.json`).

## Next task: real aerial photos for the community tiles
The owner allowed `coastalimagery.blob.core.windows.net` and `imagery.geoplatform.gov` for this environment. The change only applies to new sessions.

**Still blocked (19 Oct 2026, later session):** the egress proxy refused CONNECT (403, policy denial) to `coastalimagery.blob.core.windows.net`, `imagery.geoplatform.gov` and `www.fisheries.noaa.gov` (the InPort licence page), as well as `planetarycomputer.microsoft.com` and `naipeuwest.blob.core.windows.net`. The AWS S3 hosts the bake uses (`prd-tnm`, `noaa-nos-coastal-lidar-pds`, `sentinel-cogs`, `dataforgood-fb-data`) answered 200. Nothing was downloaded, baked or changed. Before the next try, check the environment's Network access setting (Allowed domains) holds both NAIP hosts, plus `www.fisheries.noaa.gov` for the licence record, and test with `curl -sS -o /dev/null -w '%{http_code}' https://coastalimagery.blob.core.windows.net/digitalcoast/HI_NAIP_2021_9668/index.html` before rebuilding the cache.

**Source:** USDA NAIP 2021–2023 Hawaiʻi, 4-band (RGB + NIR), about 0.6 m. Kauaʻi was mostly flown in 2022. NOAA Digital Coast distributes it:
- record: https://www.fisheries.noaa.gov/inport/item/69406
- files: https://coastalimagery.blob.core.windows.net/digitalcoast/HI_NAIP_2021_9668/index.html (tile index `tileindex_HI_NAIP_2021.zip`, plus a wget example)
- USDA also serves it as an image service: https://imagery.geoplatform.gov/iipp/rest/services/NAIP/NAIP2021_Hawaii/ImageServer

**Before using it:**
1. Read the dataset's use constraints and confirm it is public domain or otherwise open for this use. NAIP normally is. If it is not open, stop and tell the owner.
2. Do not use these, whose licences restrict commercial use: the USGS 2010 Kauaʻi high-resolution orthoimagery (DigitalGlobe licence), USDA's "hawaii_vivid_2021_50cm" (Maxar), and the state's WorldView-2 Kauaʻi layer.

**Integration notes (not built yet):**
- **Download:** fetch only the tiles that intersect the community box: UTM 4N, E 447 500–453 500, N 2 418 000–2 423 000 (`geodata/community/community.json`). Mosaic and reproject them to EPSG:32604 at the tiles' 0.488 m.
- **Baker:** in `scripts/geo_community.py`, the photo replaces the drawn land colour (Sentinel-2 plus vector fills). Keep everything else: lidar terrain and normals, reef depth colour, sea, vectors for roads and golf masks, land-cover class, canopy heights.
  - The photo already holds the flight-time sun and shadows. Ease the baked hillshade, AO and cast shadows, and the viewer's live sun shading on photo pixels, or the shadows double up.
  - Colour-match the photo to Sentinel-2 at the box edges and between flight lines, and mask cloud and glint.
  - The NIR band can sharpen the vegetation masks.
- **Disclosure:** the photos predate the current grading on the Nā Hiku strip; the modelled row stays labelled as modelled. Change "Map of open data, not a photo" to name the photo and its year, e.g. "Aerial photo: USDA NAIP 2022". Add it to `community.json` attribution, `geodata/SOURCES.txt` and `docs/community-view.md`.
- **Cache:** the bake inputs are not in git. Rebuild them into `../geo-test/cache` (or set `GEO_CACHE`) with the scripts listed under "Rebuild" in `docs/community-view.md` and in `geodata/SOURCES.txt`. These cover the USGS 1 m DEM, the USACE topobathy, the Sentinel-2 mosaic, the Overture layers, the Meta canopy tile and the 2 m DEM. They come from AWS S3 hosts that this environment already reached.
- **Bake time:** a full bake takes about an hour on 4 CPUs, run as two halves (`--only` with even and odd `c+r`).

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
