"""Loopback HTTP without DNS discovery or a public bind fallback."""
from http.server import ThreadingHTTPServer
from socketserver import TCPServer
from urllib.parse import urlsplit


class LoopbackHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        if self.server_address[0] != "127.0.0.1":
            raise ValueError("Local services require the literal IPv4 loopback address")
        # HTTPServer.server_bind calls getfqdn, which can block on reverse DNS
        # even for 127.0.0.1. Local capabilities need no network name discovery;
        # blocking here can consume a worker's lease before its first request.
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


def is_local_browser_url(url: str, origin: str) -> bool:
    if url.startswith(("about:", "data:", "blob:")):
        return True
    try:
        target, allowed = urlsplit(url), urlsplit(origin)
        return (target.scheme in {"http", "https"} and target.username is None and target.password is None
                and (target.scheme, target.hostname, target.port) == (allowed.scheme, allowed.hostname, allowed.port))
    except ValueError:
        return False
