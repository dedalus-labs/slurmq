# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Tests for sacct command construction.

These tests ensure that sacct commands are constructed with proper POSIX argument
format. Short options like -S, -E, -u must use space-separated arguments, NOT the
equals syntax (e.g., `-S value` not `-S=value`).

Background: getopt_long with short options requires `-S value` or `-Svalue`, but
NOT `-S=value`. The `=` syntax only works with GNU long options (--starttime=value).
"""

from __future__ import annotations

from collections.abc import Generator
import re
from unittest.mock import MagicMock, patch

import pytest

from slurmq.core.config import ClusterConfig


# Regex pattern to detect invalid short option syntax: -X=value where X is a single letter
# Valid: -S, --starttime=value, -Svalue, -S value
# Invalid: -S=value, -E=now, -u=alice
INVALID_SHORT_OPT_PATTERN = re.compile(r"^-[a-zA-Z]=")


def assert_no_short_opt_equals(cmd: list[str], context: str = "") -> None:
    """Assert that no short options use the invalid `=` syntax.

    Args:
        cmd: Command list to check
        context: Optional context for error message
    """
    for arg in cmd:
        if INVALID_SHORT_OPT_PATTERN.match(arg):
            pytest.fail(f"Invalid short option syntax '{arg}' - use '-X value' not '-X=value'. Context: {context}")


class TestFetchUserJobsCommand:
    """Tests for fetch_user_jobs command construction."""

    @pytest.fixture
    def mock_subprocess(self) -> Generator[MagicMock, None, None]:
        """Mock subprocess.run to capture commands."""
        with patch("subprocess.run") as mock:
            mock.return_value.stdout = '{"jobs": []}'
            mock.return_value.returncode = 0
            yield mock

    @pytest.fixture
    def cluster_config(self) -> ClusterConfig:
        """Create a cluster config for testing."""
        return ClusterConfig(
            name="Test Cluster",
            account="research",
            qos=["normal"],
            partitions=["gpu"],
            quota_limit=500,
            rolling_window_days=30,
        )

    def test_fetch_user_jobs_no_equals_in_short_opts(
        self, mock_subprocess: MagicMock, cluster_config: ClusterConfig
    ) -> None:
        """fetch_user_jobs must not use -X=value syntax for short options."""
        from slurmq.core.quota import fetch_user_jobs

        try:
            fetch_user_jobs("testuser", cluster_config)
        except Exception:
            pass  # We only care about the command construction

        assert mock_subprocess.called
        cmd = mock_subprocess.call_args[0][0]
        assert_no_short_opt_equals(cmd, "fetch_user_jobs")

    def test_fetch_user_jobs_s_and_e_are_separate_args(
        self, mock_subprocess: MagicMock, cluster_config: ClusterConfig
    ) -> None:
        """Verify -S and -E have their values as separate list elements."""
        from slurmq.core.quota import fetch_user_jobs

        try:
            fetch_user_jobs("testuser", cluster_config)
        except Exception:
            pass

        cmd = mock_subprocess.call_args[0][0]

        # Find -S and verify next arg is the value (not attached with =)
        if "-S" in cmd:
            s_idx = cmd.index("-S")
            assert s_idx + 1 < len(cmd), "-S must have a following argument"
            assert not cmd[s_idx].startswith("-S="), "-S must not use = syntax"
            assert "now-" in cmd[s_idx + 1] or "days" in cmd[s_idx + 1], "-S value should be time spec"

        # Find -E and verify next arg is the value
        if "-E" in cmd:
            e_idx = cmd.index("-E")
            assert e_idx + 1 < len(cmd), "-E must have a following argument"
            assert not cmd[e_idx].startswith("-E="), "-E must not use = syntax"

    def test_fetch_user_jobs_user_flag_format(self, mock_subprocess: MagicMock, cluster_config: ClusterConfig) -> None:
        """Verify -u flag uses proper format."""
        from slurmq.core.quota import fetch_user_jobs

        try:
            fetch_user_jobs("alice", cluster_config)
        except Exception:
            pass

        cmd = mock_subprocess.call_args[0][0]

        # -u should be followed by username as separate arg
        if "-u" in cmd:
            u_idx = cmd.index("-u")
            assert u_idx + 1 < len(cmd), "-u must have a following argument"
            assert cmd[u_idx + 1] == "alice", "-u should be followed by username"


class TestFetchPartitionDataCommand:
    """Tests for stats.py fetch_partition_data command construction."""

    @pytest.fixture
    def mock_subprocess(self) -> Generator[MagicMock, None, None]:
        """Mock subprocess.run to capture commands."""
        with patch("subprocess.run") as mock:
            mock.return_value.stdout = '{"jobs": []}'
            mock.return_value.returncode = 0
            yield mock

    def test_fetch_partition_data_no_equals_in_short_opts(self, mock_subprocess: MagicMock) -> None:
        """fetch_partition_data must not use -X=value syntax."""
        from slurmq.cli.commands.stats import fetch_partition_data

        try:
            fetch_partition_data("gpu", "normal", "2025-01-01", "2025-01-31")
        except Exception:
            pass

        assert mock_subprocess.called
        cmd = mock_subprocess.call_args[0][0]
        assert_no_short_opt_equals(cmd, "fetch_partition_data")

    def test_fetch_partition_data_s_and_e_are_separate_args(self, mock_subprocess: MagicMock) -> None:
        """Verify -S and -E have their values as separate list elements."""
        from slurmq.cli.commands.stats import fetch_partition_data

        try:
            fetch_partition_data("gpu", "normal", "2025-01-01", "2025-01-31")
        except Exception:
            pass

        cmd = mock_subprocess.call_args[0][0]

        # -S should be separate from its value
        assert "-S" in cmd, "Command should have -S flag"
        s_idx = cmd.index("-S")
        assert cmd[s_idx + 1] == "2025-01-01", "-S should be followed by start_date"

        # -E should be separate from its value
        assert "-E" in cmd, "Command should have -E flag"
        e_idx = cmd.index("-E")
        assert cmd[e_idx + 1] == "2025-01-31", "-E should be followed by end_date"


class TestLongOptionsCanUseEquals:
    """Verify that long options (--flag=value) ARE allowed."""

    @pytest.fixture
    def mock_subprocess(self) -> Generator[MagicMock, None, None]:
        """Mock subprocess.run."""
        with patch("subprocess.run") as mock:
            mock.return_value.stdout = '{"jobs": []}'
            mock.return_value.returncode = 0
            yield mock

    def test_long_options_with_equals_are_valid(self, mock_subprocess: MagicMock) -> None:
        """Long options like --qos=value, --partition=value are valid."""
        from slurmq.cli.commands.stats import fetch_partition_data

        try:
            fetch_partition_data("gpu", "normal", "2025-01-01", "2025-01-31", "research")
        except Exception:
            pass

        cmd = mock_subprocess.call_args[0][0]

        # These long options with = ARE valid
        long_opts_with_equals = [arg for arg in cmd if arg.startswith("--") and "=" in arg]
        assert len(long_opts_with_equals) > 0, "Long options should use --flag=value syntax"

        # Verify the pattern: --partition=gpu, --qos=normal, --account=research
        for opt in long_opts_with_equals:
            assert opt.startswith("--"), f"Long option {opt} should start with --"
