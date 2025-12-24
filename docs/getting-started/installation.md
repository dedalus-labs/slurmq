# Installation

## Requirements

- Python 3.11+
- SLURM with `sacct` command available

## Install with uv (recommended)

[uv](https://docs.astral.sh/uv/) is the fastest way to install Python CLI tools:

```bash
uv tool install slurmq
```

This installs `slurmq` globally, isolated from your project environments.

## Install with pip

```bash
pip install slurmq
```

## Install with pipx

```bash
pipx install slurmq
```

## Install from source

```bash
git clone https://github.com/dedalus-labs/slurmq.git
cd slurmq
uv tool install .
```

## Verify installation

```bash
slurmq --version
```

## System-wide installation (HPC)

For HPC environments where users don't have write access to their home directories, administrators can install slurmq system-wide:

```bash
# As root or with sudo
pip install --prefix=/opt/slurmq slurmq

# Add to system PATH in /etc/profile.d/slurmq.sh
export PATH="/opt/slurmq/bin:$PATH"
```

Then create a system-wide config at `/etc/slurmq/config.toml`.

## Shell completion

slurmq supports shell completion for bash, zsh, and fish:

=== "Bash"

    ```bash
    # Add to ~/.bashrc
    eval "$(slurmq --show-completion bash)"
    ```

=== "Zsh"

    ```bash
    # Add to ~/.zshrc
    eval "$(slurmq --show-completion zsh)"
    ```

=== "Fish"

    ```bash
    # Add to ~/.config/fish/config.fish
    slurmq --show-completion fish | source
    ```
