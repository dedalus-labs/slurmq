# slurmq

**GPU quota management for SLURM clusters.**

Designed to be configurable, scriptable, and pleasant to use, **`slurmq`** helps HPC administrators and users track GPU usage, enforce quotas, and generate reports.

```console
$ slurmq check

╭──────────────────── GPU Quota Report ────────────────────╮
│                                                          │
│   Cluster:  Stella HPC                                   │
│   User:     dedalus                                      │
│   QoS:      medium                                       │
│                                                          │
│   ████████████████████░░░░░░░░░░ 68.5%                   │
│                                                          │
│   Used:      342.5 GPU-hours                             │
│   Remaining: 157.5 GPU-hours                             │
│   Quota:     500 GPU-hours (rolling 30 days)             │
│                                                          │
╰──────────────────────────────────────────────────────────╯
```

## Features

- **Check quota** - See your GPU usage at a glance
- **Multi-cluster** - Switch between clusters with `--cluster`
- **Configurable** - TOML config files with env var overrides
- **Reports** - Generate usage reports in JSON, CSV, or rich tables
- **Monitoring** - Live dashboard with optional quota enforcement
- **Analytics** - Wait times, utilization stats, month-over-month trends
- **Scriptable** - JSON output, quiet mode, exit codes for automation

## Quick Start

```bash
# Install
uv tool install slurmq

# Initialize config
slurmq config init

# Check your quota
slurmq check
```

## Philosophy

slurmq follows the Unix philosophy:

- **Do one thing well** - GPU quota management
- **Composable** - Works with jq, cron, scripts
- **Configurable** - Defaults that work, overrides when you need them
- **No surprises** - Clear output, predictable behavior

## Next Steps

- [Installation](getting-started/installation.md) - Install slurmq on your system
- [Quick Start](getting-started/quickstart.md) - Get up and running in 5 minutes
- [Configuration](getting-started/configuration.md) - Set up your clusters

---

**For LLMs:**

- [`llms.txt`](https://dedalus-labs.github.io/slurmq/llms.txt)
- [`llms-full.txt`](https://dedalus-labs.github.io/slurmq/llms-full.txt)

**Viewing locally:** `uv sync --extra docs && uv run mkdocs serve` → [localhost:8000](http://127.0.0.1:8000)
