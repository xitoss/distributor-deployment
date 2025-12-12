#!/bin/sh
set -e

# ==========================
# Environment validation
# ==========================
: "${DOMAIN:?Need to set DOMAIN}"
: "${LETSENCRYPT_EMAIL:?Need to set LETSENCRYPT_EMAIL}"

PRIMARY_DOMAIN="$DOMAIN"
WWW_DOMAIN="www.$DOMAIN"
ALL_DOMAINS="$PRIMARY_DOMAIN $WWW_DOMAIN"

echo "=== Starting SSL Setup ==="
echo "Primary domain: $PRIMARY_DOMAIN"
echo "WWW domain: $WWW_DOMAIN"
echo "Certificate will cover both domains"

# ==========================
# Create directories
# ==========================
mkdir -p /var/www/certbot /etc/letsencrypt/live

# ==========================
# Prepare HTTPS Nginx config template
# ==========================
export NGINX_SERVER_NAME="$ALL_DOMAINS"
export PRIMARY_DOMAIN="$PRIMARY_DOMAIN"
envsubst '${NGINX_SERVER_NAME} ${PRIMARY_DOMAIN}' \
    < /etc/nginx/templates/app.https.conf.template \
    > /etc/nginx/conf.d/default.conf

# ==========================
# Obtain SSL certificate if missing
# ==========================
if [ ! -f "/etc/letsencrypt/live/${PRIMARY_DOMAIN}/fullchain.pem" ]; then
    echo "Step 1: Starting temporary HTTP server for ACME challenge..."

    # Generate HTTP-only Nginx config for challenge
    envsubst '${NGINX_SERVER_NAME}' \
        < /etc/nginx/templates/app.http.conf.template \
        > /etc/nginx/conf.d/acme.conf

    # Start Nginx in background for ACME challenge
    nginx -g "daemon on;"

    echo "Step 2: Obtaining SSL certificate..."
    certbot certonly \
        --webroot -w /var/www/certbot \
        -d "$PRIMARY_DOMAIN" -d "$WWW_DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" --agree-tos --non-interactive --no-eff-email

    echo "Step 3: Removing temporary HTTP config..."
    rm /etc/nginx/conf.d/acme.conf

    # Reload Nginx with HTTPS config
    nginx -s reload
else
    echo "SSL certificate already exists, skipping generation"
fi

# ==========================
# Final foreground start
# ==========================
echo "Step 4: Starting Nginx in foreground..."
nginx -g "daemon off;" &

# ==========================
# Auto-renewal background loop
# ==========================
echo "Setting up auto-renewal..."
(
    while :; do
        sleep 12h
        echo "Checking for certificate renewal..."
        certbot renew --webroot -w /var/www/certbot --quiet --deploy-hook "nginx -s reload"
    done
) &

# Wait for Nginx foreground process
wait
