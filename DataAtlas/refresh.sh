#!/usr/bin/env bash
# Scheduled refresh (Phase 5). Cron example — weekly, Monday 03:00:
#   0 3 * * 1 cd ~/DataAtlas && ./refresh.sh >> logs/refresh.log 2>&1
#
# Order matters: extract first, then diff (so schema drift is visible in the
# log), then relationships + descriptions for anything new, then re-export.
# describe/relationships skip work that's already done, so a refresh with no
# schema changes costs no LLM tokens.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

echo "=== refresh started $(date -u +%FT%TZ) ==="
$PY -m datadict.run_extraction
$PY -m datadict.changes
$PY -m datadict.relationships
$PY -m datadict.describe
$PY -m datadict.search export --out catalog.html
echo "=== refresh finished $(date -u +%FT%TZ) ==="
