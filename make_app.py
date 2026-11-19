# /// script
# requires-python = ">=3.10"
# ///
"""Build AbletonCaddy.app from this folder: bundle, launcher, icon."""
import argparse, struct, subprocess, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "AbletonCaddy.app"
PORT = 8743
VERSION = "0.1.3"

LAUNCHER = f"""#!/bin/sh
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT={PORT}
URL="http://127.0.0.1:$PORT/"
# Finder-launched apps get a minimal PATH (no Homebrew), so probe the usual
# uv install locations, matching uvx_command() in caddy.py.
UV="$(command -v uv)"
if [ -z "$UV" ]; then
  for CANDIDATE in "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv "$HOME/.cargo/bin/uv"; do
    if [ -x "$CANDIDATE" ]; then UV="$CANDIDATE"; break; fi
  done
fi
if [ -z "$UV" ]; then
  /usr/bin/osascript -e 'display alert "Ableton Caddy needs uv" message "Install uv from docs.astral.sh/uv, then open Ableton Caddy again."' >/dev/null 2>&1
  echo "Ableton Caddy: uv was not found. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi
# Let caddy.py find the uvx that sits next to uv.
PATH="$(dirname "$UV"):$PATH"; export PATH
# Port-squat guard: only open the page if it carries Caddy's own fingerprint markers
# from index.html. Port answering without them is someone else's server: refuse.
PAGE="$(/usr/bin/curl -s --max-time 1 "$URL")"
if [ -n "$PAGE" ]; then
  if printf '%s' "$PAGE" | grep -q 'id="refresh"' && printf '%s' "$PAGE" | grep -q '<title>Ableton Caddy</title>'; then
    /usr/bin/open "$URL"; exit 0
  fi
  echo "Ableton Caddy: port $PORT is already serving a different page; not opening it. Free the port and relaunch." >&2
  exit 1
fi
exec "$UV" run "$APP_DIR/Resources/caddy.py" --port $PORT
"""

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Ableton Caddy</string>
<key>CFBundleDisplayName</key><string>Ableton Caddy</string>
<key>CFBundleIdentifier</key><string>com.m8.ableton-caddy</string>
<key>CFBundleExecutable</key><string>AbletonCaddy</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>{version}</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSMinimumSystemVersion</key><string>12.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>CFBundleIconFile</key><string>AppIcon</string>
</dict></plist>
"""

def png(path, size):
    # Dark panel, rounded-corner feel is free from macOS; accent-green EQ bars + a C.
    bg = (23, 27, 26, 255); fg = (212, 246, 139, 255)
    bars = [(0.18, 0.30), (0.34, 0.55), (0.50, 0.40), (0.66, 0.68), (0.82, 0.34)]
    def pix(x, y):
        u, v = x / size, y / size
        for cx, h in bars:
            if abs(u - cx) < 0.05 / 1.0 * 0.55 and 0.78 - h < v < 0.78:
                return fg
        if 0.10 < u < 0.30 and 0.10 < v < 0.26:  # small "caddy" dot mark
            d = (u - 0.20) ** 2 + (v - 0.18) ** 2
            if d < 0.0064: return fg
        return bg
    raw = b"".join(b"\x00" + b"".join(struct.pack("4B", *pix(x, y)) for x in range(size)) for y in range(size))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

def plist():
    return PLIST.replace("{version}", VERSION)


def zip_app():
    """Zip with the .app folder at the top so unzipping yields a launchable app."""
    archive = ROOT / f"AbletonCaddy-{VERSION}.zip"
    archive.unlink(missing_ok=True)
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(APP), str(archive)], check=True)
    print(f"Zipped {archive}")


def main():
    import shutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", action="store_true", help="Also write AbletonCaddy-<version>.zip.")
    args = parser.parse_args()
    if sys.platform != "darwin":
        sys.exit("make_app.py builds a macOS app and needs macOS (iconutil, ditto).")
    shutil.rmtree(APP, ignore_errors=True)
    macos, res = APP / "Contents" / "MacOS", APP / "Contents" / "Resources"
    macos.mkdir(parents=True); res.mkdir(parents=True)
    (APP / "Contents" / "Info.plist").write_text(plist())
    exe = macos / "AbletonCaddy"
    exe.write_text(LAUNCHER); exe.chmod(0o755)
    shutil.copy2(ROOT / "caddy.py", res / "caddy.py")
    shutil.copy2(ROOT / "index.html", res / "index.html")
    shutil.copy2(ROOT / "README.md", res / "README.md")
    iconset = ROOT / "AppIcon.iconset"; shutil.rmtree(iconset, ignore_errors=True); iconset.mkdir()
    for base, s in [(16, 16), (16, 32), (32, 32), (32, 64), (128, 128), (128, 256), (256, 256), (256, 512), (512, 512), (512, 1024)]:
        name = f"icon_{base}x{base}" + ("@2x" if s != base else "") + ".png"
        png(iconset / name, s)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(res / "AppIcon.icns")], check=True)
    shutil.rmtree(iconset)
    print(f"Built {APP}")
    if args.zip:
        zip_app()

if __name__ == "__main__":
    main()
