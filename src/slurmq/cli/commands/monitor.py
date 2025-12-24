# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Monitor command for slurmq - admin monitoring."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from slurmq.core.models import JobRecord, QuotaStatus
from slurmq.core.quota import QuotaChecker, cancel_job, fetch_user_jobs

if TYPE_CHECKING:
    from slurmq.cli.main import CLIContext
    from slurmq.core.config import ClusterConfig, EnforcementConfig

console = Console()


def register_monitor_commands(app: typer.Typer) -> None:
    """Register monitor commands with the CLI app."""
    app.command("monitor")(monitor)


@dataclass
class UserStatus:
    """Status of a single user."""

    user: str
    used_gpu_hours: float
    remaining_gpu_hours: float
    usage_percentage: float
    status: QuotaStatus
    active_jobs: list[JobRecord]
    should_warn: bool = False
    should_cancel: bool = False
    in_grace_period: bool = False
    exceeded_at: float | None = None  # Unix timestamp when quota was first exceeded


def _find_exceeded_timestamp(records: list[JobRecord], quota_limit: float) -> float | None:
    """Find when a user's cumulative usage first exceeded quota.

    Returns the Unix timestamp when quota was first exceeded, or None if not exceeded.
    """
    if not records:
        return None

    # Sort by start time
    sorted_records = sorted(records, key=lambda r: r.start_time)

    cumulative = 0.0
    for record in sorted_records:
        cumulative += record.gpu_hours
        if cumulative > quota_limit:
            # Convert datetime to Unix timestamp
            return record.start_time.timestamp()

    return None


def get_all_user_statuses(
    records: list[JobRecord], cluster: ClusterConfig, checker: QuotaChecker, grace_period_hours: int = 24
) -> list[UserStatus]:
    """Get status for all users with active jobs."""
    import time

    # Group by user
    users: dict[str, list[JobRecord]] = {}
    for record in records:
        users.setdefault(record.user, []).append(record)

    results = []
    now = time.time()

    for user, user_records in users.items():
        report = checker.generate_report(user, user_records)

        # Check if user has active jobs
        active = [record for record in user_records if record.is_running]
        if not active:
            continue

        # Check grace period for exceeded users
        exceeded_at = None
        in_grace_period = False

        if report.status == QuotaStatus.EXCEEDED:
            exceeded_at = _find_exceeded_timestamp(user_records, report.quota_limit)
            if exceeded_at:
                hours_since_exceeded = (now - exceeded_at) / 3600
                in_grace_period = hours_since_exceeded < grace_period_hours

        results.append(
            UserStatus(
                user=user,
                used_gpu_hours=report.used_gpu_hours,
                remaining_gpu_hours=report.remaining_gpu_hours,
                usage_percentage=report.usage_percentage,
                status=report.status,
                active_jobs=active,
                should_warn=report.status == QuotaStatus.WARNING or in_grace_period,
                should_cancel=report.status == QuotaStatus.EXCEEDED and not in_grace_period,
                in_grace_period=in_grace_period,
                exceeded_at=exceeded_at,
            )
        )

    # Sort by usage descending
    results.sort(key=lambda u: u.used_gpu_hours, reverse=True)
    return results


def check_enforcement(
    statuses: list[UserStatus], enforcement: EnforcementConfig, dry_run: bool
) -> list[tuple[str, int, str]]:
    """Check which jobs should be cancelled and return actions taken.

    Returns list of (user, job_id, action) tuples.
    """
    actions: list[tuple[str, int, str]] = []

    for status in statuses:
        # Skip users not in exceeded state
        if status.status != QuotaStatus.EXCEEDED:
            continue

        # Check if in grace period
        if status.in_grace_period:
            for job in status.active_jobs:
                actions.append((status.user, job.job_id, "grace_period"))
            continue

        # Check exemptions
        if status.user in enforcement.exempt_users:
            for job in status.active_jobs:
                actions.append((status.user, job.job_id, "exempt_user"))
            continue

        for job in status.active_jobs:
            # Check job prefix exemptions
            exempt = any(job.name.startswith(prefix) for prefix in enforcement.exempt_job_prefixes)
            if exempt:
                actions.append((status.user, job.job_id, "exempt_prefix"))
                continue

            if dry_run:
                actions.append((status.user, job.job_id, "would_cancel"))
            else:
                # Actually cancel
                _cancel_job(job.job_id)
                actions.append((status.user, job.job_id, "cancelled"))

    return actions


def _cancel_job(job_id: int) -> None:
    """Cancel a Slurm job."""
    cancel_job(job_id, quiet=True)  # quiet=True handles race conditions


def monitor(
    ctx: typer.Context,
    interval: int = typer.Option(30, "--interval", "-i", help="Refresh interval in seconds"),
    enforce: bool = typer.Option(False, "--enforce", help="Enable quota enforcement"),
    once: bool = typer.Option(False, "--once", help="Run once and exit (no TUI)"),
) -> None:
    """Monitor all users' GPU quota usage (admin).

    Without --once, launches a TUI dashboard showing real-time quota status.
    With --once, prints status once and exits (useful for cron jobs).
    """
    cli_ctx: CLIContext = ctx.obj

    try:
        cluster = cli_ctx.cluster
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    if once:
        _run_once(cli_ctx, cluster, enforce)
    else:
        _run_tui(cli_ctx, cluster, enforce, interval)


def _run_once(cli_ctx: CLIContext, cluster, enforce: bool) -> None:
    """Run monitor once and exit."""
    # Fetch all jobs
    try:
        records = fetch_user_jobs("ALL", cluster, all_users=True)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        console.print(f"[red]Error fetching Slurm data:[/red] {e}")
        raise typer.Exit(1) from None

    checker = QuotaChecker(
        cluster,
        warning_threshold=cli_ctx.config.monitoring.warning_threshold,
        critical_threshold=cli_ctx.config.monitoring.critical_threshold,
    )

    grace_period = cli_ctx.config.enforcement.grace_period_hours
    statuses = get_all_user_statuses(records, cluster, checker, grace_period_hours=grace_period)

    if cli_ctx.json_output:
        _output_json(statuses)
        return

    # Output table (unless quiet mode)
    if not cli_ctx.quiet:
        _output_table(statuses, cluster.name)

    # Handle enforcement
    if enforce and cli_ctx.config.enforcement.enabled:
        dry_run = cli_ctx.config.enforcement.dry_run
        actions = check_enforcement(statuses, cli_ctx.config.enforcement, dry_run)

        if actions:
            console.print("\n[bold]Enforcement Actions:[/bold]")
            for user, job_id, action in actions:
                if action == "would_cancel":
                    console.print(f"  [yellow]Would cancel[/yellow] job {job_id} ({user}) [dry-run]")
                elif action == "cancelled":
                    console.print(f"  [red]Cancelled[/red] job {job_id} ({user})")
                elif action == "exempt_user":
                    console.print(f"  [dim]Skipped[/dim] job {job_id} ({user}) - user exempt")
                elif action == "exempt_prefix":
                    console.print(f"  [dim]Skipped[/dim] job {job_id} ({user}) - job prefix exempt")
                elif action == "grace_period":
                    console.print(f"  [cyan]Warning[/cyan] job {job_id} ({user}) - in grace period")
    elif enforce:
        console.print("\n[yellow]Enforcement not enabled in config.[/yellow]")


def _output_json(statuses: list[UserStatus]) -> None:
    """Output status as JSON."""
    data = {
        "users": [
            {
                "user": status.user,
                "used_gpu_hours": round(status.used_gpu_hours, 2),
                "remaining_gpu_hours": round(status.remaining_gpu_hours, 2),
                "usage_percentage": round(status.usage_percentage * 100, 1),
                "status": status.status.value,
                "active_jobs": len(status.active_jobs),
                "in_grace_period": status.in_grace_period,
                "exceeded_at": status.exceeded_at,
            }
            for status in statuses
        ]
    }
    console.print(json.dumps(data, indent=2))


def _output_table(statuses: list[UserStatus], cluster_name: str) -> None:
    """Output status as rich table."""
    table = Table(title=f"Active Users: {cluster_name}")

    table.add_column("User", style="cyan")
    table.add_column("Used (GPU-hrs)", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("Usage %", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Active Jobs", justify="right")

    status_styles = {QuotaStatus.OK: "green", QuotaStatus.WARNING: "yellow", QuotaStatus.EXCEEDED: "red"}
    status_icons = {"ok": "ok", "warning": "!", "exceeded": "x"}

    for user_status in statuses:
        style = status_styles[user_status.status]
        icon = status_icons[user_status.status.value]

        table.add_row(
            user_status.user,
            f"{user_status.used_gpu_hours:.1f}",
            f"[{style}]{user_status.remaining_gpu_hours:.1f}[/{style}]",
            f"[{style}]{user_status.usage_percentage * 100:.0f}%[/{style}]",
            f"[{style}]{icon}[/{style}]",
            str(len(user_status.active_jobs)),
        )

    console.print(table)

    if not statuses:
        console.print("[dim]No users with active jobs.[/dim]")


def _run_tui(cli_ctx: CLIContext, cluster, enforce: bool, interval: int) -> None:
    """Run the interactive TUI monitor."""
    import time

    console.print(f"[bold]Monitoring {cluster.name}[/bold] (refresh every {interval}s, Ctrl+C to exit)\n")

    try:
        while True:
            # Fetch and display
            try:
                records = fetch_user_jobs("ALL", cluster, all_users=True)
                checker = QuotaChecker(
                    cluster,
                    warning_threshold=cli_ctx.config.monitoring.warning_threshold,
                    critical_threshold=cli_ctx.config.monitoring.critical_threshold,
                )
                grace_period = cli_ctx.config.enforcement.grace_period_hours
                statuses = get_all_user_statuses(records, cluster, checker, grace_period_hours=grace_period)

                # Clear and redraw
                console.clear()
                console.print(f"[bold]Monitoring {cluster.name}[/bold] (refresh every {interval}s, Ctrl+C to exit)\n")
                _output_table(statuses, cluster.name)
                console.print(f"\n[dim]Last updated: {time.strftime('%H:%M:%S')}[/dim]")

                # Enforcement check
                if enforce and cli_ctx.config.enforcement.enabled:
                    dry_run = cli_ctx.config.enforcement.dry_run
                    actions = check_enforcement(statuses, cli_ctx.config.enforcement, dry_run)
                    if actions:
                        console.print("\n[bold]Enforcement:[/bold]")
                        for user, job_id, action in actions[:5]:  # Show first 5
                            console.print(f"  {action}: job {job_id} ({user})")

            except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as e:
                # Transient errors - continue monitoring
                console.print(f"[red]Error:[/red] {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
