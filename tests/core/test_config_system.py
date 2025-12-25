# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for system-wide config and config validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from slurmq.core.config import get_config_path, validate_config


class TestSystemWideConfig:
    """Tests for system-wide config fallback."""

    def test_env_var_takes_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SLURMQ_CONFIG env var takes highest priority."""
        env_config = tmp_path / "env.toml"
        env_config.write_text('default_cluster = "from_env"')
        monkeypatch.setenv("SLURMQ_CONFIG", str(env_config))

        path = get_config_path()
        assert path == env_config

    def test_user_config_before_system(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """User config (~/.config/slurmq) takes priority over system config."""
        # Create user config
        user_config_dir = tmp_path / "user" / ".config" / "slurmq"
        user_config_dir.mkdir(parents=True)
        user_config = user_config_dir / "config.toml"
        user_config.write_text('default_cluster = "from_user"')

        # Create system config
        system_config_dir = tmp_path / "etc" / "slurmq"
        system_config_dir.mkdir(parents=True)
        system_config = system_config_dir / "config.toml"
        system_config.write_text('default_cluster = "from_system"')

        # Mock paths
        monkeypatch.delenv("SLURMQ_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")
        monkeypatch.setattr("slurmq.core.config.SYSTEM_CONFIG_PATH", system_config)

        path = get_config_path()
        assert path == user_config

    def test_system_config_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to system config when user config doesn't exist."""
        # No user config
        user_home = tmp_path / "user"
        user_home.mkdir()

        # Create system config
        system_config_dir = tmp_path / "etc" / "slurmq"
        system_config_dir.mkdir(parents=True)
        system_config = system_config_dir / "config.toml"
        system_config.write_text('default_cluster = "from_system"')

        monkeypatch.delenv("SLURMQ_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: user_home)
        monkeypatch.setattr("slurmq.core.config.SYSTEM_CONFIG_PATH", system_config)

        path = get_config_path()
        assert path == system_config

    def test_returns_user_path_when_neither_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns user config path (for creation) when no config exists."""
        user_home = tmp_path / "user"
        user_home.mkdir()

        monkeypatch.delenv("SLURMQ_CONFIG", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: user_home)
        monkeypatch.setattr("slurmq.core.config.SYSTEM_CONFIG_PATH", tmp_path / "nonexistent" / "config.toml")

        path = get_config_path()
        # Should return user path even though it doesn't exist
        assert path == user_home / ".config" / "slurmq" / "config.toml"


class TestConfigValidate:
    """Tests for config validation."""

    def test_valid_config_passes(self, tmp_path: Path) -> None:
        """Valid config returns no errors."""
        config = tmp_path / "config.toml"
        config.write_text("""
default_cluster = "test"

[clusters.test]
name = "Test Cluster"
qos = ["normal"]
quota_limit = 500
""")
        errors = validate_config(config)
        assert errors == []

    def test_invalid_toml_syntax(self, tmp_path: Path) -> None:
        """Invalid TOML syntax returns error."""
        config = tmp_path / "config.toml"
        config.write_text("this is not valid toml [[[")

        errors = validate_config(config)
        assert len(errors) == 1
        assert "TOML" in errors[0] or "parse" in errors[0].lower()

    def test_missing_cluster_definition(self, tmp_path: Path) -> None:
        """Referencing non-existent cluster returns error."""
        config = tmp_path / "config.toml"
        config.write_text('default_cluster = "nonexistent"')

        errors = validate_config(config)
        assert len(errors) >= 1
        assert any("nonexistent" in e or "cluster" in e.lower() for e in errors)

    def test_invalid_threshold_values(self, tmp_path: Path) -> None:
        """Invalid threshold values return errors."""
        config = tmp_path / "config.toml"
        config.write_text("""
[clusters.test]
name = "Test"

[monitoring]
warning_threshold = 1.5
critical_threshold = -0.1
""")
        errors = validate_config(config)
        assert len(errors) >= 1

    def test_missing_file_returns_error(self, tmp_path: Path) -> None:
        """Missing config file returns error."""
        config = tmp_path / "nonexistent.toml"
        errors = validate_config(config)
        assert len(errors) == 1
        assert "not found" in errors[0].lower() or "exist" in errors[0].lower()

    def test_empty_config_is_valid(self, tmp_path: Path) -> None:
        """Empty config (uses defaults) is valid."""
        config = tmp_path / "config.toml"
        config.write_text("")

        errors = validate_config(config)
        assert errors == []
