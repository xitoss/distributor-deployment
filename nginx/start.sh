#!/bin/sh
set -e

# Ensure environment variables are set
: "${DOMAIN:?Need to set DOMAIN}"
: "${LETSENCRYPT_EMAIL:?Need to set LETSENCRYPT_EMAIL}"

# AUTO-GENERATE www subdomain from single domain
PRIMARY_DOMAIN="$DOMAIN"
WWW_DOMAIN="www.$DOMAIN"
ALL_DOMAINS="$PRIMARY_DOMAIN $WWW_DOMAIN"

echo "=== Starting SSL Setup ==="
echo "Primary domain: $PRIMARY_DOMAIN"
echo "WWW domain: $WWW_DOMAIN"
echo "Certificate will cover both domains"

# Create necessary directories
mkdir -p /var/www/certbot
mkdir -p /etc/letsencrypt/live

# Generate HTTP-only config for ACME challenge
echo "Step 1: Generating HTTP-only config..."
export NGINX_SERVER_NAME="$ALL_DOMAINS"
envsubst '${NGINX_SERVER_NAME}' < /etc/nginx/templates/app.http.conf.template > /etc/nginx/conf.d/default.conf

# Validate and start Nginx with HTTP only
echo "Step 2: Starting Nginx (HTTP only)..."
nginx -t
nginx

# Wait for Nginx to be ready
sleep 3

# Check if certificate already exists
if [ -f "/etc/letsencrypt/live/${PRIMARY_DOMAIN}/fullchain.pem" ]; then
    echo "Step 3: SSL certificate already exists, skipping generation"
else
    echo "Step 3: Obtaining SSL certificate for $PRIMARY_DOMAIN and $WWW_DOMAIN..."
    
    # Get certificate for both domains
    if certbot certonly \
        --webroot \
        -w /var/www/certbot \
        -d "$PRIMARY_DOMAIN" \
        -d "$WWW_DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" \
        --agree-tos \
        --non-interactive \
        --no-eff-email 2>&1 | tee /tmp/certbot.log; then
        echo "✓ Certificate obtained successfully for both domains"
    else
        echo "✗ Failed to obtain certificate. Check the log above."
        echo ""
        echo "Common issues:"
        echo "  1. DNS: Both $PRIMARY_DOMAIN and $WWW_DOMAIN must point to this server"
        echo "     Check: nslookup $PRIMARY_DOMAIN && nslookup $WWW_DOMAIN"
        echo ""
        echo "  2. Port 80 not accessible from internet"
        echo "     Fix: sudo ufw allow 80"
        echo ""
        echo "  3. Rate limit (wait 1 hour)"
        exit 1
    fi
fi

# Enable HTTPS config
echo "Step 4: Enabling HTTPS configuration..."
export NGINX_SERVER_NAME="$ALL_DOMAINS"
export PRIMARY_DOMAIN="$PRIMARY_DOMAIN"
envsubst '${NGINX_SERVER_NAME} ${PRIMARY_DOMAIN}' < /etc/nginx/templates/app.https.conf.template > /etc/nginx/conf.d/default.conf

# Validate new config
echo "Step 5: Validating HTTPS configuration..."
nginx -t

# Reload Nginx to apply HTTPS config
echo "Step 6: Reloading Nginx with HTTPS..."
nginx -s reload

echo "=== SSL Setup Complete! ==="
echo "Your site is now accessible at:"
echo "  https://$PRIMARY_DOMAIN"
echo "  https://$WWW_DOMAIN"

# Set up auto-renewal in background
echo "Setting up certificate auto-renewal..."
(
    while :; do
        sleep 12h
        echo "Checking for certificate renewal..."
        certbot renew --webroot -w /var/www/certbot --quiet --deploy-hook "nginx -s reload"
    done
) &

# Keep nginx running in foreground
nginx -g "daemon off;"