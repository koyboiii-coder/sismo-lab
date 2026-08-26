#!/usr/bin/env bash
# One-time bootstrap for the `ntfy` service in docker-compose.yml.
#
# ntfy runs with NTFY_AUTH_DEFAULT_ACCESS=deny-all (infra/docker-compose.yml),
# so nothing can publish or subscribe to any topic until users are created
# and explicitly ACL'd. This script creates two:
#
#   - sismos-daemon: write-only on the `sismos` topic, authenticated by an
#     access token (not a password) -- what daemon/alerts.py uses to POST
#     notifications. The token is written to infra/.env as NTFY_TOKEN,
#     which docker-compose.yml reads via ${NTFY_TOKEN:-}. infra/.env is
#     gitignored (see repo root .gitignore's bare `.env` pattern) -- never
#     commit it, and never paste the printed token anywhere that ends up in
#     git history, chat logs, or a public issue.
#   - sismos-viewer: read-only on the `sismos` topic, authenticated by a
#     password you choose -- for subscribing from a phone's ntfy app (or,
#     later, the dashboard) without being able to publish.
#
# Usage:
#   cd infra
#   docker compose up -d postgres ntfy   # bring up ntfy without the daemon,
#                                         # which needs NTFY_TOKEN to start
#   ./ntfy-setup.sh
#   docker compose up -d                 # now daemon can start with the token

set -euo pipefail
cd "$(dirname "$0")"

if ! docker compose exec -T ntfy true 2>/dev/null; then
    echo "error: the 'ntfy' service isn't running. Start it first:" >&2
    echo "  docker compose up -d postgres ntfy" >&2
    exit 1
fi

if [ -f .env ] && grep -q '^NTFY_TOKEN=' .env; then
    echo "infra/.env already has NTFY_TOKEN set -- refusing to overwrite it."
    echo "Delete that line first if you really want to regenerate the token."
    exit 1
fi

echo "Creating sismos-daemon (write-only, token auth)..."
bot_password="$(openssl rand -base64 24)"
# Non-interactive: ntfy reads the password from stdin when it isn't a TTY.
# The password itself is thrown away immediately after -- only the token
# below is ever used to authenticate.
printf '%s\n%s\n' "$bot_password" "$bot_password" | \
    docker compose exec -T ntfy ntfy user add --role=user sismos-daemon
docker compose exec -T ntfy ntfy access sismos-daemon sismos write-only

token_output="$(docker compose exec -T ntfy ntfy token add sismos-daemon)"
echo "$token_output"
token="$(echo "$token_output" | grep -oE 'tk_[A-Za-z0-9]+' | head -1)"
if [ -z "$token" ]; then
    echo "error: couldn't parse a token (tk_...) out of 'ntfy token add' output above." >&2
    echo "Run it manually: docker compose exec ntfy ntfy token add sismos-daemon" >&2
    exit 1
fi

printf 'NTFY_TOKEN=%s\n' "$token" >> .env
echo "Wrote NTFY_TOKEN to infra/.env"

echo
echo "Creating sismos-viewer (read-only, password auth, for phone/dashboard)..."
docker compose exec ntfy ntfy user add --role=user sismos-viewer
docker compose exec -T ntfy ntfy access sismos-viewer sismos read-only

echo
echo "Done. Now run: docker compose up -d"
echo "The ntfy app on a phone can subscribe to topic 'sismos' at your"
echo "server's URL using the sismos-viewer username/password you just set."
