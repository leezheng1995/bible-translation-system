#!/usr/bin/env bash
set -e

echo "============================================================"
echo "Install OpenClaw Official CLI"
echo "============================================================"

echo "This runs the official macOS/Linux install script:"
echo "curl -fsSL https://openclaw.ai/install.sh | bash"
echo ""

curl -fsSL https://openclaw.ai/install.sh | bash

echo ""
echo "OpenClaw installed. Next run:"
echo "openclaw onboard --install-daemon"
echo "openclaw gateway status"
echo "openclaw dashboard"
