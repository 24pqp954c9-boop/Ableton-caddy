"""Tests for the Caddy server and app builder that need neither Live nor macOS."""
import http.client
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


caddy = load("caddy")
make_app = load("make_app")


class RefreshErrorMessage(unittest.TestCase):
    def test_timeout(self):
        self.assertIn("Timed out", caddy.refresh_error_message(TimeoutError()))

    def test_missing_uvx_inside_exception_group(self):
        group = BaseExceptionGroup("spawn", [FileNotFoundError("uvx")]) if sys.version_info >= (3, 11) else None
        if group is None:
            self.skipTest("ExceptionGroup needs Python 3.11+")
        self.assertIn("uvx", caddy.refresh_error_message(group))

    def test_generic(self):
        self.assertIn("Could not read Live", caddy.refresh_error_message(RuntimeError("boom")))


class ServerGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), caddy.CaddyHandler)
        cls.port = cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path, host=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("GET", path, skip_host=True)
        conn.putheader("Host", host or f"127.0.0.1:{self.port}")
        for key, value in (headers or {}).items():
            conn.putheader(key, value)
        conn.endheaders()
        response = conn.getresponse()
        body = response.read()
        conn.close()
        return response, body

    def test_index_served_with_launcher_fingerprint(self):
        response, body = self.get("/")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("X-Ableton-Caddy-Server"), "1")
        # make_app's launcher probes for exactly these markers.
        self.assertIn(b'id="refresh"', body)
        self.assertIn(b"<title>Ableton Caddy</title>", body)

    def test_foreign_host_rejected(self):
        # DNS-rebinding guard: only the exact loopback host:port is accepted.
        self.assertEqual(self.get("/", host="evil.example")[0].status, 403)
        self.assertEqual(self.get("/", host=f"localhost:{self.port}")[0].status, 403)

    def test_session_requires_custom_header(self):
        self.assertEqual(self.get("/session")[0].status, 403)

    def test_unknown_path(self):
        self.assertEqual(self.get("/etc/passwd")[0].status, 404)

    def test_session_failure_is_reported_not_raised(self):
        async def fail():
            raise FileNotFoundError("uvx")
        with mock.patch.object(caddy, "read_session", fail):
            response, body = self.get("/session", headers={"X-Ableton-Caddy": "1"})
        self.assertEqual(response.status, 503)
        self.assertIn(b"uvx", body)


class AppBuilder(unittest.TestCase):
    def test_plist_carries_version(self):
        self.assertIn(f"<string>{make_app.VERSION}</string>", make_app.plist())
        self.assertNotIn("{version}", make_app.plist())

    def test_launcher_finds_homebrew_uv(self):
        self.assertIn("/opt/homebrew/bin/uv", make_app.LAUNCHER)
        self.assertIn(f"PORT={make_app.PORT}", make_app.LAUNCHER)

    @unittest.skipUnless(shutil.which("sh"), "needs a POSIX shell")
    def test_launcher_is_valid_shell(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as script:
            script.write(make_app.LAUNCHER)
        try:
            subprocess.run(["sh", "-n", script.name], check=True)
        finally:
            Path(script.name).unlink()


if __name__ == "__main__":
    unittest.main()
