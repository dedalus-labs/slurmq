# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Domain models for Slurm quota management.

This module contains the core data structures used throughout slurmq:
- JobState: Enum for Slurm job states with metadata
- QuotaStatus: Enum for quota status levels
- JobRecord: Parsed job data from sacct
- UsageReport: User quota usage summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any


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
        """Allocated GPU-hours (n_gpus × elapsed time, not utilization)."""
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
    """A user's quota usage report.

    GPU-hours are allocation-based (reserved time × GPUs), not utilization.

    """

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
        """Allocated GPU-hours remaining in quota."""
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
