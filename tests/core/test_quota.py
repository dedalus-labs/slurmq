# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for quota calculation and checking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TypedDict

import pytest

from slurmq.core.config import ClusterConfig
from slurmq.core.models import JobRecord, JobState, QuotaStatus, UsageReport, parse_sacct_json
from slurmq.core.quota import QuotaChecker


class TresEntry(TypedDict, total=False):
    """Single TRES allocation entry from sacct."""

    type: str
    name: str
    count: int


class TimeLimit(TypedDict, total=False):
    """Time limit structure from sacct."""

    number: int


class TimeData(TypedDict, total=False):
    """Time data from sacct job."""

    elapsed: int
    start: int
    submission: int
    limit: TimeLimit


class StateData(TypedDict):
    """Job state from sacct."""

    current: list[str]


class TresData(TypedDict, total=False):
    """TRES allocation data from sacct."""

    allocated: list[TresEntry]


class SacctJob(TypedDict, total=False):
    """Single job record from sacct JSON output."""

    job_id: int
    name: str
    user: str
    account: str
    qos: str
    state: StateData
    time: TimeData
    tres: TresData
    allocation_nodes: int


class SacctOutput(TypedDict):
    """Root sacct --json output structure."""

    jobs: list[SacctJob]


SAMPLE_SACCT_OUTPUT: SacctOutput = {
    "jobs": [
        {
            "job_id": 12345,
            "name": "train_model",
            "user": "alice",
            "account": "research",
            "qos": "high-priority",
            "state": {"current": ["COMPLETED"]},
            "time": {
                "elapsed": 7200,  # 2 hours
                "start": 1700000000,
                "submission": 1699999000,
                "limit": {"number": 86400},
            },
            "tres": {
                "allocated": [
                    {"type": "cpu", "name": "", "count": 8},
                    {"type": "gres", "name": "gpu", "count": 4},
                    {"type": "mem", "name": "", "count": 32000},
                ]
            },
            "allocation_nodes": 1,
        },
        {
            "job_id": 12346,
            "name": "inference",
            "user": "alice",
            "account": "research",
            "qos": "high-priority",
            "state": {"current": ["RUNNING"]},
            "time": {
                "elapsed": 3600,  # 1 hour so far
                "start": 1700003600,
                "submission": 1700003500,
                "limit": {"number": 86400},
            },
            "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 2}]},
            "allocation_nodes": 1,
        },
    ]
}


class TestJobRecord:
    """Tests for JobRecord parsing."""

    def test_parse_job_with_gpus(self) -> None:
        """Can parse a job with GPU allocation."""
        job_data = SAMPLE_SACCT_OUTPUT["jobs"][0]
        record = JobRecord.from_sacct(job_data)

        assert record.job_id == 12345
        assert record.name == "train_model"
        assert record.user == "alice"
        assert record.qos == "high-priority"
        assert record.n_gpus == 4
        assert record.elapsed_seconds == 7200
        assert record.is_running is False

    def test_parse_running_job(self) -> None:
        """Can identify a running job."""
        job_data = SAMPLE_SACCT_OUTPUT["jobs"][1]
        record = JobRecord.from_sacct(job_data)

        assert record.job_id == 12346
        assert record.is_running is True

    def test_gpu_hours_calculation(self) -> None:
        """GPU-hours calculated correctly."""
        job_data = SAMPLE_SACCT_OUTPUT["jobs"][0]
        record = JobRecord.from_sacct(job_data)

        # 4 GPUs * 2 hours = 8 GPU-hours
        assert record.gpu_hours == 8.0

    def test_job_without_gpus(self) -> None:
        """Jobs without GPUs have 0 GPU-hours."""
        job_data = {
            "job_id": 99999,
            "name": "cpu_job",
            "user": "bob",
            "account": "research",
            "qos": "normal",
            "state": {"current": ["COMPLETED"]},
            "time": {"elapsed": 3600, "start": 1700000000, "submission": 1699999000},
            "tres": {"allocated": [{"type": "cpu", "name": "", "count": 16}]},
        }
        record = JobRecord.from_sacct(job_data)
        assert record.n_gpus == 0
        assert record.gpu_hours == 0.0


class TestParseSacctJson:
    """Tests for parsing sacct JSON output."""

    def test_parse_multiple_jobs(self) -> None:
        """Can parse multiple jobs from sacct output."""
        records = parse_sacct_json(SAMPLE_SACCT_OUTPUT)
        assert len(records) == 2
        assert records[0].job_id == 12345
        assert records[1].job_id == 12346

    def test_parse_empty_output(self) -> None:
        """Empty jobs list returns empty list."""
        records = parse_sacct_json({"jobs": []})
        assert records == []


class TestJobState:
    """Tests for JobState enum."""

    def test_parse_full_state_names(self) -> None:
        """Can parse full Slurm state names."""
        assert JobState.from_slurm("COMPLETED") == JobState.COMPLETED
        assert JobState.from_slurm("RUNNING") == JobState.RUNNING
        assert JobState.from_slurm("PENDING") == JobState.PENDING
        assert JobState.from_slurm("FAILED") == JobState.FAILED
        assert JobState.from_slurm("TIMEOUT") == JobState.TIMEOUT
        assert JobState.from_slurm("OUT_OF_MEMORY") == JobState.OUT_OF_MEMORY

    def test_parse_abbreviations(self) -> None:
        """Can parse Slurm state abbreviations."""
        assert JobState.from_slurm("CD") == JobState.COMPLETED
        assert JobState.from_slurm("R") == JobState.RUNNING
        assert JobState.from_slurm("PD") == JobState.PENDING
        assert JobState.from_slurm("F") == JobState.FAILED
        assert JobState.from_slurm("TO") == JobState.TIMEOUT
        assert JobState.from_slurm("OOM") == JobState.OUT_OF_MEMORY
        assert JobState.from_slurm("PR") == JobState.PREEMPTED
        assert JobState.from_slurm("NF") == JobState.NODE_FAIL

    def test_parse_state_with_suffix(self) -> None:
        """Can parse states with 'by UID' suffix."""
        assert JobState.from_slurm("CANCELLED by 12345") == JobState.CANCELLED

    def test_problematic_states(self) -> None:
        """Correctly identifies problematic states."""
        assert JobState.FAILED.is_problematic
        assert JobState.TIMEOUT.is_problematic
        assert JobState.OUT_OF_MEMORY.is_problematic
        assert JobState.NODE_FAIL.is_problematic
        assert not JobState.COMPLETED.is_problematic
        assert not JobState.RUNNING.is_problematic

    def test_running_states(self) -> None:
        """Correctly identifies running states."""
        assert JobState.RUNNING.is_running
        assert JobState.PENDING.is_running
        assert not JobState.COMPLETED.is_running
        assert not JobState.FAILED.is_running


class TestQuotaStatus:
    """Tests for QuotaStatus enum."""

    def test_status_from_percentage(self) -> None:
        """Status determined correctly from usage percentage."""
        assert QuotaStatus.from_usage(0.5, warning=0.8, critical=1.0) == QuotaStatus.OK
        assert QuotaStatus.from_usage(0.85, warning=0.8, critical=1.0) == QuotaStatus.WARNING
        assert QuotaStatus.from_usage(1.0, warning=0.8, critical=1.0) == QuotaStatus.EXCEEDED
        assert QuotaStatus.from_usage(1.5, warning=0.8, critical=1.0) == QuotaStatus.EXCEEDED


class TestUsageReport:
    """Tests for UsageReport dataclass."""

    def test_basic_report(self) -> None:
        """Can create a basic usage report."""
        report = UsageReport(
            user="alice", qos="high-priority", used_gpu_hours=100.0, quota_limit=500, rolling_window_days=30
        )
        assert report.remaining_gpu_hours == 400.0
        assert report.usage_percentage == pytest.approx(0.2)
        assert report.status == QuotaStatus.OK

    def test_exceeded_report(self) -> None:
        """Report shows exceeded status when over quota."""
        report = UsageReport(
            user="bob", qos="high-priority", used_gpu_hours=600.0, quota_limit=500, rolling_window_days=30
        )
        assert report.remaining_gpu_hours == -100.0
        assert report.usage_percentage == pytest.approx(1.2)
        assert report.status == QuotaStatus.EXCEEDED


class TestQuotaChecker:
    """Tests for QuotaChecker class."""

    @pytest.fixture
    def cluster_config(self) -> ClusterConfig:
        """Sample cluster configuration."""
        return ClusterConfig(
            name="Stella", account="research", qos=["high-priority"], quota_limit=500, rolling_window_days=30
        )

    @pytest.fixture
    def checker(self, cluster_config: ClusterConfig) -> QuotaChecker:
        """QuotaChecker with sample config."""
        return QuotaChecker(cluster_config)

    def test_calculate_usage_from_records(self, checker: QuotaChecker) -> None:
        """Can calculate total GPU-hours from job records."""
        records = parse_sacct_json(SAMPLE_SACCT_OUTPUT)
        total = checker.calculate_gpu_hours(records)

        # Job 1: 4 GPUs * 2h = 8 GPU-hours
        # Job 2: 2 GPUs * 1h = 2 GPU-hours
        # Total: 10 GPU-hours
        assert total == pytest.approx(10.0)

    def test_filter_records_by_time(self, checker: QuotaChecker) -> None:
        """Can filter records within time window."""
        now = datetime.now(tz=UTC)
        records = [
            JobRecord(
                job_id=1,
                name="old_job",
                user="alice",
                qos="high-priority",
                n_gpus=4,
                elapsed_seconds=3600,
                start_time=now - timedelta(days=60),
                submission_time=now - timedelta(days=60),
                state=JobState.COMPLETED,
            ),
            JobRecord(
                job_id=2,
                name="recent_job",
                user="alice",
                qos="high-priority",
                n_gpus=4,
                elapsed_seconds=3600,
                start_time=now - timedelta(days=10),
                submission_time=now - timedelta(days=10),
                state=JobState.COMPLETED,
            ),
        ]

        # With 30-day window, only the recent job should count
        filtered = checker.filter_by_window(records, window_days=30)
        assert len(filtered) == 1
        assert filtered[0].job_id == 2

    def test_generate_report(self, checker: QuotaChecker) -> None:
        """Can generate a usage report."""
        now = datetime.now(tz=UTC)
        # Create records with recent timestamps that will be within the rolling window
        records = [
            JobRecord(
                job_id=1,
                name="train_model",
                user="alice",
                qos="high-priority",
                n_gpus=4,
                elapsed_seconds=7200,  # 2 hours -> 8 GPU-hours
                start_time=now - timedelta(days=5),
                submission_time=now - timedelta(days=5),
                state=JobState.COMPLETED,
            ),
            JobRecord(
                job_id=2,
                name="inference",
                user="alice",
                qos="high-priority",
                n_gpus=2,
                elapsed_seconds=3600,  # 1 hour -> 2 GPU-hours
                start_time=now - timedelta(days=2),
                submission_time=now - timedelta(days=2),
                state=JobState.RUNNING,
            ),
        ]
        report = checker.generate_report("alice", records)

        assert report.user == "alice"
        assert report.qos == "high-priority"
        assert report.used_gpu_hours == pytest.approx(10.0)
        assert report.quota_limit == 500
        assert report.remaining_gpu_hours == pytest.approx(490.0)
        assert report.status == QuotaStatus.OK

    def test_forecast_quota(self, checker: QuotaChecker) -> None:
        """Can forecast quota availability at future times."""
        now = datetime.now(tz=UTC)
        # Create records with specific timestamps for forecasting
        records = [
            JobRecord(
                job_id=1,
                name="job",
                user="alice",
                qos="high-priority",
                n_gpus=10,
                elapsed_seconds=3600,  # 1 hour
                start_time=now - timedelta(days=29),  # Near edge of window
                submission_time=now - timedelta(days=29),
                state=JobState.COMPLETED,
            )
        ]

        # Currently: 10 GPU-hours used (10 GPUs * 1h)
        # In 24 hours: that job will fall outside the window
        forecast = checker.forecast_quota("alice", records, hours_ahead=[24, 48])

        assert 24 in forecast
        assert 48 in forecast
        # After 24h, the job should be outside the 30-day window
        assert forecast[24] >= forecast[48]  # Usage should decrease or stay same


class TestQuotaCheckerWithMockedSlurm:
    """Tests that mock Slurm commands."""

    @pytest.fixture
    def mock_sacct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock subprocess.run for sacct command."""
        import json
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
            if cmd[0] == "sacct":
                output = json.dumps(SAMPLE_SACCT_OUTPUT)
                return subprocess.CompletedProcess(cmd, returncode=0, stdout=output, stderr="")
            msg = f"Unexpected command: {cmd}"
            raise ValueError(msg)

        monkeypatch.setattr(subprocess, "run", mock_run)

    def test_fetch_usage_mocked(self, mock_sacct: None, cluster_config: ClusterConfig) -> None:
        """Can fetch usage with mocked sacct."""
        from slurmq.core.quota import fetch_user_jobs

        cluster_config = ClusterConfig(
            name="Stella", account="research", qos=["high-priority"], quota_limit=500, rolling_window_days=30
        )

        records = fetch_user_jobs("alice", cluster_config)
        assert len(records) == 2

    @pytest.fixture
    def cluster_config(self) -> ClusterConfig:
        """Sample cluster configuration."""
        return ClusterConfig(
            name="Stella", account="research", qos=["high-priority"], quota_limit=500, rolling_window_days=30
        )
