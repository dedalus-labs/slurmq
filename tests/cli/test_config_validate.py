# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for slurmq config validate command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from slurmq.cli.main import app


if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


class TestConfigValidateCommand:
    """Tests for the config validate subcommand."""

    def test_validate_help(self) -> None:
        """Config validate has help text."""
        result = runner.invoke(app, ["config", "validate", "--help"])
        assert result.exit_code == 0
        assert "validate" in result.stdout.lower()

    def test_validate_valid_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid config passes validation."""
        config = tmp_path / "config.toml"
        config.write_text("""
default_cluster = "test"

[clusters.test]
name = "Test Cluster"
qos = ["normal"]
quota_limit = 500
""")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_invalid_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid TOML fails validation."""
        config = tmp_path / "config.toml"
        config.write_text("this is [[[not valid toml")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code != 0

    def test_validate_missing_cluster(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Referencing undefined cluster fails validation."""
        config = tmp_path / "config.toml"
        config.write_text('default_cluster = "nonexistent"')
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code != 0

    def test_validate_custom_path(self, tmp_path: Path) -> None:
        """Can validate a config at a custom path."""
        config = tmp_path / "custom.toml"
        config.write_text("""
[clusters.test]
name = "Test"
""")

        result = runner.invoke(app, ["config", "validate", "--file", str(config)])
        assert result.exit_code == 0

    def test_validate_nonexistent_file(self, tmp_path: Path) -> None:
        """Nonexistent file fails validation."""
        result = runner.invoke(app, ["config", "validate", "--file", str(tmp_path / "nope.toml")])
        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or "exist" in result.stdout.lower()

    def test_validate_json_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--json outputs validation result as JSON."""
        import json

        config = tmp_path / "config.toml"
        config.write_text("""
[clusters.test]
name = "Test"
""")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["--json", "config", "validate"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "valid" in data
        assert data["valid"] is True

    def test_validate_json_with_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--json includes errors array when validation fails."""
        import json

        config = tmp_path / "config.toml"
        config.write_text('default_cluster = "missing"')
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["--json", "config", "validate"])
        # Exit code 1 for invalid
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["valid"] is False
        assert "errors" in data
        assert len(data["errors"]) > 0
