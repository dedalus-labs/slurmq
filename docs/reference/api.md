# API Reference

Python API for programmatic usage.

## Core modules

### Configuration

::: slurmq.core.config.SlurmqConfig
    options:
      show_source: false
      members:
        - clusters
        - default_cluster
        - monitoring
        - enforcement

### Quota checking

::: slurmq.core.quota.QuotaChecker
    options:
      show_source: false

::: slurmq.core.quota.JobRecord
    options:
      show_source: false

::: slurmq.core.quota.UsageReport
    options:
      show_source: false

## Usage example

```python
from slurmq.core.config import load_config
from slurmq.core.quota import QuotaChecker

# Load config
config = load_config()
cluster = config.clusters[config.default_cluster]

# Check quota
checker = QuotaChecker(cluster)
report = checker.get_user_usage("alice")

print(f"Used: {report.used_hours:.1f} GPU-hours")
print(f"Remaining: {report.remaining_hours:.1f} GPU-hours")
```

