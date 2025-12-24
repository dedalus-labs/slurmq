# Security Policy

## Reporting Vulnerabilities

**Do not open public issues for security vulnerabilities.**

Email security reports to: [security@dedaluslabs.ai](mailto:security@dedaluslabs.ai)

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within 48 hours and provide a detailed response within 7 days.

## Supported Versions

| Version | Supported                |
| ------- | ------------------------ |
| main    | Active development       |
| < 1.0   | Pre-release, best-effort |

## Security Considerations

slurmq handles:

- **Config files**: Read from `~/.config/slurmq/config.toml` or `/etc/slurmq/config.toml`
- **Slurm commands**: Executed via subprocess (no shell=True)
- **User data**: Job IDs, usernames, GPU-hours from Slurm

### Best Practices for Admins

- Restrict write access to `/etc/slurmq/config.toml`
- Use `slurmq config validate` before deploying config changes
- Review `exempt_users` list periodically
- Monitor enforcement logs for anomalies

## Disclosure Policy

We follow coordinated disclosure:

1. Reporter submits vulnerability privately
2. We acknowledge within 48 hours
3. We investigate and develop fix
4. We release fix and credit reporter (unless anonymity requested)
5. Public disclosure after 90 days or when fix is deployed

## Contact

- Security issues: [security@dedaluslabs.ai](mailto:security@dedaluslabs.ai)
- General questions: [oss@dedaluslabs.ai](mailto:oss@dedaluslabs.ai)
