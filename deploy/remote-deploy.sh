#!/usr/bin/env bash
# Runs ON THE EC2 SERVER (as root, through AWS SSM Run Command) after the deploy bundle
# has been unpacked into /opt/etaflow. Called by deploy/aws/deploy-now.ps1 and by
# .github/workflows/deploy.yml.
#
# Usage: bash /opt/etaflow/deploy/remote-deploy.sh <ecr-image-uri:tag> <aws-region>
set -euo pipefail

IMAGE="${1:?usage: remote-deploy.sh <ecr-image-uri:tag> <aws-region>}"
REGION="${2:?usage: remote-deploy.sh <ecr-image-uri:tag> <aws-region>}"
APP_DIR="${ETAFLOW_APP_DIR:-/opt/etaflow}"
PASSWORD_PARAM="/etaflow/grafana-admin-password"

cd "$APP_DIR"

# A deploy right after the server is created can start before first-boot setup
# (Docker + Compose install) has finished, so wait for it and check the result.
if command -v cloud-init >/dev/null 2>&1; then
    echo "Waiting for server setup (cloud-init) to finish..."
    set +e
    cloud-init status --wait >/dev/null
    BOOT_RC=$?
    set -e
    if [ "$BOOT_RC" -eq 1 ]; then
        echo "ERROR: server setup failed. See /var/log/cloud-init-output.log on the server." >&2
        exit 1
    fi
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: Docker Compose is not available on this server. See /var/log/cloud-init-output.log." >&2
    exit 1
fi

# Grafana is public on port 3000, so never start it without a real admin password.
if ! GRAFANA_PW="$(aws ssm get-parameter --region "$REGION" --name "$PASSWORD_PARAM" \
        --with-decryption --query Parameter.Value --output text 2>/dev/null)" || [ -z "$GRAFANA_PW" ]; then
    echo "ERROR: SSM parameter $PASSWORD_PARAM is missing or empty." >&2
    echo "Run deploy/aws/set-grafana-password.ps1 on your PC first. Nothing was changed on this server." >&2
    exit 1
fi
case "$GRAFANA_PW" in
    *"'"*) echo "ERROR: the Grafana password must not contain a single quote. Nothing was changed." >&2; exit 1 ;;
esac

REGISTRY="${IMAGE%%/*}"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"

umask 077
printf "ETAFLOW_IMAGE='%s'\nGRAFANA_ADMIN_PASSWORD='%s'\n" "$IMAGE" "$GRAFANA_PW" > .env.tmp
mv .env.tmp .env
chmod 600 .env

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
"${COMPOSE[@]}" pull etaflow
"${COMPOSE[@]}" up -d --remove-orphans
# Remove every image no container is using (old etaflow-app tags too), so the 20 GB disk never fills up.
docker image prune -af
"${COMPOSE[@]}" ps
echo "ETAFlow deployed: $IMAGE"
