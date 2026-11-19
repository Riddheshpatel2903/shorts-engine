"""
Browser Login Helper for Playwright Automated Publishing.
Launches a visible Chromium browser window so the user can log into
YouTube Studio or Instagram once. Preserves persistent user session cookies.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = BASE_DIR / "workspace" / "browser_profile"


def launch_login(platform: str):
    platform = platform.lower().strip()
    profile_dir = PROFILES_DIR / platform
    profile_dir.mkdir(parents=True, exist_ok=True)

    target_url = "https://studio.youtube.com/" if platform == "youtube" else "https://www.instagram.com/"

    print("=" * 70)
    print(f"  🌐 Launching visible login browser for: {platform.upper()}")
    print("=" * 70)
    print(f"  1. Log into your {platform.capitalize()} account in the opened window.")
    print("  2. Complete any 2FA or security prompt.")
    print("  3. Once you see your dashboard / feed, simply CLOSE the browser window.")
    print(f"  Your session will be saved permanently to: {profile_dir}")
    print("=" * 70)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        page.goto(target_url)

        # Wait until user closes the browser context
        try:
            while context.pages:
                time.sleep(1)
        except Exception:
            pass

        print(f"[+] Login session saved for {platform.capitalize()}. You may return to the Studio!")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "youtube"
    launch_login(target)
