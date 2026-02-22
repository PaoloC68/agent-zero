# agent-zero-cisco-guard

Cisco AI Skill Scanner integration for Agent Zero's guard system.

## Installation

```bash
pip install -e agent-zero-cisco-guard/
```

## How it works

This package registers an `agent_zero.guards` entry point that fires on `skill_install` events.
When a skill is imported into Agent Zero, the handler invokes the Cisco AI Skill Scanner
and stores the verdict in `usr/skill_scans/<skill-name>.json`.

The built-in `_05_scan_status_guard` extension then checks these verdicts at runtime
and blocks tools backed by skills flagged as unsafe.

## Requirements

- `cisco-ai-skill-scanner` package (install separately)
- Agent Zero with guard system enabled