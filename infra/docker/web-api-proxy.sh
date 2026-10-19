#!/bin/sh
# Writes an /api + /health reverse proxy when API_UPSTREAM is set.
set -e
if [ -n "${API_UPSTREAM:-}" ]; then
  cat > /etc/nginx/api-proxy/api.conf <<CONF
# HTTPS upstreams use the ingress FQDN for SNI and certificate verification.
# These server-level settings cover both /api/ and /health; HTTP lab upstreams are unaffected.
proxy_ssl_server_name on;
proxy_ssl_verify on;
proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
proxy_ssl_verify_depth 3;

location /api/ {
    proxy_pass ${API_UPSTREAM};
    proxy_http_version 1.1;
    proxy_set_header Host \$proxy_host;
    proxy_set_header X-Forwarded-Host \$http_host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    # FastAPI sees the internal ingress host/scheme when generating absolute redirects.
    proxy_redirect http://\$proxy_host/ https://\$http_host/;
    proxy_redirect https://\$proxy_host/ https://\$http_host/;
    proxy_buffering off;
    proxy_read_timeout 300s;
    client_max_body_size 60m;
}
location = /health {
    proxy_pass ${API_UPSTREAM};
}
CONF
fi
