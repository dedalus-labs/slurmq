# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Monitor command for slurmq - admin monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import subprocess
import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table
import typer

from slurmq.core.models import JobRecord, QuotaStatus
from slurmq.core.quota import QuotaChecker, cancel_job, fetch_user_jobs


if TYPE_CHECKING:
    from slurmq.cli.main import CLIContext
    from slurmq.core.config import ClusterConfig, EnforcementConfig

console = Console()


class EnforcementAction(Enum):
    """Types of enforcement actions."""

    WOULD_CANCEL = "would_cancel"
    CANCELLED = "cancelled"
    EXEMPT_USER = "exempt_user"
    EXEMPT_PREFIX = "exempt_prefix"
    GRACE_PERIOD = "grace_period"

    def format_message(self, user: str, job_id: int) -> str:
        """Format display message for this action."""
        formats = {
            EnforcementAction.WOULD_CANCEL: f"  [yellow]Would cancel[/yellow] job {job_id} ({user}) [dry-run]",
            EnforcementAction.CANCELLED: f"  [red]Cancelled[/red] job {job_id} ({user})",
            EnforcementAction.EXEMPT_USER: f"  [dim]Skipped[/dim] job {job_id} ({user}) - user exempt",
            EnforcementAction.EXEMPT_PREFIX: f"  [dim]Skipped[/dim] job {job_id} ({user}) - job prefix exempt",
            EnforcementAction.GRACE_PERIOD: f"  [cyan]Warning[/cyan] job {job_id} ({user}) - in grace period",
        }
        return formats[self]


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
    records: list[JobRecord], checker: QuotaChecker, *, grace_period_hours: int = 24
) -> list[UserStatus]:
    """Get status for all users with active jobs."""
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
    statuses: list[UserStatus], enforcement: EnforcementConfig, *, dry_run: bool
) -> list[tuple[str, int, EnforcementAction]]:
    """Check which jobs should be cancelled and return actions taken.

    Returns list of (user, job_id, action) tuples.
    """
    actions: list[tuple[str, int, EnforcementAction]] = []

    for status in statuses:
        if status.status != QuotaStatus.EXCEEDED:
            continue

        if status.in_grace_period:
            actions.extend((status.user, job.job_id, EnforcementAction.GRACE_PERIOD) for job in status.active_jobs)
            continue

        if status.user in enforcement.exempt_users:
            actions.extend((status.user, job.job_id, EnforcementAction.EXEMPT_USER) for job in status.active_jobs)
            continue

        for job in status.active_jobs:
            exempt = any(job.name.startswith(prefix) for prefix in enforcement.exempt_job_prefixes)
            if exempt:
                actions.append((status.user, job.job_id, EnforcementAction.EXEMPT_PREFIX))
                continue

            if dry_run:
                actions.append((status.user, job.job_id, EnforcementAction.WOULD_CANCEL))
            else:
                _cancel_job(job.job_id)
                actions.append((status.user, job.job_id, EnforcementAction.CANCELLED))

    return actions


def _cancel_job(job_id: int) -> None:
    """Cancel a Slurm job."""
    cancel_job(job_id, quiet=True)  # quiet=True handles race conditions


def monitor(
    ctx: typer.Context,
    *,
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
        _run_once(cli_ctx, cluster, enforce=enforce)
    else:
        _run_tui(cli_ctx, cluster, enforce=enforce, interval=interval)


def _run_once(cli_ctx: CLIContext, cluster: ClusterConfig, *, enforce: bool) -> None:
    """Run monitor once and exit."""
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
    statuses = get_all_user_statuses(records, checker, grace_period_hours=grace_period)

    if cli_ctx.json_output:
        _output_json(statuses)
        return

    if not cli_ctx.quiet:
        _output_table(statuses, cluster.name)

    if not enforce:
        return

    if not cli_ctx.config.enforcement.enabled:
        console.print("\n[yellow]Enforcement not enabled in config.[/yellow]")
        return

    dry_run = cli_ctx.config.enforcement.dry_run
    actions = check_enforcement(statuses, cli_ctx.config.enforcement, dry_run=dry_run)

    if actions:
        console.print("\n[bold]Enforcement Actions:[/bold]")
        for user, job_id, action in actions:
            console.print(action.format_message(user, job_id))


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


def _run_tui(cli_ctx: CLIContext, cluster: ClusterConfig, *, enforce: bool, interval: int) -> None:
    """Run the interactive TUI monitor."""
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
                statuses = get_all_user_statuses(records, checker, grace_period_hours=grace_period)

                # Clear and redraw
                console.clear()
                console.print(f"[bold]Monitoring {cluster.name}[/bold] (refresh every {interval}s, Ctrl+C to exit)\n")
                _output_table(statuses, cluster.name)
                console.print(f"\n[dim]Last updated: {time.strftime('%H:%M:%S')}[/dim]")

                # Enforcement check
                if enforce and cli_ctx.config.enforcement.enabled:
                    dry_run = cli_ctx.config.enforcement.dry_run
                    actions = check_enforcement(statuses, cli_ctx.config.enforcement, dry_run=dry_run)
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
