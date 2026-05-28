# Audit Log Rotation

Use `logrotate` to rotate the TaskChampion MCP audit log produced at:

- default: `~/.local/share/taskchampion-mcp/audit.log`
- custom: the `logging.audit_log` path in `config.toml`

Example `/etc/logrotate.d/taskchampion-mcp`:

```conf
/home/*/.local/share/taskchampion-mcp/audit.log {
    daily
    rotate 14
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
}
```

Notes:

- `copytruncate` is suitable for a long-running MCP process writing append-only JSON Lines.
- Adjust `daily`/`rotate` to match retention requirements.
- For non-Linux systems, use an equivalent scheduled rotation mechanism.
