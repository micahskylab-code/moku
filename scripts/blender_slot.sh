#!/bin/bash
# Runs a command while holding one of N shared "Blender slots", so parallel workers never run more
# than N path-tracing processes at once (RAM: a full scene with vegetation needs several GB).
#   scripts/blender_slot.sh python3 scripts/blender_render.py ...      (BLENDER_SLOTS=2 by default)
L=/tmp/claude-0/-home-user-moku/ed1d652b-1bcf-5826-a091-375544d493d0/scratchpad/locks; mkdir -p "$L"
N=${BLENDER_SLOTS:-2}
while true; do
  for i in $(seq 0 $((N - 1))); do
    exec 9>"$L/blender-$i.lock"
    if flock -n 9; then nice -n 10 "$@"; rc=$?; exec 9>&-; exit $rc; fi
  done
  sleep 5
done
