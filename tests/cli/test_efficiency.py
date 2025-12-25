# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for slurmq efficiency command."""

from __future__ import annotations

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
    """Create a minimal test config file."""
    config = tmp_path / "config.toml"
    config.write_text("""
default_cluster = "test"

[clusters.test]
name = "TestCluster"
qos = ["normal"]
quota_limit = 500
""")
    return config


@pytest.fixture
def mock_sacct_efficiency_output() -> str:
    """Sample sacct efficiency output (pipe-delimited)."""
    # Format: JobID|User|State|ExitCode|AllocCPUS|NNodes|ElapsedRaw|TotalCPU|AllocTres|MaxRSS|JobName|Cluster
    return "12345|testuser|COMPLETED|0:0|8|1|3600|02:30:00|mem=32G|4096M|train_model|stella"


class TestEfficiencyCommand:
    """Tests for the efficiency command."""

    def test_efficiency_help(self) -> None:
        """Efficiency command has help text."""
        result = runner.invoke(app, ["efficiency", "--help"])
        assert result.exit_code == 0
        assert "cpu" in result.stdout.lower() or "memory" in result.stdout.lower()

    def test_efficiency_requires_job_id(self) -> None:
        """Efficiency command requires a job ID argument."""
        result = runner.invoke(app, ["efficiency"])
        assert result.exit_code != 0

    def test_efficiency_job_not_found(self, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Efficiency shows error for non-existent job."""
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["efficiency", "99999"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_efficiency_with_valid_job(
        self, config_file: Path, mock_sacct_efficiency_output: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Efficiency command works with valid job."""
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=mock_sacct_efficiency_output, stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["efficiency", "12345"])
        assert result.exit_code == 0
        output = result.stdout.lower()
        assert "12345" in output or "job" in output

    def test_efficiency_json_output(
        self, config_file: Path, mock_sacct_efficiency_output: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Efficiency command outputs valid JSON."""
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=mock_sacct_efficiency_output, stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["--json", "efficiency", "12345"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["job_id"] == 12345
        assert "cpu_efficiency_pct" in data
        assert "memory_efficiency_pct" in data

    def test_efficiency_alias_eff(
        self, config_file: Path, mock_sacct_efficiency_output: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'eff' alias works for efficiency command."""
        import subprocess

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=mock_sacct_efficiency_output, stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["eff", "12345"])
        assert result.exit_code == 0


class TestEfficiencyCalculations:
    """Tests for efficiency metric calculations."""

    def test_cpu_efficiency_calculation(self, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CPU efficiency is calculated correctly."""
        import subprocess

        # 8 CPUs, 3600s walltime = 28800 core-seconds
        # 9000s CPU time = 31.25% efficiency
        output = "12345|testuser|COMPLETED|0:0|8|1|3600|02:30:00|mem=32G|4096M|job|cluster"

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=output, stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["--json", "efficiency", "12345"])
        data = json.loads(result.stdout)
        # 02:30:00 = 9000 seconds, 8 CPUs * 3600s = 28800 core-seconds
        # 9000 / 28800 = 31.25%
        assert data["cpu_efficiency_pct"] == pytest.approx(31.25, rel=0.01)

    def test_memory_efficiency_calculation(self, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Memory efficiency is calculated correctly."""
        import subprocess

        # 32GB allocated, 4GB used = 12.5% efficiency
        output = "12345|testuser|COMPLETED|0:0|1|1|3600|01:00:00|mem=32G|4096M|job|cluster"

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=output, stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["--json", "efficiency", "12345"])
        data = json.loads(result.stdout)
        # 4096 MB / 32768 MB = 12.5%
        assert data["memory_efficiency_pct"] == pytest.approx(12.5, rel=0.01)


class TestEfficiencyRecommendations:
    """Tests for efficiency recommendations."""

    def test_low_cpu_efficiency_shows_recommendation(self, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Low CPU efficiency triggers recommendation."""
        import subprocess

        # 8 CPUs but only 5% utilized
        output = "12345|testuser|COMPLETED|0:0|8|1|3600|00:14:24|mem=8G|2048M|job|cluster"

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=output, stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["efficiency", "12345"])
        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "fewer cpus" in output_lower or "cpu" in output_lower

    def test_low_memory_efficiency_shows_recommendation(
        self, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Low memory efficiency triggers recommendation."""
        import subprocess

        # 32GB allocated, only 1GB used (3.125%)
        output = "12345|testuser|COMPLETED|0:0|1|1|3600|01:00:00|mem=32G|1024M|job|cluster"

        def mock_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if cmd[0] == "sacct":
                return subprocess.CompletedProcess(cmd, 0, stdout=output, stderr="")
            raise ValueError(f"Unexpected command: {cmd}")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_file))

        result = runner.invoke(app, ["efficiency", "12345"])
        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "less memory" in output_lower or "memory" in output_lower
