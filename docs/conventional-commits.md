# Conventional Commits

Commit messages determine version bumps. Format them correctly.

```plaintext
<type>(<optional scope>): <description>
```

## Types

**Version-bumping:**

- `feat` — New feature (bumps minor)
- `fix` — Bug fix (bumps patch)
- `perf` — Performance improvement (bumps patch)

**Non-releasing:**

- `refactor` — Restructure code, no behavior change
- `style` — Formatting, whitespace
- `test` — Add or fix tests
- `docs` — Documentation only
- `build` — Build system, dependencies
- `ci` — CI configuration
- `chore` — Miscellaneous

## Version Bumps

| Commit Type           | Version Bump  |
| --------------------- | ------------- |
| `feat`                | Minor (0.X.0) |
| `fix`                 | Patch (0.0.X) |
| `perf`                | Patch (0.0.X) |
| Breaking change (`!`) | Major (X.0.0) |
| Others                | No release    |

`docs:` commits don't trigger releases. `fix(docs):` commits do.

## Scopes

Optional but encouraged. Use these for slurmq:

- `cli` — CLI entry point
- `check` — Check command
- `monitor` — Monitor command
- `report` — Report command
- `stats` — Stats command
- `efficiency` — Efficiency command
- `config` — Configuration
- `quota` — Quota calculation
- `models` — Domain models

Don't use issue IDs as scopes.

## Breaking Changes

Add `!` before the colon:

```plaintext
feat(config)!: require cluster in config
```

Or use a footer:

```plaintext
feat(config): new config format

BREAKING CHANGE: Config files must specify [clusters] section.
```

## Description Rules

- Imperative mood: "add" not "added"
- No capital first letter
- No period at end

## Examples

```plaintext
feat(stats): add partition comparison
```

```plaintext
fix(quota): correct GPU-hours for multi-node jobs
```

```plaintext
refactor(core): extract models to models.py
```

```plaintext
docs: add installation guide
```

```plaintext
ci: add security scanning
```

## Fixing Bad Commits

```bash
git rebase -i HEAD~3
# Change 'pick' to 'reword', save, edit messages
```

For squash-merge PRs, only the PR title matters.

## References

- https://www.conventionalcommits.org/
- https://github.com/googleapis/release-please
