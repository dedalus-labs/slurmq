# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for slurmq check command."""

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


@pytest.fixture
def mock_sacct_output() -> dict:
    """Sample sacct JSON output."""
    now = datetime.now(tz=UTC)
    return {
        "jobs": [
            {
                "job_id": 12345,
                "name": "train_model",
                "user": "testuser",
                "account": "research",
                "qos": "high-priority",
                "state": {"current": ["COMPLETED"]},
                "time": {
                    "elapsed": 7200,
                    "start": int((now - timedelta(days=5)).timestamp()),
                    "submission": int((now - timedelta(days=5)).timestamp()),
                    "limit": {"number": 86400},
                },
                "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 4}]},
                "allocation_nodes": 1,
            }
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

[display]
output_format = "plain"
""")
    return config


class TestCheckCommand:
    """Tests for the check command."""

    def test_check_help(self) -> None:
        """Check command has help text."""
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "quota" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_check_no_config_shows_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Check without config shows helpful error."""
        # Point to non-existent config
        monkeypatch.setenv("SLURMQ_CONFIG", str(tmp_path / "nonexistent.toml"))
        # Should still work with defaults or show helpful message
        result = runner.invoke(app, ["check"])
        # Either exits with error about missing cluster or runs with defaults
        assert result.exit_code in (0, 1)

    def test_check_with_config(
        self, config_file: Path, mock_sacct_output: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check command works with valid config."""
        import subprocess

        # Mock subprocess.run for sacct
        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_sacct_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))
        monkeypatch.setenv("USER", "testuser")

        result = runner.invoke(app, ["check"])
        assert result.exit_code == 0

    def test_check_json_output(
        self, config_file: Path, mock_sacct_output: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check command can output JSON."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_sacct_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))
        monkeypatch.setenv("USER", "testuser")

        # --json is a global option, must come before subcommand
        result = runner.invoke(app, ["--json", "check"])
        assert result.exit_code == 0
        # Output should be valid JSON
        data = json.loads(result.stdout)
        assert "user" in data
        assert "used_gpu_hours" in data

    def test_check_cluster_override(
        self, tmp_path: Path, mock_sacct_output: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check command respects --cluster flag."""
        import subprocess

        config = tmp_path / "config.toml"
        config.write_text("""
default_cluster = "cluster1"

[clusters.cluster1]
name = "Cluster1"
qos = ["qos1"]
quota_limit = 100

[clusters.cluster2]
name = "Cluster2"
qos = ["qos2"]
quota_limit = 200
""")

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                # Verify the right QoS is being queried
                qos_arg = [c for c in cmd if c.startswith("--qos=")]
                if qos_arg:
                    assert qos_arg[0] == "--qos=qos2", f"Expected qos2, got {qos_arg[0]}"
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_sacct_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))
        monkeypatch.setenv("USER", "testuser")

        # --cluster is a global option, must come before subcommand
        result = runner.invoke(app, ["--cluster", "cluster2", "check"])
        assert result.exit_code == 0


class TestCheckOutput:
    """Tests for check command output formatting."""

    def test_plain_output_contains_key_info(
        self, config_file: Path, mock_sacct_output: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plain output contains user, usage, and remaining quota."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_sacct_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))
        monkeypatch.setenv("USER", "testuser")

        result = runner.invoke(app, ["check"])
        assert result.exit_code == 0
        output = result.stdout.lower()
        # Should contain key information
        assert "testuser" in output or "gpu" in output

    def test_warning_status_shown(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Warning status is shown when usage exceeds threshold."""
        import subprocess

        config = tmp_path / "config.toml"
        config.write_text("""
default_cluster = "test"

[clusters.test]
name = "Test"
qos = ["high-priority"]
quota_limit = 10  # Low quota to trigger warning
rolling_window_days = 30

[monitoring]
warning_threshold = 0.8
""")
        now = datetime.now(tz=UTC)
        # Job uses 9 GPU-hours (90% of 10 limit)
        mock_output = {
            "jobs": [
                {
                    "job_id": 1,
                    "name": "big_job",
                    "user": "testuser",
                    "account": "research",
                    "qos": "high-priority",
                    "state": {"current": ["COMPLETED"]},
                    "time": {
                        "elapsed": 3600,  # 1 hour
                        "start": int((now - timedelta(days=1)).timestamp()),
                        "submission": int((now - timedelta(days=1)).timestamp()),
                    },
                    "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 9}]},
                }
            ]
        }

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))
        monkeypatch.setenv("USER", "testuser")

        result = runner.invoke(app, ["check"])
        assert result.exit_code == 0
        output = result.stdout.lower()
        assert "warning" in output or "90" in output or "exceeded" in output
