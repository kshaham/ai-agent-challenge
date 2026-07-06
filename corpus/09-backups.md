# Backups and Restore

Meridian supports snapshot backups through the CLI.

## Creating a backup

    meridian-cli backup --output /snapshots/meridian-2025-01-01

Backups are incremental: after the first full snapshot, subsequent backups only
copy shards that changed. A daily backup schedule is recommended.

## Restoring

    meridian-cli restore --input /snapshots/meridian-2025-01-01

Restore replays the snapshot into a fresh data directory. The node must be stopped
before restoring.

## Point-in-time recovery

Point-in-time recovery (replaying to an arbitrary timestamp) is available only on
the Enterprise tier. On other tiers, recovery granularity is the most recent
snapshot.
