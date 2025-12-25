# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Cluster statistics and analytics commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from statistics import median
import subprocess
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table
import typer


if TYPE_CHECKING:
    from slurmq.cli.main import CLIContext
    from slurmq.core.config import ClusterConfig

console = Console()

# Constants for display and thresholds
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
MIN_WAIT_SECONDS = 600  # 10 minutes
LONG_WAIT_HOURS = 6
MAX_DAYS_FOR_WEEKLY = 6


@dataclass
class JobStats:
    """Parsed job statistics from sacct."""

    n_gpus: int
    elapsed_h: float
    gpu_hours: float
    wait_hours: float
    start_time: int
    partition: str
    qos: str
    group: str = ""  # Aggregation group (partition or QoS name)


@dataclass
class PartitionStats:
    """Statistics for a single partition/QoS."""

    name: str
    job_count: int
    gpu_hours: float
    median_wait_hours: float
    long_wait_count: int  # Jobs with wait > 6h
    long_wait_pct: float


@dataclass
class PeriodStats:
    """Stats for a time period, with optional comparison."""

    current: list[PartitionStats]
    previous: list[PartitionStats] | None = None


def fetch_partition_data(
    partition: str | None, qos: str | None, start_date: str, end_date: str, account: str | None = None
) -> list[JobStats]:
    """Fetch job data from sacct for a partition/QoS."""
    cmd = [
        "sacct",
        "-X",  # Allocations only
        "-S",
        start_date,
        "-E",
        end_date,
        "--allusers",
        "--json",
    ]

    if partition:
        cmd.append(f"--partition={partition}")
    if qos:
        cmd.append(f"--qos={qos}")
    if account:
        cmd.append(f"--account={account}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603 - sacct args from config
        data = json.loads(result.stdout)
        return parse_jobs(data)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []


def parse_jobs(data: dict) -> list[JobStats]:
    """Parse sacct JSON output into job records."""
    jobs = []
    for job in data.get("jobs", []):
        n_gpus = 0
        for alloc in job.get("tres", {}).get("allocated", []):
            if alloc.get("type") == "gres" and alloc.get("name") == "gpu":
                n_gpus += int(alloc.get("count", 0))

        start_time = job.get("time", {}).get("start", 0)
        submit_time = job.get("time", {}).get("submission", 0)
        elapsed = job.get("time", {}).get("elapsed", 0)

        # Skip jobs with no GPUs or very short runtime (< 10min)
        if n_gpus == 0 or elapsed < MIN_WAIT_SECONDS:
            continue

        wait_time = start_time - submit_time if start_time and submit_time else 0

        # Skip jobs with unreasonable wait times (> 31 days)
        if wait_time > 3600 * 24 * 31:
            continue

        jobs.append(
            JobStats(
                n_gpus=n_gpus,
                elapsed_h=elapsed / 3600,
                gpu_hours=(n_gpus * elapsed) / 3600,
                wait_hours=wait_time / 3600,
                start_time=start_time,
                partition=job.get("partition", "unknown"),
                qos=job.get("qos", "unknown"),
            )
        )

    return jobs


def calculate_partition_stats(jobs: list[JobStats], name: str) -> PartitionStats:
    """Calculate statistics for a set of jobs."""
    if not jobs:
        return PartitionStats(
            name=name, job_count=0, gpu_hours=0, median_wait_hours=0, long_wait_count=0, long_wait_pct=0
        )

    job_count = len(jobs)
    gpu_hours = sum(job.gpu_hours for job in jobs)

    # Calculate median wait time
    wait_times = [job.wait_hours for job in jobs]
    median_wait = median(wait_times) if wait_times else 0.0

    # Long wait jobs (> 6 hours)
    long_wait_count = sum(1 for job in jobs if job.wait_hours > LONG_WAIT_HOURS)
    long_wait_pct = (long_wait_count / job_count * 100) if job_count > 0 else 0

    return PartitionStats(
        name=name,
        job_count=job_count,
        gpu_hours=gpu_hours,
        median_wait_hours=median_wait,
        long_wait_count=long_wait_count,
        long_wait_pct=long_wait_pct,
    )


def format_time_human(hours: float) -> str:
    """Format hours to human-readable (e.g., '1h15', '15min', '< 1min')."""
    if hours == 0:
        return "< 1min"

    total_minutes = hours * MINUTES_PER_HOUR
    if total_minutes < 1:
        return "< 1min"

    h = int(hours)
    minutes = round((hours - h) * MINUTES_PER_HOUR)

    if minutes == MINUTES_PER_HOUR:
        h += 1
        minutes = 0

    if h > 0:
        return f"{h}h{minutes:02d}" if minutes > 0 else f"{h}h"
    return f"{minutes}min"


def format_pct_change(current: float, previous: float) -> str:
    """Format percentage change as a string."""
    if previous == 0:
        return ""
    pct = ((current - previous) / previous) * 100
    if abs(pct) == float("inf"):
        return ""
    sign = "+" if pct >= 0 else ""
    color = "green" if pct >= 0 else "red"
    return f" [{color}]({sign}{pct:.0f}%)[/{color}]"


_PARTITION_OPTION: list[str] | None = typer.Option(None, "--partition", "-p", help="Filter by partition(s)")
_QOS_OPTION: list[str] | None = typer.Option(None, "--qos", "-q", help="Filter by QoS(s)")


def _resolve_partitions(
    partition: list[str] | None, qos: list[str] | None, cluster: ClusterConfig | None
) -> list[tuple[str | None, str | None]]:
    """Determine which partitions/QoS to analyze.

    Returns list of (partition, qos) tuples. Raises typer.Exit on error.
    """
    if partition:
        return [(p, None) for p in partition]
    if qos:
        return [(None, q) for q in qos]
    if not cluster:
        console.print("[yellow]No cluster configured. Use --partition or --qos flags.[/yellow]")
        raise typer.Exit(1)
    if cluster.partitions:
        return [(p, None) for p in cluster.partitions]
    if cluster.qos:
        return [(None, q) for q in cluster.qos]
    console.print("[yellow]No partitions or QoS configured. Use --partition or --qos flags.[/yellow]")
    raise typer.Exit(1)


def _fetch_jobs_for_period(
    partitions: list[tuple[str | None, str | None]], start: str, end: str, account: str | None, *, verbose: bool
) -> list[JobStats]:
    """Fetch job data for all partitions in a date range."""
    jobs: list[JobStats] = []
    for part, q in partitions:
        name = part or q or "unknown"
        if verbose:
            console.print(f"[dim]  -> {name}[/dim]")
        partition_jobs = fetch_partition_data(part, q, start, end, account)
        for job in partition_jobs:
            job.group = name
        jobs.extend(partition_jobs)
    return jobs


def stats(
    ctx: typer.Context,
    *,
    days: int = typer.Option(30, "--days", "-d", help="Analysis period in days"),
    compare: bool = typer.Option(True, "--compare/--no-compare", help="Show month-over-month comparison"),
    partition: list[str] | None = _PARTITION_OPTION,
    qos: list[str] | None = _QOS_OPTION,
    small_threshold: float = typer.Option(50, "--small-threshold", help="GPU-hours threshold for small vs large jobs"),
) -> None:
    """Show cluster statistics and analytics.

    Displays GPU utilization, wait times, and job counts with optional
    month-over-month comparison. Separates analysis by job size.
    """
    cli_ctx: CLIContext = ctx.obj
    cluster = cli_ctx.cluster

    partitions_to_check = _resolve_partitions(partition, qos, cluster)
    account = cluster.account if cluster else None

    # Date ranges
    now = datetime.now(tz=UTC)
    current_start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    current_end = now.strftime("%Y-%m-%d")
    previous_start = (now - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    previous_end = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    verbose = not cli_ctx.json_output
    if verbose:
        console.print(f"[dim]Fetching data for the last {days} days...[/dim]")

    all_current_jobs = _fetch_jobs_for_period(
        partitions_to_check, current_start, current_end, account, verbose=verbose
    )

    all_previous_jobs = (
        _fetch_jobs_for_period(partitions_to_check, previous_start, previous_end, account, verbose=False)
        if compare
        else []
    )

    if not all_current_jobs:
        if cli_ctx.json_output:
            sys.stdout.write('{"error": "No jobs found in the specified period"}\n')
        else:
            console.print("[yellow]No jobs found in the specified period.[/yellow]")
        raise typer.Exit(0)

    if cli_ctx.json_output:
        _output_json(all_current_jobs, all_previous_jobs, days, small_threshold)
    else:
        _output_rich(all_current_jobs, all_previous_jobs, days, small_threshold, partitions_to_check, compare=compare)


def _output_json(current_jobs: list[JobStats], previous_jobs: list[JobStats], days: int, threshold: float) -> None:
    """Output stats as JSON."""

    def jobs_to_stats(jobs: list[JobStats]) -> dict:
        groups: dict[str, list[JobStats]] = {}
        for job in jobs:
            groups.setdefault(job.group or "unknown", []).append(job)

        result = {}
        for name, group_jobs in groups.items():
            small = [job for job in group_jobs if job.gpu_hours <= threshold]
            large = [job for job in group_jobs if job.gpu_hours > threshold]

            result[name] = {
                "all": _stats_dict(calculate_partition_stats(group_jobs, name)),
                "small": _stats_dict(calculate_partition_stats(small, name)),
                "large": _stats_dict(calculate_partition_stats(large, name)),
            }
        return result

    def _stats_dict(s: PartitionStats) -> dict:
        return {
            "job_count": s.job_count,
            "gpu_hours": round(s.gpu_hours, 2),
            "median_wait_hours": round(s.median_wait_hours, 2),
            "long_wait_pct": round(s.long_wait_pct, 2),
        }

    output = {"period_days": days, "current": jobs_to_stats(current_jobs)}
    if previous_jobs:
        output["previous"] = jobs_to_stats(previous_jobs)

    sys.stdout.write(json.dumps(output, indent=2) + "\n")


def _output_rich(
    current_jobs: list[JobStats],
    previous_jobs: list[JobStats],
    days: int,
    threshold: float,
    partitions: list[tuple[str | None, str | None]],
    *,
    compare: bool,
) -> None:
    """Output stats with Rich formatting."""

    # Group jobs by partition/QoS
    def group_jobs(jobs: list[JobStats]) -> dict[str, list[JobStats]]:
        groups: dict[str, list[JobStats]] = {}
        for job in jobs:
            groups.setdefault(job.group or "unknown", []).append(job)
        return groups

    current_groups = group_jobs(current_jobs)
    previous_groups = group_jobs(previous_jobs) if previous_jobs else {}

    # Build utilization table
    util_table = Table(title=f"GPU Utilization (Last {days} Days)", show_header=True, header_style="bold")
    util_table.add_column("Partition/QoS")
    util_table.add_column("GPU Hours", justify="right")
    util_table.add_column("Jobs", justify="right")

    for part, q in partitions:
        name = part or q or "unknown"
        current = current_groups.get(name, [])
        previous = previous_groups.get(name, [])

        current_stats = calculate_partition_stats(current, name)
        previous_stats = calculate_partition_stats(previous, name) if previous else None

        gpu_str = f"{current_stats.gpu_hours / 1000:,.1f}k"
        jobs_str = f"{current_stats.job_count:,}"

        if compare and previous_stats:
            gpu_str += format_pct_change(current_stats.gpu_hours, previous_stats.gpu_hours)
            jobs_str += format_pct_change(current_stats.job_count, previous_stats.job_count)

        util_table.add_row(name, gpu_str, jobs_str)

    console.print(util_table)
    console.print()

    # Wait times - small jobs
    _print_wait_table(current_groups, previous_groups, partitions, threshold, compare=compare, is_small=True)
    console.print()

    # Wait times - large jobs
    _print_wait_table(current_groups, previous_groups, partitions, threshold, compare=compare, is_small=False)


def _print_wait_table(
    current_groups: dict[str, list[JobStats]],
    previous_groups: dict[str, list[JobStats]],
    partitions: list[tuple[str | None, str | None]],
    threshold: float,
    *,
    compare: bool,
    is_small: bool,
) -> None:
    """Print a wait time table for small or large jobs."""
    size_label = f"Small (≤{threshold:.0f} GPU-h)" if is_small else f"Large (>{threshold:.0f} GPU-h)"
    table = Table(title=f"Wait Times: {size_label}", show_header=True, header_style="bold")
    table.add_column("Partition/QoS")
    table.add_column("Median Wait", justify="right")
    table.add_column("Wait > 6h", justify="right")
    table.add_column("Jobs", justify="right")

    for part, q in partitions:
        name = part or q or "unknown"

        current_all = current_groups.get(name, [])
        previous_all = previous_groups.get(name, [])

        if is_small:
            current = [job for job in current_all if job.gpu_hours <= threshold]
            previous = [job for job in previous_all if job.gpu_hours <= threshold]
        else:
            current = [job for job in current_all if job.gpu_hours > threshold]
            previous = [job for job in previous_all if job.gpu_hours > threshold]

        current_stats = calculate_partition_stats(current, name)
        previous_stats = calculate_partition_stats(previous, name) if previous else None

        wait_str = format_time_human(current_stats.median_wait_hours)
        pct_str = f"{current_stats.long_wait_pct:.1f}%"
        jobs_str = f"{current_stats.job_count:,}"

        if compare and previous_stats and previous_stats.job_count > 0:
            wait_str += format_pct_change(current_stats.median_wait_hours, previous_stats.median_wait_hours)
            pct_str += format_pct_change(current_stats.long_wait_pct, previous_stats.long_wait_pct)
            jobs_str += format_pct_change(current_stats.job_count, previous_stats.job_count)

        table.add_row(name, wait_str, pct_str, jobs_str)

    console.print(table)


def register_stats_commands(app: typer.Typer) -> None:
    """Register stats commands with the main app."""
    app.command(name="stats")(stats)
