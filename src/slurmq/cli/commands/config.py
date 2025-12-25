# Copyright (c) 2025 Dedalus Labs, Inc. and its contributors
# SPDX-License-Identifier: MIT

"""Config command for slurmq - manage configuration."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
import tomli_w
import typer

from slurmq.core.config import ClusterConfig, SlurmqConfig, get_config_path, validate_config


if TYPE_CHECKING:
    from slurmq.cli.main import CLIContext

console = Console()

# Type alias for TOML-compatible config values
ConfigValue = str | int | float | bool


def register_config_commands(app: typer.Typer) -> None:
    """Register config commands with the CLI app."""
    config_app = typer.Typer(name="config", help="Manage slurmq configuration.")
    config_app.command("show")(show)
    config_app.command("path")(path)
    config_app.command("init")(init)
    config_app.command("set")(set_value)
    config_app.command("validate")(validate)
    app.add_typer(config_app)


def show(ctx: typer.Context) -> None:
    """Show current configuration."""
    config: SlurmqConfig = ctx.obj.config

    lines = [
        f"[bold]Default cluster:[/bold] {config.default_cluster or '(not set)'}",
        f"[bold]Clusters:[/bold] {', '.join(config.cluster_names) or '(none)'}",
        "",
        "[bold]Monitoring:[/bold]",
        f"  Warning threshold: {config.monitoring.warning_threshold * 100:.0f}%",
        f"  Critical threshold: {config.monitoring.critical_threshold * 100:.0f}%",
        "",
        "[bold]Enforcement:[/bold]",
        f"  Enabled: {config.enforcement.enabled}",
        f"  Dry run: {config.enforcement.dry_run}",
        "",
        "[bold]Display:[/bold]",
        f"  Output format: {config.display.output_format}",
        f"  Color: {config.display.color}",
    ]

    if config.cluster_names:
        lines.append("\n[bold]Cluster Details:[/bold]")
        for name in config.cluster_names:
            cluster = config.clusters[name]
            lines.append(f"\n  [{name}]")
            lines.append(f"    Name: {cluster.name}")
            lines.append(f"    QoS: {', '.join(cluster.qos)}")
            lines.append(f"    Quota: {cluster.quota_limit} GPU-hours")
            lines.append(f"    Window: {cluster.rolling_window_days} days")

    panel = Panel("\n".join(lines), title="[bold]slurmq Configuration[/bold]")
    console.print(panel)


def path() -> None:
    """Show config file path."""
    console.print(str(get_config_path()))


def init() -> None:
    """Initialize configuration interactively."""
    config_path = get_config_path()

    # Check if config exists
    if config_path.exists() and not Confirm.ask(f"Config already exists at {config_path}. Overwrite?", default=False):
        console.print("[yellow]Aborted.[/yellow]")
        return

    console.print("\n[bold]slurmq Configuration Wizard[/bold]\n")
    console.print("Let's set up your first cluster.\n")

    # Gather cluster info
    cluster_id = Prompt.ask("Cluster ID (short name, e.g., 'stella')", default="stella")
    cluster_name = Prompt.ask("Cluster display name", default=cluster_id.title())
    account = Prompt.ask("Slurm account name", default="")
    qos = Prompt.ask("QoS (comma-separated if multiple)", default="normal")
    quota_limit = IntPrompt.ask("GPU-hours quota limit", default=500)
    rolling_window = IntPrompt.ask("Rolling window (days)", default=30)

    # Build config
    qos_list = [q.strip() for q in qos.split(",") if q.strip()]

    config = SlurmqConfig(
        default_cluster=cluster_id,
        clusters={
            cluster_id: ClusterConfig(
                name=cluster_name,
                account=account,
                qos=qos_list,
                quota_limit=quota_limit,
                rolling_window_days=rolling_window,
            )
        },
    )

    # Save config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config.save(config_path)

    console.print(f"\n[green]ok:[/green] Configuration saved to {config_path}")
    console.print("\nYou can now run [bold]slurmq check[/bold] to check your quota.")


def set_value(
    key: str = typer.Argument(..., help="Config key (e.g., 'clusters.stella.quota_limit')"),
    value: str = typer.Argument(..., help="New value"),
) -> None:
    """Set a configuration value."""
    config_path = get_config_path()

    if not config_path.exists():
        console.print(f"[red]Config file not found:[/red] {config_path}")
        console.print("Run [bold]slurmq config init[/bold] first.")
        raise typer.Exit(1)

    # Load existing config as dict
    with config_path.open("rb") as f:
        data = tomllib.load(f)

    # Parse the key path and set value
    keys = key.split(".")
    _set_nested(data, keys, _parse_value(value))

    # Save updated config
    with config_path.open("wb") as f:
        tomli_w.dump(data, f)

    console.print(f"[green]ok:[/green] Set {key} = {value}")


def _set_nested(data: dict[str, Any], keys: list[str], value: ConfigValue) -> None:
    """Set a nested dict value by key path."""
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


def _parse_value(value: str) -> ConfigValue:
    """Parse a string value to appropriate type."""
    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Try bool
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False

    # Return as string
    return value


def validate(
    ctx: typer.Context, *, file: str | None = typer.Option(None, "--file", "-f", help="Config file to validate")
) -> None:
    """Validate configuration file syntax and semantics."""
    cli_ctx: CLIContext = ctx.obj

    # Determine file to validate
    config_path = Path(file) if file else get_config_path()

    # Run validation
    errors = validate_config(config_path)

    # Output results
    if cli_ctx.json_output:
        result = {"valid": len(errors) == 0, "path": str(config_path), "errors": errors}
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        if errors:
            raise typer.Exit(1)
    elif errors:
        console.print(f"[red]Config validation failed:[/red] {config_path}\n")
        for error in errors:
            console.print(f"  [red]•[/red] {error}")
        raise typer.Exit(1)
    else:
        console.print(f"[green]ok:[/green] Config valid: {config_path}")
