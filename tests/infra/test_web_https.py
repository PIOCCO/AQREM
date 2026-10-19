"""Exercise the generated web proxy against real local HTTP/TLS upstreams.

Requires backend dependencies, nginx, and sh. Set AQREM_TEST_NGINX
and AQREM_TEST_SHELL when they are not on PATH. No Azure or database is used.
"""

import contextlib
import http.client
import http.server
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
NGINX = os.environ.get("AQREM_TEST_NGINX") or shutil.which("nginx")
SHELL = os.environ.get("AQREM_TEST_SHELL") or shutil.which("sh")
HIDDEN = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

REDIRECT_APP = FastAPI()
REDIRECT_APP.add_api_route("/api/v1/projects", lambda: {"ok": True})


@REDIRECT_APP.get("/api/redirect-https")
def internal_https_redirect(request: Request):
    return RedirectResponse(f"https://{request.headers['host']}/api/v1/projects?from=redirect")


@REDIRECT_APP.get("/api/redirect-external")
def external_https_redirect():
    return RedirectResponse("https://login.example.test/callback")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Upstream(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith(("/api/v1/projects/", "/api/redirect-")):
            # The internal ingress terminates TLS before FastAPI's HTTP listener.
            with TestClient(REDIRECT_APP) as client:
                response = client.get(self.path, headers=dict(self.headers), follow_redirects=False)
            self.send_response(response.status_code)
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(response.content)
            return
        body = json.dumps({"path": self.path, "host": self.headers.get("Host"),
                           "public_host": self.headers.get("X-Forwarded-Host"),
                           "proto": self.headers.get("X-Forwarded-Proto")}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@unittest.skipUnless(NGINX and SHELL, "nginx and sh are required for proxy integration tests")
class WebHttpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="aqrem-https-")
        cls.folder = Path(cls.temp.name)
        now = datetime.now(timezone.utc)
        cls.ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AQREM local test CA")])
        cls.ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                  .public_key(cls.ca_key.public_key()).serial_number(x509.random_serial_number())
                  .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
                  .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                  .sign(cls.ca_key, hashes.SHA256()))
        cls.ca_path = cls.folder / "test-ca.crt"
        cls.ca_path.write_bytes(cls.ca.public_bytes(serialization.Encoding.PEM))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def certificate(self, hostname, *, trusted=True, expired=False):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
        try:
            san = x509.IPAddress(ipaddress.ip_address(hostname))
        except ValueError:
            san = x509.DNSName(hostname)
        cert = (x509.CertificateBuilder().subject_name(name)
                .issuer_name(self.ca.subject if trusted else name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=2))
                .not_valid_after(now + timedelta(days=-1 if expired else 1))
                .add_extension(x509.SubjectAlternativeName([san]), critical=False)
                .sign(self.ca_key if trusted else key, hashes.SHA256()))
        stem = self.folder / str(cert.serial_number)
        cert_path, key_path = stem.with_suffix(".crt"), stem.with_suffix(".key")
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        return cert_path, key_path

    @contextlib.contextmanager
    def upstream(self, *, tls=True, hostname="localhost", trusted=True, expired=False):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        self.sni_names = []
        if tls:
            cert, key = self.certificate(hostname, trusted=trusted, expired=expired)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert, key)
            ctx.set_servername_callback(lambda _sock, name, _ctx: self.sni_names.append(name))
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"{'https' if tls else 'http'}://localhost:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    @contextlib.contextmanager
    def proxy(self, upstream):
        with tempfile.TemporaryDirectory(prefix="proxy-", dir=self.folder) as raw:
            folder = Path(raw)
            (folder / "logs").mkdir()
            (folder / "temp").mkdir()
            conf_path = folder / "api.conf"
            script = (ROOT / "infra/docker/web-api-proxy.sh").read_text()
            # Relocate only container filesystem paths, leaving proxy directives unchanged.
            script = script.replace("/etc/nginx/api-proxy/api.conf", f'"{conf_path.as_posix()}"')
            script_path = folder / "generate.sh"
            script_path.write_text(script, newline="\n")
            env = dict(os.environ, API_UPSTREAM=upstream)
            subprocess.run([SHELL, str(script_path)], check=True, env=env, **HIDDEN)
            proxy_conf = conf_path.read_text().replace("/etc/ssl/certs/ca-certificates.crt",
                                                       self.ca_path.as_posix())
            conf_path.write_text(proxy_conf)
            port = free_port()
            web = (ROOT / "infra/docker/nginx-web.conf").read_text()
            # Model the public TLS terminator locally; production uses Container Apps ingress.
            edge_cert, edge_key = self.certificate("localhost")
            web = web.replace("listen 80;", f"listen 127.0.0.1:{port} ssl;\n"
                              f"ssl_certificate {edge_cert.as_posix()};\n"
                              f"ssl_certificate_key {edge_key.as_posix()};")
            web = web.replace("/etc/nginx/api-proxy/*.conf", conf_path.as_posix())
            config = folder / "nginx.conf"
            config.write_text('worker_processes 1;\nevents { worker_connections 64; }\nhttp {\n'
                              + web + '\n}\n')
            command = [NGINX, "-p", folder.as_posix() + "/", "-c", config.as_posix()]
            check = subprocess.run(command + ["-t"], capture_output=True, text=True, **HIDDEN)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            proc = subprocess.Popen(command + ["-g", "daemon off;"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **HIDDEN)
            try:
                deadline = time.monotonic() + 8
                while True:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        if proc.poll() is not None or time.monotonic() > deadline:
                            self.fail((folder / "logs/error.log").read_text())
                        time.sleep(0.05)
                yield port
            finally:
                subprocess.run(command + ["-s", "quit"], capture_output=True, **HIDDEN)
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

    def request(self, port, path, *, include_headers=False):
        context = ssl.create_default_context(cafile=str(self.ca_path))
        conn = http.client.HTTPSConnection("localhost", port, timeout=5, context=context)
        try:
            conn.request("GET", path, headers={"Host": "public.example.test",
                         "X-Forwarded-Host": "spoofed.example.test", "X-Forwarded-Proto": "https"})
            response = conn.getresponse()
            body = response.read()
            if include_headers:
                return response.status, body, {name.lower(): value for name, value in response.getheaders()}
            return response.status, body
        finally:
            conn.close()

    def test_trusted_https_preserves_public_origin_and_path(self):
        with self.upstream() as upstream, self.proxy(upstream) as port:
            status, body = self.request(port, "/api/v1/version?test=1")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertEqual(data["path"], "/api/v1/version?test=1")
            self.assertEqual(data["host"], upstream.split("://")[1])
            self.assertEqual(data["public_host"], "public.example.test")
            self.assertEqual(data["proto"], "https")
            self.assertIn("localhost", self.sni_names)

    def test_health_uses_verified_https(self):
        with self.upstream() as upstream, self.proxy(upstream) as port:
            status, body = self.request(port, "/health")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["path"], "/health")
            self.assertIn("localhost", self.sni_names)

    def test_untrusted_certificate_is_rejected(self):
        with self.upstream(trusted=False) as upstream, self.proxy(upstream) as port:
            self.assertEqual(self.request(port, "/api/v1/version")[0], 502)
            self.assertEqual(self.request(port, "/health")[0], 502)

    def test_wrong_certificate_hostname_is_rejected(self):
        with self.upstream(hostname="wrong.example.test") as upstream, self.proxy(upstream) as port:
            self.assertEqual(self.request(port, "/api/v1/version")[0], 502)
            self.assertEqual(self.request(port, "/health")[0], 502)

    def test_expired_certificate_is_rejected(self):
        with self.upstream(expired=True) as upstream, self.proxy(upstream) as port:
            self.assertEqual(self.request(port, "/api/v1/version")[0], 502)
            self.assertEqual(self.request(port, "/health")[0], 502)

    def test_explicit_local_http_upstream_still_works(self):
        with self.upstream(tls=False) as upstream, self.proxy(upstream) as port:
            self.assertEqual(self.request(port, "/api/v1/version")[0], 200)
            self.assertEqual(self.request(port, "/health")[0], 200)

    def test_fastapi_slash_redirect_preserves_public_https_origin(self):
        with self.upstream() as upstream, self.proxy(upstream) as port:
            status, _, headers = self.request(port, "/api/v1/projects/?from=redirect", include_headers=True)
            self.assertEqual(status, 307)
            self.assertEqual(headers["location"], "https://public.example.test/api/v1/projects?from=redirect")

    def test_internal_https_redirect_preserves_public_origin(self):
        with self.upstream() as upstream, self.proxy(upstream) as port:
            status, _, headers = self.request(port, "/api/redirect-https", include_headers=True)
            self.assertEqual(status, 307)
            self.assertEqual(headers["location"], "https://public.example.test/api/v1/projects?from=redirect")

    def test_external_https_redirect_is_preserved(self):
        with self.upstream() as upstream, self.proxy(upstream) as port:
            status, _, headers = self.request(port, "/api/redirect-external", include_headers=True)
            self.assertEqual(status, 307)
            self.assertEqual(headers["location"], "https://login.example.test/callback")


if __name__ == "__main__":
    unittest.main()
