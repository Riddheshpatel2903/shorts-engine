"""
Browser Login Helper for Playwright Automated Publishing.
Launches a genuine Google Chrome/Edge browser window with anti-bot stealth
so the user can log into YouTube Studio or Instagram cleanly without triggering
automation bot-flags or endless CAPTCHAs. Preserves persistent user session cookies.
"""

import sys
import time
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = BASE_DIR / "workspace" / "browser_profile"


def get_installed_browser_channel() -> Optional[str]:
    """Finds installed Google Chrome or Microsoft Edge on Windows."""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    for p in chrome_paths:
        if Path(p).exists():
            return "chrome"

    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    for p in edge_paths:
        if Path(p).exists():
            return "msedge"

    return None


def launch_login(platform: str):
    platform = platform.lower().strip()
    profile_dir = PROFILES_DIR / platform
    profile_dir.mkdir(parents=True, exist_ok=True)

    target_url = "https://studio.youtube.com/" if platform == "youtube" else "https://www.instagram.com/"
    channel = get_installed_browser_channel()

    print("=" * 75)
    print(f"  🌐 Launching Genuine Browser Login for: {platform.upper()}")
    print("=" * 75)
    print(f"  Browser Engine: {'Google Chrome' if channel == 'chrome' else ('Microsoft Edge' if channel == 'msedge' else 'Chromium')}")
    print(f"  Anti-Bot Stealth: ACTIVE (Automation flags removed to bypass bot detection)")
    print("=" * 75)
    print(f"  1. Log into your {platform.capitalize()} account in the opened window.")
    print("  2. If Instagram or Google prompts for a 2FA code or security check, enter it.")
    print("  3. Once you see your feed or studio dashboard, close the window (or it will auto-detect).")
    print(f"  Session storage: {profile_dir}")
    print("=" * 75)

    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "viewport": None,
        "ignore_default_args": ["--enable-automation"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--start-maximized",
            "--disable-features=IsolateOrigins,site-per-process",
            "--lang=en-US,en"
        ],
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }

    if channel:
        launch_kwargs["channel"] = channel

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(**launch_kwargs)

        # Inject stealth scripts into all new pages
        context.add_init_script("""
            // Hide navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // Overwrite plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            // Overwrite languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            // Realistic WebGL vendor
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Google Inc. (NVIDIA)';
                if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX, OpenGL 4.5)';
                return getParameter.apply(this, arguments);
            };
        """)

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(target_url)

        login_detected = False

        # Monitor login state while user interacts with the window
        try:
            while context.pages:
                time.sleep(1.5)
                cookies = context.cookies()
                cookie_names = {c.get("name") for c in cookies}

                if platform == "instagram" and "sessionid" in cookie_names and not login_detected:
                    login_detected = True
                    print("\n" + "*" * 60)
                    print("  🎉 INSTAGRAM LOGIN CONFIRMED! Session cookies captured.")
                    print("  You can now close the browser window or return to the Studio.")
                    print("*" * 60 + "\n")

                elif platform == "youtube" and ("LOGIN_INFO" in cookie_names or "SAPISID" in cookie_names) and not login_detected:
                    login_detected = True
                    print("\n" + "*" * 60)
                    print("  🎉 YOUTUBE STUDIO LOGIN CONFIRMED! Session cookies captured.")
                    print("  You can now close the browser window or return to the Studio.")
                    print("*" * 60 + "\n")

        except Exception:
            pass

        print(f"\n[+] Login session saved permanently for {platform.capitalize()}. You may return to the Studio!")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "youtube"
    launch_login(target)
