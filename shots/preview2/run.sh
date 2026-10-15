#!/bin/bash
# Recovery milestone: fix round r1: one consolidated front/back concept preview from the single export in blender/.
cd /tmp/claude-0/-home-user-moku/ed1d652b-1bcf-5826-a091-375544d493d0/scratchpad/nahiku-walkthrough
set -x
scripts/blender_slot.sh python3 scripts/blender_render.py blender/nahiku.glb blender/nahiku-meta.json shots/preview2 --views front back --samples 128 --res 1650x871 --threads 4
T="CONCEPT VISUALIZATION · internal draft · not construction or as-built documentation · views not guaranteed"
S="SUPPLIED: areas 2,300 / 352 / 494 sq ft, 4 bd / 4.5 ba (brochure p6) · terrain USGS 3DEP lidar · imagery Sentinel-2"
E="ESTIMATE: floor-plan scale 23 px/ft fitted to stated areas (±3-8%; p6 has no dimension strings)"
A1="ASSUMED: garage pavilion 22 x 15.9 ft + position (not on plan; from rendering p4) · ʻohana placement (rendering p4) · lot 61.5 ft wide · homesite 7 of 14"
A2="ASSUMED: heights, roof pitch/overhangs, pool 30 x 13 ft, ~5 ft retaining wall + grading, landscape layout, finishes (renderings p4/p5, board p7) · neighbours = copies of this design"
for v in front back; do
  [ -f shots/preview2/$v.png ] || continue
  sun=$([ $v = front ] && echo "Sun: 21 Jun 10:00 HST (alt 53°, az 80°)" || echo "Sun: ~22 Sep 15:25 HST (alt 44°, az 261°)")
  python3 scripts/photo_finish.py shots/preview2/$v.png shots/preview2/$v-finished.png --ref ref/$v.png --grade 0.3
  python3 scripts/label_preview.py shots/preview2/$v-finished.png shots/preview2/$v-labelled.jpg "$T" "$S" "$E" "$A1" "$A2" "$sun"
done
echo PREVIEW DONE
