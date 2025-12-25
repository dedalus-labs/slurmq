# Guidelines For Coding Agents

Instructions for AI coding agents (Wingman, Claude, Codex, Cursor, etc.) working on this codebase.

## Essential Commands

```bash
# Install dependencies
uv sync --extra dev

# Run the app
uv run slurmq --help

# Test
uv run pytest

# Lint and format
uv run ruff check src/slurmq/
uv run ruff format src/slurmq/

# Type check
uv run ty check src/slurmq/

# Pre-commit (install once, runs on each commit)
uv run pre-commit install
uv run pre-commit run --all-files

# Docs (local preview)
uv sync --extra docs
uv run mkdocs serve          # http://127.0.0.1:8000
uv run mkdocs build --strict # build to site/
```

## Before You Code

**Scan wide before you write.** Search for logic that already does what you need. Understand where your contribution fits contextually within this codebase.

1. Grep the codebase for related functionality—it may already exist
2. Look at similar existing code for patterns and conventions
3. Identify code that your implementation should integrate with

## Code Standards

See [docs/style/index.md](docs/style/index.md) for the full style guide.

- All code formatted with `ruff format` (double quotes)
- Type hints required for function signatures
- Google-style docstrings for public APIs
- Follow existing patterns in `src/slurmq/core/` and `src/slurmq/cli/`

### Naming

| Type     | Convention        | Example             |
| -------- | ----------------- | ------------------- |
| Module   | `snake_case`      | `slurm_client.py`   |
| Class    | `PascalCase`      | `SlurmqConfig`      |
| Function | `snake_case`      | `get_gpu_usage()`   |
| Constant | `SCREAMING_SNAKE` | `DEFAULT_QOS`       |
| Private  | `_leading_under`  | `_parse_sacct_line` |

Slurm is itself stylized as "Slurm", not SLURM.

## Key Files

| Path                        | Purpose                      |
| --------------------------- | ---------------------------- |
| `src/slurmq/cli/main.py`    | Typer CLI entry point        |
| `src/slurmq/cli/commands/`  | Command implementations      |
| `src/slurmq/core/config.py` | Configuration and validation |
| `src/slurmq/core/models.py` | Domain models and enums      |
| `src/slurmq/core/quota.py`  | GPU-hours calculation        |

## Don't

- Add dependencies without justification
- Use `shell=True` in subprocess calls
- Commit config files with real cluster data
- Hardcode cluster-specific values (QoS names, accounts, etc.)
- Use `panic()`-style exceptions for recoverable errors

## Do

- Test with mocked Slurm output (see `tests/` for patterns)
- Validate config changes with `slurmq config validate`
- Follow the existing error handling patterns
- Fail explicitly rather than silently degrade
- Ask clarifying questions if requirements are ambiguous
