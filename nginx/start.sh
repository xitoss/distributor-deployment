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
# Check if SSL certificate exists
# ==========================
if [ ! -f "/etc/letsencrypt/live/${PRIMARY_DOMAIN}/fullchain.pem" ]; then
    echo "Step 1: No SSL certificate found, obtaining via standalone mode..."
    
    # Use certbot standalone mode (no nginx needed yet)
    certbot certonly \
        --standalone \
        --preferred-challenges http \
        -d "$PRIMARY_DOMAIN" -d "$WWW_DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" \
        --agree-tos --non-interactive --no-eff-email

    echo "Step 2: Certificate obtained successfully!"
else
    echo "SSL certificate already exists"
fi

# ==========================
# Generate HTTPS Nginx config
# ==========================
export NGINX_SERVER_NAME="$ALL_DOMAINS"
export PRIMARY_DOMAIN="$PRIMARY_DOMAIN"
envsubst '${NGINX_SERVER_NAME} ${PRIMARY_DOMAIN}' \
    < /etc/nginx/templates/app.https.conf.template \
    > /etc/nginx/conf.d/default.conf

# ==========================
# Start Nginx in foreground (only once)
# ==========================
echo "Starting Nginx in foreground with HTTPS..."
nginx -g "daemon off;" &

# ==========================
# Auto-renewal background loop
# ==========================
echo "Setting up auto-renewal..."
(
    while :; do
        sleep 12h
        echo "Checking for certificate renewal..."
        # Use webroot for renewals (nginx is now running)
        certbot renew --webroot -w /var/www/certbot --quiet --deploy-hook "nginx -s reload"
    done
) &

# Wait for Nginx foreground process
wait