#!/bin/sh
set -eu
region=${AWS_REGION:?required}
repo_url=${REPOSITORY_URL:?required}
public_hostname=${PUBLIC_HOSTNAME:?required}
app_dir=/opt/changeshield

sudo dnf install -y docker git awscli2
sudo systemctl enable --now docker
if [ ! -d "$app_dir/.git" ]; then sudo git clone "$repo_url" "$app_dir"; fi
sudo chown -R ec2-user:ec2-user "$app_dir"
cd "$app_dir"
db_password=$(aws ssm get-parameter --region "$region" --name /changeshield/database-password --with-decryption --query Parameter.Value --output text)
django_secret=$(aws ssm get-parameter --region "$region" --name /changeshield/django-secret-key --with-decryption --query Parameter.Value --output text)
groq_key=$(aws ssm get-parameter --region "$region" --name /changeshield/groq-api-key --with-decryption --query Parameter.Value --output text)
umask 077
printf 'PUBLIC_HOSTNAME=%s\nCONTROL_DB_PASSWORD=%s\nDJANGO_SECRET_KEY=%s\nGROQ_API_KEY=%s\n' "$public_hostname" "$db_password" "$django_secret" "$groq_key" > .env
sudo docker compose -f docker-compose.production.yml up -d --build

