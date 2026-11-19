# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.29.1,<2"]
# ///
"""Run the read-only Ableton Caddy companion on loopback."""
import argparse
import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent


async def read_session():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = StdioServerParameters(command="uvx", args=["mcp-server-ableton-live@1.8.1"])
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool("get_session_snapshot", {})
            if result.isError:
                raise RuntimeError("The Ableton MCP server could not read the set.")
            blocks = [item.text for item in result.content if item.type == "text"]
            if len(blocks) != 1:
                raise ValueError("Expected a single Ableton snapshot.")
            data = json.loads(blocks[0])
            if not isinstance(data, dict) or not isinstance(data.get("tracks"), list):
                raise ValueError("The Ableton MCP snapshot has an unexpected format.")
            return data


class CaddyHandler(BaseHTTPRequestHandler):
    def send_content(self, status, content, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status, payload):
        self.send_content(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.send_error(403)
            return
        if self.path == "/":
            self.send_content(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if self.path != "/session":
            self.send_error(404)
            return
        if self.headers.get("X-Ableton-Caddy") != "1":
            self.send_error(403)
            return
        if not self.server.refresh_lock.acquire(blocking=False):
            self.send_json(409, {"error": "A session refresh is already running."})
            return
        try:
            session = asyncio.run(asyncio.wait_for(read_session(), timeout=45))
        except Exception as error:
            print(f"Live refresh failed: {error!r}", flush=True)
            self.send_json(503, {"error": "Could not read Live. Check that Live is open, AbletonMCP is active, and the server passes its doctor check. See the terminal for details."})
        else:
            self.send_json(200, {"demo": False, "session": session})
        finally:
            self.server.refresh_lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Use a specific local port.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), CaddyHandler) as server:
        server.refresh_lock = threading.Lock()
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Ableton Caddy: {url}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
