# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for slurmq configuration system."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from slurmq.core.config import ClusterConfig, EmailConfig, EnforcementConfig, SlurmqConfig, load_config

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class TestClusterConfig:
    """Tests for ClusterConfig model."""

    def test_minimal_cluster(self) -> None:
        """Cluster config requires only a name."""
        cluster = ClusterConfig(name="stella")
        assert cluster.name == "stella"
        assert cluster.account == ""
        assert cluster.qos == ["normal"]
        assert cluster.partitions == []
        assert cluster.quota_limit == 500
        assert cluster.rolling_window_days == 30

    def test_full_cluster(self) -> None:
        """Cluster config with all fields."""
        cluster = ClusterConfig(
            name="Stella HPC",
            account="research-group",
            qos=["high-priority", "normal"],
            partitions=["gpu", "gpu-large"],
            quota_limit=1000,
            rolling_window_days=14,
        )
        assert cluster.name == "Stella HPC"
        assert cluster.account == "research-group"
        assert cluster.qos == ["high-priority", "normal"]
        assert cluster.partitions == ["gpu", "gpu-large"]
        assert cluster.quota_limit == 1000
        assert cluster.rolling_window_days == 14


class TestEnforcementConfig:
    """Tests for EnforcementConfig model."""

    def test_defaults_are_safe(self) -> None:
        """Enforcement is disabled and dry-run by default (safety first)."""
        enforcement = EnforcementConfig()
        assert enforcement.enabled is False
        assert enforcement.dry_run is True
        assert enforcement.grace_period_hours == 24
        assert enforcement.cancel_order == "lifo"
        assert enforcement.exempt_users == []
        assert enforcement.exempt_job_prefixes == []

    def test_exempt_users(self) -> None:
        """Can specify users exempt from enforcement."""
        enforcement = EnforcementConfig(exempt_users=["admin", "root"])
        assert enforcement.exempt_users == ["admin", "root"]

    def test_exempt_job_prefixes(self) -> None:
        """Can specify job prefixes exempt from cancellation."""
        enforcement = EnforcementConfig(exempt_job_prefixes=["debug_", "test_"])
        assert enforcement.exempt_job_prefixes == ["debug_", "test_"]


class TestEmailConfig:
    """Tests for EmailConfig model."""

    def test_defaults(self) -> None:
        """Email defaults to disabled with dedalus sender."""
        email = EmailConfig()
        assert email.enabled is False
        assert email.sender == "oss@dedaluslabs.ai"
        assert email.smtp_port == 587


class TestSlurmqConfig:
    """Tests for the main SlurmqConfig."""

    def test_empty_config(self) -> None:
        """Empty config has sensible defaults."""
        config = SlurmqConfig()
        assert config.default_cluster == ""
        assert config.clusters == {}
        assert config.display.color is True
        assert config.enforcement.enabled is False

    def test_get_cluster_by_name(self) -> None:
        """Can retrieve a cluster by name."""
        config = SlurmqConfig(
            clusters={
                "stella": ClusterConfig(name="Stella HPC"),
                "other": ClusterConfig(name="Other Cluster"),
            }
        )
        cluster = config.get_cluster("stella")
        assert cluster.name == "Stella HPC"

    def test_get_cluster_default(self) -> None:
        """get_cluster() with no arg uses default_cluster."""
        config = SlurmqConfig(
            default_cluster="stella",
            clusters={"stella": ClusterConfig(name="Stella HPC")},
        )
        cluster = config.get_cluster()
        assert cluster.name == "Stella HPC"

    def test_get_cluster_no_default_raises(self) -> None:
        """get_cluster() raises if no default and no arg."""
        config = SlurmqConfig(clusters={"stella": ClusterConfig(name="Stella HPC")})
        with pytest.raises(ValueError, match="No cluster specified"):
            config.get_cluster()

    def test_get_cluster_unknown_raises(self) -> None:
        """get_cluster() raises for unknown cluster name."""
        config = SlurmqConfig(
            default_cluster="stella",
            clusters={"stella": ClusterConfig(name="Stella HPC")},
        )
        with pytest.raises(ValueError, match="Unknown cluster"):
            config.get_cluster("nonexistent")

    def test_cluster_names_property(self) -> None:
        """Can list all configured cluster names."""
        config = SlurmqConfig(
            clusters={
                "stella": ClusterConfig(name="Stella HPC"),
                "other": ClusterConfig(name="Other Cluster"),
            }
        )
        assert set(config.cluster_names) == {"stella", "other"}


class TestConfigFromToml:
    """Tests for loading config from TOML files."""

    def test_load_from_toml(self, tmp_path: Path) -> None:
        """Can load config from a TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
default_cluster = "stella"

[clusters.stella]
name = "Stella HPC"
account = "research"
qos = ["high-priority"]
quota_limit = 1000

[monitoring]
warning_threshold = 0.9

[display]
output_format = "json"
""")
        config = load_config(config_file)
        assert config.default_cluster == "stella"
        assert config.clusters["stella"].name == "Stella HPC"
        assert config.clusters["stella"].quota_limit == 1000
        assert config.monitoring.warning_threshold == 0.9
        assert config.display.output_format == "json"

    def test_load_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        """Missing config file returns default config."""
        config = load_config(tmp_path / "nonexistent.toml")
        assert config.default_cluster == ""
        assert config.clusters == {}

    def test_load_partial_config(self, tmp_path: Path) -> None:
        """Partial config file merges with defaults."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[email]
enabled = true
domain = "example.edu"
""")
        config = load_config(config_file)
        assert config.email.enabled is True
        assert config.email.domain == "example.edu"
        assert config.email.sender == "oss@dedaluslabs.ai"  # default preserved


class TestConfigFromEnv:
    """Tests for loading config from environment variables."""

    def test_env_overrides_file(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Environment variables override file config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
default_cluster = "stella"
""")
        monkeypatch.setenv("SLURMQ_DEFAULT_CLUSTER", "other")
        config = load_config(config_file)
        assert config.default_cluster == "other"

    def test_nested_env_var(self, monkeypatch: MonkeyPatch) -> None:
        """Can set nested config via double-underscore env vars."""
        monkeypatch.setenv("SLURMQ_DISPLAY__OUTPUT_FORMAT", "plain")
        config = load_config()
        assert config.display.output_format == "plain"


class TestConfigSave:
    """Tests for saving config to TOML files."""

    def test_save_config(self, tmp_path: Path) -> None:
        """Can save config to a TOML file."""
        config = SlurmqConfig(
            default_cluster="stella",
            clusters={"stella": ClusterConfig(name="Stella HPC", quota_limit=750)},
        )
        config_file = tmp_path / "config.toml"
        config.save(config_file)

        # Reload and verify
        loaded = load_config(config_file)
        assert loaded.default_cluster == "stella"
        assert loaded.clusters["stella"].quota_limit == 750


class TestConfigPaths:
    """Tests for config file path resolution."""

    def test_default_config_path(self, monkeypatch: MonkeyPatch) -> None:
        """Default config path is XDG compliant."""
        from slurmq.core.config import get_default_config_path

        monkeypatch.setenv("HOME", "/home/testuser")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        path = get_default_config_path()
        assert path == Path("/home/testuser/.config/slurmq/config.toml")

    def test_xdg_config_home_respected(self, monkeypatch: MonkeyPatch) -> None:
        """XDG_CONFIG_HOME is respected."""
        from slurmq.core.config import get_default_config_path

        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        path = get_default_config_path()
        assert path == Path("/custom/config/slurmq/config.toml")

    def test_slurmq_config_env_override(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """SLURMQ_CONFIG env var overrides default path."""
        from slurmq.core.config import get_config_path

        custom_path = tmp_path / "custom.toml"
        monkeypatch.setenv("SLURMQ_CONFIG", str(custom_path))
        path = get_config_path()
        assert path == custom_path
