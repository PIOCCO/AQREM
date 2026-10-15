#!/bin/sh
# Ensure LOCAL_UPLOAD_DIR is owned by aqrem (uid 1001) when using Docker volumes.
set -e

if [ "$(id -u)" = "0" ]; then
  upload_dir="${LOCAL_UPLOAD_DIR:-/data/uploads}"
  if [ -n "$upload_dir" ]; then
    mkdir -p "$upload_dir"
    chown -R aqrem:aqrem "$upload_dir"
  fi
  exec setpriv --reuid=1001 --regid=1001 --clear-groups -- "$@"
fi

exec "$@"
