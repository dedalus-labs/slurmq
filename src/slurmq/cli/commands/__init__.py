# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""CLI commands for slurmq."""

from .check import register_check_commands
from .config import register_config_commands
from .efficiency import register_efficiency_commands
from .monitor import register_monitor_commands
from .report import register_report_commands
from .stats import register_stats_commands


__all__ = [
    "register_check_commands",
    "register_config_commands",
    "register_efficiency_commands",
    "register_monitor_commands",
    "register_report_commands",
    "register_stats_commands",
]
