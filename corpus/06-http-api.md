# HTTP API

The Meridian HTTP API is served on port 7280.

## Endpoints

- `POST /write` — ingest points in line protocol.
- `POST /query` — run an MQL query supplied in the request body.
- `GET /health` — readiness check; returns `200 OK` when the node can serve reads.

## Authentication

Requests are authenticated with a token in the `Authorization` header:

    Authorization: Token <your-token>

Tokens are created with the CLI (see the Security guide).

## Rate limits

The hosted Free tier is limited to 1000 requests per minute. Self-hosted nodes are
not rate limited by default.
