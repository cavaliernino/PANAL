#!/bin/bash
# Refresh the national snapshot. Installed in cron every 10 minutes, matching
# the GOES full-disk cadence — one minute past, not on the minute:
#
#   1-59/10 * * * * /var/www/panal.ninobozzi.cl/ingest/scripts/cron_national.sh
#
# NOAA publishes each scan 6-10 s after :x0 (measured 2026-10-02 against the
# bucket's LastModified). Run at :x0 and the newest scan is never there yet,
# so every snapshot carried the previous one, ten minutes staler than it had
# to be. A minute past leaves ~50 s of margin.
#
# Logs to data/cron_national.log, kept under 1 MB. Failures stay in the log
# instead of mailing root, and the previous snapshot survives untouched
# because the write is atomic.
#
# Dead-man's switch: if ~/.config/panal/healthcheck_url holds a
# healthchecks.io ping URL, every run reports its exit code there, and
# healthchecks.io mails when a run fails or when runs stop arriving. A
# chain that dies silently is the failure the page cannot show, because
# nobody is looking at the page. The URL stays on the server, out of git:
# anyone holding it can mark the check healthy.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="$ROOT/data/cron_national.log"
mkdir -p "$ROOT/data"

# Keep the log from growing without bound.
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1048576 ]; then
  tail -c 262144 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

{
  echo "--- $(date '+%Y-%m-%d %H:%M:%S %z') ---"
  cd "$ROOT/ingest" || exit 1
  "$ROOT/.venv/bin/python" scripts/build_national.py \
      -o "$ROOT/web/data/national.json" 2>&1
  status=$?
  echo "exit=$status"

  HC="${PANAL_HEALTHCHECK_FILE:-$HOME/.config/panal/healthcheck_url}"
  if [ -s "$HC" ]; then
    curl -fsS -m 10 --retry 3 -o /dev/null "$(head -n1 "$HC")/$status" \
      || echo "healthcheck: no se pudo avisar"
  fi
} >> "$LOG" 2>&1
