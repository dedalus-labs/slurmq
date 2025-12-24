# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Quota calculation and checking for Slurm GPU usage.

This module handles:
- Parsing sacct output to extract job records
- Calculating GPU-hours used within a rolling window
- Generating usage reports with status (OK, WARNING, EXCEEDED)
- Forecasting quota availability at future times
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ClusterConfig


class JobState(StrEnum):
    """Slurm job states with metadata about severity."""

    # Normal states
    COMPLETED = "COMPLETED"
    RUNNING = "RUNNING"
    PENDING = "PENDING"
    CANCELLED = "CANCELLED"

    # Problematic states (highlighted in reports)
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    NODE_FAIL = "NODE_FAIL"
    PREEMPTED = "PREEMPTED"

    # Other states
    SUSPENDED = "SUSPENDED"
    REQUEUED = "REQUEUED"
    BOOT_FAIL = "BOOT_FAIL"
    DEADLINE = "DEADLINE"
    RESIZING = "RESIZING"
    REVOKED = "REVOKED"

    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_slurm(cls, state_str: str) -> JobState:
        """Parse Slurm state string (handles abbreviations)."""
        # Map abbreviations to full names
        abbrevs = {
            "BF": cls.BOOT_FAIL,
            "CA": cls.CANCELLED,
            "CD": cls.COMPLETED,
            "DL": cls.DEADLINE,
            "F": cls.FAILED,
            "NF": cls.NODE_FAIL,
            "OOM": cls.OUT_OF_MEMORY,
            "PD": cls.PENDING,
            "PR": cls.PREEMPTED,
            "R": cls.RUNNING,
            "RQ": cls.REQUEUED,
            "RS": cls.RESIZING,
            "RV": cls.REVOKED,
            "S": cls.SUSPENDED,
            "TO": cls.TIMEOUT,
        }
        # Strip any suffix like "by 12345" from "CANCELLED by 12345"
        base_state = state_str.split()[0].upper()
        if base_state in abbrevs:
            return abbrevs[base_state]
        try:
            return cls(base_state)
        except ValueError:
            return cls.UNKNOWN

    @property
    def is_running(self) -> bool:
        """Check if job is active."""
        return self in (JobState.RUNNING, JobState.PENDING)

    @property
    def is_problematic(self) -> bool:
        """Check if this state indicates a problem."""
        return self in (
            JobState.FAILED,
            JobState.TIMEOUT,
            JobState.OUT_OF_MEMORY,
            JobState.NODE_FAIL,
            JobState.PREEMPTED,
            JobState.BOOT_FAIL,
        )

    @property
    def color(self) -> str:
        """Rich color for this state."""
        colors = {
            JobState.COMPLETED: "green",
            JobState.RUNNING: "cyan",
            JobState.PENDING: "yellow",
            JobState.CANCELLED: "dim",
            JobState.FAILED: "red bold",
            JobState.TIMEOUT: "red",
            JobState.OUT_OF_MEMORY: "red bold",
            JobState.NODE_FAIL: "red",
            JobState.PREEMPTED: "orange1",
        }
        return colors.get(self, "white")

    @property
    def symbol(self) -> str:
        """Short symbol/indicator for this state."""
        symbols = {
            JobState.COMPLETED: "ok",
            JobState.RUNNING: ">",
            JobState.PENDING: ".",
            JobState.CANCELLED: "x",
            JobState.FAILED: "x",
            JobState.TIMEOUT: "T",
            JobState.OUT_OF_MEMORY: "OOM",
            JobState.NODE_FAIL: "NF",
            JobState.PREEMPTED: "PR",
        }
        return symbols.get(self, "?")


class QuotaStatus(StrEnum):
    """Status of quota usage."""

    OK = auto()
    WARNING = auto()
    EXCEEDED = auto()

    @classmethod
    def from_usage(cls, percentage: float, warning: float = 0.8, critical: float = 1.0) -> QuotaStatus:
        """Determine status from usage percentage.

        Args:
            percentage: Usage as fraction (e.g., 0.5 = 50%)
            warning: Threshold for warning status
            critical: Threshold for exceeded status

        Returns:
            QuotaStatus based on thresholds
        """
        if percentage >= critical:
            return cls.EXCEEDED
        if percentage >= warning:
            return cls.WARNING
        return cls.OK


@dataclass
class JobRecord:
    """A single Slurm job record."""

    job_id: int
    name: str
    user: str
    qos: str
    n_gpus: int
    elapsed_seconds: int
    start_time: datetime
    submission_time: datetime
    state: JobState
    account: str = ""
    allocation_nodes: int = 1
    n_cpus: int = 0
    req_mem: str = ""  # Requested memory (e.g., "32G")
    max_rss: int = 0  # Max RSS in bytes (for efficiency calc)

    @property
    def is_running(self) -> bool:
        """Check if job is currently running."""
        return self.state.is_running

    @property
    def is_problematic(self) -> bool:
        """Check if job ended with a problem."""
        return self.state.is_problematic

    @property
    def gpu_hours(self) -> float:
        """Calculate GPU-hours for this job."""
        return (self.n_gpus * self.elapsed_seconds) / 3600

    @classmethod
    def from_sacct(cls, job_data: dict[str, Any]) -> JobRecord:
        """Parse a job record from sacct JSON output.

        Args:
            job_data: Single job dict from sacct --json output

        Returns:
            Parsed JobRecord
        """
        # Extract GPU count and CPU count from TRES
        n_gpus = 0
        n_cpus = 0
        for tres in job_data.get("tres", {}).get("allocated", []):
            if tres.get("type") == "gres" and tres.get("name") == "gpu":
                n_gpus = int(tres.get("count", 0))
            elif tres.get("type") == "cpu":
                n_cpus = int(tres.get("count", 0))

        # Parse time fields
        time_data = job_data.get("time", {})
        start_ts = time_data.get("start", 0)
        submission_ts = time_data.get("submission", 0)

        # Parse state (using our enum)
        state_data = job_data.get("state", {})
        current_state = state_data.get("current", ["UNKNOWN"])
        state_str = current_state[0] if current_state else "UNKNOWN"
        state = JobState.from_slurm(state_str)

        # Parse memory fields for efficiency
        req_mem = job_data.get("required", {}).get("memory", "")
        max_rss = 0
        # maxrss is typically in the steps, try to get it
        if "steps" in job_data:
            for step in job_data.get("steps", []):
                step_rss = step.get("statistics", {}).get("RSS", {}).get("max", {}).get("value", 0)
                max_rss = max(max_rss, step_rss)

        return cls(
            job_id=job_data.get("job_id", 0),
            name=job_data.get("name", ""),
            user=job_data.get("user", ""),
            qos=job_data.get("qos", ""),
            account=job_data.get("account", ""),
            n_gpus=n_gpus,
            n_cpus=n_cpus,
            req_mem=req_mem,
            max_rss=max_rss,
            elapsed_seconds=time_data.get("elapsed", 0),
            start_time=datetime.fromtimestamp(start_ts, tz=UTC) if start_ts else datetime.min.replace(tzinfo=UTC),
            submission_time=datetime.fromtimestamp(submission_ts, tz=UTC)
            if submission_ts
            else datetime.min.replace(tzinfo=UTC),
            state=state,
            allocation_nodes=job_data.get("allocation_nodes", 1),
        )


def parse_sacct_json(data: dict[str, Any]) -> list[JobRecord]:
    """Parse sacct JSON output into JobRecords.

    Args:
        data: Full sacct --json output dict

    Returns:
        List of JobRecord objects
    """
    jobs = data.get("jobs", [])
    return [JobRecord.from_sacct(job) for job in jobs]


@dataclass
class UsageReport:
    """A user's quota usage report."""

    user: str
    qos: str
    used_gpu_hours: float
    quota_limit: int
    rolling_window_days: int
    active_jobs: list[JobRecord] = field(default_factory=list)
    warning_threshold: float = 0.8
    critical_threshold: float = 1.0

    @property
    def remaining_gpu_hours(self) -> float:
        """GPU-hours remaining in quota."""
        return self.quota_limit - self.used_gpu_hours

    @property
    def usage_percentage(self) -> float:
        """Usage as a fraction (0.0 to 1.0+)."""
        if self.quota_limit == 0:
            return 0.0
        return self.used_gpu_hours / self.quota_limit

    @property
    def status(self) -> QuotaStatus:
        """Current quota status."""
        return QuotaStatus.from_usage(self.usage_percentage, self.warning_threshold, self.critical_threshold)


class QuotaChecker:
    """Checks GPU quota usage against cluster configuration."""

    def __init__(self, cluster: ClusterConfig, warning_threshold: float = 0.8, critical_threshold: float = 1.0) -> None:
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
        """Calculate total GPU-hours from job records.

        Args:
            records: List of job records

        Returns:
            Total GPU-hours
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
        return [r for r in records if r.start_time >= cutoff]

    def filter_by_qos(self, records: list[JobRecord], qos: str | None = None) -> list[JobRecord]:
        """Filter records by QoS.

        Args:
            records: List of job records
            qos: QoS to filter by (uses first from cluster config if None)

        Returns:
            Records matching the QoS
        """
        target_qos = qos if qos is not None else self.cluster.qos[0]
        return [r for r in records if r.qos == target_qos]

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
        user_records = [r for r in records if r.user == user]
        windowed = self.filter_by_window(user_records)
        qos_filtered = self.filter_by_qos(windowed, target_qos)

        used_hours = self.calculate_gpu_hours(qos_filtered)
        active = [r for r in qos_filtered if r.is_running]

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
        user_records = [r for r in records if r.user == user]
        qos_filtered = self.filter_by_qos(user_records, target_qos)

        forecast: dict[int, float] = {}
        window_days = self.cluster.rolling_window_days

        for hours in hours_ahead:
            # Calculate what the cutoff will be N hours from now
            future_cutoff = datetime.now(tz=UTC) + timedelta(hours=hours) - timedelta(days=window_days)

            # Sum GPU-hours for jobs that will still be in window at that time
            future_records = [r for r in qos_filtered if r.start_time >= future_cutoff]
            future_usage = self.calculate_gpu_hours(future_records)
            forecast[hours] = self.cluster.quota_limit - future_usage

        return forecast


def fetch_user_jobs(
    user: str,
    cluster: ClusterConfig,
    all_users: bool = False,
    truncate: bool = True,
    *,
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
        f"-S=now-{window_days}days",  # Slurm's nice relative time format
        "-E=now",
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

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return parse_sacct_json(data)


def cancel_job(job_id: int, quiet: bool = True) -> bool:
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
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
