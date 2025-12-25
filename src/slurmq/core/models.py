# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Domain models for Slurm quota management.

This module contains the core data structures used throughout slurmq:
- Sacct* models: Pydantic models for sacct JSON output
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

from pydantic import BaseModel, Field


# --- Sacct JSON Models (Pydantic) ---


class SacctTresEntry(BaseModel):
    """Single TRES allocation entry from sacct --json."""

    type: str
    name: str = ""
    count: int = 0


class SacctTimeLimit(BaseModel):
    """Time limit structure from sacct --json."""

    number: int = 0


class SacctTime(BaseModel):
    """Time data from sacct --json job entry."""

    elapsed: int = 0
    start: int = 0
    submission: int = 0
    limit: SacctTimeLimit = Field(default_factory=SacctTimeLimit)


class SacctState(BaseModel):
    """Job state from sacct --json."""

    current: list[str] = Field(default_factory=list)


class SacctTres(BaseModel):
    """TRES allocation data from sacct --json."""

    allocated: list[SacctTresEntry] = Field(default_factory=list)


class SacctRssMax(BaseModel):
    """RSS max value structure."""

    value: int = 0


class SacctRss(BaseModel):
    """RSS statistics structure."""

    max: SacctRssMax = Field(default_factory=SacctRssMax)


class SacctStatistics(BaseModel):
    """Step statistics from sacct --json."""

    RSS: SacctRss = Field(default_factory=SacctRss)


class SacctStep(BaseModel):
    """Job step from sacct --json."""

    statistics: SacctStatistics = Field(default_factory=SacctStatistics)


class SacctRequired(BaseModel):
    """Required resources from sacct --json."""

    memory: str = ""


class SacctJob(BaseModel):
    """Single job record from sacct --json output."""

    job_id: int
    name: str = ""
    user: str = ""
    account: str = ""
    qos: str = ""
    state: SacctState = Field(default_factory=SacctState)
    time: SacctTime = Field(default_factory=SacctTime)
    tres: SacctTres = Field(default_factory=SacctTres)
    allocation_nodes: int = 1
    required: SacctRequired = Field(default_factory=SacctRequired)
    steps: list[SacctStep] = Field(default_factory=list)


class SacctOutput(BaseModel):
    """Root sacct --json output structure."""

    jobs: list[SacctJob] = Field(default_factory=list)


# --- Domain Enums ---


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
        """Allocated GPU-hours (n_gpus x elapsed time, not utilization)."""
        return (self.n_gpus * self.elapsed_seconds) / 3600

    @classmethod
    def from_sacct(cls, job: SacctJob) -> JobRecord:
        """Parse a job record from sacct JSON output.

        Args:
            job: Validated SacctJob from sacct --json output

        Returns:
            Parsed JobRecord

        """
        # Extract GPU count and CPU count from TRES
        n_gpus = 0
        n_cpus = 0
        for tres in job.tres.allocated:
            if tres.type == "gres" and tres.name == "gpu":
                n_gpus = tres.count
            elif tres.type == "cpu":
                n_cpus = tres.count

        # Parse state (using our enum)
        state_str = job.state.current[0] if job.state.current else "UNKNOWN"
        state = JobState.from_slurm(state_str)

        # Get max RSS from steps
        max_rss = max((step.statistics.RSS.max.value for step in job.steps), default=0)

        return cls(
            job_id=job.job_id,
            name=job.name,
            user=job.user,
            qos=job.qos,
            account=job.account,
            n_gpus=n_gpus,
            n_cpus=n_cpus,
            req_mem=job.required.memory,
            max_rss=max_rss,
            elapsed_seconds=job.time.elapsed,
            start_time=datetime.fromtimestamp(job.time.start, tz=UTC)
            if job.time.start
            else datetime.min.replace(tzinfo=UTC),
            submission_time=datetime.fromtimestamp(job.time.submission, tz=UTC)
            if job.time.submission
            else datetime.min.replace(tzinfo=UTC),
            state=state,
            allocation_nodes=job.allocation_nodes,
        )


def parse_sacct_json(data: dict[str, Any]) -> list[JobRecord]:
    """Parse sacct JSON output into JobRecords.

    Args:
        data: Raw sacct --json output dict (will be validated)

    Returns:
        List of JobRecord objects

    """
    output = SacctOutput.model_validate(data)
    return [JobRecord.from_sacct(job) for job in output.jobs]


@dataclass
class UsageReport:
    """A user's quota usage report.

    GPU-hours are allocation-based (reserved time * GPUs), not utilization.

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
