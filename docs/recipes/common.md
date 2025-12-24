# Common Patterns

Recipes for common slurmq usage patterns.

## Check before submitting

Block job submission if quota exceeded:

```bash
#!/bin/bash
# submit-job.sh

# Check quota first
if ! slurmq --quiet check; then
  echo "Quota exceeded! Cannot submit job."
  exit 1
fi

# Submit job
sbatch my_job.sh
```

## Get remaining quota

Extract remaining hours for scripts:

```bash
remaining=$(slurmq --json check | jq '.remaining_gpu_hours')
echo "You have $remaining GPU-hours remaining"

# Check if enough for a job
if (( $(echo "$remaining < 10" | bc -l) )); then
  echo "Warning: Less than 10 hours remaining!"
fi
```

## Multi-cluster workflow

Switch between clusters:

```bash
# Check all clusters
for cluster in stella stellar traverse; do
  echo "=== $cluster ==="
  slurmq --cluster $cluster check
done
```

## Export weekly report

Generate CSV report for spreadsheets:

```bash
#!/bin/bash
# weekly-report.sh

DATE=$(date +%Y-%m-%d)
OUTPUT_DIR="/shared/reports"

slurmq report --format csv --output "$OUTPUT_DIR/usage-$DATE.csv"
```

## Slack notification

Send alerts to Slack:

```bash
#!/bin/bash
# check-and-alert.sh

WEBHOOK_URL="https://hooks.slack.com/services/..."

# Check for exceeded users
exceeded=$(slurmq --json report | jq '[.users[] | select(.status == "exceeded")] | length')

if [ "$exceeded" -gt 0 ]; then
  curl -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"warning: $exceeded users have exceeded GPU quota\"}" \
    "$WEBHOOK_URL"
fi
```

## Pre-commit hook

Check quota before git push (for ML repos):

```bash
#!/bin/bash
# .git/hooks/pre-push

# Only check if on training branch
branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$branch" == "train-"* ]]; then
  if ! slurmq --quiet check; then
    echo "Quota exceeded! Training jobs may fail."
    read -p "Push anyway? (y/N) " confirm
    [[ "$confirm" != "y" ]] && exit 1
  fi
fi
```

## Dashboard integration

Export metrics for Grafana/Prometheus:

```bash
#!/bin/bash
# metrics.sh - Run every minute via cron

METRICS_FILE="/var/lib/prometheus/slurmq.prom"

# Get stats
stats=$(slurmq --json report 2>/dev/null)

if [ $? -eq 0 ]; then
  # Generate Prometheus metrics
  echo "# HELP slurmq_users_total Total number of users"
  echo "# TYPE slurmq_users_total gauge"
  echo "slurmq_users_total $(echo $stats | jq '.users | length')"

  echo "# HELP slurmq_exceeded_users Users over quota"
  echo "# TYPE slurmq_exceeded_users gauge"
  echo "slurmq_exceeded_users $(echo $stats | jq '[.users[] | select(.status == \"exceeded\")] | length')"
fi > "$METRICS_FILE"
```

## Job wrapper

Wrap sbatch to check quota first:

```bash
#!/bin/bash
# /usr/local/bin/sbatch-safe

# Check quota
remaining=$(slurmq --json check 2>/dev/null | jq -r '.remaining_gpu_hours // 0')

if (( $(echo "$remaining <= 0" | bc -l) )); then
  echo "Error: GPU quota exceeded. Cannot submit job." >&2
  exit 1
fi

# Pass through to real sbatch
exec /usr/bin/sbatch "$@"
```

Then alias: `alias sbatch=/usr/local/bin/sbatch-safe`
