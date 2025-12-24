# report

Generate usage reports for all users.

## Usage

```bash
slurmq report [OPTIONS]
```

## Options

| Option        | Short | Description                                    |
| ------------- | ----- | ---------------------------------------------- |
| `--format`    | `-f`  | Output format: rich, json, csv (default: rich) |
| `--output`    | `-o`  | Output file path                               |
| `--qos`       | `-q`  | QoS to report on (overrides config)            |
| `--account`   | `-a`  | Account to report on (overrides config)        |
| `--partition` | `-p`  | Partition to report on (overrides config)      |

## Examples

### Basic usage

```bash
slurmq report
```

Output:

```console
        GPU Usage Report: Stella (normal)
┏━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ User    ┃ Used (GPU-h)┃ Remaining ┃ Usage % ┃ Status ┃ Active ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ alice   │ 487.5       │ 12.5      │ 98%     │ !      │ 3      │
│ bob     │ 342.0       │ 158.0     │ 68%     │ ok     │ 1      │
│ charlie │ 125.5       │ 374.5     │ 25%     │ ok     │ -      │
└─────────┴─────────────┴───────────┴─────────┴────────┴────────┘

Total users: 3
```

### Export formats

```bash
# JSON
slurmq report --format json

# CSV (for spreadsheets)
slurmq report --format csv

# Save to file
slurmq report --format csv --output usage.csv
```

### Filter by QoS/account

```bash
# Specific QoS
slurmq report --qos high-priority

# Specific account
slurmq report --account research-gpu
```

## JSON output

```json
{
  "cluster": "Stella",
  "qos": "normal",
  "users": [
    {
      "user": "alice",
      "used_gpu_hours": 487.5,
      "quota_limit": 500,
      "remaining_gpu_hours": 12.5,
      "usage_percentage": 97.5,
      "status": "warning",
      "active_jobs": 3,
      "total_jobs": 45
    }
  ]
}
```

## CSV output

```csv
user,used_gpu_hours,quota_limit,remaining_gpu_hours,usage_percentage,status,active_jobs,total_jobs
alice,487.5,500,12.5,97.5,warning,3,45
bob,342.0,500,158.0,68.4,ok,1,23
charlie,125.5,500,374.5,25.1,ok,0,12
```

## Use cases

- **Weekly reports** - Track who's using resources
- **Capacity planning** - Identify heavy users
- **Billing** - Export CSV for chargeback
- **Compliance** - Audit quota enforcement
