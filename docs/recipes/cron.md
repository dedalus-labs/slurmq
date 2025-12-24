# Cron Jobs

Setting up automated quota monitoring and enforcement.

## Basic monitoring cron

Check quotas every 5 minutes:

```bash
# /etc/cron.d/slurmq-monitor
*/5 * * * * root /usr/local/bin/slurmq --quiet monitor --once >> /var/log/slurmq/monitor.log 2>&1
```

## Enforcement cron

With quota enforcement enabled:

```bash
# /etc/cron.d/slurmq-enforce
*/5 * * * * root /usr/local/bin/slurmq --quiet monitor --once --enforce >> /var/log/slurmq/enforce.log 2>&1
```

!!! warning "Enable in config first"
Make sure `[enforcement]` is configured properly before enabling:

    ```toml
    [enforcement]
    enabled = true
    dry_run = false  # Only set false when ready!
    ```

## Daily reports

Generate daily usage report:

```bash
# /etc/cron.d/slurmq-report
0 8 * * * root /usr/local/bin/slurmq report --format csv -o /var/log/slurmq/daily-$(date +\%Y\%m\%d).csv
```

## Weekly stats

Generate weekly analytics:

```bash
# /etc/cron.d/slurmq-weekly
0 9 * * 1 root /usr/local/bin/slurmq --json stats --days 7 > /var/log/slurmq/weekly-$(date +\%Y\%W).json
```

## Systemd timers (alternative)

More robust than cron for modern systems.

### Monitor timer

```ini
# /etc/systemd/system/slurmq-monitor.timer
[Unit]
Description=Run slurmq quota monitoring

[Timer]
OnCalendar=*:0/5
Persistent=true
RandomizedDelaySec=30

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/slurmq-monitor.service
[Unit]
Description=slurmq quota monitoring
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/slurmq --quiet monitor --once --enforce
StandardOutput=append:/var/log/slurmq/monitor.log
StandardError=append:/var/log/slurmq/monitor.log
```

Enable:

```bash
sudo systemctl enable --now slurmq-monitor.timer
```

### Daily report timer

```ini
# /etc/systemd/system/slurmq-report.timer
[Unit]
Description=Daily slurmq report

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/slurmq-report.service
[Unit]
Description=Generate daily slurmq report

[Service]
Type=oneshot
ExecStart=/bin/bash -c '/usr/local/bin/slurmq report --format csv -o /var/log/slurmq/daily-$(date +%%Y%%m%%d).csv'
```

## Log rotation

Rotate slurmq logs:

```
# /etc/logrotate.d/slurmq
/var/log/slurmq/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
```

## Monitoring the monitor

Alert if slurmq itself fails:

```bash
#!/bin/bash
# /usr/local/bin/slurmq-healthcheck.sh

if ! slurmq --quiet check 2>/dev/null; then
  echo "slurmq check failed!" | mail -s "slurmq alert" admin@example.edu
fi
```

```bash
# Cron entry
*/30 * * * * root /usr/local/bin/slurmq-healthcheck.sh
```

## Best practices

1. **Start with dry_run** - Always test enforcement with `dry_run = true` first
2. **Log everything** - Keep logs for audit trail
3. **Use systemd** - More reliable than cron for critical monitoring
4. **Set up alerts** - Know when slurmq itself fails
5. **Test restores** - Verify config after system updates
