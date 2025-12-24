# Config File Reference

Complete reference for `config.toml`.

## File locations

slurmq searches for config files in this order:

1. `$SLURMQ_CONFIG` (environment variable)
2. `~/.config/slurmq/config.toml` (user)
3. `/etc/slurmq/config.toml` (system)

## Complete example

```toml
# Default cluster when --cluster is not specified
default_cluster = "stella"

# Cluster definitions
[clusters.stella]
name = "Stella HPC GPU Cluster"
account = "research-group"
qos = ["high-priority", "normal", "low"]
partitions = ["gpu", "gpu-large"]
quota_limit = 500
rolling_window_days = 30

[clusters.stellar]
name = "Stellar"
account = "astro"
qos = ["standard"]
partitions = ["gpu"]
quota_limit = 200
rolling_window_days = 30

# Monitoring settings
[monitoring]
check_interval_minutes = 30
warning_threshold = 0.8
critical_threshold = 1.0

# Quota enforcement
[enforcement]
enabled = false
dry_run = true
grace_period_hours = 24
cancel_order = "lifo"
exempt_users = ["admin", "root"]
exempt_job_prefixes = ["checkpoint_", "debug_"]

# Email notifications
[email]
enabled = false
sender = "hpc-alerts@example.edu"
domain = "example.edu"
subject_prefix = "[Stella HPC-GPU]"
smtp_host = "smtp.example.edu"
smtp_port = 587
smtp_user_env = "SLURMQ_SMTP_USER"
smtp_pass_env = "SLURMQ_SMTP_PASS"

# Display preferences
[display]
color = true
output_format = "rich"

# Cache settings
[cache]
enabled = true
ttl_minutes = 60
directory = ""
```

## Section reference

### `default_cluster`

```toml
default_cluster = "stella"
```

Name of the cluster to use when `--cluster` is not specified.

### `[clusters.<name>]`

Define cluster profiles. You can have multiple clusters.

| Key                   | Type   | Required | Description               |
| --------------------- | ------ | -------- | ------------------------- |
| `name`                | string | No       | Display name              |
| `account`             | string | No       | Slurm account             |
| `qos`                 | array  | No       | List of QoS names         |
| `partitions`          | array  | No       | List of partitions        |
| `quota_limit`         | int    | Yes      | GPU-hours quota           |
| `rolling_window_days` | int    | No       | Window size (default: 30) |

### `[monitoring]`

| Key                      | Type  | Default | Description                 |
| ------------------------ | ----- | ------- | --------------------------- |
| `check_interval_minutes` | int   | 30      | Monitoring interval         |
| `warning_threshold`      | float | 0.8     | Warn at this percentage     |
| `critical_threshold`     | float | 1.0     | Critical at this percentage |

### `[enforcement]`

| Key                   | Type   | Default | Description                   |
| --------------------- | ------ | ------- | ----------------------------- |
| `enabled`             | bool   | false   | Enable enforcement            |
| `dry_run`             | bool   | true    | Preview mode                  |
| `grace_period_hours`  | int    | 24      | Warning window                |
| `cancel_order`        | string | "lifo"  | "lifo" or "fifo"              |
| `exempt_users`        | array  | []      | Skip these users              |
| `exempt_job_prefixes` | array  | []      | Skip jobs with these prefixes |

### `[email]`

| Key              | Type   | Default | Description          |
| ---------------- | ------ | ------- | -------------------- |
| `enabled`        | bool   | false   | Enable email         |
| `sender`         | string | -       | From address         |
| `domain`         | string | -       | User email domain    |
| `subject_prefix` | string | ""      | Email subject prefix |
| `smtp_host`      | string | -       | SMTP server          |
| `smtp_port`      | int    | 587     | SMTP port            |
| `smtp_user_env`  | string | -       | Env var for username |
| `smtp_pass_env`  | string | -       | Env var for password |

### `[display]`

| Key             | Type   | Default | Description           |
| --------------- | ------ | ------- | --------------------- |
| `color`         | bool   | true    | Enable colors         |
| `output_format` | string | "rich"  | Default output format |

### `[cache]`

| Key           | Type   | Default | Description     |
| ------------- | ------ | ------- | --------------- |
| `enabled`     | bool   | true    | Enable caching  |
| `ttl_minutes` | int    | 60      | Cache TTL       |
| `directory`   | string | ""      | Cache directory |

## Validation

Check your config for errors:

```bash
slurmq config validate
```

## Minimal config

The smallest valid config:

```toml
default_cluster = "mycluster"

[clusters.mycluster]
quota_limit = 500
```
