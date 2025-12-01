#!/bin/bash
set -e

echo "=== Setting up media/processing/backup permissions ==="

# Base directory
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIRS="$BASE_DIR/media $BASE_DIR/processing $BASE_DIR/backup"

# Check if web container is running and ready
WEB_CONTAINER="xitoss-distributor-web-1"

if ! docker ps --format '{{.Names}}' | grep -q "^$WEB_CONTAINER\$"; then
    echo "Web container is not running. Please start the containers first:"
    echo "  docker compose up -d --build"
    exit 1
fi

# Wait until appuser exists inside the container
echo "Checking if appuser exists inside web container..."
MAX_TRIES=10
TRY=1
while ! docker compose exec web id appuser &>/dev/null; do
    if [ $TRY -ge $MAX_TRIES ]; then
        echo "appuser still not available inside web container. Please try again later."
        exit 1
    fi
    echo "Waiting for web container to be ready... ($TRY/$MAX_TRIES)"
    TRY=$((TRY+1))
    sleep 3
done

# Get UID and GID of appuser
APP_UID=$(docker compose exec web id -u appuser | tr -d '\r')
APP_GID=$(docker compose exec web id -g appuser | tr -d '\r')
echo "appuser UID:GID = $APP_UID:$APP_GID"

# Create folders and set ownership/permissions
for DIR in $DIRS; do
    mkdir -p "$DIR"
    echo "$DIR has been created."
    sudo chown -R "$APP_UID:$APP_GID" "$DIR"
    chmod -R 775 "$DIR"
    echo "Assigned ownership $APP_UID:$APP_GID and permissions 775 to $DIR"
done

echo "=== Permissions setup complete ==="
