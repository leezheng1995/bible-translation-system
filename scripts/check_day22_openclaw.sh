#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8000"

echo "============================================================"
echo "Day 22 OpenClaw Verification"
echo "============================================================"

echo ""
echo "===== 1. Python compile ====="
python3 -m py_compile \
  app/services/slack_notify_service.py \
  app/services/claw_skill_service.py \
  app/routers/claw_skill.py

echo ""
echo "===== 2. OpenAPI route check ====="
python3 - <<'PY2'
import json
import urllib.request

base = "http://localhost:8000"

with urllib.request.urlopen(base + "/openapi.json", timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))

paths = sorted(data.get("paths", {}).keys())
claw_paths = [p for p in paths if p.startswith("/skills/claw")]

print("claw_route_count =", len(claw_paths))
for p in claw_paths:
    print(p)

required = [
    "/skills/claw/status",
    "/skills/claw/scan-drive",
    "/skills/claw/scan_drive",
    "/skills/claw/review-job/{job_id}",
    "/skills/claw/review_job/{job_id}",
    "/skills/claw/approve",
    "/skills/claw/archive",
    "/skills/claw/slack-notify",
    "/skills/claw/slack_notify",
]

missing = [p for p in required if p not in claw_paths]
if missing:
    raise SystemExit("MISSING CLAW ROUTES: " + ", ".join(missing))
PY2

echo ""
echo "===== 3. Claw status ====="
curl -s "$BASE_URL/skills/claw/status" | python3 -m json.tool

echo ""
echo "===== 4. Claw scan-drive dry run ====="
curl -s -X POST "$BASE_URL/skills/claw/scan-drive" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "notify": true}' | python3 -m json.tool

echo ""
echo "===== 5. Claw Slack notify test ====="
curl -s -X POST "$BASE_URL/skills/claw/slack-notify" \
  -H "Content-Type: application/json" \
  -d '{"text": "Day 22 OpenClaw Slack notify test"}' | python3 -m json.tool

echo ""
echo "===== 6. Claw review-job ====="
JOB_ID="$(python3 - <<'PY2'
import json
import urllib.request

base = "http://localhost:8000"

with urllib.request.urlopen(base + "/jobs", timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))

jobs = data.get("jobs", [])
if not jobs:
    raise SystemExit("No job found")
print(jobs[0]["id"])
PY2
)"

echo "JOB_ID=$JOB_ID"

curl -s "$BASE_URL/skills/claw/review-job/$JOB_ID" | python3 -m json.tool

echo ""
echo "===== 7. Catholic dictionary still OK ====="
python3 - <<'PY2'
import json
import urllib.request

base = "http://localhost:8000"

with urllib.request.urlopen(base + "/skills/library/catholic-translation/dictionary", timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))

entries = data.get("entries", [])
found = {e["source"] for e in entries if e["source"] in {"God", "Christ", "Peter", "John"}}

print("dictionary_count =", data.get("count"))
print("found =", sorted(found))

if data.get("count", 0) < 200:
    raise SystemExit("dictionary_count < 200")

if "God" not in found:
    raise SystemExit("God not found")
PY2

echo ""
echo "===== 8. Git status ====="
git status --short

echo ""
echo "============================================================"
echo "Day 22 OpenClaw check finished."
echo "============================================================"
