#!/bin/sh
set -e

# Ensure environment variables are set
: "${DOMAIN:?Need to set DOMAIN}"
: "${LETSENCRYPT_EMAIL:?Need to set LETSENCRYPT_EMAIL}"

# Create Certbot webroot if not exists
mkdir -p /var/www/certbot

# Always enable HTTP
echo "Generating HTTP config..."
envsubst '${DOMAIN}' < /etc/nginx/templates/app.http.conf.template > /etc/nginx/conf.d/app.http.conf

# Start Nginx in background (HTTP only)
echo "Starting Nginx (HTTP only) for ACME challenge..."
nginx -g "daemon off;" &
NGINX_PID=$!

# Wait a few seconds to ensure Nginx is fully up
sleep 5

# Generate SSL certificate if it does not exist
if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
    echo "Creating initial SSL certificate for $DOMAIN..."
    certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" \
        --agree-tos --non-interactive --no-eff-email
fi

# Enable HTTPS config now that certificate exists
echo "Generating HTTPS config..."
envsubst '${DOMAIN}' < /etc/nginx/templates/app.https.conf.template > /etc/nginx/conf.d/app.https.conf

# Reload Nginx so HTTPS is enabled
echo "Reloading Nginx with HTTPS..."
nginx -s reload

# Keep container running
wait $NGINX_PID
