#!/bin/sh
uvicorn http_server:app --host 0.0.0.0 --port 8001 &
exec /usr/local/openresty/bin/openresty -g "daemon off;"
