#!/usr/bin/env bash

set -euo pipefail

LOGS=${TMPDIR:-/app/logs}

if ! pgrep -x postgres > /dev/null; then
  echo "Starting Postgresql"
  (
    cd "$PGDATA"
    echo > "$LOGS/postgres.log"
    pg_ctl -l "$LOGS/postgres.log" start 
  )
fi

if ! pgrep -x pebble > /dev/null; then
  echo "Starting Pebble"
  (
    cd /
    PEBBLE_WFE_NONCEREJECT=0 pebble \
      -config="/test/config/pebble-config.json" \
      -dnsserver="127.0.0.1:8053" \
      -strict \
      > "$LOGS/pebble.log" 2>&1 &
  )
fi

if ! pgrep -x pebble-challtestsrv > /dev/null; then
  echo "Starting Pebble Challenge Test Server"
  (
    cd /app
    pebble-challtestsrv \
      > "$LOGS/pebble-challtestsrv.log" 2>&1 &
  )
fi

