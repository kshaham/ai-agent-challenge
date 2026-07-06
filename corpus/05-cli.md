# Command-Line Interface

`meridian-cli` is the administrative client. It connects to a node with the
`--host` and `--port` flags (defaulting to `localhost:7280`).

## Common commands

- `meridian-cli ping` — check that a node is reachable.
- `meridian-cli write` — write points using line protocol.
- `meridian-cli query "<MQL>"` — run a query and print the result.
- `meridian-cli backup` — create a snapshot (see the Backups guide).
- `meridian-cli restore` — restore from a snapshot.
- `meridian-cli token` — manage authentication tokens (see the Security guide).

## Example

    meridian-cli --host db.internal --port 7280 query "SELECT count(value) FROM cpu"
