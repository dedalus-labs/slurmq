# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Pytest fixtures for slurmq tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest import MonkeyPatch


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Clear SLURMQ_* env vars and reset config module state before each test."""
    # Clear env vars
    for key in list(os.environ.keys()):
        if key.startswith("SLURMQ_"):
            monkeypatch.delenv(key, raising=False)

    # Reset config module state
    import slurmq.core.config as config_module

    monkeypatch.setattr(config_module, "_config_file_path", None)

    yield


@pytest.fixture
def sample_config_toml() -> str:
    """Sample TOML config content."""
    return """
default_cluster = "stella"

[clusters.stella]
name = "Stella HPC"
account = "research-group"
qos = ["high-priority", "normal"]
partitions = ["gpu", "gpu-large"]
quota_limit = 500
rolling_window_days = 30

[clusters.other]
name = "Other Cluster"
account = "astro"
qos = ["standard"]
partitions = ["gpu"]
quota_limit = 200

[monitoring]
check_interval_minutes = 30
warning_threshold = 0.8
critical_threshold = 1.0

[enforcement]
enabled = false
dry_run = true
grace_period_hours = 24
cancel_order = "lifo"
exempt_users = []
exempt_job_prefixes = ["debug_", "test_"]

[email]
enabled = false
sender = "oss@dedaluslabs.ai"
domain = "dedaluslabs.ai"
subject_prefix = "[Stella-GPU]"

[display]
color = true
output_format = "rich"

[cache]
enabled = true
ttl_minutes = 60
"""


@pytest.fixture
def config_file(tmp_path: Path, sample_config_toml: str) -> Path:
    """Create a temporary config file with sample content."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(sample_config_toml)
    return config_path
