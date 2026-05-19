#!/usr/bin/env bash
set -e

echo "============================================================"
echo "Start OpenClaw Official Dashboard"
echo "============================================================"

if ! command -v openclaw >/dev/null 2>&1; then
  echo "ERROR: openclaw CLI not installed."
  echo ""
  echo "Install command:"
  echo "curl -fsSL https://openclaw.ai/install.sh | bash"
  echo ""
  echo "Then run:"
  echo "openclaw onboard --install-daemon"
  exit 1
fi

echo ""
echo "===== OpenClaw version ====="
openclaw --version || true

echo ""
echo "===== Gateway status ====="
openclaw gateway status || true

echo ""
echo "===== OpenClaw status ====="
openclaw status || true

echo ""
echo "===== Opening official dashboard ====="
echo "Expected local URL: http://127.0.0.1:18789/"
openclaw dashboard
