# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for slurmq report command."""

from __future__ import annotations

import csv
import io
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
                "state": {"current": ["COMPLETED"]},
                "time": {
                    "elapsed": 7200,  # 2h -> 8 GPU-hrs with 4 GPUs
                    "start": int((now - timedelta(days=5)).timestamp()),
                    "submission": int((now - timedelta(days=5)).timestamp()),
                },
                "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 4}]},
            },
            {
                "job_id": 2,
                "name": "bob_inference",
                "user": "bob",
                "account": "research",
                "qos": "high-priority",
                "state": {"current": ["COMPLETED"]},
                "time": {
                    "elapsed": 3600,  # 1h -> 2 GPU-hrs with 2 GPUs
                    "start": int((now - timedelta(days=2)).timestamp()),
                    "submission": int((now - timedelta(days=2)).timestamp()),
                },
                "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 2}]},
            },
            {
                "job_id": 3,
                "name": "alice_eval",
                "user": "alice",
                "account": "research",
                "qos": "high-priority",
                "state": {"current": ["RUNNING"]},
                "time": {
                    "elapsed": 1800,  # 0.5h -> 4 GPU-hrs with 8 GPUs
                    "start": int((now - timedelta(hours=1)).timestamp()),
                    "submission": int((now - timedelta(hours=1)).timestamp()),
                },
                "tres": {"allocated": [{"type": "gres", "name": "gpu", "count": 8}]},
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

[display]
output_format = "plain"
""")
    return config


class TestReportCommand:
    """Tests for the report command."""

    def test_report_help(self) -> None:
        """Report command has help text."""
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0
        assert "report" in result.stdout.lower()

    def test_report_json_output(self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch) -> None:
        """Report command can output JSON."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["report", "--format", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "users" in data
        assert len(data["users"]) >= 2  # alice and bob

    def test_report_csv_output(self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch) -> None:
        """Report command can output CSV."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["report", "--format", "csv"])
        assert result.exit_code == 0

        # Parse CSV
        reader = csv.DictReader(io.StringIO(result.stdout))
        rows = list(reader)
        assert len(rows) >= 2
        assert "user" in reader.fieldnames
        assert "used_gpu_hours" in reader.fieldnames

    def test_report_rich_output(self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch) -> None:
        """Report command shows rich table by default."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["report"])
        assert result.exit_code == 0
        # Should contain user names
        assert "alice" in result.stdout.lower() or "bob" in result.stdout.lower()

    def test_report_to_file(
        self, config_file: Path, mock_all_users_sacct: dict, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Report command can write to file."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        output_file = tmp_path / "report.csv"
        result = runner.invoke(app, ["report", "--format", "csv", "--output", str(output_file)])
        assert result.exit_code == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "alice" in content.lower() or "bob" in content.lower()

    def test_report_aggregates_by_user(
        self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch
    ) -> None:
        """Report aggregates GPU-hours by user."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["report", "--format", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        users = {u["user"]: u for u in data["users"]}

        # alice: 8 (job1) + 4 (job3) = 12 GPU-hours
        assert users["alice"]["used_gpu_hours"] == pytest.approx(12.0, rel=0.1)
        # bob: 2 GPU-hours
        assert users["bob"]["used_gpu_hours"] == pytest.approx(2.0, rel=0.1)


class TestReportSorting:
    """Tests for report sorting options."""

    def test_report_sorted_by_usage(
        self, config_file: Path, mock_all_users_sacct: dict, monkeypatch: MonkeyPatch
    ) -> None:
        """Report is sorted by usage descending by default."""
        import subprocess

        def mock_run(cmd, **kwargs):
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(mock_all_users_sacct), stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["report", "--format", "json"])
        data = json.loads(result.stdout)

        # Should be sorted by usage descending
        usages = [u["used_gpu_hours"] for u in data["users"]]
        assert usages == sorted(usages, reverse=True)
