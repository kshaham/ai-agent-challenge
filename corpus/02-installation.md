# Installing Meridian

Meridian ships as a single static binary and as an official Docker image,
`lumenlabs/meridian:3.2`.

## Requirements

A Meridian node requires at least 2 CPU cores and 4 GB of RAM. Supported operating
systems are Linux and macOS. Windows is not supported for production use.

## Install from binary

Download the `meridian` binary for your platform, make it executable, and run
`meridian server`. By default the server stores data under `/var/lib/meridian`.

## Install with Docker

    docker run -p 7280:7280 -v meridian-data:/var/lib/meridian lumenlabs/meridian:3.2

The container exposes the HTTP API on port 7280.
