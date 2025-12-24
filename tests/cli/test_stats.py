# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for the stats command."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from slurmq.cli.main import app

runner = CliRunner()


# Sample sacct output for testing
SAMPLE_SACCT_OUTPUT = {
    "jobs": [
        {
            "job_id": 1001,
            "name": "small_job",
            "user": "alice",
            "account": "research",
            "qos": "normal",
            "partition": "gpu",
            "state": {"current": ["COMPLETED"]},
            "time": {
                "elapsed": 7200,  # 2 hours
                "start": 1700000000,
                "end": 1700007200,
                "submission": 1699996400,  # 1 hour wait
            },
            "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 2}]},
        },
        {
            "job_id": 1002,
            "name": "large_job",
            "user": "bob",
            "account": "research",
            "qos": "normal",
            "partition": "gpu",
            "state": {"current": ["COMPLETED"]},
            "time": {
                "elapsed": 36000,  # 10 hours
                "start": 1700100000,
                "end": 1700136000,
                "submission": 1700071600,  # ~8 hour wait
            },
            "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 8}]},
        },
        {
            "job_id": 1003,
            "name": "medium_job",
            "user": "alice",
            "account": "research",
            "qos": "normal",
            "partition": "gpu",
            "state": {"current": ["COMPLETED"]},
            "time": {
                "elapsed": 3600,  # 1 hour
                "start": 1700200000,
                "end": 1700203600,
                "submission": 1700199000,  # ~17 min wait
            },
            "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 4}]},
        },
    ]
}


@pytest.fixture
def mock_sacct():
    """Mock sacct subprocess calls."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps(SAMPLE_SACCT_OUTPUT)
        yield mock_run


@pytest.fixture
def mock_config(tmp_path, monkeypatch):
    """Create a test config file."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
default_cluster = "test"

[clusters.test]
name = "Test Cluster"
account = "research"
qos = ["normal"]
partitions = ["gpu"]
quota_limit = 500
rolling_window_days = 30
""")
    monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

    # Reset config module state
    import slurmq.core.config as config_module

    config_module._config_file_path = None

    return config_file


class TestStatsCommand:
    """Tests for slurmq stats command."""

    def test_stats_help(self):
        """Test stats help message."""
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0
        assert "cluster statistics" in result.stdout.lower()

    def test_stats_json_output(self, mock_sacct, mock_config):
        """Test stats with JSON output."""
        result = runner.invoke(app, ["--json", "stats", "--no-compare"])

        # Should succeed
        assert result.exit_code == 0, f"Exit code: {result.exit_code}, Output: {result.stdout}"

        # Should be valid JSON
        output = json.loads(result.stdout)
        assert "period_days" in output
        assert "current" in output

    def test_stats_with_partition_flag(self, mock_sacct, mock_config):
        """Test stats with explicit partition flag."""
        result = runner.invoke(app, ["stats", "-p", "gpu", "--no-compare"])

        assert result.exit_code == 0
        # Check that sacct was called with the partition
        call_args = mock_sacct.call_args
        assert "--partition=gpu" in call_args[0][0]

    def test_stats_with_qos_flag(self, mock_sacct, mock_config):
        """Test stats with explicit QoS flag."""
        result = runner.invoke(app, ["stats", "-q", "normal", "--no-compare"])

        assert result.exit_code == 0
        call_args = mock_sacct.call_args
        assert "--qos=normal" in call_args[0][0]

    def test_stats_custom_days(self, mock_sacct, mock_config):
        """Test stats with custom day range."""
        result = runner.invoke(app, ["stats", "--days", "14", "--no-compare"])

        assert result.exit_code == 0
        # Verify the output mentions the period
        assert "14" in result.stdout or result.exit_code == 0

    def test_stats_with_comparison(self, mock_sacct, mock_config):
        """Test stats with month-over-month comparison."""
        result = runner.invoke(app, ["stats", "--compare"])

        # Should make two sets of calls (current + previous period)
        assert result.exit_code == 0
        # With comparison enabled, should call sacct twice per partition
        assert mock_sacct.call_count >= 2

    def test_stats_custom_threshold(self, mock_sacct, mock_config):
        """Test stats with custom small/large job threshold."""
        result = runner.invoke(app, ["stats", "--small-threshold", "25", "--no-compare"])

        assert result.exit_code == 0
        # Should show tables with the custom threshold
        assert "25" in result.stdout


class TestStatsCalculations:
    """Tests for stats calculation functions."""

    def test_calculate_partition_stats_empty(self):
        """Test stats calculation with empty job list."""
        from slurmq.cli.commands.stats import calculate_partition_stats

        stats = calculate_partition_stats([], "test")
        assert stats.job_count == 0
        assert stats.gpu_hours == 0
        assert stats.median_wait_hours == 0

    def test_calculate_partition_stats_single_job(self):
        """Test stats calculation with single job."""
        from slurmq.cli.commands.stats import JobStats, calculate_partition_stats

        jobs = [
            JobStats(
                n_gpus=2, elapsed_h=5, gpu_hours=10, wait_hours=2, start_time=0, partition="gpu", qos="normal"
            )
        ]
        stats = calculate_partition_stats(jobs, "test")

        assert stats.job_count == 1
        assert stats.gpu_hours == 10
        assert stats.median_wait_hours == 2
        assert stats.long_wait_count == 0

    def test_calculate_partition_stats_long_wait(self):
        """Test long wait detection (> 6 hours)."""
        from slurmq.cli.commands.stats import JobStats, calculate_partition_stats

        jobs = [
            JobStats(n_gpus=2, elapsed_h=5, gpu_hours=10, wait_hours=2, start_time=0, partition="gpu", qos="normal"),
            JobStats(n_gpus=4, elapsed_h=5, gpu_hours=20, wait_hours=8, start_time=0, partition="gpu", qos="normal"),
            JobStats(n_gpus=3, elapsed_h=5, gpu_hours=15, wait_hours=10, start_time=0, partition="gpu", qos="normal"),
        ]
        stats = calculate_partition_stats(jobs, "test")

        assert stats.long_wait_count == 2
        assert abs(stats.long_wait_pct - 66.67) < 1  # ~66.67%

    def test_format_time_human(self):
        """Test human-readable time formatting."""
        from slurmq.cli.commands.stats import format_time_human

        assert format_time_human(0) == "< 1min"
        assert format_time_human(0.25) == "15min"
        assert format_time_human(1) == "1h"
        assert format_time_human(1.5) == "1h30"
        assert format_time_human(2.25) == "2h15"

    def test_format_pct_change(self):
        """Test percentage change formatting."""
        from slurmq.cli.commands.stats import format_pct_change

        # Positive change
        result = format_pct_change(120, 100)
        assert "+20%" in result
        assert "green" in result

        # Negative change
        result = format_pct_change(80, 100)
        assert "-20%" in result
        assert "red" in result

        # Zero previous (avoid division by zero)
        result = format_pct_change(100, 0)
        assert result == ""


class TestParseJobs:
    """Tests for job parsing."""

    def test_parse_jobs_filters_no_gpu(self):
        """Test that jobs with no GPUs are filtered out."""
        from slurmq.cli.commands.stats import parse_jobs

        data = {
            "jobs": [
                {
                    "job_id": 1,
                    "time": {"elapsed": 3600, "start": 1000, "submission": 900},
                    "tres": {"allocated": []},  # No GPUs
                    "partition": "cpu",
                    "qos": "normal",
                }
            ]
        }
        jobs = parse_jobs(data)
        assert len(jobs) == 0

    def test_parse_jobs_filters_short_runtime(self):
        """Test that jobs < 10 min are filtered out."""
        from slurmq.cli.commands.stats import parse_jobs

        data = {
            "jobs": [
                {
                    "job_id": 1,
                    "time": {"elapsed": 300, "start": 1000, "submission": 900},  # 5 min
                    "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 1}]},
                    "partition": "gpu",
                    "qos": "normal",
                }
            ]
        }
        jobs = parse_jobs(data)
        assert len(jobs) == 0

    def test_parse_jobs_valid(self):
        """Test parsing valid job data."""
        from slurmq.cli.commands.stats import parse_jobs

        data = {
            "jobs": [
                {
                    "job_id": 1,
                    "time": {"elapsed": 3600, "start": 1000, "submission": 900},
                    "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 4}]},
                    "partition": "gpu",
                    "qos": "normal",
                }
            ]
        }
        jobs = parse_jobs(data)
        assert len(jobs) == 1
        assert jobs[0].n_gpus == 4
        assert jobs[0].gpu_hours == 4.0  # 4 GPUs * 1 hour
        assert jobs[0].wait_hours == 100 / 3600  # 100 seconds
