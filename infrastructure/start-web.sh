#!/bin/sh
set -eu
upstream=${ORQENTRA_API_UPSTREAM:-api:8000}
case "$upstream" in
  *[!a-zA-Z0-9._:-]*|:*|*:|'') echo 'Invalid API upstream' >&2; exit 1 ;;
esac
case "$upstream" in *:*) ;; *) echo 'API upstream requires a port' >&2; exit 1 ;; esac
host=${upstream%:*}
port=${upstream##*:}
case "$host" in *:*|'') echo 'API upstream must be a hostname and port' >&2; exit 1 ;; esac
case "$port" in *[!0-9]*|'') echo 'Invalid API port' >&2; exit 1 ;; esac
[ "$port" -ge 1 ] && [ "$port" -le 65535 ] || exit 1
resolver=${ORQENTRA_DNS_RESOLVER:-$(awk '$1 == "nameserver" { print $2; exit }' /etc/resolv.conf)}
case "$resolver" in *[!0-9a-fA-F:.]*|'') echo 'Invalid DNS resolver' >&2; exit 1 ;; esac
case "$resolver" in *:*) resolver="[$resolver]" ;; esac
sed -e "s|resolver 127.0.0.11 valid=5s ipv6=off;|resolver $resolver valid=5s ipv6=off;|" \
    -e "s|api:8000;|$upstream;|" /etc/nginx/nginx.conf > /tmp/orqentra-nginx.conf
nginx -t -c /tmp/orqentra-nginx.conf
exec nginx -c /tmp/orqentra-nginx.conf -g 'daemon off;'
