#!/usr/bin/env python3
"""
space 项目后端代理服务 — 方案 B
代理头像 + TLE + 乘组 API, 避免国内用户翻墙。

安全设计:
  1. 目标 URL 必须是 https
  2. host 必须在白名单内
  3. path 必须以白名单 host 对应前缀开头
  4. 拒绝解析到内网 IP 的 host (SSRF 防护)
  5. 5 秒请求超时
  6. 10 MB 响应体上限
  7. 不跟随重定向 (避免绕过白名单)

所有路由都挂在 /space/api/ 下 (与前端同前缀, 便于 nginx 隔离)。

路由:
  GET /space/api/proxy?u=<url-encoded-https-url>   通用代理 (白名单内)
  GET /space/api/health                             健康检查

启动:
  python3 proxy_server.py                # 默认 0.0.0.0:8080
  python3 proxy_server.py --port 8090     # 自定义端口
"""

import argparse
import hashlib
import ipaddress
import os
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ──────────────────────────────────────────────────────────────────────────────
# 白名单: host → 允许的 path 前缀列表
# ──────────────────────────────────────────────────────────────────────────────
ALLOWED_HOSTS = {
    "upload.wikimedia.org": ["/wikipedia/commons/"],
    "celestrak.org": ["/NORAD/elements/gp.php"],
    "tle.ivanstanojevic.me": ["/api/tle/"],
    "api.wheretheiss.at": ["/v1/satellites/"],
    "raw.githubusercontent.com": [
        "/corquaid/international-space-station-APIs/",
        "/johan/world.geo.json/",
        "/mrdoob/three.js/",
    ],
    "corquaid.github.io": ["/international-space-station-APIs/"],
    "cdn.jsdelivr.net": ["/gh/mrdoob/three.js", "/npm/satellite.js"],
    "unpkg.com": ["/three@"],
}

# 内网 IP 范围 (SSRF 防护)
PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# 请求超时和响应体上限
TIMEOUT = 15           # 秒
MAX_BODY = 10 * 1024 * 1024  # 10 MB

# 上游请求限速 — Wikimedia 429: Too Many Requests
# 当多个头像首次请求时, 排队发上游, 每个请求间隔 ≥1 秒 (缓存命中不排队)
_upstream_lock = threading.Lock()
_last_request_time = {}  # host → 上次请求时间
MIN_INTERVAL = 1.0  # 同 host 最小请求间隔 (秒)

def rate_limit_wait(host):
    """对同一 host 的上游请求做限速, 避免被 429 封."""
    if not host:
        return
    with _upstream_lock:
        now = time.time()
        last = _last_request_time.get(host, 0)
        wait = MIN_INTERVAL - (now - last)
        if wait > 0:
            time.sleep(wait)
        _last_request_time[host] = time.time()

# 磁盘缓存目录 — 对图片/API 响应做缓存,减少上游请求
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
CACHE_TTL = 7 * 24 * 3600  # 7 天 (秒)

def cache_path(url):
    """URL → 缓存文件路径 (sha256 截短)."""
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, h)

def cache_get(url):
    """从缓存读取, 返回 (body, content_type) 或 None."""
    p = cache_path(url)
    if not os.path.exists(p):
        return None
    mtime = os.path.getmtime(p)
    if time.time() - mtime > CACHE_TTL:
        return None  # 过期
    meta_p = p + ".meta"
    ct = "application/octet-stream"
    if os.path.exists(meta_p):
        with open(meta_p, "r") as f:
            ct = f.read().strip() or ct
    with open(p, "rb") as f:
        body = f.read(MAX_BODY + 1)
    if len(body) > MAX_BODY:
        return None
    return body, ct

def cache_put(url, body, content_type):
    """写入缓存."""
    try:
        p = cache_path(url)
        with open(p, "wb") as f:
            f.write(body)
        with open(p + ".meta", "w") as f:
            f.write(content_type or "application/octet-stream")
    except Exception:
        pass  # 缓存写失败不影响请求

# 允许透传的响应头 (避免泄露后端信息)
PASSTHROUGH_HEADERS = {
    "content-type", "content-length", "cache-control", "expires",
    "last-modified", "etag", "accept-ranges",
}


def is_private_ip(host):
    """解析 host 的所有 IP 地址, 判断是否落入内网段."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return True  # DNS 解析失败 → 拒绝

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        for net in PRIVATE_NETWORKS:
            if ip in net:
                return True
    return False


def validate_target(url):
    """
    校验目标 URL, 返回 (ok, error_message).
    ok=True 时 url 可以安全请求.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, "invalid URL"

    if parsed.scheme != "https":
        return False, "only https allowed"

    host = parsed.hostname
    if not host:
        return False, "missing host"

    if host not in ALLOWED_HOSTS:
        return False, f"host '{host}' not in whitelist"

    if not any(parsed.path.startswith(p) for p in ALLOWED_HOSTS[host]):
        return False, f"path '{parsed.path}' not in whitelist for '{host}'"

    if is_private_ip(host):
        return False, "SSRF blocked: host resolves to private IP"

    return True, None


def make_request(url):
    """向白名单内的 URL 发请求, 返回 (status, headers, body) 或抛异常."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    })
    # 不跟随重定向
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # 不重定向

    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(req, timeout=TIMEOUT) as resp:
        body = resp.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("response too large")
        return resp.status, dict(resp.headers), body


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "space-proxy/1.0"

    def _send(self, status, content_type, body, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, obj):
        import json
        body = json.dumps(obj).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # 健康检查
        if parsed.path == "/space/api/health":
            self._json(200, {"ok": True, "service": "space-proxy", "version": "1.0"})
            return

        # 通用代理: /space/api/proxy?u=<url>
        if parsed.path == "/space/api/proxy":
            qs = urllib.parse.parse_qs(parsed.query)
            url_list = qs.get("u")
            if not url_list:
                self._json(400, {"error": "missing 'u' parameter"})
                return

            target = url_list[0]
            ok, err = validate_target(target)
            if not ok:
                self._json(403, {"error": err, "target": target})
                return

            # 先查缓存
            cached = cache_get(target)
            if cached:
                body, ct = cached
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=604800")
                self.send_header("X-Cache", "HIT")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
                return

            # 限速: 同一 host 最小间隔 2 秒, 避免 Wikimedia 429
            from urllib.parse import urlparse as _up
            rate_limit_wait(_up(target).hostname)

            # 429 自动重试 (Wikimedia 限速严格, 等待后重试一次)
            max_retries = 2
            status, headers, body = 0, {}, b""
            for attempt in range(max_retries):
                try:
                    status, headers, body = make_request(target)
                    break  # 成功, 跳出重试循环
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt < max_retries - 1:
                        # 429 Too Many Requests — 等待 5 秒后重试
                        time.sleep(5)
                        rate_limit_wait(_up(target).hostname)
                        continue
                    # 非 429 或最后一次重试 — 透传错误
                    body = e.read(MAX_BODY + 1) or b'{"error":"upstream error"}'
                    ct = e.headers.get("Content-Type", "application/json")
                    self._send(e.code, ct, body)
                    return
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    self._json(502, {"error": f"upstream failed: {e}"})
                    return

            # 透传白名单内的响应头
            extra = {}
            for k, v in headers.items():
                if k.lower() in PASSTHROUGH_HEADERS:
                    extra[k] = v
            ct = headers.get("Content-Type", "application/octet-stream")
            # 只缓存 2xx 响应 (不缓存错误、不缓存大文件)
            if 200 <= status < 300 and len(body) <= MAX_BODY:
                cache_put(target, body, ct)
                extra["X-Cache"] = "MISS"
                extra["Cache-Control"] = "public, max-age=604800"
            self._send(status, ct, body, extra)
            return

        # 未知路由
        self._json(404, {"error": "not found", "path": parsed.path})

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, fmt, *args):
        # 简化日志: IP "METHOD path" status
        sys.stderr.write(
            f"{self.client_address[0]} \"{self.command} {self.path}\" {getattr(self, '_status', '?')}\n"
        )


def main():
    parser = argparse.ArgumentParser(description="space proxy server")
    parser.add_argument("--host", default="0.0.0.0", help="bind host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="listen port (default 8080)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ProxyHandler)
    print(f"space-proxy listening on {args.host}:{args.port}")
    print(f"whitelisted hosts: {', '.join(sorted(ALLOWED_HOSTS))}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
