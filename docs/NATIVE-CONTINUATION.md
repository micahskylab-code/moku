# Native continuation: isolation and transfer plan (19 Oct 2026)

This file records a separate cloud session picking up the owner's local native (Blender) and browser "207" work. The session works only on the branch `nahiku-native-continuation`.

## Isolation
- **Branch:** `nahiku-native-continuation`, branched from `nahiku-walkthrough` at `3d0a5d9`. This session never pushes to `nahiku-walkthrough`.
- **Hands off:** the aerial-photo (NAIP) session owns `scripts/geo_community.py`, `geodata/community/`, `geodata/SOURCES.txt`, `src/community.js`, `docs/community-view.md` and `docs/HANDOFF.md`. This session does not edit them.
- **Native editing:** the owner's local coordinator owns `Na Hiku.blend` and `native_controls.py`. Agree on ownership before any patch to them is applied.

## What the cloud host can reach
- **Mac paths:** none. `/Users/micah/...` does not exist here, and the Mac's `127.0.0.1:8767` cannot be reached.
- **Repository:** contains the older three.js viewer and the Blender still pipeline. None of the native files (`native_controls.py`, `launch_native.py`, `runtime/`, `proof/`) are in the repository, and neither are the 207-series browser modules (`scene.js`, `*207.js`) or the `current65` GLB export.
- **Tools:** Blender is not installed, and installing it is out of scope. Native renders and launcher acceptance can only be checked on the Mac.

## Smallest useful transfer (owner screens each file first)
To fix the open native items (twilight visibility, rain exposure, zero-power night lights in the export, water roughness, launcher/UI acceptance) and review the visuals, the minimum is:

1. **Code (text, small):** `native_controls.py`, `launch_native.py`, and `Open Na Hiku.command`. Check for absolute home paths, tokens and hostnames before sharing.
2. **Reports (JSON, small):** `build-report.json`, `proof/environment-checks.json`, `proof/material-corrections.json`, `proof/water-corrections.json`, `current65-validation.json`, `current65-export-metadata.json`, and `EXPORT-HANDOFF.txt`.
3. **Browser modules (code only):** `environment207.js`, `sky207.js`, `water207.js`, `walk207.js`, `interior207.js`, `neighborhood207.js`, `native-export207.js` and `scene.js` from `work-house207/candidate/`. Leave out `candidate/data/` and `acquired/` until each source and licence is checked.
4. **Proof images (optional, needs clearance):** eye-height frames from `proof/` (interior, primary bedroom, neighbourhood, dusk, rain, the two night skies, covered lanai). They show the house design, whose plan provenance is not cleared, so share them only if the owner clears them.

## Never transferred
The `.blend` (about 1.5 GB) and the full GLB (about 522 MiB) stay local, as do whole directories, `runtime/`, `candidate/data/` and `acquired/` until screened, credentials, hidden configs, browser profiles and logs. Only `modern_arm_chair_01` and `jacaranda_tree` have a verified licence so far (CC0-1.0, Poly Haven).

## Standing rules
The scene is an illustrative concept, not surveyed or as-built, and the weather presets are not forecasts. Photoreal quality is not yet accepted: acceptance needs real eye-height exterior, pool, street and furnished-interior frames, not formulas.
