# Environment Variables

All configuration values can be overridden with environment variables.

## Naming convention

Environment variables use the `SLURMQ_` prefix with double underscores for nesting:

```plaintext
SLURMQ_<KEY>
SLURMQ_<SECTION>__<KEY>
```

## Available variables

### Core settings

| Variable                 | Description          | Example                   |
| ------------------------ | -------------------- | ------------------------- |
| `SLURMQ_CONFIG`          | Path to config file  | `/etc/slurmq/config.toml` |
| `SLURMQ_DEFAULT_CLUSTER` | Default cluster name | `stella`                  |

### Monitoring

| Variable                                    | Description        | Default |
| ------------------------------------------- | ------------------ | ------- |
| `SLURMQ_MONITORING__CHECK_INTERVAL_MINUTES` | Check interval     | `30`    |
| `SLURMQ_MONITORING__WARNING_THRESHOLD`      | Warn at this %     | `0.8`   |
| `SLURMQ_MONITORING__CRITICAL_THRESHOLD`     | Critical at this % | `1.0`   |

### Enforcement

| Variable                                 | Description        | Default |
| ---------------------------------------- | ------------------ | ------- |
| `SLURMQ_ENFORCEMENT__ENABLED`            | Enable enforcement | `false` |
| `SLURMQ_ENFORCEMENT__DRY_RUN`            | Preview mode       | `true`  |
| `SLURMQ_ENFORCEMENT__GRACE_PERIOD_HOURS` | Warning window     | `24`    |
| `SLURMQ_ENFORCEMENT__CANCEL_ORDER`       | `lifo` or `fifo`   | `lifo`  |

### Display

| Variable                        | Description               | Default |
| ------------------------------- | ------------------------- | ------- |
| `SLURMQ_DISPLAY__COLOR`         | Enable colors             | `true`  |
| `SLURMQ_DISPLAY__OUTPUT_FORMAT` | `rich`, `plain`, `json`   | `rich`  |
| `NO_COLOR`                      | Disable colors (standard) | -       |

### Email

| Variable                  | Description                | Default |
| ------------------------- | -------------------------- | ------- |
| `SLURMQ_EMAIL__ENABLED`   | Enable email               | `false` |
| `SLURMQ_EMAIL__SENDER`    | From address               | -       |
| `SLURMQ_EMAIL__SMTP_HOST` | SMTP server                | -       |
| `SLURMQ_EMAIL__SMTP_PORT` | SMTP port                  | `587`   |
| `SLURMQ_SMTP_USER`        | SMTP username (via config) | -       |
| `SLURMQ_SMTP_PASS`        | SMTP password (via config) | -       |

### Cache

| Variable                    | Description     | Default            |
| --------------------------- | --------------- | ------------------ |
| `SLURMQ_CACHE__ENABLED`     | Enable caching  | `true`             |
| `SLURMQ_CACHE__TTL_MINUTES` | Cache TTL       | `60`               |
| `SLURMQ_CACHE__DIRECTORY`   | Cache directory | `~/.cache/slurmq/` |

## Examples

### Override default cluster

```bash
export SLURMQ_DEFAULT_CLUSTER=stellar
slurmq check
```

### Disable colors

```bash
export NO_COLOR=1
slurmq check
```

### Use different config

```bash
export SLURMQ_CONFIG=/etc/slurmq/production.toml
slurmq check
```

### Enable enforcement in CI

```bash
export SLURMQ_ENFORCEMENT__ENABLED=true
export SLURMQ_ENFORCEMENT__DRY_RUN=false
slurmq monitor --once --enforce
```

## Priority

Environment variables override config file values:

1. CLI flags (highest)
2. Environment variables
3. Config file
4. System config (`/etc/slurmq/config.toml`)
5. Defaults (lowest)

## Boolean values

For boolean environment variables, these values are truthy:

- `true`, `True`, `TRUE`
- `1`
- `yes`, `Yes`, `YES`
- `on`, `On`, `ON`

Everything else is falsy.
