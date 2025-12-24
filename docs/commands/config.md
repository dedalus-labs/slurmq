# config

Manage slurmq configuration.

## Subcommands

### init

Interactive configuration wizard.

```bash
slurmq config init
```

Creates `~/.config/slurmq/config.toml` with your cluster settings.

The wizard prompts for:

1. Cluster name
2. Account
3. QoS list
4. Quota limit
5. Rolling window days

### show

Display current configuration.

```bash
slurmq config show
```

Shows the merged configuration from all sources (env vars, config file, defaults).

### path

Show config file location.

```bash
slurmq config path
```

Output:

```
Config file: /home/user/.config/slurmq/config.toml
Status: exists
```

### validate

Validate configuration file.

```bash
slurmq config validate
```

Checks for:

- TOML syntax errors
- Invalid threshold values (must be 0-1)
- Missing cluster definitions
- Unknown configuration keys
- Logical errors (e.g., warning > critical threshold)

Example output:

```
✓ Config file is valid: /home/user/.config/slurmq/config.toml
```

Or with errors:

```
✗ Config validation failed:
  - monitoring.warning_threshold (1.5) must be between 0 and 1
  - default_cluster "nonexistent" not found in clusters
```

### set

Set a configuration value.

```bash
slurmq config set <KEY> <VALUE>
```

Examples:

```bash
# Set default cluster
slurmq config set default_cluster stellar

# Set nested value
slurmq config set monitoring.warning_threshold 0.9
```

## Examples

### Initial setup

```bash
# Create config interactively
slurmq config init

# Verify
slurmq config show
slurmq config validate
```

### Check config location

```bash
$ slurmq config path
Config file: /home/user/.config/slurmq/config.toml
Status: exists
```

### Debug configuration

```bash
# See what config slurmq is actually using
slurmq config show

# Check for errors
slurmq config validate

# See where it's loading from
SLURMQ_CONFIG=/tmp/test.toml slurmq config path
```
