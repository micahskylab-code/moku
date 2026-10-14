# Na Hiku walkthrough

Walk through a floor plan in the browser, built to scale with three.js. No build step and no CDN: three.js is in `vendor/`.

```
npx http-server -c-1 .        # then open http://localhost:8080/?plan=<plan-id>
```

Desktop: WASD/arrows to walk, mouse to look, Shift to walk faster. Phone: drag left half to walk, right half to look. Click the minimap to jump.

## A plan is one JSON file — `plans/<plan-id>.json`

All units are **feet**, traced from the floor plan. Plan `x` runs left to right, plan `y` runs top to bottom (as the drawing reads).

| key | what |
|---|---|
| `rooms[]` | `polygon` (corner points), `floor` (`oak` `walnut` `stone` `tile` `travertine` `deck` `concrete` or `#hex`), `wall` colour, `outdoor` |
| `walls[]` | centreline `a` → `b`; `openings[]` with `type` (`door` `slider` `window` `cased`), `at` (feet from `a`), `width`, `height`, `sill` |
| `furniture[]` | `type` (`sofa` `chair` `rug` `table` `dining` `island` `counter` `vanity` `bed` `lounger` `cabinet` `tv` `plant` `pool`), centre `x,y`, `w`, `d`, `rot` (deg), colours |
| `viewpoints[]` | `pos`, `look`, optional `fov`/`eye`, and `photo` — the listing photo this camera should reproduce |

`plans/test-plan.json` is a placeholder that exercises the engine. It is **not** Na Hiku.

## Builder / critic loop

1. Trace the plan into `plans/<plan-id>.json`; place one viewpoint per listing photo, matching the photographer's position and lens (`fov`).
2. `node scripts/shoot.mjs <plan-id>` renders every viewpoint to `shots/<plan-id>/<view>.png`.
3. For each viewpoint, a **critic with fresh context** gets only the shot and its photo, picks the better match, and names the single biggest gap (geometry first, then materials, then furniture, then light).
4. A **builder** fixes that one gap in the JSON (or adds what the engine is missing), re-shoots that view, and goes back to step 3.
5. Stop when the critic picks ours or the gap is something the engine can't express; log those in `GAPS.md`.

Photos go in `photos/` (git-ignored): they're the builder's copyright and are only used as reference.
