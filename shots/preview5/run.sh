#!/bin/bash
# Fix round r5 -> preview r5: one export (blender/), each view rendered, finished and labelled before the next.
cd /tmp/claude-0/-home-user-moku/ed1d652b-1bcf-5826-a091-375544d493d0/scratchpad/nahiku-walkthrough
set -x
O=shots/preview5
T="CONCEPT VISUALIZATION · independent internal draft, not by the developer · not construction or as-built documentation · views not guaranteed"
S="SUPPLIED: areas 2,300 / 352 / 494 sq ft, 4 bd / 4.5 ba (brochure p6) · terrain USGS 3DEP lidar · imagery Sentinel-2"
E="ESTIMATE: floor-plan scale 23 px/ft fitted to stated areas (±3-8%; p6 has no dimension strings) · site position ±25 m"
for v in front back; do
  if [ $v = front ]; then
    IEV=3.0   # foyer and great room glow through the entry glazing (critique-preview4-front #5)
    A1="ASSUMED: garage pavilion 22 x 15.9 ft + position (not on plan; rendering p4) · ʻohana placement (rendering p4) · lot 61.5 ft wide · homesite 7 of 14"
    A2="ASSUMED: great-room cross-hip roof form (from rendering p4, not on plan) · heights, roof pitch/overhangs, landscape layout, finishes (renderings p4/p5, board p7)"
    A3="ASSUMED: neighbours = copies of this design, their roofs softened (retouch) · background buildings = generic footprint massing · ocean/backdrop from DEM, view not verified"
    sun="Sun: 21 Jun 10:00 HST (alt 53°, az 80°), the real position for that date and site"
  else
    IEV=2.3
    A1="ASSUMED: vanishing edge 3 ft drop + catch basin, pool 30 x 13 ft, spa (rendering p5; needs pool plans) · ~5 ft retaining wall + grading (needs civil grading plan)"
    A2="ASSUMED: heights, roof pitch/overhangs, landscape layout, finishes, lānai furnishing (renderings p4/p5, board p7)"
    A3="ASSUMED: neighbours = copies of this design, their roofs softened (retouch) · lot 61.5 ft wide, neighbours ~70 ft apart (needs subdivision plat) · views not verified"
    sun="Sun: 20 Nov 13:30 HST (alt 45°, az 202°), the real position for that date; date chosen for side light"
  fi
  scripts/blender_slot.sh python3 scripts/blender_render.py blender/nahiku.glb blender/nahiku-meta.json $O --views $v --samples 128 --res 1650x871 --threads 4 --interior-ev $IEV
  [ -f $O/$v.png ] || continue
  python3 scripts/photo_finish.py $O/$v.png $O/$v-finished.png --ref ref/$v.png --grade 0.3
  python3 scripts/label_preview.py $O/$v-finished.png $O/$v-labelled.jpg "$T" "$S" "$E" "$A1" "$A2" "$A3" "$sun"
done
echo PREVIEW DONE
