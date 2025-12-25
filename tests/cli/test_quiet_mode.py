# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for quiet mode (-q/--quiet) flag."""

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
def config_file(tmp_path: Path) -> Path:
    """Create a test config file."""
    config = tmp_path / "config.toml"
    config.write_text("""
default_cluster = "test"

[clusters.test]
name = "TestCluster"
qos = ["normal"]
quota_limit = 500
rolling_window_days = 30
""")
    return config


@pytest.fixture
def mock_sacct_output() -> dict:
    """Sample sacct JSON output."""
    now = datetime.now(tz=UTC)
    return {
        "jobs": [
            {
                "job_id": 12345,
                "name": "test_job",
                "user": "testuser",
                "account": "research",
                "qos": "normal",
                "state": {"current": ["COMPLETED"]},
                "time": {
                    "elapsed": 3600,
                    "start": int((now - timedelta(days=1)).timestamp()),
                    "submission": int((now - timedelta(days=1)).timestamp()),
                    "limit": {"number": 86400},
                },
                "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 2}]},
                "allocation_nodes": 1,
            }
        ]
    }


class TestQuietMode:
    """Tests for the --quiet flag."""

    def test_quiet_flag_exists(self) -> None:
        """--quiet flag is recognized."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--quiet" in result.stdout or "-q" in result.stdout

    def test_check_quiet_suppresses_output(
        self, config_file: Path, mock_sacct_output: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check --quiet produces no output on success."""
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_sacct_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))
        monkeypatch.setenv("USER", "testuser")

        result = runner.invoke(app, ["--quiet", "check"])
        assert result.exit_code == 0
        assert result.stdout.strip() == ""

    def test_check_quiet_shows_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Check --quiet still shows errors."""
        # Point to non-existent config
        monkeypatch.setenv("SLURMQ_CONFIG", str(tmp_path / "nonexistent.toml"))

        result = runner.invoke(app, ["--quiet", "check"])
        # Should still show error, even in quiet mode
        assert result.exit_code != 0

    def test_monitor_quiet_suppresses_table(
        self, config_file: Path, mock_sacct_output: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Monitor --once --quiet produces no output on success."""
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_sacct_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["--quiet", "monitor", "--once"])
        assert result.exit_code == 0
        # Should have no table output
        assert "User" not in result.stdout
        assert "GPU" not in result.stdout

    def test_quiet_with_json_still_outputs_json(
        self, config_file: Path, mock_sacct_output: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--quiet --json still outputs JSON (quiet only affects rich output)."""
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_sacct_output), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))
        monkeypatch.setenv("USER", "testuser")

        result = runner.invoke(app, ["--quiet", "--json", "check"])
        assert result.exit_code == 0
        # Should still have JSON output
        data = json.loads(result.stdout)
        assert "user" in data
