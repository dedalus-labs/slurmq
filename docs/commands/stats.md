# stats

Cluster-wide analytics with month-over-month comparison.

## Usage

```bash
slurmq stats [OPTIONS]
```

## Options

| Option                   | Short | Description                                            |
| ------------------------ | ----- | ------------------------------------------------------ |
| `--days`                 | `-d`  | Analysis period in days (default: 30)                  |
| `--compare/--no-compare` |       | Show month-over-month comparison (default: on)         |
| `--partition`            | `-p`  | Filter by partition(s) (repeatable)                    |
| `--qos`                  | `-q`  | Filter by QoS(s) (repeatable)                          |
| `--small-threshold`      |       | GPU-hours threshold for small/large jobs (default: 50) |

## Examples

### Basic usage

```bash
# Analyze the last 30 days with MoM comparison
slurmq stats
```

Output:

```
           GPU Utilization (Last 30 Days)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Partition    ┃ GPU Hours     ┃ Jobs       ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ gpu          │ 125.3k (+12%) │ 1,245 (-5%)│
│ gpu-large    │ 45.2k (+8%)   │ 234 (+15%) │
└──────────────┴───────────────┴────────────┘

      Wait Times - Small (≤50 GPU-h)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┓
┃ Partition    ┃ Median Wait┃ Wait > 6h ┃ Jobs  ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━┩
│ gpu          │ 15min (-8%)│ 2.1%      │ 1,100 │
│ gpu-large    │ 45min (+3%)│ 8.5%      │ 180   │
└──────────────┴────────────┴───────────┴───────┘

      Wait Times - Large (>50 GPU-h)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┓
┃ Partition    ┃ Median Wait┃ Wait > 6h ┃ Jobs  ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━┩
│ gpu          │ 2h15 (+15%)│ 25.0%     │ 145   │
│ gpu-large    │ 8h30 (-2%) │ 62.5%     │ 54    │
└──────────────┴────────────┴───────────┴───────┘
```

### Custom time range

```bash
# Last 14 days
slurmq stats --days 14

# Last 7 days, no comparison
slurmq stats --days 7 --no-compare
```

### Filter by partition or QoS

```bash
# Specific partitions
slurmq stats --partition gpu --partition gpu-large

# Specific QoS
slurmq stats --qos high-priority
```

### Custom job size threshold

```bash
# Jobs ≤25 GPU-hours are "small"
slurmq stats --small-threshold 25
```

### JSON output

```bash
slurmq --json stats
```

```json
{
  "period_days": 30,
  "current": {
    "gpu": {
      "all": {
        "job_count": 1245,
        "gpu_hours": 125300.5,
        "median_wait_hours": 0.75,
        "long_wait_pct": 12.5
      },
      "small": { ... },
      "large": { ... }
    }
  },
  "previous": { ... }
}
```

## Metrics explained

| Metric          | Description                                  |
| --------------- | -------------------------------------------- |
| **GPU Hours**   | Total GPU-hours consumed                     |
| **Jobs**        | Number of jobs completed                     |
| **Median Wait** | Median time from submission to start         |
| **Wait > 6h**   | Percentage of jobs waiting more than 6 hours |

## Use cases

- **Capacity planning** - Track utilization trends
- **SLA monitoring** - Watch wait time percentiles
- **QoS tuning** - Compare partition performance
- **Monthly reports** - Export JSON for dashboards
