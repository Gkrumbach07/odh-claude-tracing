# ODH Claude Tracing

MLflow production tracing for Claude Code skills. Captures traces (tool calls, LLM interactions, timing, cost) and sends them to the team's shared MLflow instance.

## Quickstart

### 1. Add the marketplace (one-time)

```bash
claude plugin marketplace add Gkrumbach07/claude-plugins
```

### 2. Install the plugin

```bash
claude plugin install odh-claude-tracing@gkrumbach07-claude-plugins
```

### 3. Restart Claude Code, then run

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
| `/trace-setup` | Full setup — install mlflow, authenticate, write config |
| `/trace-setup on` | Turn tracing ON immediately (live, no restart) |
| `/trace-setup off` | Turn tracing OFF immediately (live, no restart) |
| `/trace-setup on <skill>` | Add a skill to the auto-trace list |
| `/trace-setup off <skill>` | Remove a skill from the auto-trace list |
| `/trace-setup reauth` | Refresh expired ROSA token (no reinstall) |
| `/trace-setup status` | Check health, trigger mode, and traced skills |
| `/trace-setup uninstall` | Remove all tracing config |

## Trigger Modes

Control **when** tracing is active. Set during install with `--trigger=<mode>`:

| Mode | Default | Description |
|------|---------|-------------|
| `always` | ✓ | Every turn is traced |
| `skill` | | Tracing off by default; auto-enables for specific skills |
| `manual` | | Tracing off by default; use `on`/`off` commands to control |

### Per-skill tracing

With `--trigger=skill`, you choose exactly which skills are traced:

```bash
# Install with skill-trigger mode
/trace-setup --trigger=skill

# Add skills to trace
/trace-setup on preflight
/trace-setup on jira-triage

# Or add skills during install (implies --trigger=skill)
/trace-setup --skills=preflight,jira-triage

# Remove a skill from tracing
/trace-setup off preflight

# Check which skills are traced
/trace-setup --status
```

When you run a traced skill (e.g., `/preflight`), tracing auto-enables for that skill's entire run — including multi-turn follow-ups. When the skill completes, tracing auto-disables. Non-traced skills and regular conversation are never traced.

## How it works

1. `/trace-setup` authenticates to ROSA and writes env vars to `.claude/settings.local.json`
2. The plugin ships `hooks/hooks.json` with Stop and SessionStart hooks — auto-registered when the plugin is enabled
3. On session start, the hook confirms MLflow is reachable and reports trigger mode
4. Tracing state (`MLFLOW_CLAUDE_TRACING_ENABLED`) is toggled per-turn in real time by editing `settings.local.json`
5. In `skill` mode, `PreToolUse` hooks with `if` filters auto-enable tracing for specific skills
6. When a traced skill completes, Claude auto-disables tracing based on context instructions from the hook
7. On session exit, the Stop hook sends traces to MLflow and resets the tracing state

## Privacy

- **`always` mode**: All turns in all sessions are traced
- **`skill` mode**: Only turns during traced skill invocations are traced
- **`manual` mode**: Only turns between `/trace-setup on` and `/trace-setup off` are traced
- Config lives in `.claude/settings.local.json` — never committed to git
- Token expires in ~24h; run `/trace-setup reauth` to refresh
