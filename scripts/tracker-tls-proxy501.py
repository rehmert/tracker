"""Release 501: loopback-only TLS reverse proxy for disposable browser qualification.

This is a test fixture, not a production reverse proxy. TLS terminates here
and requests are forwarded only to the separately launched localhost candidate.
No network discovery, credentials, or installed Tracker data are used.
"""
import argparse
import http.client
import http.server
import re
import ssl
import sys

HOP = frozenset({
    "connection", "proxy-connection", "keep-alive", "transfer-encoding",
    "upgrade", "te", "trailer", "proxy-authenticate", "proxy-authorization",
})


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    backend_port: int
    qa_rewrite_browser_host: bool = False

    def _rewrite_browser_host(self):
        """Simulate production TLS Host rewriting on guarded browser writes."""
        if not self.qa_rewrite_browser_host or self.command not in (
            "POST", "DELETE",
        ):
            return False
        path = self.path.split("?", 1)[0]
        if path in ("/vitals", "/labs", "/labs/import-csv", "/coas/new"):
            return True
        return any(re.fullmatch(pattern, path) is not None for pattern in (
            r"/vitals/[1-9][0-9]{0,9}(?:/edit)?",
            r"/labs/[1-9][0-9]{0,9}/(?:edit|delete|import-csv)",
            r"/coas/[1-9][0-9]{0,9}/(?:edit|verify|delete)",
        ))

    def proxy(self):
        try:
            length = self.headers.get("Content-Length")
            if length is None and self.command in ("POST", "PUT", "PATCH"):
                self.send_error(411, "Content-Length required")
                return
            if length is not None and (
                not length.isascii() or not length.isdecimal()
                or int(length) > 4 * 1024 * 1024
            ):
                self.send_error(413, "Invalid body length")
                return
            body = self.rfile.read(int(length)) if length else None
            conn = http.client.HTTPConnection(
                "127.0.0.1", self.backend_port, timeout=15
            )
            try:
                conn.putrequest(
                    self.command, self.path,
                    skip_host=True, skip_accept_encoding=True,
                )
                for key, value in self.headers.items():
                    if key.lower() not in HOP and key.lower() not in (
                        "content-length", "x-forwarded-proto",
                        "x-forwarded-host", "x-forwarded-for",
                    ):
                        if key.lower() == "host" and self._rewrite_browser_host():
                            # Simulate a real LAN TLS proxy that forwards
                            # the browser's public Origin unmodified while
                            # changing Host to the backend listener.
                            conn.putheader(
                                "Host", f"127.0.0.1:{self.backend_port}"
                            )
                        else:
                            conn.putheader(key, value)
                # TLS is terminated here; never trust caller-supplied proxy
                # metadata. Uvicorn trusts this loopback peer for scheme.
                conn.putheader("X-Forwarded-Proto", "https")
                conn.putheader("Connection", "close")
                if body is not None:
                    conn.putheader("Content-Length", str(len(body)))
                conn.endheaders(body)
                response = conn.getresponse()
                payload = response.read()
                self.send_response_only(response.status, response.reason)
                for key, value in response.getheaders():
                    if key.lower() not in HOP and key.lower() != "content-length":
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Connection", "close")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)
            finally:
                conn.close()
        except (OSError, http.client.HTTPException, ValueError) as exc:
            print(f"TLS_QA_PROXY_ERROR={type(exc).__name__}", file=sys.stderr)
            if not self.wfile.closed:
                try:
                    self.send_error(502, "Disposable candidate unavailable")
                except OSError:
                    pass
        finally:
            self.close_connection = True

    do_GET = proxy
    do_POST = proxy
    do_HEAD = proxy
    do_PUT = proxy
    do_PATCH = proxy
    do_DELETE = proxy

    def log_message(self, format, *args):
        # Never log request paths, tokens, cookies, or form payloads.
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument(
        "--qa-rewrite-browser-host", action="store_true",
        help="Test-only: rewrite Host on Vitals, Labs and COA writes",
    )
    args = parser.parse_args()
    for port in (args.listen_port, args.backend_port):
        if not 1024 <= port <= 65535:
            parser.error("Only unprivileged ports are allowed")

    class BoundHandler(Handler):
        backend_port = args.backend_port
        qa_rewrite_browser_host = args.qa_rewrite_browser_host

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", args.listen_port), BoundHandler
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    if args.qa_rewrite_browser_host:
        print("QA_WRITE_PROXY_HOST_REWRITE=ENABLED", flush=True)
    print("TLS_QA_PROXY_READY=YES", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
