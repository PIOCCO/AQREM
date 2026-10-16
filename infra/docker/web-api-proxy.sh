#!/bin/sh
# Writes an /api + /health reverse proxy when API_UPSTREAM is set (e.g. http://contoso-api).
set -e
if [ -n "${API_UPSTREAM:-}" ]; then
  cat > /etc/nginx/api-proxy/api.conf <<CONF
location /api/ {
    proxy_pass ${API_UPSTREAM};
    proxy_http_version 1.1;
    proxy_set_header Host \$proxy_host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_buffering off;
    proxy_read_timeout 300s;
    client_max_body_size 60m;
}
location = /health {
    proxy_pass ${API_UPSTREAM};
}
CONF
fi
