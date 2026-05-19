#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8000"

echo "============================================================"
echo "Day 24 - OpenClaw Task Management Verification"
echo "============================================================"

echo ""
echo "===== 1. Local files ====="
for f in \
  app/services/claw_task_management_service.py \
  app/routers/claw_task_management.py \
  skills/claw_task_management/SKILL.md \
  docs/day24_claw_task_management.md
do
  if [ -f "$f" ]; then
    echo "OK: $f"
  else
    echo "MISSING: $f"
    exit 1
  fi
done

echo ""
echo "===== 2. Python compile ====="
python3 -m py_compile \
  app/services/claw_task_management_service.py \
  app/routers/claw_task_management.py

echo ""
echo "===== 3. Rebuild / restart API and Celery ====="
docker compose up -d --build api celery-worker

echo ""
echo "===== 4. Wait API boot ====="
sleep 8

echo ""
echo "===== 5. OpenAPI route check ====="
python3 - <<'PY2'
import json
import urllib.request

base = "http://localhost:8000"

with urllib.request.urlopen(base + "/openapi.json", timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))

paths = sorted(data.get("paths", {}).keys())
task_paths = [p for p in paths if p.startswith("/skills/claw/tasks")]

print("task_route_count =", len(task_paths))
for p in task_paths:
    print(p)

required = {
    "/skills/claw/tasks/board",
    "/skills/claw/tasks/jobs/{job_id}/summary",
    "/skills/claw/tasks/jobs/{job_id}/review-package",
    "/skills/claw/tasks/jobs/{job_id}/action",
    "/skills/claw/tasks/jobs/{job_id}/notify-summary",
}

missing = sorted(required - set(task_paths))
if missing:
    raise SystemExit("Missing Day 24 task routes: " + ", ".join(missing))
PY2

echo ""
echo "===== 6. Skill Library check ====="
python3 - <<'PY2'
import json
import urllib.request

base = "http://localhost:8000"

with urllib.request.urlopen(base + "/skills/library", timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))

names = [x.get("name") for x in data.get("skills", [])]
print("skills =", names)

if "claw_task_management" not in names:
    raise SystemExit("claw_task_management skill not found in Skill Library")
PY2

echo ""
echo "===== 7. Board API check ====="
curl -s "$BASE_URL/skills/claw/tasks/board?limit=20" | python3 -m json.tool

echo ""
echo "===== 8. Pick first job and test summary / review-package / notify ====="
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

echo ""
echo "--- job summary ---"
curl -s "$BASE_URL/skills/claw/tasks/jobs/$JOB_ID/summary" | python3 -m json.tool

echo ""
echo "--- job review package summary ---"
python3 - <<PY2
import json
import urllib.request

base = "http://localhost:8000"
job_id = "$JOB_ID"

with urllib.request.urlopen(base + f"/skills/claw/tasks/jobs/{job_id}/review-package", timeout=120) as resp:
    data = json.loads(resp.read().decode("utf-8"))

print(json.dumps({
    "status": data.get("status"),
    "job_id": data.get("job_id"),
    "summary": data.get("summary"),
    "segment_packages_count": len(data.get("segment_packages", [])),
}, ensure_ascii=False, indent=2))

if data.get("status") != "ok":
    raise SystemExit("review-package status is not ok")

if len(data.get("segment_packages", [])) < 1:
    raise SystemExit("segment_packages_count < 1")
PY2

echo ""
echo "--- notify summary, Slack may be skipped if not configured ---"
curl -s -X POST "$BASE_URL/skills/claw/tasks/jobs/$JOB_ID/notify-summary" | python3 -m json.tool

echo ""
echo "===== 9. Day 22 still OK ====="
curl -s "$BASE_URL/skills/claw/status" | python3 -m json.tool | head -120

echo ""
echo "===== 10. OpenClaw official dashboard still OK ====="
openclaw gateway status || true
openclaw models list || true

echo ""
echo "===== 11. Git status ====="
git status --short

echo ""
echo "============================================================"
echo "Day 24 check finished."
echo "Success criteria:"
echo "- task_route_count = 5"
echo "- claw_task_management listed in Skill Library"
echo "- task board returns jobs"
echo "- job summary returns counts"
echo "- review-package returns segment_packages_count >= 1"
echo "- notify-summary returns ok or Slack skipped"
echo "============================================================"
