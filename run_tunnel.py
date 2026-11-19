"""
Cloudflare Tunnel & Local Server Orchestrator for ViralShortsEngine.
Launches local Streamlit Studio on port 8501 and exposes it via a high-speed,
un-throttled Cloudflare HTTPS Tunnel accessible from any device worldwide.
"""

import os
import sys
import time
import re
import signal
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_BIN = BASE_DIR / "cloudflared.exe"
PORT = 8501

def main():
    print("=" * 70)
    print("  🎬 ViralShortsEngine Pro Studio + Cloudflare Live Tunnel")
    print("=" * 70)

    if not CLOUDFLARED_BIN.exists():
        print(f"[-] ERROR: cloudflared.exe not found at {CLOUDFLARED_BIN}")
        print("    Please ensure cloudflared.exe is in the project root.")
        sys.exit(1)

    print(f"[*] Step 1/2: Starting Local Streamlit Engine on http://localhost:{PORT}...")
    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "ui.py",
        f"--server.port={PORT}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.serverAddress=localhost",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false"
    ]

    streamlit_proc = subprocess.Popen(
        streamlit_cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Give Streamlit 2 seconds to initialize
    time.sleep(2)

    print(f"[*] Step 2/2: Starting Cloudflare Tunnel...")
    cf_cmd = [
        str(CLOUDFLARED_BIN),
        "tunnel",
        "--url",
        f"http://127.0.0.1:{PORT}"
    ]

    cf_proc = subprocess.Popen(
        cf_cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    tunnel_url = None
    pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Read output to capture the generated trycloudflare URL
    start_time = time.time()
    while time.time() - start_time < 30:
        line = cf_proc.stdout.readline()
        if not line:
            if cf_proc.poll() is not None:
                break
            time.sleep(0.1)
            continue
        
        match = pattern.search(line)
        if match:
            tunnel_url = match.group(0)
            break

    if tunnel_url:
        # Save active tunnel URL to file for convenience
        try:
            (BASE_DIR / "workspace").mkdir(exist_ok=True)
            with open(BASE_DIR / "workspace" / "tunnel_url.txt", "w", encoding="utf-8") as f:
                f.write(tunnel_url.strip())
        except Exception:
            pass

        print("\n" + "=" * 70)
        print("  🚀 VIRAL SHORTS ENGINE IS LIVE WORLDWIDE!")
        print("=" * 70)
        print(f"  🌐 Public Cloudflare URL : {tunnel_url}")
        print(f"  💻 Local Computer URL    : http://localhost:{PORT}")
        print("=" * 70)
        print("  ✨ BENEFITS:")
        print("     • 100% of your computer's CPU & GPU (No cloud throttling!)")
        print("     • Full 1080x1920 MP4 rendering speed with NVENC / multi-core")
        print("     • Secure HTTPS accessible from phone, tablet, or anywhere")
        print("=" * 70)
        print("  Press Ctrl+C at any time in this window to stop the server.\n")
    else:
        print("[-] Could not automatically capture Cloudflare URL. Check output below:")

    def cleanup(sig=None, frame=None):
        print("\n[*] Stopping Cloudflare Tunnel and Streamlit server...")
        try:
            cf_proc.terminate()
            cf_proc.wait(timeout=3)
        except Exception:
            try:
                cf_proc.kill()
            except Exception:
                pass

        try:
            streamlit_proc.terminate()
            streamlit_proc.wait(timeout=3)
        except Exception:
            try:
                streamlit_proc.kill()
            except Exception:
                pass
        print("[+] All services stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            time.sleep(1)
            if streamlit_proc.poll() is not None or cf_proc.poll() is not None:
                print("[-] One of the processes exited unexpectedly.")
                cleanup()
                break
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
