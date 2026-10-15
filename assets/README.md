# Na Hiku asset library (generated - do not edit by hand)

Built by `python3 scripts/fetch_assets.py`. Real photo-scanned PBR textures and real sky HDRIs,
all CC0 (ambientCG, Poly Haven). See `manifest.json` for every file, its real-world tile size,
the canonical source page, the exact mirror it was fetched from, and per-asset notes.

* `textures/<category>/<name>/` : color.jpg (sRGB), normal.jpg (OpenGL, +Y up), roughness.jpg,
  ao.jpg, disp.png (0.5 = mid), metalness.jpg, opacity.png (atlases).  Mapping: one tile =
  `tile_m` metres (world units are feet in three.js; metres in the exported GLB).
* `hdri/<name>.hdr` : equirectangular Radiance HDR.  Day skies also have `<name>_nosun.hdr`
  (sun disc painted out) plus the measured sun direction / irradiance / colour in manifest.json,
  so a Blender Sun lamp can be placed at the astronomically correct position for any date/time
  while the photographed sky + clouds still light the scene.
* `contact_sheet.jpg` : thumbnails of everything.
