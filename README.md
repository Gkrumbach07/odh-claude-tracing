# ODH Claude Tracing

MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance.

## Quickstart

### 1. Install the tracing plugin (one-time)

```bash
claude plugin marketplace add Gkrumbach07/claude-plugins
claude plugin install odh-claude-tracing@gkrumbach07-claude-plugins
```

### 2. Run the setup skill

Restart Claude Code after installing, then run:

```
/trace-setup
```

The skill walks you through ROSA auth and writes env vars to `.claude/settings.local.json`. Hooks ship with the plugin automatically.

### Prerequisites

- Python >= 3.11
- `oc` CLI (optional — for browser-based SSO auth)

## Commands

| Command | Description |
|---------|-------------|
| `/trace-setup` | Install with always-on tracing |
| `/trace-setup --skills=a,b` | Install with tracing off by default, auto-on for listed skills |
| `/trace-setup on` | Turn tracing ON immediately (live, no restart) |
| `/trace-setup off` | Turn tracing OFF immediately (live, no restart) |
| `/trace-setup on <skill>` | Add a skill to the auto-trace list |
| `/trace-setup off <skill>` | Remove a skill from the auto-trace list |
| `/trace-setup reauth` | Refresh expired ROSA token (no reinstall) |
| `/trace-setup status` | Check health and traced skills |
| `/trace-setup uninstall` | Remove all tracing config |

## Per-skill tracing

Choose exactly which skills are traced:

```bash
# Install with specific skills
/trace-setup --skills=preflight,jira-triage

# Add more skills later
/trace-setup on eval-run

# Remove a skill
/trace-setup off preflight

# Check what's traced
/trace-setup status
```

When you run a traced skill (e.g., `/preflight`), tracing auto-enables for that skill's entire run — including multi-turn follow-ups. When the skill completes, tracing auto-disables. Non-traced skills and regular conversation are never traced.

## How it works

1. `/trace-setup` authenticates to ROSA and writes env vars to `.claude/settings.local.json`
2. The plugin ships `hooks/hooks.json` with Stop and SessionStart hooks — auto-registered when the plugin is enabled
3. On session start, the hook confirms MLflow is reachable
4. Tracing state (`MLFLOW_CLAUDE_TRACING_ENABLED`) is toggled per-turn in real time by editing `settings.local.json`
5. `PreToolUse` hooks with `if` filters auto-enable tracing for specific skills
6. When a traced skill completes, Claude auto-disables tracing based on context instructions from the hook
7. On session exit, the Stop hook sends traces to MLflow and resets the tracing state

## Privacy

- `/trace-setup` (no flags): all turns in all sessions are traced
- `/trace-setup --skills=...`: only turns during traced skill invocations are traced
- Config lives in `.claude/settings.local.json` — never committed to git
- Token expires in ~24h; run `/trace-setup reauth` to refresh
