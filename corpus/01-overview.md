# Meridian Overview

Meridian is an open-source time-series database built for metrics, IoT telemetry,
and observability workloads. It is developed by Lumen Labs and is written in Rust.

The current stable release is version 3.2, released in 2025. Meridian is
distributed under the Apache 2.0 license.

## Design goals

Meridian is designed for high-cardinality ingestion, fast range queries, and
predictable memory use. It stores data in immutable, time-partitioned shards and
compacts them in the background.

## Where to go next

See the Installation guide to get a node running, the Configuration reference for
tuning, and the Query Language guide for MQL.
