#!/bin/sh
exec caddy file-server --listen ":${PORT:-80}" --root /srv
