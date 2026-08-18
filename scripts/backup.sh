#!/bin/sh
set -eu
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose -f docker-compose.production.yml exec -T control-db pg_dump -U changeshield -Fc changeshield > "changeshield-${stamp}.dump"
aws s3 cp "changeshield-${stamp}.dump" "s3://${BACKUP_BUCKET}/database/changeshield-${stamp}.dump" --sse AES256
echo "Uploaded encrypted backup changeshield-${stamp}.dump"

