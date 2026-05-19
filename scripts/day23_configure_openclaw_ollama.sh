#!/usr/bin/env bash
set -e

echo "============================================================"
echo "Day 23 - Configure OpenClaw with local Ollama"
echo "============================================================"

echo ""
echo "===== 1. Check Ollama local models ====="
ollama list

echo ""
echo "===== 2. Check Ollama API ====="
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool >/tmp/ollama_tags.json
cat /tmp/ollama_tags.json | head -80

echo ""
echo "===== 3. Check OpenClaw CLI ====="
command -v openclaw
openclaw --version

echo ""
echo "===== 4. Export Ollama local env ====="
export OLLAMA_API_KEY="ollama-local"

echo ""
echo "===== 5. Run OpenClaw onboarding with Ollama local model ====="
echo "If this command fails because CLI flags changed, use the interactive fallback printed below."
echo ""

set +e
openclaw onboard \
  --non-interactive \
  --install-daemon \
  --auth-choice ollama \
  --custom-base-url "http://127.0.0.1:11434" \
  --custom-model-id "qwen3:14b" \
  --accept-risk

ONBOARD_EXIT=$?
set -e

echo ""
echo "onboard_exit_code=$ONBOARD_EXIT"

if [ "$ONBOARD_EXIT" -ne 0 ]; then
  echo ""
  echo "============================================================"
  echo "Non-interactive onboarding failed."
  echo "Now use interactive mode manually:"
  echo ""
  echo "openclaw onboard --install-daemon"
  echo ""
  echo "When it asks:"
  echo "1. Model/auth provider: choose More… or Ollama"
  echo "2. Choose Ollama"
  echo "3. Ollama base URL: http://127.0.0.1:11434"
  echo "4. Mode: Local only"
  echo "5. Model: qwen3:14b"
  echo "6. Do NOT choose OpenAI"
  echo "============================================================"
  exit 1
fi

echo ""
echo "===== 6. Check OpenClaw gateway status ====="
openclaw gateway status || true

echo ""
echo "===== 7. Check OpenClaw status ====="
openclaw status || true

echo ""
echo "===== 8. Check OpenClaw models ====="
openclaw models list || true

echo ""
echo "===== 9. Try set default model to Ollama qwen3:14b ====="
openclaw models set "ollama/qwen3:14b" || true

echo ""
echo "===== 10. Final gateway check ====="
openclaw gateway status || true
openclaw status || true

echo ""
echo "============================================================"
echo "If gateway is reachable, open dashboard with:"
echo "openclaw dashboard"
echo ""
echo "Expected URL:"
echo "http://127.0.0.1:18789/"
echo "============================================================"
