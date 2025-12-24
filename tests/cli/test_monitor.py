# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for slurmq monitor command."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from slurmq.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch

runner = CliRunner()


@pytest.fixture
def mock_all_users_sacct() -> dict:
    """Sample sacct output with multiple users."""
    now = datetime.now()
    return {
        "jobs": [
            {
                "job_id": 1,
                "name": "alice_train",
                "user": "alice",
                "account": "research",
                "qos": "high-priority",
                "state": {"current": ["RUNNING"]},
                "time": {
                    "elapsed": 7200,
                    "start": int((now - timedelta(hours=2)).timestamp()),
                    "submission": int((now - timedelta(hours=2)).timestamp()),
                },
                "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 4}]},
            },
            {
                "job_id": 2,
                "name": "bob_job",
                "user": "bob",
                "account": "research",
                "qos": "high-priority",
                "state": {"current": ["RUNNING"]},
                "time": {
                    "elapsed": 3600,
                    "start": int((now - timedelta(hours=1)).timestamp()),
                    "submission": int((now - timedelta(hours=1)).timestamp()),
                },
                "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 2}]},
            },
        ]
    }


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Create a test config file."""
    config = tmp_path / "config.toml"
    config.write_text("""
default_cluster = "test"

[clusters.test]
name = "TestCluster"
account = "research"
qos = ["high-priority"]
quota_limit = 500
rolling_window_days = 30

[enforcement]
enabled = false
dry_run = true
""")
    return config


class TestMonitorCommand:
    """Tests for the monitor command."""

    def test_monitor_help(self) -> None:
        """Monitor command has help text."""
        result = runner.invoke(app, ["monitor", "--help"])
        assert result.exit_code == 0
        assert "monitor" in result.stdout.lower()

    def test_monitor_once_mode(self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch) -> None:
        """Monitor --once shows status and exits."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["monitor", "--once"])
        assert result.exit_code == 0
        # Should show user info
        assert "alice" in result.stdout.lower() or "bob" in result.stdout.lower()

    def test_monitor_json_output(
        self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch
    ) -> None:
        """Monitor --once --json outputs JSON."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["--json", "monitor", "--once"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "users" in data


class TestMonitorEnforcement:
    """Tests for monitor enforcement behavior."""

    def test_enforce_dry_run_does_not_cancel(
        self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch
    ) -> None:
        """Enforce with dry_run=true logs but doesn't cancel."""
        import subprocess

        cancelled_jobs: list[int] = []

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            if cmd[0] == "scancel":
                cancelled_jobs.append(int(cmd[1]))
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Config with enforcement enabled but dry_run
        config = config_file.parent / "enforce_config.toml"
        config.write_text("""
default_cluster = "test"

[clusters.test]
name = "TestCluster"
qos = ["high-priority"]
quota_limit = 1  # Very low to trigger enforcement

[enforcement]
enabled = true
dry_run = true
""")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        runner.invoke(app, ["monitor", "--once", "--enforce"])
        # Should NOT actually cancel jobs in dry run mode
        assert len(cancelled_jobs) == 0

    def test_enforce_respects_exempt_users(
        self, tmp_path: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch
    ) -> None:
        """Enforcement skips exempt users."""
        import subprocess

        cancelled_jobs: list[int] = []

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            if cmd[0] == "scancel":
                # scancel may have -Q flag, job_id is last argument
                job_id = int(cmd[-1])
                cancelled_jobs.append(job_id)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)

        config = tmp_path / "config.toml"
        config.write_text("""
default_cluster = "test"

[clusters.test]
name = "TestCluster"
qos = ["high-priority"]
quota_limit = 1

[enforcement]
enabled = true
dry_run = false
exempt_users = ["alice"]  # Alice is exempt
""")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["monitor", "--once", "--enforce"])
        assert result.exit_code == 0
        # Alice's job (job_id=1) should NOT be cancelled, but bob's (job_id=2) may be
        assert 1 not in cancelled_jobs  # Alice is exempt


class TestMonitorActiveJobs:
    """Tests for active job display."""

    def test_shows_active_jobs(self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch) -> None:
        """Monitor shows active jobs."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["monitor", "--once"])
        assert result.exit_code == 0
        # All jobs in fixture are RUNNING
        output = result.stdout.lower()
        assert "running" in output or "active" in output or "alice" in output
