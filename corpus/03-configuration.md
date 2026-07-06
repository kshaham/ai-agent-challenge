# Configuration Reference

Meridian reads its configuration from `meridian.toml` in the working directory, or
from the path given by the `--config` flag.

## Network

The HTTP API listens on port 7280 by default. The gRPC ingestion endpoint listens
on port 7281. Both can be overridden with the `http_port` and `grpc_port` keys.

## Storage and retention

- `retention` — how long to keep data before it is dropped. Default is `30d`.
- `shard_duration` — the time span of each storage shard. Default is `1d`.
- `max_connections` — maximum concurrent client connections. Default is `128`.

## Example

    [server]
    http_port = 7280
    grpc_port = 7281
    max_connections = 128

    [storage]
    retention = "30d"
    shard_duration = "1d"
