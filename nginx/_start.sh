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
    echo "Step 1: No SSL certificate found, starting HTTP-only mode..."
    
    # Generate HTTP-only Nginx config for ACME challenge
    export NGINX_SERVER_NAME="$ALL_DOMAINS"
    envsubst '${NGINX_SERVER_NAME}' \
        < /etc/nginx/templates/app.http.conf.template \
        > /etc/nginx/conf.d/default.conf

    # Start Nginx in background for ACME challenge
    echo "Step 2: Starting Nginx for ACME challenge..."
    nginx -g "daemon on;"
    
    # Wait a moment for Nginx to start
    sleep 2

    echo "Step 3: Obtaining SSL certificate..."
    certbot certonly \
        --webroot -w /var/www/certbot \
        -d "$PRIMARY_DOMAIN" -d "$WWW_DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" --agree-tos --non-interactive --no-eff-email

    echo "Step 4: Certificate obtained! Switching to HTTPS configuration..."
    
    # Now generate HTTPS config
    export PRIMARY_DOMAIN="$PRIMARY_DOMAIN"
    envsubst '${NGINX_SERVER_NAME} ${PRIMARY_DOMAIN}' \
        < /etc/nginx/templates/app.https.conf.template \
        > /etc/nginx/conf.d/default.conf

    # Stop the background Nginx to restart it in foreground with HTTPS
    echo "Step 5: Stopping temporary Nginx..."
    nginx -s stop
    
    # Wait for port 80 to be fully released
    sleep 3
    
    # Verify port is free
    while netstat -tuln | grep -q ':80 '; do
        echo "Waiting for port 80 to be released..."
        sleep 1
    done
    echo "Port 80 is now available"
else
    echo "SSL certificate already exists, using HTTPS configuration"
    
    # Generate HTTPS config
    export NGINX_SERVER_NAME="$ALL_DOMAINS"
    export PRIMARY_DOMAIN="$PRIMARY_DOMAIN"
    envsubst '${NGINX_SERVER_NAME} ${PRIMARY_DOMAIN}' \
        < /etc/nginx/templates/app.https.conf.template \
        > /etc/nginx/conf.d/default.conf
fi

# ==========================
# Final foreground start
# ==========================
echo "Starting Nginx in foreground..."
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