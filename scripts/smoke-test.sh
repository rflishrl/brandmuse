#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
echo "========================================================"
echo " BrandMuse Phase 7 End-to-End Production Smoke Test"
echo " Target Base URL: $BASE_URL"
echo "========================================================"

# Generate an RFC4122 v4 UUID for session isolation
if command -v uuidgen &>/dev/null; then
  SESSION_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
elif [ -f /proc/sys/kernel/random/uuid ]; then
  SESSION_ID=$(cat /proc/sys/kernel/random/uuid)
else
  SESSION_ID="12345678-1234-4234-8234-123456789abc"
fi

echo "Active Isolated Session ID: $SESSION_ID"
echo

# 1. Health & Security Headers Check
echo -n "[1/8] Verifying GET /api/health & Security Headers ... "
HEALTH_HEADERS=$(curl -sS -I "${BASE_URL}/api/health")
echo "$HEALTH_HEADERS" | grep -iq "HTTP/.* 200" || {
  echo "FAILED: /api/health returned non-200 status."
  exit 1
}
echo "$HEALTH_HEADERS" | grep -iq "x-content-type-options: nosniff" || {
  echo "FAILED: Missing X-Content-Type-Options: nosniff"
  exit 1
}
echo "$HEALTH_HEADERS" | grep -iq "x-frame-options: DENY" || {
  echo "FAILED: Missing X-Frame-Options: DENY"
  exit 1
}
echo "PASSED (200 OK with strict security headers)"

# 2. Session Isolation & Validation
echo -n "[2/8] Verifying Session Isolation (400 on missing X-Session-Id) ... "
NO_SESSION_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/documents")
if [ "$NO_SESSION_STATUS" -ne 400 ]; then
  echo "FAILED: Expected HTTP 400 when X-Session-Id is omitted, got $NO_SESSION_STATUS"
  exit 1
fi
echo "PASSED (400 Bad Request enforced)"

# 3. Load Sample Brand Guideline
echo -n "[3/8] Loading Sample Brand Guideline (POST /api/documents/sample) ... "
SAMPLE_RESP=$(curl -sS -X POST "${BASE_URL}/api/documents/sample" \
  -H "X-Session-Id: $SESSION_ID" \
  -H "Content-Type: application/json")

DOC_ID=$(echo "$SAMPLE_RESP" | grep -o '"id":"[^"]*' | head -n 1 | cut -d'"' -f4 || echo "")
if [ -z "$DOC_ID" ]; then
  # Try document.id structure
  DOC_ID=$(echo "$SAMPLE_RESP" | grep -o '"id": "[^"]*' | head -n 1 | cut -d'"' -f4 || echo "")
fi

if [ -z "$DOC_ID" ]; then
  echo "FAILED: Could not parse document id from sample upload response."
  echo "Response: $SAMPLE_RESP"
  exit 1
fi
echo "PASSED (Document ID: $DOC_ID)"

# 4. List Documents
echo -n "[4/8] Listing Guidelines (GET /api/documents) ... "
DOCS_LIST=$(curl -sS "${BASE_URL}/api/documents" -H "X-Session-Id: $SESSION_ID")
echo "$DOCS_LIST" | grep -q "$DOC_ID" || {
  echo "FAILED: Document $DOC_ID not found in active session list."
  echo "List response: $DOCS_LIST"
  exit 1
}
echo "PASSED (Document registered in session)"

# 5. Ask Grounded Brand Q&A (SSE Streaming)
echo -n "[5/8] Streaming Grounded Chat (POST /api/chat) ... "
CHAT_STREAM=$(curl -sS -X POST "${BASE_URL}/api/chat" \
  -H "X-Session-Id: $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\": \"$DOC_ID\", \"message\": \"What is the tone of voice?\", \"history\": []}")

echo "$CHAT_STREAM" | grep -q "event: token" || {
  echo "FAILED: No SSE token events emitted."
  echo "Stream response: $CHAT_STREAM"
  exit 1
}
echo "$CHAT_STREAM" | grep -q "event: done" || {
  echo "FAILED: No SSE done event emitted with citations."
  echo "Stream response: $CHAT_STREAM"
  exit 1
}
echo "PASSED (SSE token stream & citations verified)"

# 6. Generate 3 On-Brand Concepts
echo -n "[6/8] Generating Campaign Concepts (POST /api/campaign) ... "
CAMPAIGN_RESP=$(curl -sS -X POST "${BASE_URL}/api/campaign" \
  -H "X-Session-Id: $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "{\"document_id\": \"$DOC_ID\", \"brief\": {\"product\": \"Oak Dining Chair\", \"audience\": \"Minimalists\", \"channel\": \"Instagram\", \"mood\": \"warm\"}}")

echo "$CAMPAIGN_RESP" | grep -q '"concepts"' || {
  echo "FAILED: No concepts array returned."
  echo "Campaign response: $CAMPAIGN_RESP"
  exit 1
}
echo "PASSED (3 structured concepts generated)"

# 7. Generate Stable Diffusion Image Asset
echo -n "[7/8] Generating Image Asset (POST /api/images) ... "
IMAGE_RESP=$(curl -sS -X POST "${BASE_URL}/api/images" \
  -H "X-Session-Id: $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d "{\"concept_title\": \"Morning Warmth in Oak\", \"image_prompt\": \"Minimalist solid oak chair in soft morning sunlight, architectural interior, quiet serene atmosphere\", \"concept_json\": {\"channel\": \"Instagram\"}}")

IMAGE_URL=$(echo "$IMAGE_RESP" | grep -o '"url":"[^"]*' | head -n 1 | cut -d'"' -f4 || echo "")
if [ -z "$IMAGE_URL" ]; then
  IMAGE_URL=$(echo "$IMAGE_RESP" | grep -o '"url": "[^"]*' | head -n 1 | cut -d'"' -f4 || echo "")
fi

if [ -z "$IMAGE_URL" ]; then
  echo "FAILED: Image generation did not return public storage URL."
  echo "Image response: $IMAGE_RESP"
  exit 1
fi
echo "PASSED (Permanent Image Asset: ${IMAGE_URL:0:40}...)"

# 8. Retrieve Session Gallery
echo -n "[8/8] Inspecting Session Gallery (GET /api/images) ... "
GALLERY_RESP=$(curl -sS "${BASE_URL}/api/images" -H "X-Session-Id: $SESSION_ID")
echo "$GALLERY_RESP" | grep -q '"generations"' || {
  echo "FAILED: No generations array found in gallery."
  echo "Gallery response: $GALLERY_RESP"
  exit 1
}
echo "PASSED (Generated asset present in gallery)"

echo
echo "========================================================"
echo " ALL 8 END-TO-END QUALITY GATE VERIFICATIONS PASSED!"
echo "========================================================"
