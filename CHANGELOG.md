# Changelog

## [0.0.2](https://github.com/dedalus-labs/slurmq/compare/v0.0.1...v0.0.2) (2025-12-25)


### Bug Fixes

* **cli:** use specific exception types instead of broad Exception ([5cb738a](https://github.com/dedalus-labs/slurmq/commit/5cb738a8627510f77e0f95a8d50683dfbf5e54f1))
* **slurm:** use separate args for sacct date options ([8f2360e](https://github.com/dedalus-labs/slurmq/commit/8f2360ecbd7efa035d130087e426662c831883a5))
* **tests:** correct fixture return type annotations ([f467109](https://github.com/dedalus-labs/slurmq/commit/f46710997cc488e41f8ba041ad64bdba2a966cca))


### Refactors

* **core:** extract domain models to models.py ([5ca0414](https://github.com/dedalus-labs/slurmq/commit/5ca0414e29e9802c2f227a808a4b7fdb3ddc5119))
* **core:** fix lint violations from ALL rules ([9d72425](https://github.com/dedalus-labs/slurmq/commit/9d724258001358609bc7b0e1d26e77b1b89bf64c))
* **core:** use Pydantic models for sacct JSON parsing ([ba83103](https://github.com/dedalus-labs/slurmq/commit/ba831031173d307c04c5cb2945e6223a26c87038))
* **core:** use timezone-aware datetime and TYPE_CHECKING imports ([efa0aa3](https://github.com/dedalus-labs/slurmq/commit/efa0aa3d97eac3b3c826d36cf69d807620930f22))
* **stats:** add JobStats dataclass for typed job data ([589f6da](https://github.com/dedalus-labs/slurmq/commit/589f6da92ba4b6a7bf25c785540cd884efd23392))
* **stats:** use statistics.median for cleaner calculation ([e719d76](https://github.com/dedalus-labs/slurmq/commit/e719d760f321bc2af89c4c6b1f8644788f8a1272))
* **tests:** fix lint violations and type annotations ([a3fc3e1](https://github.com/dedalus-labs/slurmq/commit/a3fc3e16ff4080e8038cad10be3e3c727e13843a))


### Documentation

* add conventional commits guide and improve writing quality ([1787e9d](https://github.com/dedalus-labs/slurmq/commit/1787e9d4f9ce665b4ef8b782ae8f5c6ee1f23cef))
* add git-revision-date, magiclink, PyPI link ([446f17b](https://github.com/dedalus-labs/slurmq/commit/446f17b48e6aec18b27eb95eb06fa5795136698e))
* add Python style guide ([6155f6a](https://github.com/dedalus-labs/slurmq/commit/6155f6afa8069dfa5e9977dcfda8527daac4fff6))
* **models:** clarify GPU-hours are allocation-based ([20f022e](https://github.com/dedalus-labs/slurmq/commit/20f022e4e22539b1ab8a6389a465a416d8e6bd78))
* SLURM -&gt; Slurm ([7aa729f](https://github.com/dedalus-labs/slurmq/commit/7aa729ff6ff7bf37602c3006f98f55ebf495c468))


### Chores

* add missing docstrings for D107/D102 ([ffe7c88](https://github.com/dedalus-labs/slurmq/commit/ffe7c88022450ec1bc8babf2ddcff18ec18f0a87))
* add pre-commit hooks and lint configs ([f9bf83d](https://github.com/dedalus-labs/slurmq/commit/f9bf83def5b12c48f906db4c0d2778ac33ec6d39))
* add pre-commit to dev deps ([b2d3675](https://github.com/dedalus-labs/slurmq/commit/b2d3675f257defb2e1fa8dc72646e5a596c47dda))
* bump deps ([a0676cf](https://github.com/dedalus-labs/slurmq/commit/a0676cf64865f9895c06e426eebef1049db63fc7))
* change wording for project description ([698b8e0](https://github.com/dedalus-labs/slurmq/commit/698b8e0d5ab6d007b2bab0a64b64ad40c417f9ae))
* **ci:** add zizmor security config ([73167b2](https://github.com/dedalus-labs/slurmq/commit/73167b217d694d965e9d47da4d4bfa1160b6ab6e))
* **ci:** harden workflows with persist-credentials and job-level perms ([263c87e](https://github.com/dedalus-labs/slurmq/commit/263c87ee2d3ef6d30e95cabeeb9463a69bff4a5a))
* **deps:** sync lockfile and bump ty to 0.0.7 ([c4498cd](https://github.com/dedalus-labs/slurmq/commit/c4498cd1fa4d6b9948b50a8f414ca5a967e058c7))
* **lint:** add pydocstyle rules with Google convention ([f5212cb](https://github.com/dedalus-labs/slurmq/commit/f5212cbc376704e4207b3130b96e3f7466d71e1e))
* **lint:** configure ruff ALL rules with justified ignores ([b95cd0d](https://github.com/dedalus-labs/slurmq/commit/b95cd0d91c88a45a7da83b5d4c1842ef1600ee6e))
* reset version to 0.0.1 for proper release-please bump ([ee8b3e6](https://github.com/dedalus-labs/slurmq/commit/ee8b3e6fa41ec3dbb5cbdc35e021f6c0e17826cf))
* update dependencies ([d4f6131](https://github.com/dedalus-labs/slurmq/commit/d4f6131fa407f9e73b540add10e46ee5b35b0a0e))

## [0.0.2](https://github.com/dedalus-labs/slurmq/compare/v0.0.1...v0.0.2) (2025-12-24)


### Chores

* init ([ee2c1f9](https://github.com/dedalus-labs/slurmq/commit/ee2c1f983fd962861c5fb2a500b0142f7f459027))

## Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

This changelog is automatically maintained by [release-please](https://github.com/googleapis/release-please).
