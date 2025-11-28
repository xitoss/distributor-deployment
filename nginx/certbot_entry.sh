#!/bin/sh

set -e

DOMAIN="${DOMAIN}"
EMAIL="${LETSENCRYPT_EMAIL}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "DOMAIN or LETSENCRYPT_EMAIL is missing from environment variables!"
    exit 1
fi

echo "Checking if certificate already exists for $DOMAIN..."

if [ ! -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]; then
    echo "⚡ Generating initial certificate for $DOMAIN"
    certbot certonly \
        --webroot -w /var/www/certbot \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive \
        --no-eff-email
else
    echo "Certificate already exists. Skipping generation."
fi

echo "Starting auto-renewal loop..."
trap exit TERM
while :; do
    certbot renew --webroot -w /var/www/certbot --quiet
    sleep 12h & wait $!
done
