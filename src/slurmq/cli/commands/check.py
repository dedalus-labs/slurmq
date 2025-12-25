# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Check command for slurmq - check your GPU quota usage."""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from slurmq.core.models import QuotaStatus, UsageReport
from slurmq.core.quota import QuotaChecker, fetch_user_jobs


if TYPE_CHECKING:
    from slurmq.cli.main import CLIContext

console = Console()

# Display constants
HOURS_PER_WEEK = 168
QUOTA_WARNING_PCT = 20  # Below this percentage, show yellow

# Type alias for YAML-serializable values
YamlValue = str | int | float | bool | None


def _yaml_value(v: YamlValue) -> str:
    """Convert a scalar value to YAML string representation."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        # Quote if contains special chars
        if any(c in v for c in ":{}[]#&*!|>'\"%@`"):
            return f'"{v}"'
        return v
    return str(v)


def _yaml_serialize(obj: dict[str, Any] | list[Any], lines: list[str], indent: int = 0) -> None:
    """Recursively serialize dict/list to YAML lines."""
    prefix = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict | list):
                lines.append(f"{prefix}{k}:")
                _yaml_serialize(v, lines, indent + 1)
            else:
                lines.append(f"{prefix}{k}: {_yaml_value(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                _yaml_serialize(item, lines, indent + 1)
            else:
                lines.append(f"{prefix}- {_yaml_value(item)}")


def _to_yaml(data: dict[str, Any]) -> str:
    """Convert dict to YAML without external dependency."""
    lines: list[str] = []
    _yaml_serialize(data, lines)
    return "\n".join(lines)


def register_check_commands(app: typer.Typer) -> None:
    """Register check commands with the CLI app."""
    app.command("check")(check)


def check(
    ctx: typer.Context,
    *,
    user: str | None = typer.Option(None, "--user", "-u", help="User to check (default: current user)"),
    qos: str | None = typer.Option(None, "--qos", "-q", help="QoS to check (overrides config)"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account to check (overrides config)"),
    partition: str | None = typer.Option(None, "--partition", "-p", help="Partition to check (overrides config)"),
    forecast: bool = typer.Option(False, "--forecast", "-f", help="Show quota forecast"),
) -> None:
    """Check GPU quota usage for a user.

    Shows current usage, remaining quota, and status (OK/WARNING/EXCEEDED).
    """
    cli_ctx: CLIContext = ctx.obj

    # Get user
    target_user = user or os.environ.get("USER", "unknown")

    try:
        cluster = cli_ctx.cluster
    except ValueError as e:
        if cli_ctx.json_output:
            console.print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Create checker
    checker = QuotaChecker(
        cluster,
        warning_threshold=cli_ctx.config.monitoring.warning_threshold,
        critical_threshold=cli_ctx.config.monitoring.critical_threshold,
    )

    # Fetch jobs from SLURM (with CLI overrides)
    try:
        records = fetch_user_jobs(
            target_user, cluster, qos_override=qos, account_override=account, partition_override=partition
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        if cli_ctx.json_output:
            console.print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error fetching Slurm data:[/red] {e}")
        raise typer.Exit(1) from None

    # Generate report
    report = checker.generate_report(target_user, records, qos=qos)

    # Output
    if cli_ctx.json_output:
        _output_json(report)
    elif cli_ctx.yaml_output:
        _output_yaml(report)
    elif not cli_ctx.quiet:
        _output_rich(report, cluster.name, checker, records, target_user, show_forecast=forecast)


def _report_to_dict(report: UsageReport) -> dict:
    """Convert report to dict for JSON/YAML output."""
    return {
        "user": report.user,
        "qos": report.qos,
        "used_gpu_hours": round(report.used_gpu_hours, 2),
        "quota_limit": report.quota_limit,
        "remaining_gpu_hours": round(report.remaining_gpu_hours, 2),
        "usage_percentage": round(report.usage_percentage * 100, 1),
        "status": report.status.value,
        "rolling_window_days": report.rolling_window_days,
        "active_jobs": len(report.active_jobs),
    }


def _output_json(report: UsageReport) -> None:
    """Output report as JSON."""
    console.print(json.dumps(_report_to_dict(report), indent=2))


def _output_yaml(report: UsageReport) -> None:
    """Output report as YAML."""
    console.print(_to_yaml(_report_to_dict(report)))


def _output_rich(
    report: UsageReport, cluster_name: str, checker: QuotaChecker, records: list, user: str, *, show_forecast: bool
) -> None:
    """Output report with rich formatting."""
    # Determine color based on status
    status_colors = {QuotaStatus.OK: "green", QuotaStatus.WARNING: "yellow", QuotaStatus.EXCEEDED: "red"}
    color = status_colors[report.status]

    # Create progress bar
    pct = min(report.usage_percentage, 1.5)  # Cap at 150% for display
    bar_width = 30
    filled = int(pct * bar_width)
    bar = "█" * min(filled, bar_width) + "░" * max(0, bar_width - filled)

    # Build content
    lines = [
        f"[bold]User:[/bold] {report.user}",
        f"[bold]QoS:[/bold] {report.qos}",
        f"[bold]Cluster:[/bold] {cluster_name}",
        "",
        f"[{color}]{bar}[/{color}] {report.usage_percentage * 100:.1f}%",
        "",
        f"[bold]Used:[/bold] {report.used_gpu_hours:.1f} GPU-hours",
        f"[bold]Remaining:[/bold] {report.remaining_gpu_hours:.1f} GPU-hours",
        f"[bold]Quota:[/bold] {report.quota_limit} GPU-hours (rolling {report.rolling_window_days} days)",
    ]

    if report.active_jobs:
        lines.append(f"\n[bold]Active jobs:[/bold] {len(report.active_jobs)}")

    # Status message
    if report.status == QuotaStatus.EXCEEDED:
        lines.append(
            f"\n[red bold]WARNING: QUOTA EXCEEDED![/red bold]\nJobs submitted to {report.qos} may be cancelled."
        )
    elif report.status == QuotaStatus.WARNING:
        lines.append("\n[yellow]Warning: Approaching quota limit.[/yellow]")

    # Create panel
    panel = Panel("\n".join(lines), title="[bold]GPU Quota Report[/bold]", border_style=color)
    console.print(panel)

    # Forecast if requested
    if show_forecast:
        forecast = checker.forecast_quota(user, records)
        _output_forecast(forecast, report.quota_limit)


def _output_forecast(forecast: dict[int, float], quota_limit: int) -> None:
    """Output quota forecast table."""
    table = Table(title="Quota Forecast")
    table.add_column("Time", style="cyan")
    table.add_column("Available GPU-hours", justify="right")
    table.add_column("% Available", justify="right")

    for hours, available in sorted(forecast.items()):
        pct = (available / quota_limit) * 100 if quota_limit > 0 else 0
        color = "green" if pct > QUOTA_WARNING_PCT else "yellow" if pct > 0 else "red"
        time_str = f"+{hours}h" if hours < HOURS_PER_WEEK else f"+{hours // 24}d"
        table.add_row(time_str, f"[{color}]{available:.1f}[/{color}]", f"[{color}]{pct:.1f}%[/{color}]")

    console.print(table)
