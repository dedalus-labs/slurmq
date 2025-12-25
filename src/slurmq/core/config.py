# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Configuration system for slurmq.

Supports:
- TOML config files (~/.config/slurmq/config.toml)
- Environment variable overrides (SLURMQ_* prefix)
- Multi-cluster profiles
- XDG Base Directory compliance
"""

from __future__ import annotations

import os
from pathlib import Path
import tomllib
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
import tomli_w


if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

# Module-level variable to hold the config file path for settings source
_config_file_path: Path | None = None

# System-wide config path (for HPC deployments)
SYSTEM_CONFIG_PATH = Path("/etc/slurmq/config.toml")

# Maximum valid threshold value (200% of quota)
MAX_THRESHOLD_VALUE = 2.0


class TomlFileSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads from a TOML file."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        """Load TOML config file if path is set."""
        super().__init__(settings_cls)
        self._data: dict[str, Any] = {}
        if _config_file_path is not None:
            self._data = _load_toml_raw(_config_file_path)

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        """Return field value from loaded TOML data."""
        value = self._data.get(field_name)
        return value, field_name, value is not None

    def __call__(self) -> dict[str, Any]:
        """Return all loaded TOML data."""
        return self._data


def _load_toml_raw(path: Path) -> dict[str, Any]:
    """Load TOML file, returning empty dict if not found."""
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


class ClusterConfig(BaseModel):
    """Configuration for a single Slurm cluster."""

    name: str
    account: str = ""
    qos: list[str] = Field(default_factory=lambda: ["normal"])
    partitions: list[str] = Field(default_factory=list)
    quota_limit: int = 500
    rolling_window_days: int = 30


class MonitoringConfig(BaseModel):
    """Configuration for quota monitoring behavior."""

    check_interval_minutes: int = 30
    warning_threshold: float = 0.8
    critical_threshold: float = 1.0


class EnforcementConfig(BaseModel):
    """Configuration for quota enforcement (job cancellation).

    Defaults are conservative: disabled and dry-run only.
    """

    enabled: bool = False
    dry_run: bool = True
    grace_period_hours: int = 24
    cancel_order: str = "lifo"  # "lifo" = newest first, "fifo" = oldest first
    exempt_users: list[str] = Field(default_factory=list)
    exempt_job_prefixes: list[str] = Field(default_factory=list)


class EmailConfig(BaseModel):
    """Configuration for email notifications."""

    enabled: bool = False
    sender: str = "oss@dedaluslabs.ai"
    domain: str = ""
    subject_prefix: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user_env: str = "SLURMQ_SMTP_USER"
    smtp_secret_env: str = "SLURMQ_SMTP_PASS"  # noqa: S105 - env var name, not a password


class DisplayConfig(BaseModel):
    """Configuration for CLI output display."""

    color: bool = True
    output_format: str = "rich"  # "rich", "plain", "json"
    # Custom sacct format string (like SACCT_FORMAT env var)
    # e.g., "jobid,user,account,state,elapsed"
    sacct_format: str = ""


class CacheConfig(BaseModel):
    """Configuration for data caching."""

    enabled: bool = True
    ttl_minutes: int = 60
    directory: str = ""


class SlurmqConfig(BaseSettings):
    """Main configuration for slurmq.

    Supports loading from:
    1. TOML config file
    2. Environment variables (SLURMQ_* prefix)
    3. Programmatic overrides

    Priority (highest first): env vars > TOML file > defaults
    """

    default_cluster: str = ""
    clusters: dict[str, ClusterConfig] = Field(default_factory=dict)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    enforcement: EnforcementConfig = Field(default_factory=EnforcementConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

    model_config = SettingsConfigDict(env_prefix="SLURMQ_", env_nested_delimiter="__")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources priority.

        Priority (highest first):
        1. init_settings (programmatic overrides)
        2. env_settings (environment variables)
        3. TomlFileSettingsSource (config file)
        """
        return (init_settings, env_settings, TomlFileSettingsSource(settings_cls))

    @property
    def cluster_names(self) -> list[str]:
        """List of all configured cluster names."""
        return list(self.clusters.keys())

    def get_cluster(self, name: str | None = None) -> ClusterConfig:
        """Get cluster config by name, or default cluster if not specified.

        Args:
            name: Cluster name. If None, uses default_cluster.

        Returns:
            ClusterConfig for the specified cluster.

        Raises:
            ValueError: If no cluster specified and no default set,
                       or if the cluster name is not found.
        """
        key = name or self.default_cluster
        if not key:
            msg = "No cluster specified and no default_cluster set"
            raise ValueError(msg)
        if key not in self.clusters:
            msg = f"Unknown cluster: {key}"
            raise ValueError(msg)
        return self.clusters[key]

    def save(self, path: Path) -> None:
        """Save configuration to a TOML file.

        Args:
            path: Path to save the config file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json", exclude_defaults=False)
        with path.open("wb") as f:
            tomli_w.dump(data, f)


def get_default_config_path() -> Path:
    """Get the default config file path (XDG compliant).

    Returns:
        Path to ~/.config/slurmq/config.toml or $XDG_CONFIG_HOME/slurmq/config.toml
    """
    # Respect XDG_CONFIG_HOME explicitly for cross-platform consistency
    if xdg_config := os.environ.get("XDG_CONFIG_HOME"):
        return Path(xdg_config) / "slurmq" / "config.toml"
    # Fall back to ~/.config on all platforms for consistency
    return Path.home() / ".config" / "slurmq" / "config.toml"


def get_config_path() -> Path:
    """Get the config file path with fallback chain.

    Resolution order:
    1. SLURMQ_CONFIG env var (explicit override)
    2. User config (~/.config/slurmq/config.toml) if it exists
    3. System config (/etc/slurmq/config.toml) if it exists
    4. User config path (for creation, even if doesn't exist)

    Returns:
        Path to the config file to use.
    """
    # 1. Env var takes priority
    if env_path := os.environ.get("SLURMQ_CONFIG"):
        return Path(env_path)

    # 2. User config if exists
    user_config = get_default_config_path()
    if user_config.exists():
        return user_config

    # 3. System config if exists
    if SYSTEM_CONFIG_PATH.exists():
        return SYSTEM_CONFIG_PATH

    # 4. Fall back to user path (for creation)
    return user_config


def load_config(path: Path | None = None) -> SlurmqConfig:
    """Load configuration from file and environment.

    Priority (highest first):
    1. Environment variables (SLURMQ_*)
    2. Config file (specified path or default)
    3. Built-in defaults

    Args:
        path: Optional path to config file. If None, uses get_config_path().

    Returns:
        Loaded SlurmqConfig instance.
    """
    global _config_file_path  # noqa: PLW0603 - required for pydantic-settings file source
    _config_file_path = path if path is not None else get_config_path()

    # SlurmqConfig.settings_customize_sources will use _config_file_path
    # to load the TOML file, and env vars will override
    return SlurmqConfig()


def validate_config(path: Path) -> list[str]:
    """Validate a config file without loading it.

    Args:
        path: Path to the config file to validate.

    Returns:
        List of error messages. Empty list means valid.
    """
    errors: list[str] = []

    # Check file exists
    if not path.exists():
        return [f"Config file not found: {path}"]

    # Check TOML syntax
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        return [f"TOML parse error: {e}"]

    # Check default_cluster references valid cluster
    default_cluster = data.get("default_cluster", "")
    clusters = data.get("clusters", {})

    if default_cluster and default_cluster not in clusters:
        errors.append(f"default_cluster '{default_cluster}' not defined in [clusters]")

    # Check threshold values
    monitoring = data.get("monitoring", {})
    warning = monitoring.get("warning_threshold", 0.8)
    critical = monitoring.get("critical_threshold", 1.0)

    if not (0 <= warning <= MAX_THRESHOLD_VALUE):
        errors.append(f"warning_threshold {warning} should be between 0 and {MAX_THRESHOLD_VALUE}")
    if not (0 <= critical <= MAX_THRESHOLD_VALUE):
        errors.append(f"critical_threshold {critical} should be between 0 and {MAX_THRESHOLD_VALUE}")
    if warning > critical:
        errors.append("warning_threshold should be <= critical_threshold")

    # Check cluster configs have required fields
    for name, cluster in clusters.items():
        if not isinstance(cluster, dict):
            errors.append(f"Cluster '{name}' must be a table")
            continue
        if "name" not in cluster:
            errors.append(f"Cluster '{name}' missing required field 'name'")

    return errors
