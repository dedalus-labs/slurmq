# Quick Start

Get up and running with slurmq in 5 minutes.

## 1. Initialize configuration

Run the interactive setup wizard:

```bash
slurmq config init
```

This creates `~/.config/slurmq/config.toml` with your cluster settings.

!!! tip "Minimal config"
You can also create a minimal config manually:

    ```toml
    default_cluster = "mycluster"

    [clusters.mycluster]
    name = "My Cluster"
    qos = ["normal"]
    quota_limit = 500
    ```

## 2. Check your quota

```bash
slurmq check
```

That's it! You'll see your current GPU usage and remaining quota.

## 3. Useful variations

```bash
# Check another user's quota
slurmq check --user alice

# Use a different QoS
slurmq check --qos high-priority

# Get JSON output for scripting
slurmq --json check

# Show forecast of when quota frees up
slurmq check --forecast
```

## 4. Admin commands

If you're an administrator:

```bash
# See all users' usage
slurmq report

# Live monitoring dashboard
slurmq monitor

# Cluster analytics
slurmq stats
```

## Next steps

- [Configuration](configuration.md) - Full config file reference
- [Commands](../commands/index.md) - All available commands
- [Recipes](../recipes/common.md) - Common usage patterns
