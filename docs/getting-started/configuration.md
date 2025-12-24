# Configuration

slurmq uses a layered configuration system with these priorities (highest first):

1. **CLI flags** - `--qos`, `--account`, `--cluster`
2. **Environment variables** - `SLURMQ_*`
3. **Config file** - `~/.config/slurmq/config.toml`
4. **System config** - `/etc/slurmq/config.toml`
5. **Defaults**

## Config file locations

slurmq looks for config files in this order:

1. `$SLURMQ_CONFIG` (env var override)
2. `~/.config/slurmq/config.toml` (user config)
3. `/etc/slurmq/config.toml` (system-wide)

## Full config example

```toml
# ~/.config/slurmq/config.toml

# Default cluster to use when --cluster is not specified
default_cluster = "stella"

# Cluster profiles
[clusters.stella]
name = "Stella HPC GPU Cluster"
account = "research-group"
qos = ["high-priority", "normal", "low"]
partitions = ["gpu", "gpu-large"]
quota_limit = 500                 # GPU-hours per user
rolling_window_days = 30          # Rolling window for quota

[clusters.stellar]
name = "Stellar"
account = "astro"
qos = ["standard"]
partitions = ["gpu"]
quota_limit = 200

# Monitoring thresholds
[monitoring]
check_interval_minutes = 30
warning_threshold = 0.8           # Warn at 80% usage
critical_threshold = 1.0          # Critical at 100%

# Quota enforcement (admin)
[enforcement]
enabled = false                   # Must explicitly enable
dry_run = true                    # Preview mode - no actual cancels
grace_period_hours = 24           # Warning before cancel
cancel_order = "lifo"             # "lifo" or "fifo"
exempt_users = ["admin", "root"]
exempt_job_prefixes = ["checkpoint_", "debug_"]

# Email notifications (optional)
[email]
enabled = false
sender = "hpc-alerts@example.edu"
domain = "example.edu"            # User email domain
subject_prefix = "[Stella HPC-GPU]"
smtp_host = "smtp.example.edu"
smtp_port = 587
smtp_user_env = "SLURMQ_SMTP_USER"
smtp_pass_env = "SLURMQ_SMTP_PASS"

# Display preferences
[display]
color = true                      # Respects NO_COLOR env
output_format = "rich"            # "rich", "plain", "json"

# Cache settings
[cache]
enabled = true
ttl_minutes = 60
directory = ""                    # Default: ~/.cache/slurmq/
```

## Environment variables

All config values can be overridden with environment variables using the `SLURMQ_` prefix:

```bash
# Override default cluster
export SLURMQ_DEFAULT_CLUSTER=stellar

# Override nested values with double underscore
export SLURMQ_MONITORING__WARNING_THRESHOLD=0.9
export SLURMQ_ENFORCEMENT__DRY_RUN=false

# Point to a different config file
export SLURMQ_CONFIG=/path/to/config.toml
```

## CLI flag overrides

Most config values can be overridden per-command:

```bash
# Override cluster
slurmq --cluster stellar check

# Override QoS, account, partition
slurmq check --qos high-priority --account mygroup --partition gpu-large

# Override output format
slurmq --json check
slurmq --yaml check
```

## Multiple clusters

Define multiple clusters and switch between them:

```toml
default_cluster = "stella"

[clusters.stella]
name = "Stella HPC"
quota_limit = 500
qos = ["normal"]

[clusters.traverse]
name = "Traverse"
quota_limit = 1000
qos = ["gpu"]
```

```bash
slurmq check                     # Uses stella (default)
slurmq --cluster traverse check
```

## Validating config

Check your config file for errors:

```bash
slurmq config validate
```

This catches:

- TOML syntax errors
- Invalid threshold values
- Missing cluster definitions
- Unknown config keys
