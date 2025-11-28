#!/bin/sh
set -e

# Load environment variables
export DOMAIN=${DOMAIN}

# Always enable HTTP
envsubst '${DOMAIN}' < /etc/nginx/templates/app.http.conf.template > /etc/nginx/conf.d/app.http.conf

# Enable HTTPS config only if cert exists
if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
    echo "Enabling HTTPS..."
    envsubst '${DOMAIN}' < /etc/nginx/templates/app.https.conf.template > /etc/nginx/conf.d/app.https.conf
else
    echo "HTTPS disabled — waiting for Certbot to create certificates."
fi

# Start nginx in background
nginx -g "daemon off;" &
NGINX_PID=$!

# Wait for Nginx to start so Certbot can succeed
sleep 5

# If certificate does not exist, run Certbot to create it
if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
    echo "Creating initial SSL certificate for $DOMAIN..."
    certbot certonly --webroot -w /var/www/certbot \
        -d ${DOMAIN} \
        --email ${LETSENCRYPT_EMAIL} \
        --agree-tos --non-interactive
    echo "Reloading Nginx with new certificate..."
    envsubst '${DOMAIN}' < /etc/nginx/templates/app.https.conf.template > /etc/nginx/conf.d/app.https.conf
    nginx -s reload
fi

# Keep the container running
wait $NGINX_PID
