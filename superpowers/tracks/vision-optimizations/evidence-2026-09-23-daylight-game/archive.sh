#!/bin/bash
# Mirror smartbox-katrain's journal from the RK3562 into a local file, reconnecting on drops.
# Resumes from the last archived timestamp (a few duplicate lines at each seam; dedupe on read).
LOG="$1"
SINCE0="$2"   # e.g. "2026-09-23 14:17:00"
touch "$LOG"
while true; do
  last=$(tail -n 1 "$LOG" | cut -c1-19 | tr T ' ')
  since="${last:-$SINCE0}"
  [ -z "$last" ] && since="$SINCE0"
  echo "[archive] connect since=$since $(date '+%H:%M:%S')" >&2
  ssh -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 rk3562-direct \
    "journalctl -u smartbox-katrain -o short-iso-precise -f --no-pager --since '$since'" >> "$LOG"
  echo "[archive] ssh exited rc=$? $(date '+%H:%M:%S')" >&2
  sleep 5
done
