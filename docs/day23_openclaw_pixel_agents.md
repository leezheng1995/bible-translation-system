# Day 23 - OpenClaw Official Dashboard + pixel-agents Integration

## Goal

Day 23 does not build a custom FastAPI static dashboard.

The correct direction is:

1. Use the official OpenClaw dashboard / Control UI.
2. Keep our FastAPI system as the Bible Translation backend.
3. Keep Day 22 OpenClaw command layer APIs.
4. Use pixel-agents as an external visualization tool, not as app/static.
5. Do not commit external cloned repositories.

## OpenClaw official dashboard

Expected commands:

- openclaw --version
- openclaw gateway status
- openclaw status
- openclaw dashboard

Expected local dashboard:

- http://127.0.0.1:18789/

Security note:

The dashboard is an admin surface. Keep it local or protected. Do not expose it publicly.

## pixel-agents

Repository:

- https://github.com/pablodelucca/pixel-agents

Current limitation:

pixel-agents currently works mainly as a VS Code extension with Claude Code. It is not yet a native OpenClaw dashboard plugin.

Install from source flow:

- git clone https://github.com/pablodelucca/pixel-agents.git
- cd pixel-agents
- npm install
- cd webview-ui && npm install && cd ..
- npm run build

The cloned repo should stay under external_tools/ and should not be committed.

## Project rule

Do not create:

- app/static/claw_panel
- app/routers/claw_panel.py
- skills/claw_panel
- /claw-panel route
