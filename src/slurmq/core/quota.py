# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Quota checking and Slurm interaction.

GPU-hours are allocation-based (reserved time * GPUs), not actual utilization.
This matches standard HPC billing semantics.

This module handles:
- QuotaChecker: Calculating allocated GPU-hours and generating usage reports
- fetch_user_jobs: Querying sacct for job data
- cancel_job: Cancelling jobs for enforcement
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import subprocess
from typing import TYPE_CHECKING

from .models import JobRecord, UsageReport, parse_sacct_json


if TYPE_CHECKING:
    from .config import ClusterConfig

__all__ = ["QuotaChecker", "cancel_job", "fetch_user_jobs"]


class QuotaChecker:
    """Checks allocated GPU-hours against cluster quota configuration."""

    def __init__(
        self, cluster: ClusterConfig, warning_threshold: float = 0.8, critical_threshold: float = 1.0
    ) -> None:
        """Initialize QuotaChecker.

        Args:
            cluster: Cluster configuration with quota settings
            warning_threshold: Usage fraction for warning status
            critical_threshold: Usage fraction for exceeded status

        """
        self.cluster = cluster
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def calculate_gpu_hours(self, records: list[JobRecord]) -> float:
        """Calculate total allocated GPU-hours from job records.

        Args:
            records: List of job records

        Returns:
            Total allocated GPU-hours

        """
        return sum(record.gpu_hours for record in records)

    def filter_by_window(self, records: list[JobRecord], window_days: int | None = None) -> list[JobRecord]:
        """Filter records to those within the rolling window.

        Args:
            records: List of job records
            window_days: Number of days in window (uses cluster config if None)

        Returns:
            Records with start_time within the window

        """
        days = window_days if window_days is not None else self.cluster.rolling_window_days
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        return [record for record in records if record.start_time >= cutoff]

    def filter_by_qos(self, records: list[JobRecord], qos: str | None = None) -> list[JobRecord]:
        """Filter records by QoS.

        Args:
            records: List of job records
            qos: QoS to filter by (uses first from cluster config if None)

        Returns:
            Records matching the QoS

        """
        target_qos = qos if qos is not None else self.cluster.qos[0]
        return [record for record in records if record.qos == target_qos]

    def generate_report(self, user: str, records: list[JobRecord], qos: str | None = None) -> UsageReport:
        """Generate a usage report for a user.

        Args:
            user: Username
            records: Job records (will be filtered)
            qos: QoS to report on (uses first from cluster config if None)

        Returns:
            UsageReport with quota status

        """
        target_qos = qos if qos is not None else self.cluster.qos[0]

        # Filter to user's jobs in the rolling window for the target QoS
        user_records = [record for record in records if record.user == user]
        windowed = self.filter_by_window(user_records)
        qos_filtered = self.filter_by_qos(windowed, target_qos)

        used_hours = self.calculate_gpu_hours(qos_filtered)
        active = [record for record in qos_filtered if record.is_running]

        return UsageReport(
            user=user,
            qos=target_qos,
            used_gpu_hours=used_hours,
            quota_limit=self.cluster.quota_limit,
            rolling_window_days=self.cluster.rolling_window_days,
            active_jobs=active,
            warning_threshold=self.warning_threshold,
            critical_threshold=self.critical_threshold,
        )

    def forecast_quota(
        self, user: str, records: list[JobRecord], hours_ahead: list[int] | None = None, qos: str | None = None
    ) -> dict[int, float]:
        """Forecast quota availability at future times.

        As time passes, old jobs fall outside the rolling window,
        freeing up quota. This method calculates how much quota
        will be available at each future time point.

        Args:
            user: Username
            records: Job records
            hours_ahead: List of hours to forecast (default: [12, 24, 72, 168])
            qos: QoS to forecast for

        Returns:
            Dict mapping hours_ahead to available GPU-hours at that time

        """
        if hours_ahead is None:
            hours_ahead = [12, 24, 72, 168]

        target_qos = qos if qos is not None else self.cluster.qos[0]
        user_records = [record for record in records if record.user == user]
        qos_filtered = self.filter_by_qos(user_records, target_qos)

        forecast: dict[int, float] = {}
        window_days = self.cluster.rolling_window_days

        for hours in hours_ahead:
            # Calculate what the cutoff will be N hours from now
            future_cutoff = datetime.now(tz=UTC) + timedelta(hours=hours) - timedelta(days=window_days)

            # Sum GPU-hours for jobs that will still be in window at that time
            future_records = [record for record in qos_filtered if record.start_time >= future_cutoff]
            future_usage = self.calculate_gpu_hours(future_records)
            forecast[hours] = self.cluster.quota_limit - future_usage

        return forecast


def fetch_user_jobs(
    user: str,
    cluster: ClusterConfig,
    *,
    all_users: bool = False,
    truncate: bool = True,
    qos_override: str | None = None,
    account_override: str | None = None,
    partition_override: str | None = None,
) -> list[JobRecord]:
    """Fetch job records from Slurm for a user.

    Args:
        user: Username to query (or "ALL" for all users)
        cluster: Cluster configuration
        all_users: If True, fetch all users' jobs
        truncate: If True, truncate job times to the window boundaries
                  (for accurate time-bounded accounting)
        qos_override: Override QoS from config (CLI flag)
        account_override: Override account from config (CLI flag)
        partition_override: Override partition from config (CLI flag)

    Returns:
        List of JobRecord objects

    Raises:
        subprocess.CalledProcessError: If sacct command fails

    """
    # Build command with best-practice flags:
    # -X: allocations only (skip job steps for cleaner data)
    # -S: start time using Slurm's relative time format
    # -T: truncate times to window for accurate accounting
    # --qos: filter at Slurm level (more efficient)
    # --json: structured output
    window_days = cluster.rolling_window_days
    cmd = [
        "sacct",
        "-X",  # Allocations only - skip job steps
        "-S",
        f"now-{window_days}days",  # Slurm relative time format
        "-E",
        "now",
        "--json",
    ]

    # -T truncates job times to the specified window
    # This means a job that started before our window will have its
    # start time set to the window start, giving accurate GPU-hours
    # for the reporting period rather than the full job lifetime
    if truncate:
        cmd.append("-T")

    # QoS: CLI flag > config
    qos = qos_override or (cluster.qos[0] if cluster.qos else None)
    if qos:
        cmd.append(f"--qos={qos}")

    # Account: CLI flag > config
    account = account_override or cluster.account
    if account:
        cmd.append(f"--account={account}")

    # Partition: CLI flag > config
    partition = partition_override or (cluster.partitions[0] if cluster.partitions else None)
    if partition:
        cmd.append(f"--partition={partition}")

    if all_users:
        cmd.append("--allusers")
    else:
        cmd.extend(["-u", user])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603 - sacct args from config
    data = json.loads(result.stdout)
    return parse_sacct_json(data)


def cancel_job(job_id: int, *, quiet: bool = True) -> bool:
    """Cancel a Slurm job.

    Args:
        job_id: The job ID to cancel
        quiet: If True, don't error if job already completed (race condition safe)

    Returns:
        True if command succeeded

    """
    cmd = ["scancel"]
    if quiet:
        cmd.append("-Q")  # Don't error if job already completed
    cmd.append(str(job_id))

    try:
        subprocess.run(cmd, check=True)  # noqa: S603 - scancel with job_id arg
    except subprocess.CalledProcessError:
        return False
    else:
        return True
