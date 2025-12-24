# Commands Overview

slurmq provides several commands for managing GPU quotas.

## User Commands

| Command                       | Description                     |
| ----------------------------- | ------------------------------- |
| [`check`](check.md)           | Check your GPU quota usage      |
| [`efficiency`](efficiency.md) | Analyze job resource efficiency |

## Admin Commands

| Command                 | Description                          |
| ----------------------- | ------------------------------------ |
| [`report`](report.md)   | Generate usage reports for all users |
| [`stats`](stats.md)     | Cluster analytics and wait times     |
| [`monitor`](monitor.md) | Live monitoring with enforcement     |

## Configuration Commands

| Command                                 | Description               |
| --------------------------------------- | ------------------------- |
| [`config init`](config.md#init)         | Interactive setup wizard  |
| [`config show`](config.md#show)         | Display current config    |
| [`config path`](config.md#path)         | Show config file location |
| [`config validate`](config.md#validate) | Validate config file      |

## Global Options

These options work with all commands:

```
--cluster, -c    Cluster to use (overrides default_cluster)
--json           Output as JSON
--yaml           Output as YAML
--verbose, -v    Verbose output
--quiet, -q      Suppress non-error output
--config         Path to config file
--version        Show version
--help           Show help
```

## Exit Codes

| Code | Meaning                         |
| ---- | ------------------------------- |
| 0    | Success                         |
| 1    | Error (config, SLURM, etc.)     |
| 2    | Quota exceeded (with `--quiet`) |
