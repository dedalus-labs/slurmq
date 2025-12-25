# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Efficiency command for slurmq - show job CPU/memory efficiency (inspired by seff)."""

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
import typer

from slurmq.cli.commands.check import _to_yaml


if TYPE_CHECKING:
    from slurmq.cli.main import CLIContext

console = Console()

# Constants for display formatting and thresholds
KB_PER_UNIT = 1024  # 1024 KB = 1 MB, etc.
DECIMAL_PLACES_TIME = 2
DECIMAL_PLACES_SIZE = 3
TIME_COLUMN_WIDTH = 10
VALUE_COLUMN_WIDTH = 11
GOOD_EFFICIENCY_PCT = 70
WARN_EFFICIENCY_PCT = 50
GOOD_MEMORY_PCT = 30
WARN_MEMORY_PCT = 20
CPU_GOOD_PCT = 30
CPU_WARN_PCT = 60
MEM_GOOD_PCT = 20
MEM_WARN_KB = 1024  # 1 MB
SACCT_MIN_FIELDS = 11  # Minimum fields expected from sacct output

# Time parsing: HH:MM:SS has 3 parts, MM:SS has 2
TIME_PARTS_HMS = 3
TIME_PARTS_MS = 2


@dataclass
class JobEfficiency:
    """Efficiency metrics for a SLURM job."""

    job_id: int
    user: str
    state: str
    exit_code: int
    n_cpus: int
    n_nodes: int
    elapsed_seconds: int
    total_cpu_seconds: float  # User + System CPU time
    allocated_mem_mb: int
    max_rss_mb: int
    job_name: str = ""
    cluster: str = ""

    @property
    def walltime_str(self) -> str:
        """Format elapsed time as D-HH:MM:SS."""
        return _format_time(self.elapsed_seconds)

    @property
    def core_walltime_seconds(self) -> int:
        """Total core-seconds available."""
        return self.elapsed_seconds * self.n_cpus

    @property
    def cpu_efficiency(self) -> float:
        """CPU efficiency as percentage (0-100+)."""
        if self.core_walltime_seconds == 0:
            return 0.0
        return (self.total_cpu_seconds / self.core_walltime_seconds) * 100

    @property
    def mem_efficiency(self) -> float:
        """Memory efficiency as percentage (0-100+)."""
        if self.allocated_mem_mb == 0:
            return 0.0
        return (self.max_rss_mb / self.allocated_mem_mb) * 100


def _format_time(seconds: int) -> str:
    """Format seconds as D-HH:MM:SS."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}-{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_bytes(kb: int) -> str:
    """Format kilobytes as human-readable string."""
    if kb == 0:
        return "0.00 MB"
    units = ["KB", "MB", "GB", "TB", "PB"]
    size = float(kb)
    for unit in units:
        if size < KB_PER_UNIT:
            return f"{size:.2f} {unit}"
        size /= KB_PER_UNIT
    return f"{size:.2f} PB"


def _parse_mem_str(mem_str: str) -> int:
    """Parse memory string like '32G' to MB."""
    if not mem_str:
        return 0
    # Strip trailing 'n' or 'c' (per-node or per-core)
    mem_str = mem_str.rstrip("nc")
    multipliers = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}
    for suffix, mult in multipliers.items():
        if mem_str.endswith(suffix):
            try:
                return int(float(mem_str[:-1]) * mult)
            except ValueError:
                return 0
    # No suffix, assume MB
    try:
        return int(mem_str)
    except ValueError:
        return 0


def _fetch_job_efficiency(job_id: str) -> JobEfficiency | None:
    """Fetch job efficiency data from SLURM.

    Uses sacct with specific fields to get efficiency metrics.
    """
    # Get job data with efficiency-relevant fields
    cmd = [
        "sacct",
        "-j",
        job_id,
        "-X",  # Allocations only
        "--noheader",
        "-P",  # Parsable
        "--format=JobID,User,State,ExitCode,AllocCPUS,NNodes,ElapsedRaw,TotalCPU,AllocTres,MaxRSS,JobName,Cluster",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603 - sacct with job_id arg
    except subprocess.CalledProcessError:
        return None

    lines = result.stdout.strip().split("\n")
    if not lines or not lines[0]:
        return None

    # Parse first line (job allocation)
    fields = lines[0].split("|")
    if len(fields) < SACCT_MIN_FIELDS:
        return None

    # Parse exit code (format: 0:0 or 1:0)
    exit_parts = fields[3].split(":")
    exit_code = int(exit_parts[0]) if exit_parts else 0

    # Parse TotalCPU (format: DD-HH:MM:SS or HH:MM:SS or MM:SS.mmm)
    total_cpu_str = fields[7]
    total_cpu_seconds = _parse_cpu_time(total_cpu_str)

    # Parse AllocTRES to get allocated memory
    alloc_tres = fields[8]
    allocated_mem_mb = 0
    for tres in alloc_tres.split(","):
        if tres.startswith("mem="):
            allocated_mem_mb = _parse_mem_str(tres[4:])

    # Parse MaxRSS (may be empty or have suffix like K, M, G)
    max_rss_str = fields[9]
    max_rss_mb = 0
    if max_rss_str:
        # MaxRSS is in KB by default
        max_rss_mb = _parse_mem_str(max_rss_str) if max_rss_str else 0

    return JobEfficiency(
        job_id=int(fields[0].split("_")[0].split(".")[0]),  # Handle array jobs
        user=fields[1],
        state=fields[2],
        exit_code=exit_code,
        n_cpus=int(fields[4]) if fields[4] else 1,
        n_nodes=int(fields[5]) if fields[5] else 1,
        elapsed_seconds=int(fields[6]) if fields[6] else 0,
        total_cpu_seconds=total_cpu_seconds,
        allocated_mem_mb=allocated_mem_mb,
        max_rss_mb=max_rss_mb,
        job_name=fields[10] if len(fields) > SACCT_MIN_FIELDS - 1 else "",
        cluster=fields[11] if len(fields) > SACCT_MIN_FIELDS else "",
    )


def _parse_cpu_time(time_str: str) -> float:
    """Parse TotalCPU time string to seconds."""
    if not time_str:
        return 0.0

    # Handle formats: DD-HH:MM:SS.mmm, HH:MM:SS.mmm, MM:SS.mmm
    days = 0
    if "-" in time_str:
        day_part, time_str = time_str.split("-", 1)
        days = int(day_part)

    # Split off microseconds
    if "." in time_str:
        time_str, usec_str = time_str.rsplit(".", 1)
    else:
        usec_str = "0"

    parts = time_str.split(":")
    if len(parts) == TIME_PARTS_HMS:
        hours, minutes, seconds = map(int, parts)
    elif len(parts) == TIME_PARTS_MS:
        hours = 0
        minutes, seconds = map(int, parts)
    else:
        return 0.0

    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    total += int(usec_str) / 1_000_000
    return total


def register_efficiency_commands(app: typer.Typer) -> None:
    """Register efficiency commands with the CLI app."""
    app.command("efficiency", help="Show CPU/memory efficiency for a job (like seff)")(efficiency)
    # Alias
    app.command("eff", hidden=True)(efficiency)


def efficiency(ctx: typer.Context, job_id: str = typer.Argument(..., help="Job ID to check")) -> None:
    """Show CPU and memory efficiency for a completed job.

    This is inspired by the 'seff' tool and shows:
    - CPU Efficiency: How much of the allocated CPU time was actually used
    - Memory Efficiency: How much of the allocated memory was actually used

    Low efficiency may indicate:
    - Requesting too many CPUs (low CPU efficiency)
    - Requesting too much memory (low memory efficiency)
    - I/O bound workload (low CPU efficiency)
    """
    cli_ctx: CLIContext = ctx.obj

    eff = _fetch_job_efficiency(job_id)
    if eff is None:
        if cli_ctx.json_output:
            console.print(json.dumps({"error": f"Job {job_id} not found"}))
        else:
            console.print(f"[red]Error:[/red] Job {job_id} not found")
        raise typer.Exit(1)

    if cli_ctx.json_output:
        _output_json(eff)
    elif cli_ctx.yaml_output:
        _output_yaml(eff)
    else:
        _output_rich(eff)


def _eff_to_dict(eff: JobEfficiency) -> dict[str, Any]:
    """Convert efficiency to dict for JSON/YAML."""
    return {
        "job_id": eff.job_id,
        "job_name": eff.job_name,
        "user": eff.user,
        "cluster": eff.cluster,
        "state": eff.state,
        "exit_code": eff.exit_code,
        "nodes": eff.n_nodes,
        "cpus": eff.n_cpus,
        "walltime_seconds": eff.elapsed_seconds,
        "walltime": eff.walltime_str,
        "cpu_utilized_seconds": round(eff.total_cpu_seconds, 2),
        "core_walltime_seconds": eff.core_walltime_seconds,
        "cpu_efficiency_pct": round(eff.cpu_efficiency, 2),
        "memory_utilized_mb": eff.max_rss_mb,
        "memory_allocated_mb": eff.allocated_mem_mb,
        "memory_efficiency_pct": round(eff.mem_efficiency, 2),
    }


def _output_json(eff: JobEfficiency) -> None:
    """Output efficiency as JSON."""
    console.print(json.dumps(_eff_to_dict(eff), indent=2))


def _output_yaml(eff: JobEfficiency) -> None:
    """Output efficiency as YAML."""
    console.print(_to_yaml(_eff_to_dict(eff)))


def _efficiency_color(pct: float, good: float, warn: float) -> str:
    """Get color based on efficiency percentage thresholds."""
    if pct >= good:
        return "green"
    return "yellow" if pct >= warn else "red"


def _output_rich(eff: JobEfficiency) -> None:
    """Output efficiency with rich formatting."""
    cpu_color = _efficiency_color(eff.cpu_efficiency, GOOD_EFFICIENCY_PCT, GOOD_MEMORY_PCT)
    mem_color = _efficiency_color(eff.mem_efficiency, WARN_EFFICIENCY_PCT, WARN_MEMORY_PCT)

    # State color
    state_color = "green" if eff.state == "COMPLETED" else "yellow" if eff.state == "RUNNING" else "red"

    # Build output
    lines = [f"[bold]Job ID:[/bold] {eff.job_id}"]
    if eff.job_name:
        lines.append(f"[bold]Job Name:[/bold] {eff.job_name}")
    if eff.cluster:
        lines.append(f"[bold]Cluster:[/bold] {eff.cluster}")
    lines.append(f"[bold]User:[/bold] {eff.user}")

    # State with exit code
    if eff.state in ("PENDING", "RUNNING"):
        lines.append(f"[bold]State:[/bold] [{state_color}]{eff.state}[/{state_color}]")
    else:
        lines.append(f"[bold]State:[/bold] [{state_color}]{eff.state}[/{state_color}] (exit code {eff.exit_code})")

    # Resources
    lines.append("")
    lines.append(f"[bold]Nodes:[/bold] {eff.n_nodes}")
    lines.append(f"[bold]CPUs:[/bold] {eff.n_cpus}")

    if eff.state == "PENDING":
        lines.append("")
        lines.append("[dim]Efficiency not available for PENDING jobs.[/dim]")
    else:
        lines.append("")
        lines.append(f"[bold]Job Wall-clock time:[/bold] {eff.walltime_str}")
        lines.append("")

        # CPU efficiency
        cpu_utilized = _format_time(int(eff.total_cpu_seconds))
        core_walltime = _format_time(eff.core_walltime_seconds)
        lines.append(f"[bold]CPU Utilized:[/bold] {cpu_utilized}")
        lines.append(
            f"[bold]CPU Efficiency:[/bold] [{cpu_color}]{eff.cpu_efficiency:.2f}%[/{cpu_color}] "
            f"of {core_walltime} core-walltime"
        )

        # Memory efficiency
        lines.append("")
        mem_utilized = _format_bytes(eff.max_rss_mb * 1024)  # Convert MB to KB for formatter
        mem_allocated = _format_bytes(eff.allocated_mem_mb * 1024)
        lines.append(f"[bold]Memory Utilized:[/bold] {mem_utilized}")
        lines.append(
            f"[bold]Memory Efficiency:[/bold] [{mem_color}]{eff.mem_efficiency:.2f}%[/{mem_color}] of {mem_allocated}"
        )

        # Recommendations
        if eff.cpu_efficiency < CPU_GOOD_PCT and eff.elapsed_seconds > CPU_WARN_PCT:
            lines.append("")
            lines.append(
                "[yellow]💡 Low CPU efficiency. Consider:[/yellow]\n"
                "   - Using fewer CPUs (--cpus-per-task)\n"
                "   - Checking for I/O bottlenecks"
            )
        if eff.mem_efficiency < MEM_GOOD_PCT and eff.allocated_mem_mb > MEM_WARN_KB:
            lines.append("")
            lines.append(
                "[yellow]💡 Low memory efficiency. Consider:[/yellow]\n"
                "   - Requesting less memory (--mem or --mem-per-cpu)"
            )

    panel = Panel("\n".join(lines), title="[bold]Job Efficiency Report[/bold]", border_style="cyan")
    console.print(panel)
