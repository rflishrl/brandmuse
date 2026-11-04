#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
echo "Running BrandMuse smoke test against: $BASE_URL"

# 1. Health check
echo -n "Checking GET /api/health ... "
HEALTH_RESP=$(curl -sSf "${BASE_URL}/api/health")
echo "$HEALTH_RESP" | grep -q '"status"' || {
  echo "FAILED: /api/health did not return expected status json."
  echo "Response: $HEALTH_RESP"
  exit 1
}
echo "OK"

echo "Smoke test passed successfully for Phase 1!"
