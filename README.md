# slurmq

GPU quota management for Slurm clusters.

```console
$ slurmq check

╭──────────────────── GPU Quota Report ────────────────────╮
│                                                          │
│   User:     dedalus                                      │
│   QoS:      medium                                       │
│   Cluster:  Stella HPC                                   │
│                                                          │
│   ████████████████████░░░░░░░░░░ 68.5%                   │
│                                                          │
│   Used:      342.5 GPU-hours                             │
│   Remaining: 157.5 GPU-hours                             │
│   Quota:     500 GPU-hours (rolling 30 days)             │
│                                                          │
╰──────────────────────────────────────────────────────────╯
```

## Install

```bash
uv tool install slurmq
```

## Setup

```bash
slurmq config init       # interactive wizard
slurmq config show       # verify settings
slurmq config validate   # check syntax before deploy
```

Config resolution order:

1. `SLURMQ_CONFIG` env var
2. `~/.config/slurmq/config.toml` (user)
3. `/etc/slurmq/config.toml` (system-wide)

```toml
default_cluster = "stella"

[clusters.stella]
name = "Stella HPC"
account = "research"
qos = ["low", "medium"]
quota_limit = 500        # GPU-hours
rolling_window_days = 30
```

## Commands

### check

```bash
slurmq check                  # current user
slurmq check --user alice     # specific user
slurmq check --cluster other  # different cluster
slurmq check --forecast       # usage projection
slurmq --json check           # machine-readable
slurmq --quiet check          # silent on success (for scripts)
```

### efficiency

Analyze job resource efficiency (like `seff`).

```bash
slurmq efficiency 12345
```

Flags low efficiency: CPU < 30%, Memory < 20%.

### report

Generate usage reports (admin).

```bash
slurmq report                          # table view
slurmq report --format csv -o out.csv
```

### monitor

Real-time monitoring with optional enforcement (admin).

```bash
slurmq monitor                # live dashboard, 30s refresh
slurmq monitor --interval 10
slurmq monitor --once         # single check, for cron
slurmq monitor --enforce      # cancel jobs over quota
```

### stats

Cluster-wide analytics with month-over-month comparison.

```bash
slurmq stats                          # GPU utilization + wait times
slurmq stats --days 14                # custom period
slurmq stats --no-compare             # skip MoM comparison
slurmq stats -p gpu -p gpu-large      # specific partitions
slurmq stats --small-threshold 25     # custom job size threshold
slurmq --json stats                   # machine-readable
```

Shows:

- GPU utilization by partition/QoS
- Wait time analysis (median, % jobs waiting > 6h)
- Small vs large job breakdown
- Month-over-month trends

## Enforcement

Cancel jobs automatically when users exceed quota.

```toml
[enforcement]
enabled = true
dry_run = true            # preview mode
grace_period_hours = 24   # warn before cancel
exempt_users = ["admin"]
exempt_job_prefixes = ["checkpoint_"]
```

Run with `slurmq monitor --enforce`. Disable `dry_run` when ready.

Grace period: users exceeding quota get a warning window before jobs are cancelled.

## Job States

Problematic states are highlighted:

| State | Meaning       |
| ----- | ------------- |
| `OOM` | Out of Memory |
| `TO`  | Timeout       |
| `NF`  | Node Failure  |
| `F`   | Failed        |
| `PR`  | Preempted     |

## Scripting

```bash
# check quota status
if slurmq --json check | jq -e '.status == "exceeded"' > /dev/null; then
  echo "Quota exceeded"
fi

# cron: enforce every 5 minutes (quiet mode)
*/5 * * * * slurmq --quiet monitor --once --enforce >> /var/log/slurmq.log 2>&1
```

## Documentation

**Online:** [dedalus-labs.github.io/slurmq](https://dedalus-labs.github.io/slurmq)

**For LLMs:** [llms.txt](https://dedalus-labs.github.io/slurmq/llms.txt) | [llms-full.txt](https://dedalus-labs.github.io/slurmq/llms-full.txt)

**Locally:**

```bash
uv sync --extra docs
uv run mkdocs serve
```

## Development

```bash
git clone https://github.com/dedalus-labs/slurmq.git && cd slurmq
uv sync --all-extras
uv run pytest
uv run ruff check
uv run ty check
```

## License

MIT
