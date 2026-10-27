#!/bin/sh
# Runs docker compose for the local Attendee stack with our overrides.
#   infra/attendee.sh up -d      start everything
#   infra/attendee.sh down       stop everything
#   infra/attendee.sh logs -f attendee-app-local
cd "$(dirname "$0")/../attendee" || exit 1
exec docker compose -f dev.docker-compose.yaml -f ../infra/attendee.local.yaml "$@"
