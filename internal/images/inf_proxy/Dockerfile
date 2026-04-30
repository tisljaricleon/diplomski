FROM openresty/openresty:1.25.3.2-alpine

# Remove default nginx config
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy our nginx config and Lua routing script
COPY nginx.conf /etc/nginx/nginx.conf
COPY lua/proxy.lua /etc/nginx/lua/proxy.lua

EXPOSE 80

CMD ["/usr/local/openresty/bin/openresty", "-g", "daemon off;"]
