# Exit Codes

slurmq uses standard exit codes for scripting.

## Exit code reference

| Code | Meaning        | When                                   |
| ---- | -------------- | -------------------------------------- |
| 0    | Success        | Command completed successfully         |
| 1    | Error          | Configuration error, Slurm error, etc. |
| 2    | Quota exceeded | With `--quiet` flag only               |

## Usage in scripts

### Check success

```bash
if slurmq check; then
  echo "Quota check passed"
else
  echo "Quota check failed"
fi
```

### Check specific codes

```bash
slurmq --quiet check
case $? in
  0) echo "Quota OK" ;;
  1) echo "Error running check" ;;
  2) echo "Quota exceeded" ;;
esac
```

### Guard job submission

```bash
#!/bin/bash
set -e

# This will exit 2 if quota exceeded
slurmq --quiet check

# Only reached if quota OK
sbatch my_job.sh
```

## Quiet mode

The `--quiet` flag:

- Suppresses normal output
- Returns exit code 2 for exceeded quota
- Still shows errors on stderr

```bash
# Silent check
slurmq --quiet check
echo "Exit code: $?"

# Capture errors only
if ! slurmq --quiet check 2>/dev/null; then
  echo "Problem detected"
fi
```

## Error messages

Errors are always written to stderr:

```bash
# Separate stdout and stderr
slurmq check > /tmp/output.txt 2> /tmp/errors.txt
```

## JSON error output

With `--json`, errors are also JSON:

```bash
slurmq --json check
```

```json
{
  "error": "No cluster specified and no default_cluster set"
}
```

## Best practices

1. **Use `--quiet` for scripts** - Clean exit codes without parsing output
2. **Check exit codes explicitly** - Don't assume success
3. **Capture stderr** - Errors go there
4. **Use `set -e`** - Exit on first error in shell scripts
