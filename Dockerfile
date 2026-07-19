FROM nginx:alpine

LABEL org.opencontainers.image.title="space-orbital-tracker"
LABEL org.opencontainers.image.description="空间站实时追踪 Orbital Tracker LIVE (ISS/CSS 实时位置)"
LABEL org.opencontainers.image.source="https://github.com/a125477365/space"

# 关闭 access log 减少 disk io,推荐生产场景打开
RUN sed -i 's/access_log .*/access_log off;/g' /etc/nginx/nginx.conf

WORKDIR /usr/share/nginx/html
COPY . .

# 自检:打印 index.html 大小便于排查
RUN ls -l index.html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://localhost/ >/dev/null || exit 1
