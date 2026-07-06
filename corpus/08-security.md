# Security

Meridian secures access with authentication tokens and TLS.

## Tokens

Create a token with the CLI:

    meridian-cli token create --role writer --database metrics

Tokens can be scoped to a single database and are passed in the `Authorization`
header on every request.

## Roles

Meridian has three built-in roles:

- `admin` — full control, including token and user management.
- `writer` — may write and read data.
- `reader` — read-only access.

## TLS

Enable TLS by setting `tls_cert` and `tls_key` in the `[server]` section of
`meridian.toml`. When TLS is enabled the HTTP API is served over HTTPS on the same
port.
