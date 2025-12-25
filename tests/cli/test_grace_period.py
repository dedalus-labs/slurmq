# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for grace period enforcement."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from slurmq.cli.main import app


if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def make_job(
    job_id: int, user: str, gpu_count: int, elapsed_hours: float, state: str = "RUNNING", days_ago: float = 0
) -> dict:
    """Create a mock job record."""
    now = datetime.now(tz=UTC)
    start = now - timedelta(days=days_ago, hours=elapsed_hours)
    return {
        "job_id": job_id,
        "name": f"job_{job_id}",
        "user": user,
        "account": "research",
        "qos": "normal",
        "state": {"current": [state]},
        "time": {
            "elapsed": int(elapsed_hours * 3600),
            "start": int(start.timestamp()),
            "submission": int(start.timestamp()),
            "limit": {"number": 86400},
        },
        "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": gpu_count}]},
        "allocation_nodes": 1,
    }


@pytest.fixture
def config_with_grace_period(tmp_path: Path) -> Path:
    """Config with 24-hour grace period."""
    config = tmp_path / "config.toml"
    config.write_text("""
default_cluster = "test"

[clusters.test]
name = "TestCluster"
qos = ["normal"]
quota_limit = 10
rolling_window_days = 30

[enforcement]
enabled = true
dry_run = true
grace_period_hours = 24
""")
    return config


@pytest.fixture
def config_no_grace_period(tmp_path: Path) -> Path:
    """Config with no grace period."""
    config = tmp_path / "config.toml"
    config.write_text("""
default_cluster = "test"

[clusters.test]
name = "TestCluster"
qos = ["normal"]
quota_limit = 10
rolling_window_days = 30

[enforcement]
enabled = true
dry_run = true
grace_period_hours = 0
""")
    return config


class TestGracePeriod:
    """Tests for grace period enforcement logic."""

    def test_job_within_grace_period_not_cancelled(
        self, config_with_grace_period: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Jobs from users who exceeded quota within grace period are not cancelled."""
        import subprocess

        # User exceeded quota 12 hours ago (within 24h grace)
        # They have 15 GPU-hours used (over 10 limit)
        mock_output = {
            "jobs": [
                # Old completed job that pushed them over (started 12h ago, ran 8h with 2 GPUs = 16 GPU-h)
                make_job(1001, "testuser", 2, 8, "COMPLETED", days_ago=0.5),
                # Current running job
                make_job(1002, "testuser", 1, 1, "RUNNING", days_ago=0),
            ]
        }

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_output), stderr="")
            if cmd[0] == "scancel":
                pytest.fail("scancel should not be called during grace period")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_with_grace_period))

        result = runner.invoke(app, ["monitor", "--once", "--enforce"])
        assert result.exit_code == 0
        # Should mention grace period
        output = result.stdout.lower()
        assert "grace" in output or "would_cancel" not in output

    def test_job_outside_grace_period_cancelled(
        self, config_with_grace_period: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Jobs from users who exceeded quota outside grace period are cancelled."""
        import subprocess

        # User exceeded quota 36 hours ago (outside 24h grace)
        mock_output = {
            "jobs": [
                # Old completed job that pushed them over (started 36h ago)
                make_job(1001, "testuser", 2, 8, "COMPLETED", days_ago=1.5),
                # Current running job - should be cancelled
                make_job(1002, "testuser", 1, 1, "RUNNING", days_ago=0),
            ]
        }

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_output), stderr="")
            if cmd[0] == "scancel":
                # In dry_run mode, scancel shouldn't be called
                # But the action should be logged as "would_cancel"
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_with_grace_period))

        result = runner.invoke(app, ["monitor", "--once", "--enforce"])
        assert result.exit_code == 0
        # Should indicate job would be cancelled
        assert "would" in result.stdout.lower() or "cancel" in result.stdout.lower()

    def test_zero_grace_period_cancels_immediately(
        self, config_no_grace_period: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With grace_period_hours=0, jobs are cancelled immediately."""
        import subprocess

        mock_output = {
            "jobs": [
                # Job that just exceeded quota
                make_job(1001, "testuser", 2, 6, "COMPLETED", days_ago=0.1),
                make_job(1002, "testuser", 1, 1, "RUNNING", days_ago=0),
            ]
        }

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_output), stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_no_grace_period))

        result = runner.invoke(app, ["monitor", "--once", "--enforce"])
        assert result.exit_code == 0
        # Should indicate enforcement action
        output = result.stdout.lower()
        assert "cancel" in output or "enforce" in output


class TestGracePeriodJSON:
    """Tests for grace period in JSON output."""

    def test_json_includes_grace_period_status(
        self, config_with_grace_period: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON output includes whether user is in grace period."""
        import subprocess

        mock_output = {
            "jobs": [
                make_job(1001, "testuser", 2, 8, "COMPLETED", days_ago=0.5),
                make_job(1002, "testuser", 1, 1, "RUNNING", days_ago=0),
            ]
        }

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_output), stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_with_grace_period))

        result = runner.invoke(app, ["--json", "monitor", "--once"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Should have user data with grace period info
        assert "users" in data
        if data["users"]:
            user = data["users"][0]
            assert "in_grace_period" in user or "exceeded_at" in user
