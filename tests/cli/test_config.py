# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for slurmq config command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from slurmq.cli.main import app


if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


class TestConfigShow:
    """Tests for config show command."""

    def test_config_show_help(self) -> None:
        """Config show has help text."""
        result = runner.invoke(app, ["config", "show", "--help"])
        assert result.exit_code == 0

    def test_config_show_displays_settings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config show displays current settings."""
        config = tmp_path / "config.toml"
        config.write_text("""
default_cluster = "mytest"

[clusters.mytest]
name = "MyTestCluster"
quota_limit = 750
""")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "mytest" in result.stdout.lower()


class TestConfigPath:
    """Tests for config path command."""

    def test_config_path_shows_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config path shows the config file path."""
        config = tmp_path / "config.toml"
        config.write_text("default_cluster = 'test'")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config))

        result = runner.invoke(app, ["config", "path"])
        assert result.exit_code == 0
        assert str(config) in result.stdout or "config.toml" in result.stdout


class TestConfigInit:
    """Tests for config init command."""

    def test_config_init_creates_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config init creates a config file with prompts."""
        config_path = tmp_path / "slurmq" / "config.toml"
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_path))

        # Simulate user input: cluster name, account, qos, quota
        runner.invoke(app, ["config", "init"], input="stella\nStella HPC\nresearch-group\nhigh-priority\n500\n30\n")

        # Should create the file
        assert config_path.exists()
        content = config_path.read_text()
        assert "stella" in content.lower()

    def test_config_init_does_not_overwrite_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config init warns if config already exists."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("# existing config\ndefault_cluster = 'existing'")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_path))

        result = runner.invoke(app, ["config", "init"], input="n\n")  # Say no to overwrite
        assert result.exit_code == 0
        # Original content preserved
        assert "existing" in config_path.read_text()

    def test_config_init_can_overwrite(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config init can overwrite existing config."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("default_cluster = 'oldclustername'")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_path))

        runner.invoke(app, ["config", "init"], input="y\nnewcluster\nNew Cluster\nmyaccount\nnormal\n100\n14\n")

        content = config_path.read_text()
        assert "newcluster" in content.lower()
        assert "oldclustername" not in content  # Original cluster name should be gone


class TestConfigSet:
    """Tests for config set command."""

    def test_config_set_updates_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Config set updates a config value."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
default_cluster = "test"

[clusters.test]
name = "Test"
quota_limit = 500
""")
        monkeypatch.setenv("SLURMQ_CONFIG", str(config_path))

        result = runner.invoke(app, ["config", "set", "clusters.test.quota_limit", "750"])
        assert result.exit_code == 0

        # Verify update
        from slurmq.core.config import load_config

        config = load_config(config_path)
        assert config.clusters["test"].quota_limit == 750
