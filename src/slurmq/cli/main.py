# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Main CLI entry point for slurmq."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.traceback import install as rich_traceback
import typer

from slurmq.cli.commands import (
    register_check_commands,
    register_config_commands,
    register_efficiency_commands,
    register_monitor_commands,
    register_report_commands,
    register_stats_commands,
)
from slurmq.core.config import SlurmqConfig, load_config


if TYPE_CHECKING:
    from slurmq.core.config import ClusterConfig


# Install rich tracebacks for better error messages
rich_traceback(show_locals=False)

app = typer.Typer(
    name="slurmq",
    help="Quota monitoring and management for Slurm.",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=False,
)
console = Console()


class OutputFormat:
    """Output format enum."""

    RICH = "rich"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"
    PLAIN = "plain"


class CLIContext:
    """Shared context for CLI commands."""

    def __init__(
        self,
        config: SlurmqConfig,
        cluster: str | None = None,
        output_format: str = OutputFormat.RICH,
        *,
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        """Initialize CLI context with config and output settings."""
        self.config = config
        self.cluster_name = cluster
        self.output_format = output_format
        self.verbose = verbose
        self.quiet = quiet

    @property
    def cluster(self) -> ClusterConfig:
        """Get the active cluster config."""
        return self.config.get_cluster(self.cluster_name)

    @property
    def json_output(self) -> bool:
        """Check if JSON output is requested."""
        return self.output_format == OutputFormat.JSON

    @property
    def yaml_output(self) -> bool:
        """Check if YAML output is requested."""
        return self.output_format == OutputFormat.YAML


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    *,
    cluster: str | None = typer.Option(None, "--cluster", "-c", help="Cluster to use (overrides default)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    yaml_output: bool = typer.Option(False, "--yaml", help="Output as YAML"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output"),
    config_path: str | None = typer.Option(None, "--config", help="Path to config file"),
    version: bool = typer.Option(False, "--version", help="Show version"),
) -> None:
    """Quota monitoring and management for Slurm.

    Run without a subcommand to check your quota (same as 'slurmq check').
    """
    if version:
        from slurmq import __version__

        console.print(f"slurmq {__version__}")
        raise typer.Exit

    # Determine output format
    if json_output and yaml_output:
        console.print("[red]Cannot use both --json and --yaml[/red]")
        raise typer.Exit(1)
    output_format = OutputFormat.RICH
    if json_output:
        output_format = OutputFormat.JSON
    elif yaml_output:
        output_format = OutputFormat.YAML

    # Load configuration
    config = load_config(Path(config_path) if config_path else None)

    # Store context for subcommands
    ctx.obj = CLIContext(config=config, cluster=cluster, output_format=output_format, verbose=verbose, quiet=quiet)

    # If no subcommand, run check
    if ctx.invoked_subcommand is None:
        from slurmq.cli.commands.check import check

        ctx.invoke(check)


# Register command modules
register_check_commands(app)
register_config_commands(app)
register_efficiency_commands(app)
register_monitor_commands(app)
register_report_commands(app)
register_stats_commands(app)


def run() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
