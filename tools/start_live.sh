#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Runtime files stay outside the checkout. A new feed version gets a separate database.
if [ "$#" -gt 0 ]; then
    pelinie_runtime=$(python3 tools/prepare_transit.py --directory "${TMPDIR:-/tmp}/pelinie-transit" --zip "$1")
else
    pelinie_runtime=$(python3 tools/prepare_transit.py --directory "${TMPDIR:-/tmp}/pelinie-transit")
fi
set -- python3 server.py --data "$pelinie_runtime/catalog.json" --gtfs "$pelinie_runtime/gtfs.zip" --db "$pelinie_runtime/reports.sqlite3" --realtime --bind "${PELINIE_BIND:-127.0.0.1}" --port "${PORT:-8000}"
pelinie_origin=${PELINIE_PUBLIC_ORIGIN:-${RENDER_EXTERNAL_URL:-}}
if [ -n "$pelinie_origin" ]; then
    set -- "$@" --public-origin "$pelinie_origin"
fi
exec "$@"
