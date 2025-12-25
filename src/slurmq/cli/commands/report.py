# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Report command for slurmq - generate usage reports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import json
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table
import typer

from slurmq.core.models import JobRecord, QuotaStatus
from slurmq.core.quota import QuotaChecker, fetch_user_jobs


if TYPE_CHECKING:
    from slurmq.cli.main import CLIContext

console = Console()


def register_report_commands(app: typer.Typer) -> None:
    """Register report commands with the CLI app."""
    app.command("report")(report)


@dataclass
class UserUsage:
    """Usage summary for a single user."""

    user: str
    used_gpu_hours: float
    quota_limit: int
    remaining_gpu_hours: float
    usage_percentage: float
    status: QuotaStatus
    active_jobs: int
    total_jobs: int


def aggregate_by_user(records: list[JobRecord], checker: QuotaChecker) -> list[UserUsage]:
    """Aggregate job records by user."""
    users: dict[str, list[JobRecord]] = {}
    for record in records:
        users.setdefault(record.user, []).append(record)

    results = []
    for user, user_records in users.items():
        report = checker.generate_report(user, user_records)
        results.append(
            UserUsage(
                user=user,
                used_gpu_hours=report.used_gpu_hours,
                quota_limit=report.quota_limit,
                remaining_gpu_hours=report.remaining_gpu_hours,
                usage_percentage=report.usage_percentage,
                status=report.status,
                active_jobs=len(report.active_jobs),
                total_jobs=len(user_records),
            )
        )

    # Sort by usage descending
    results.sort(key=lambda u: u.used_gpu_hours, reverse=True)
    return results


def report(
    ctx: typer.Context,
    *,
    output_format: str = typer.Option("rich", "--format", "-f", help="Output format: rich, json, csv"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path"),
    qos: str | None = typer.Option(None, "--qos", "-q", help="QoS to report on (overrides config)"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account to report on (overrides config)"),
    partition: str | None = typer.Option(None, "--partition", "-p", help="Partition to report on (overrides config)"),
) -> None:
    """Generate usage report for all users.

    Produces a summary of GPU usage across all users for the rolling window.
    """
    cli_ctx: CLIContext = ctx.obj

    try:
        cluster = cli_ctx.cluster
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Fetch all users' jobs (with CLI overrides)
    try:
        records = fetch_user_jobs(
            "ALL", cluster, all_users=True, qos_override=qos, account_override=account, partition_override=partition
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        console.print(f"[red]Error fetching Slurm data:[/red] {e}")
        raise typer.Exit(1) from None

    # Filter by QoS if needed (for post-filtering when sacct doesn't filter)
    target_qos = qos or (cluster.qos[0] if cluster.qos else None)
    if target_qos:
        records = [record for record in records if record.qos == target_qos]

    # Create checker and aggregate
    checker = QuotaChecker(
        cluster,
        warning_threshold=cli_ctx.config.monitoring.warning_threshold,
        critical_threshold=cli_ctx.config.monitoring.critical_threshold,
    )
    user_usages = aggregate_by_user(records, checker)

    # Generate output
    if output_format == "json":
        content = _format_json(user_usages, cluster.name, target_qos)
    elif output_format == "csv":
        content = _format_csv(user_usages)
    else:
        _output_rich(user_usages, cluster.name, target_qos)
        return

    # Write to file or stdout
    if output:
        Path(output).write_text(content)
        console.print(f"Report written to {output}")
    else:
        console.print(content)


def _format_json(usages: list[UserUsage], cluster_name: str, qos: str | None) -> str:
    """Format report as JSON."""
    data = {
        "cluster": cluster_name,
        "qos": qos,
        "users": [
            {
                "user": usage.user,
                "used_gpu_hours": round(usage.used_gpu_hours, 2),
                "quota_limit": usage.quota_limit,
                "remaining_gpu_hours": round(usage.remaining_gpu_hours, 2),
                "usage_percentage": round(usage.usage_percentage * 100, 1),
                "status": usage.status.value,
                "active_jobs": usage.active_jobs,
                "total_jobs": usage.total_jobs,
            }
            for usage in usages
        ],
    }
    return json.dumps(data, indent=2)


def _format_csv(usages: list[UserUsage]) -> str:
    """Format report as CSV."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "user",
            "used_gpu_hours",
            "quota_limit",
            "remaining_gpu_hours",
            "usage_percentage",
            "status",
            "active_jobs",
            "total_jobs",
        ],
    )
    writer.writeheader()
    for usage in usages:
        writer.writerow(
            {
                "user": usage.user,
                "used_gpu_hours": round(usage.used_gpu_hours, 2),
                "quota_limit": usage.quota_limit,
                "remaining_gpu_hours": round(usage.remaining_gpu_hours, 2),
                "usage_percentage": round(usage.usage_percentage * 100, 1),
                "status": usage.status.value,
                "active_jobs": usage.active_jobs,
                "total_jobs": usage.total_jobs,
            }
        )
    return output.getvalue()


def _output_rich(usages: list[UserUsage], cluster_name: str, qos: str | None) -> None:
    """Output report with rich table."""
    table = Table(title=f"GPU Usage Report: {cluster_name}" + (f" ({qos})" if qos else ""))

    table.add_column("User", style="cyan")
    table.add_column("Used (GPU-hrs)", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("Usage %", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Active", justify="right")

    status_styles = {QuotaStatus.OK: "green", QuotaStatus.WARNING: "yellow", QuotaStatus.EXCEEDED: "red"}

    for usage in usages:
        style = status_styles[usage.status]
        status_icon = {"ok": "ok", "warning": "!", "exceeded": "x"}[usage.status.value]

        table.add_row(
            usage.user,
            f"{usage.used_gpu_hours:.1f}",
            f"[{style}]{usage.remaining_gpu_hours:.1f}[/{style}]",
            f"[{style}]{usage.usage_percentage * 100:.0f}%[/{style}]",
            f"[{style}]{status_icon}[/{style}]",
            str(usage.active_jobs) if usage.active_jobs > 0 else "-",
        )

    console.print(table)
    console.print(f"\n[dim]Total users: {len(usages)}[/dim]")
