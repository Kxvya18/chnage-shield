#!/bin/sh
set -eu
dump_path=${1:?usage: restore-check.sh path-to-dump}
docker compose -f docker-compose.production.yml exec -T control-db createdb -U changeshield changeshield_restore_check || true
docker compose -f docker-compose.production.yml exec -T control-db pg_restore -U changeshield -d changeshield_restore_check --clean --if-exists < "$dump_path"
docker compose -f docker-compose.production.yml exec -T control-db psql -U changeshield -d changeshield_restore_check -c 'SELECT COUNT(*) FROM control_workflow;'
