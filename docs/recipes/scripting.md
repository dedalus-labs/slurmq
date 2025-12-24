# Scripting

Using slurmq in scripts and automation.

## JSON output

Always use `--json` for machine-readable output:

```bash
slurmq --json check
slurmq --json report
slurmq --json stats
```

## Parsing with jq

### Get specific fields

```bash
# Get remaining hours
slurmq --json check | jq '.remaining_gpu_hours'

# Get status
slurmq --json check | jq -r '.status'

# Check if exceeded
slurmq --json check | jq -e '.status == "exceeded"'
```

### Filter users

```bash
# Users over 80% usage
slurmq --json report | jq '.users[] | select(.usage_percentage > 80)'

# Users with active jobs
slurmq --json report | jq '.users[] | select(.active_jobs > 0)'

# Top 5 users by usage
slurmq --json report | jq '.users | sort_by(-.used_gpu_hours) | .[:5]'
```

### Extract for other tools

```bash
# Get user list for email
slurmq --json report | jq -r '.users[] | select(.status == "exceeded") | .user'

# CSV-like output
slurmq --json report | jq -r '.users[] | [.user, .used_gpu_hours, .status] | @csv'
```

## Exit codes

Use exit codes for conditionals:

```bash
# Check succeeds if quota OK
if slurmq --quiet check; then
  echo "Quota OK"
else
  echo "Quota problem"
fi
```

| Code | Meaning                         |
| ---- | ------------------------------- |
| 0    | Success / quota OK              |
| 1    | Error                           |
| 2    | Quota exceeded (with `--quiet`) |

## Python integration

```python
import json
import subprocess

def get_quota():
    """Get quota info as dict."""
    result = subprocess.run(
        ["slurmq", "--json", "check"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)

def check_quota_ok() -> bool:
    """Return True if quota is not exceeded."""
    try:
        info = get_quota()
        return info["status"] != "exceeded"
    except subprocess.CalledProcessError:
        return False

# Usage
if check_quota_ok():
    submit_training_job()
else:
    print("Quota exceeded!")
```

## Environment variables

Override config via environment:

```bash
# In scripts
export SLURMQ_DEFAULT_CLUSTER=stellar
export SLURMQ_CONFIG=/etc/slurmq/prod.toml

# One-liner
SLURMQ_DEFAULT_CLUSTER=stellar slurmq check
```

## Error handling

Handle errors gracefully:

```bash
#!/bin/bash
set -e

# Capture output and exit code
if output=$(slurmq --json check 2>&1); then
  remaining=$(echo "$output" | jq '.remaining_gpu_hours')
  echo "Remaining: $remaining hours"
else
  echo "Error checking quota: $output" >&2
  exit 1
fi
```

## Parallel checks

Check multiple clusters in parallel:

```bash
#!/bin/bash

clusters=(stella stellar traverse)

for cluster in "${clusters[@]}"; do
  slurmq --cluster "$cluster" --json check &
done | jq -s '.'

wait
```
