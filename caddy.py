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
import time
import webbrowser

ROOT = Path(__file__).resolve().parent

REFRESH_SOFT_TIMEOUT = 45  # seconds the uvx read itself may take
REFRESH_HARD_TIMEOUT = 60  # seconds the request waits before calling a worker stuck

# One-refresh-at-a-time slot (used by run_refresh/_refresh_worker): a daemon thread
# reports here, and a generation counter plus started-at timestamp let a hung worker
# be orphaned without any lock ever being held indefinitely.
refresh_state = {"lock": threading.Lock(), "generation": 0, "started_at": None,
                 "result": None, "done": None}


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


def refresh_error_message(error):
    """Explain a failed refresh by its likely cause."""
    cause = error
    for _ in range(8):  # anyio may wrap the real spawn error in an ExceptionGroup
        nested = getattr(cause, "exceptions", None)
        if not nested:
            break
        cause = nested[0]
    timeouts = (TimeoutError, asyncio.TimeoutError)
    if isinstance(error, timeouts) or isinstance(cause, timeouts):
        return "Timed out reading Live — the first run downloads the bridge; try Refresh again."
    if isinstance(cause, FileNotFoundError):
        return "The 'uvx' command was not found. Install uv."
    return "Could not read Live. Check that Live is open, AbletonMCP is active, and the server passes its doctor check. See the terminal for details."


# The read runs in a daemon thread signalling the shared slot so a hang in
# asyncio.run's cancellation cleanup can never hold a lock across requests.
def _refresh_worker(generation):
    result = (500, {"error": "The refresh worker stopped unexpectedly. Try Refresh again."})
    try:
        session = asyncio.run(asyncio.wait_for(read_session(), timeout=REFRESH_SOFT_TIMEOUT))
        result = (200, {"demo": False, "session": session})
    except Exception as error:
        print(f"Live refresh failed: {error!r}", flush=True)
        result = (503, {"error": refresh_error_message(error)})
    finally:
        with refresh_state["lock"]:
            if refresh_state["generation"] == generation:  # skip writes after being orphaned
                refresh_state["started_at"] = None
                refresh_state["result"] = result
                refresh_state["done"].set()


class CaddyHandler(BaseHTTPRequestHandler):
    def send_content(self, status, content, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Ableton-Caddy-Server", "1")  # fingerprint for the launcher probe
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
        status, payload = self.run_refresh()
        # The response is sent after the refresh slot is freed, so a client
        # disconnect during the send cannot strand the slot or double-send.
        self.send_json(status, payload)

    def run_refresh(self):
        now = time.monotonic()
        with refresh_state["lock"]:
            started = refresh_state["started_at"]
            if started is not None and now - started < REFRESH_HARD_TIMEOUT:
                return 409, {"error": "A session refresh is already running."}
            if started is not None:
                print("Orphaning the stuck refresh worker.", flush=True)
            refresh_state["generation"] += 1
            generation = refresh_state["generation"]
            refresh_state["started_at"] = now
            refresh_state["result"] = None
            done = refresh_state["done"] = threading.Event()
        threading.Thread(target=_refresh_worker, args=(generation,), daemon=True).start()
        done.wait(REFRESH_HARD_TIMEOUT)
        with refresh_state["lock"]:
            if refresh_state["generation"] != generation:
                return 504, {"error": "Refresh is stuck (often the first-run download); try again or restart Caddy."}
            if refresh_state["result"] is not None:  # finished right at the timeout edge
                return refresh_state["result"]
            # Worker outlived the hard timeout: invalidate its slot writes and free
            # the slot so the next Refresh starts immediately, never a permanent 409.
            refresh_state["generation"] += 1
            refresh_state["started_at"] = None
        return 504, {"error": "Refresh is stuck (often the first-run download); try again or restart Caddy."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Use a specific local port.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), CaddyHandler) as server:
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
