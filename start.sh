#!/usr/bin/env bash
# Auto-restart wrapper: if KHUSHI bot crashes/exits for any reason, restart it.
# Backoff: 2s, 5s, 10s, then steady 15s. Resets after 60s of stable uptime.
#
# All secrets (BOT_TOKEN, API_ID, API_HASH, STRING_SESSION, MONGO_DB_URI,
# OWNER_ID, LOGGER_ID, etc.) MUST be supplied via environment variables.
# On Railway: set them in your service "Variables" tab.
# Locally: copy .env.example to .env and fill in, then `source .env`.

cd "$(dirname "$0")"
PY="${PYTHON_BIN:-python3}"
export PYTHONUNBUFFERED=1

DELAYS=(2 5 10 15)
i=0
while true; do
  start_ts=$(date +%s)
  echo "[watchdog] starting KHUSHI music bot (attempt $((i+1))) at $(date -Iseconds)"
  "$PY" -m KHUSHI
  rc=$?
  end_ts=$(date +%s)
  uptime=$((end_ts - start_ts))
  echo "[watchdog] bot exited rc=$rc after ${uptime}s"
  if [ "$uptime" -gt 60 ]; then
    i=0
  fi
  delay=${DELAYS[$i]:-15}
  echo "[watchdog] restarting in ${delay}s..."
  sleep "$delay"
  if [ "$i" -lt 3 ]; then i=$((i+1)); fi
done
