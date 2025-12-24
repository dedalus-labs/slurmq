# check

Check GPU quota usage for a user.

## Usage

```bash
slurmq check [OPTIONS]
```

## Options

| Option        | Short | Description                           |
| ------------- | ----- | ------------------------------------- |
| `--user`      | `-u`  | User to check (default: current user) |
| `--qos`       | `-q`  | QoS to check (overrides config)       |
| `--account`   | `-a`  | Account to check (overrides config)   |
| `--partition` | `-p`  | Partition to check (overrides config) |
| `--forecast`  | `-f`  | Show quota forecast                   |

## Examples

### Basic usage

```bash
# Check your own quota
slurmq check

# Check another user's quota
slurmq check --user alice
```

### Override filters

```bash
# Check a specific QoS
slurmq check --qos high-priority

# Check a specific account
slurmq check --account research-gpu

# Combine multiple overrides
slurmq check --qos normal --partition gpu-large
```

### Output formats

```bash
# Rich terminal output (default)
slurmq check

# JSON for scripting
slurmq --json check

# YAML output
slurmq --yaml check
```

### Forecast

Show when quota will free up:

```bash
slurmq check --forecast
```

```
╭─────────── Quota Forecast ───────────╮
│  Time     Available    % Available   │
│  +12h     78.5         15.7%         │
│  +24h     125.0        25.0%         │
│  +72h     312.5        62.5%         │
│  +168h    500.0        100.0%        │
╰──────────────────────────────────────╯
```

## JSON output

```json
{
  "user": "dedalus",
  "qos": "normal",
  "used_gpu_hours": 342.5,
  "quota_limit": 500,
  "remaining_gpu_hours": 157.5,
  "usage_percentage": 68.5,
  "status": "ok",
  "rolling_window_days": 30,
  "active_jobs": 2
}
```

## Exit codes

| Code | Condition                       |
| ---- | ------------------------------- |
| 0    | Success                         |
| 1    | Error                           |
| 2    | Quota exceeded (with `--quiet`) |

## Scripting

```bash
# Check if quota exceeded
if slurmq --json check | jq -e '.status == "exceeded"' > /dev/null; then
  echo "Quota exceeded!"
  exit 1
fi

# Get remaining hours
remaining=$(slurmq --json check | jq '.remaining_gpu_hours')
echo "You have $remaining GPU-hours remaining"
```
