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

The skill walks you through ROSA auth and configures everything. After setup, restart Claude Code and all interactions are traced to MLflow.

### Prerequisites

- Python >= 3.11
- `oc` CLI (optional — for browser-based SSO auth)

## Commands

| Command | Description |
|---------|-------------|
| `/trace-setup` | Full setup — install mlflow, authenticate, configure hooks |
| `/trace-setup --status` | Check connection health and config |
| `/trace-setup --disable` | Remove tracing config and opt out |

## How it works

1. `/trace-setup` runs `mlflow autolog claude` to generate the Stop hook
2. Config is moved to `.claude/settings.local.json` (never committed)
3. On each session start, a health check confirms MLflow is reachable
4. On each Stop event, MLflow captures a trace with tool calls, timing, and cost
5. Traces appear in the team's MLflow experiment at the configured tracking URI
