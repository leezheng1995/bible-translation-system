#!/usr/bin/env bash
set -e

PROJECT_DIR="/Users/edike/Projects/bible-translation-system"
BASE_URL="http://localhost:8000"
PIXEL_DIR="$PROJECT_DIR/external_tools/pixel-agents"

echo "============================================================"
echo "Day 23 Check - Official OpenClaw Dashboard + pixel-agents"
echo "============================================================"

cd "$PROJECT_DIR"

echo ""
echo "===== 1. Git state ====="
git branch --show-current
git status --short
git log --oneline -5

echo ""
echo "===== 2. Confirm wrong static UI does NOT exist ====="
if [ -d "app/static/claw_panel" ]; then
  echo "ERROR: app/static/claw_panel still exists"
  exit 1
else
  echo "OK: no app/static/claw_panel"
fi

if [ -f "app/routers/claw_panel.py" ]; then
  echo "ERROR: app/routers/claw_panel.py still exists"
  exit 1
else
  echo "OK: no app/routers/claw_panel.py"
fi

if [ -d "skills/claw_panel" ]; then
  echo "ERROR: skills/claw_panel still exists"
  exit 1
else
  echo "OK: no skills/claw_panel"
fi

echo ""
echo "===== 3. Docker / Day 22 backend check ====="
docker compose ps

python3 - <<'PY2'
import json
import urllib.request

base = "http://localhost:8000"

def get_json(path):
    with urllib.request.urlopen(base + path, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

openapi = get_json("/openapi.json")
paths = sorted(openapi.get("paths", {}).keys())

panel_paths = [p for p in paths if p.startswith("/claw-panel")]
claw_paths = [p for p in paths if p.startswith("/skills/claw")]
library_paths = [p for p in paths if p.startswith("/skills/library")]

print("panel_paths =", panel_paths)
print("claw_route_count =", len(claw_paths))
print("skill_library_route_count =", len(library_paths))

if panel_paths:
    raise SystemExit("ERROR: /claw-panel route still exists")

if len(claw_paths) < 9:
    raise SystemExit("ERROR: /skills/claw route count is too low")

if len(library_paths) < 5:
    raise SystemExit("ERROR: /skills/library route count is too low")

skills = get_json("/skills/library")
skill_names = [x.get("name") for x in skills.get("skills", [])]
print("skills =", skill_names)

if "claw_panel" in skill_names:
    raise SystemExit("ERROR: wrong claw_panel skill still exists")

for required in ["claw", "catholic_translation_role", "catholic_translation_dictionary"]:
    if required not in skill_names:
        raise SystemExit(f"ERROR: missing skill {required}")

dictionary = get_json("/skills/library/catholic-translation/dictionary")
print("dictionary_count =", dictionary.get("count"))
if dictionary.get("count", 0) < 200:
    raise SystemExit("ERROR: catholic dictionary broken")

claw = get_json("/skills/claw/status")
print("claw_status =", claw.get("status"))
print("catholic_dictionary_count =", claw.get("catholic_dictionary_count"))
if claw.get("status") != "ok":
    raise SystemExit("ERROR: OpenClaw backend status not ok")
PY2

echo ""
echo "===== 4. Node / npm check for pixel-agents ====="
if command -v node >/dev/null 2>&1; then
  echo "node path: $(command -v node)"
  node --version
else
  echo "WARN: node not found. OpenClaw docs recommend Node 24, Node 22.14+ also supported."
fi

if command -v npm >/dev/null 2>&1; then
  echo "npm path: $(command -v npm)"
  npm --version
else
  echo "WARN: npm not found."
fi

echo ""
echo "===== 5. OpenClaw CLI check ====="
if command -v openclaw >/dev/null 2>&1; then
  echo "openclaw path: $(command -v openclaw)"
  openclaw --version || true

  echo ""
  echo "--- openclaw gateway status ---"
  openclaw gateway status || true

  echo ""
  echo "--- openclaw status ---"
  openclaw status || true

  echo ""
  echo "OpenClaw dashboard command is available:"
  echo "openclaw dashboard"
else
  echo "WARN: openclaw CLI not installed."
  echo ""
  echo "Official install command for macOS/Linux:"
  echo "curl -fsSL https://openclaw.ai/install.sh | bash"
  echo ""
  echo "After install:"
  echo "openclaw onboard --install-daemon"
  echo "openclaw gateway status"
  echo "openclaw dashboard"
fi

echo ""
echo "===== 6. Clone / update pixel-agents under external_tools ====="
mkdir -p "$PROJECT_DIR/external_tools"

if [ -d "$PIXEL_DIR/.git" ]; then
  echo "pixel-agents already cloned. Pull latest."
  git -C "$PIXEL_DIR" pull --ff-only || true
else
  git clone https://github.com/pablodelucca/pixel-agents.git "$PIXEL_DIR"
fi

echo ""
echo "===== 7. pixel-agents repo check ====="
if [ -d "$PIXEL_DIR" ]; then
  cd "$PIXEL_DIR"
  git log --oneline -3 || true
  test -f package.json && echo "OK: package.json exists"
  test -d webview-ui && echo "OK: webview-ui exists"
else
  echo "ERROR: pixel-agents directory missing after clone"
  exit 1
fi

echo ""
echo "===== 8. Optional pixel-agents dependency install/build check ====="
cd "$PIXEL_DIR"

if command -v npm >/dev/null 2>&1; then
  echo "Installing root npm dependencies..."
  npm install

  echo ""
  echo "Installing missing pixel-agents test/build dev dependency..."
  npm install -D vitest

  echo ""
  echo "Installing webview-ui npm dependencies..."
  cd "$PIXEL_DIR/webview-ui"
  npm install

  echo ""
  echo "Building pixel-agents..."
  cd "$PIXEL_DIR"
  npm run build

  echo "OK: pixel-agents build completed"
else
  echo "SKIPPED: npm not found, cannot build pixel-agents"
fi

echo ""
echo "===== 9. Verify external_tools is ignored by git ====="
cd "$PROJECT_DIR"

git status --short

if git status --short | grep -E "^(\?\?| M|M ) external_tools" >/dev/null 2>&1; then
  echo "ERROR: external_tools is not ignored correctly"
  exit 1
else
  echo "OK: external_tools is ignored"
fi

echo ""
echo "============================================================"
echo "Day 23 check finished."
echo ""
echo "Official OpenClaw dashboard:"
echo "  openclaw dashboard"
echo "  http://127.0.0.1:18789/"
echo ""
echo "pixel-agents source:"
echo "  external_tools/pixel-agents"
echo ""
echo "Next expected git changes:"
echo "  .gitignore"
echo "  docs/day23_openclaw_pixel_agents.md"
echo "  scripts/day23_openclaw_pixel_agents_check.sh"
echo "============================================================"
