"""Loopback HTTP without DNS discovery or a public bind fallback."""
from http.server import ThreadingHTTPServer
from socketserver import TCPServer


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
