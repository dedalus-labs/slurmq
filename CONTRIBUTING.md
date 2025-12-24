# Contributing to slurmq

Thanks for your interest in contributing! This guide will help you get started.

## Your First Pull Request

### 1. Fork the repository

Click the **Fork** button on the [slurmq repo](https://github.com/dedalus-labs/slurmq). This creates your own copy.

### 2. Clone your fork

```bash
git clone https://github.com/YOUR-USERNAME/slurmq.git
cd slurmq
```

### 3. Set up the project

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (including dev tools)
uv sync --extra dev
```

### 4. Create a branch

```bash
git checkout -b fix/my-first-contribution
```

Pick a name that describes your change: `fix/typo-in-readme`, `feat/add-cluster-option`, `docs/clarify-setup`.

### 5. Make your changes

Edit the code, then run the checks:

```bash
uv run ruff check src/slurmq/   # Lint
uv run ruff format src/slurmq/  # Format
uv run ty check src/slurmq/     # Type check
uv run pytest                   # Test
```

### 6. Commit with a conventional message

```bash
git add .
git commit -m "fix: correct quota calculation for multi-GPU jobs"
```

The commit type (`fix:`, `feat:`, `docs:`) matters—it determines the version bump.

### 7. Push to your fork

```bash
git push origin fix/my-first-contribution
```

### 8. Open a Pull Request

Go to your fork on GitHub. You'll see a banner to **Compare & pull request**. Click it!

- **Base repository**: `dedalus-labs/slurmq`, branch `main`
- **Head repository**: your fork, your branch
- Write a clear title (this becomes the commit message when we merge)
- Describe what you changed and why

### 9. Wait for review

CI will run automatically. A maintainer will review your PR and may suggest changes.

---

## Code Standards

```bash
uv run ruff check src/slurmq/           # Lint
uv run ruff format --check src/slurmq/  # Format check
uv run ty check src/slurmq/             # Type check
uv run pytest                           # Test
```

All must pass.

## AI Disclosure

If you use AI tools (Copilot, Claude, Cursor), mention it in your PR. You must understand code you submit.

## Areas Needing Help

- **Documentation**: Improve README, add examples
- **Testing**: Increase coverage, especially for SLURM edge cases
- **Clusters**: Test on different SLURM configurations
- **Features**: New monitoring capabilities

Look for issues labeled `good first issue` to get started.

## Links

| Resource | Description |
|----------|-------------|
| [SECURITY.md](SECURITY.md) | Reporting vulnerabilities |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
