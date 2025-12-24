# efficiency

Analyze job resource efficiency (inspired by Slurm's `seff`).

## Usage

```bash
slurmq efficiency <JOB_ID>
```

## Arguments

| Argument | Description             |
| -------- | ----------------------- |
| `JOB_ID` | Slurm job ID to analyze |

## Examples

### Basic usage

```bash
slurmq efficiency 12345678
```

Output:

```console
╭──────────────── Job Efficiency Report ────────────────╮
│                                                       │
│  Job ID:     12345678                                 │
│  Job Name:   train_model                              │
│  User:       alice                                    │
│  Account:    research                                 │
│  State:      COMPLETED                                │
│                                                       │
│  CPU Efficiency:    78.5%  ████████░░                 │
│  Memory Efficiency: 45.2%  █████░░░░░  ! Low          │
│                                                       │
│  Cores requested:   32                                │
│  CPU time used:     12h 30m (of 16h allocated)        │
│                                                       │
│  Memory requested:  128GB                             │
│  Memory used:       58GB (peak)                       │
│                                                       │
╰───────────────────────────────────────────────────────╯
```

## Efficiency thresholds

| Metric | Good | Warning | Low  |
| ------ | ---- | ------- | ---- |
| CPU    | ≥50% | 30-50%  | <30% |
| Memory | ≥30% | 20-30%  | <20% |

## Use cases

- **Debugging** - Why did my job fail (OOM)?
- **Optimization** - Am I requesting too many resources?
- **Education** - Help users right-size their jobs

## Tips for improving efficiency

### CPU efficiency low?

- Your job may be I/O bound
- Consider fewer cores with faster storage
- Check for serial bottlenecks in your code

### Memory efficiency low?

- Request less memory in your submission
- Use `--mem-per-cpu` instead of `--mem`
- Profile your application's memory usage

## JSON output

```bash
slurmq --json efficiency 12345678
```

```json
{
  "job_id": "12345678",
  "job_name": "train_model",
  "user": "alice",
  "state": "COMPLETED",
  "cpu_efficiency": 78.5,
  "memory_efficiency": 45.2,
  "cores_requested": 32,
  "cpu_time_used_seconds": 45000,
  "memory_requested_gb": 128,
  "memory_used_gb": 58
}
```
