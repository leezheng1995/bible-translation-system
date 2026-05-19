#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8000"

echo "============================================================"
echo "Day 25 - Memory Review + Rule Conflict Checker Verification"
echo "============================================================"

echo ""
echo "===== 1. Local files ====="
for f in \
  app/services/claw_memory_review_service.py \
  app/routers/claw_memory_review.py \
  skills/claw_memory_review/SKILL.md \
  docs/day25_memory_review_conflict_checker.md
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
  app/services/claw_memory_review_service.py \
  app/routers/claw_memory_review.py

echo ""
echo "===== 3. Rebuild / restart API and Celery ====="
docker compose up -d --build api celery-worker

echo ""
echo "===== 4. Wait API boot ====="
sleep 8

echo ""
echo "===== 5. OpenAPI route check ====="
curl -s "$BASE_URL/openapi.json" > /tmp/day25_openapi.json

python3 -c '
import json
data = json.load(open("/tmp/day25_openapi.json"))
paths = sorted(data.get("paths", {}).keys())
memory_paths = [p for p in paths if p.startswith("/skills/claw/memory")]

print("memory_route_count =", len(memory_paths))
for p in memory_paths:
    print(p)

required = {
    "/skills/claw/memory/policy",
    "/skills/claw/memory/board",
    "/skills/claw/memory/jobs/{job_id}/review-board",
    "/skills/claw/memory/conflict-check",
    "/skills/claw/memory/jobs/{job_id}/notify-summary",
}

missing = sorted(required - set(memory_paths))
if missing:
    raise SystemExit("Missing Day 25 memory routes: " + ", ".join(missing))
'

echo ""
echo "===== 6. Skill Library check ====="
curl -s "$BASE_URL/skills/library" > /tmp/day25_skills.json

python3 -c '
import json
data = json.load(open("/tmp/day25_skills.json"))
names = [x.get("name") for x in data.get("skills", [])]
print("skills =", names)

if "claw_memory_review" not in names:
    raise SystemExit("claw_memory_review skill not found in Skill Library")
'

echo ""
echo "===== 7. Pick first job ====="
curl -s "$BASE_URL/jobs" > /tmp/day25_jobs.json

JOB_ID="$(python3 -c '
import json
data = json.load(open("/tmp/day25_jobs.json"))
jobs = data.get("jobs", [])
if not jobs:
    raise SystemExit("No job found")
print(jobs[0]["id"])
')"

echo "JOB_ID=$JOB_ID"

echo ""
echo "===== 8. Memory policy ====="
curl -s "$BASE_URL/skills/claw/memory/policy" | python3 -m json.tool

echo ""
echo "===== 9. Memory board ====="
curl -s "$BASE_URL/skills/claw/memory/board?limit=20" | python3 -m json.tool

echo ""
echo "===== 10. Job memory review board summary ====="
curl -s "$BASE_URL/skills/claw/memory/jobs/$JOB_ID/review-board" > /tmp/day25_review_board.json

python3 -c '
import json
data = json.load(open("/tmp/day25_review_board.json"))

print(json.dumps({
    "status": data.get("status"),
    "job_id": data.get("job_id"),
    "summary": data.get("summary"),
    "decision_rules_count": len(data.get("decision_rules", [])),
}, ensure_ascii=False, indent=2))

if data.get("status") != "ok":
    raise SystemExit("review-board status is not ok")

if data.get("summary", {}).get("approved_memories_count", 0) < 1:
    raise SystemExit("approved_memories_count < 1")
'

echo ""
echo "===== 11. Conflict check ====="
curl -s -X POST "$BASE_URL/skills/claw/memory/conflict-check" \
  -H "Content-Type: application/json" \
  -d "{\"job_id\":\"$JOB_ID\", \"query\":\"God\", \"include_dictionary\":true, \"notify\":false}" \
  | python3 -m json.tool

echo ""
echo "===== 12. Notify summary, Slack may be skipped if not configured ====="
curl -s -X POST "$BASE_URL/skills/claw/memory/jobs/$JOB_ID/notify-summary" | python3 -m json.tool

echo ""
echo "===== 13. Day 24 task board still OK ====="
curl -s "$BASE_URL/skills/claw/tasks/board?limit=20" | python3 -m json.tool | head -120

echo ""
echo "===== 14. Day 22 OpenClaw still OK ====="
curl -s "$BASE_URL/skills/claw/status" | python3 -m json.tool | head -80

echo ""
echo "===== 15. Git status ====="
git status --short

echo ""
echo "============================================================"
echo "Day 25 check finished."
echo "Success criteria:"
echo "- memory_route_count = 5"
echo "- claw_memory_review listed in Skill Library"
echo "- memory policy returns human_approved_only"
echo "- memory board returns jobs"
echo "- review-board approved_memories_count >= 1"
echo "- conflict-check returns status ok"
echo "- notify-summary returns ok or Slack skipped"
echo "============================================================"
