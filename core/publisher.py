"""
Social Media Browser-Automated Publishing Engine for YouTube Shorts and Instagram Reels.
Uses Playwright with persistent user profiles:
- Zero Google Cloud Console / Meta Developer Setup
- Zero API keys or OAuth redirect URIs
- Log in once in a standard browser window; session cookies persist indefinitely
- Automatic headless video uploading with title, description, and hashtags
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from config import WORKSPACE_DIR
from core.cleanup_profiles import release_profile_lock, release_all_locks

logger = logging.getLogger("ViralShortsEngine.Publisher")

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = Path(WORKSPACE_DIR) / "browser_profile"
SETTINGS_FILE = Path(WORKSPACE_DIR) / "social_settings.json"

STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Google Inc. (NVIDIA)';
        if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX, OpenGL 4.5)';
        return getParameter.apply(this, arguments);
    };
"""


def get_installed_browser_channel() -> Optional[str]:
    """Finds installed Google Chrome or Microsoft Edge on Windows."""
    for p in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]:
        if Path(p).exists():
            return "chrome"

    for p in [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]:
        if Path(p).exists():
            return "msedge"

    return None


class PlaywrightPublisher:
    """Automates publishing to YouTube Shorts and Instagram Reels via persistent browser sessions."""

    def __init__(self):
        self.profiles_dir = PROFILES_DIR
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = SETTINGS_FILE
        self._load_settings()

    def _load_settings(self):
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            except Exception:
                self.settings = self._default_settings()
        else:
            self.settings = self._default_settings()
            self._save_settings()

    def _default_settings(self) -> Dict[str, Any]:
        return {
            "youtube_privacy": "public",  # public, unlisted, private
            "auto_publish_on_render": True
        }

    def _save_settings(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save social settings: {e}")

    def update_settings(self, **kwargs):
        self.settings.update(kwargs)
        self._save_settings()

    def check_status(self) -> Dict[str, Any]:
        """Checks if login profiles have been initialized for YouTube and Instagram."""
        yt_dir = self.profiles_dir / "youtube"
        ig_dir = self.profiles_dir / "instagram"

        # Check for profile cookies/Default folder
        yt_ready = yt_dir.exists() and any(yt_dir.iterdir())
        ig_ready = ig_dir.exists() and any(ig_dir.iterdir())

        return {
            "youtube_connected": yt_ready,
            "youtube_privacy": self.settings.get("youtube_privacy", "public"),
            "instagram_connected": ig_ready,
            "auto_publish": self.settings.get("auto_publish_on_render", True)
        }

    # Alias for compatibility
    get_status = check_status

    def unlock_profiles(self):
        """Releases any lingering profile locks and kills zombie browser sessions."""
        release_all_locks()

    @property
    def creds(self) -> Dict[str, Any]:
        return {
            "auto_publish_on_render": self.settings.get("auto_publish_on_render", True),
            "youtube": {"privacy": self.settings.get("youtube_privacy", "public")},
            "instagram": {}
        }

    def auto_publish_if_enabled(self, video_path: str, social_copy: Dict[str, Any]) -> Dict[str, Any]:
        """Uploads automatically if auto_publish_on_render is enabled and profiles are active."""
        if not self.settings.get("auto_publish_on_render", True):
            return {"status": "skipped", "message": "Auto-publish disabled."}

        results = {}
        status = self.check_status()
        yt_done = False
        ig_done = False

        caption_text = social_copy.get("instagram_caption") or social_copy.get("caption", "")
        hashtags_text = social_copy.get("hashtags", "")

        if status.get("youtube_connected"):
            try:
                results["youtube"] = self.publish_to_youtube(
                    video_path=video_path,
                    title=social_copy.get("title", "Viral Short #shorts"),
                    description=caption_text,
                    tags=hashtags_text
                )
                yt_done = True
            except Exception as e:
                results["youtube"] = {"success": False, "error": str(e)}

        if status.get("instagram_connected"):
            try:
                ig_full_cap = f"{caption_text}\n\n{hashtags_text}".strip()
                results["instagram"] = self.publish_to_instagram(
                    video_url_or_path=video_path,
                    caption=ig_full_cap
                )
                ig_done = True
            except Exception as e:
                results["instagram"] = {"success": False, "error": str(e)}

        if not status.get("youtube_connected") and not status.get("instagram_connected"):
            return {
                "status": "not_logged_in",
                "message": "Auto-publish is enabled, but neither YouTube nor Instagram account is connected. Log in via sidebar to auto-publish."
            }

        return results

    def publish_short(
        self,
        video_path: str,
        platform: str,
        title: str = "",
        caption: str = "",
        tags: str = ""
    ) -> Dict[str, Any]:
        """Convenience method to publish to a specific platform."""
        platform = platform.lower().strip()
        if platform in ["youtube", "yt"]:
            return self.publish_to_youtube(
                video_path=video_path,
                title=title or "Viral Short #shorts",
                description=caption,
                tags=tags
            )
        elif platform in ["instagram", "ig", "reels"]:
            full_cap = f"{caption}\n\n{tags}".strip() if tags else caption
            return self.publish_to_instagram(
                video_url_or_path=video_path,
                caption=full_cap
            )
        else:
            return {"success": False, "error": f"Unknown platform: {platform}"}

    def open_login_browser(self, platform: str) -> Dict[str, Any]:
        """Spawns a visible browser window so user can sign in on their screen."""
        platform = platform.lower().strip()
        script_path = BASE_DIR / "core" / "browser_login.py"

        try:
            cmd = [sys.executable, str(script_path), platform]
            subprocess.Popen(cmd, cwd=str(BASE_DIR))
            return {
                "success": True,
                "message": f"Browser opened for {platform.capitalize()}! Sign in, then close the window when done."
            }
        except Exception as e:
            logger.error(f"Could not launch login browser: {e}")
            return {"success": False, "error": str(e)}

    def publish_to_youtube(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: str = "",
        privacy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads an MP4 video directly to YouTube Studio as a 9:16 Short using Playwright.
        """
        from playwright.sync_api import sync_playwright

        vid_file = Path(video_path).resolve()
        if not vid_file.exists():
            return {"success": False, "error": f"Video file not found: {video_path}"}

        upload_privacy = privacy or self.settings.get("youtube_privacy", "public")
        profile_dir = self.profiles_dir / "youtube"

        if not (profile_dir.exists() and any(profile_dir.iterdir())):
            return {
                "success": False,
                "error": "YouTube account not logged in. Click 'Open YouTube Login Window' first."
            }

        # Ensure #shorts is in the title
        clean_title = title.strip()
        if "#shorts" not in clean_title.lower():
            clean_title = f"{clean_title[:80]} #shorts"

        full_desc = f"{description.strip()}\n\n{tags.strip()}\n\n#shorts #viral #gaming".strip()

        # Ensure profile locks from lingering sessions are released cleanly
        try:
            release_profile_lock("youtube", self.profiles_dir)
            import time
            time.sleep(0.5)
        except Exception as e:
            logger.debug(f"Profile lock release note: {e}")

        logger.info(f"Starting automated YouTube upload for: {vid_file.name}")

        try:
            channel = get_installed_browser_channel()
            launch_kwargs = {
                "user_data_dir": str(profile_dir),
                "headless": False,  # Visible browser avoids Google bot blocks and headless crash
                "viewport": {"width": 1280, "height": 800},
                "ignore_default_args": ["--enable-automation"],
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars"
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
                context.add_init_script(STEALTH_SCRIPT)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://studio.youtube.com", timeout=60000)
                page.wait_for_load_state("networkidle")

                # Verify if logged in
                if "accounts.google.com" in page.url or "signin" in page.url:
                    context.close()
                    return {
                        "success": False,
                        "error": "Session expired or not logged in. Please click 'Open YouTube Login Window' to sign in."
                    }

                # Click Create / Upload button
                try:
                    page.locator("#create-icon, [aria-label='Create'], button:has-text('Create')").first.click(timeout=10000)
                    page.locator("#text-item-0, tp-yt-paper-item:has-text('Upload videos')").first.click(timeout=10000)
                except Exception:
                    page.goto("https://studio.youtube.com/channel/videos/upload?d=ud", timeout=30000)

                # Upload File
                file_input = page.locator("input[type='file']")
                file_input.wait_for(state="attached", timeout=15000)
                file_input.set_input_files(str(vid_file))
                logger.info("File attached to YouTube upload dialog.")

                # Wait for Details step to load
                page.wait_for_selector("#textbox", timeout=30000)
                time_sleep = page.wait_for_timeout

                # 1. Fill Title
                title_box = page.locator("#textbox").first
                title_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                title_box.type(clean_title[:95], delay=15)

                # 2. Fill Description
                desc_boxes = page.locator("#textbox")
                if desc_boxes.count() > 1:
                    desc_box = desc_boxes.nth(1)
                    desc_box.click()
                    desc_box.type(full_desc[:4000], delay=5)

                # 3. Not Made for Kids
                try:
                    not_for_kids = page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK'], [name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").first
                    not_for_kids.click(timeout=8000)
                except Exception:
                    pass

                # Next through Video Elements and Checks
                for _ in range(3):
                    next_btn = page.locator("#next-button, button:has-text('Next')").first
                    next_btn.click(timeout=10000)
                    time_sleep(1500)

                # 4. Set Visibility (Public / Unlisted)
                if upload_privacy == "public":
                    page.locator("tp-yt-paper-radio-button[name='PUBLIC'], [name='PUBLIC']").first.click(timeout=8000)
                elif upload_privacy == "unlisted":
                    page.locator("tp-yt-paper-radio-button[name='UNLISTED'], [name='UNLISTED']").first.click(timeout=8000)
                else:
                    page.locator("tp-yt-paper-radio-button[name='PRIVATE'], [name='PRIVATE']").first.click(timeout=8000)

                time_sleep(1000)

                # 5. Extract Video URL if available before publishing
                yt_link = "https://youtube.com/shorts"
                try:
                    link_elem = page.locator("a.ytcp-video-info, a[href*='youtu.be']").first
                    if link_elem.is_visible():
                        yt_link = link_elem.get_attribute("href") or yt_link
                except Exception:
                    pass

                # 6. Click Done / Publish
                done_btn = page.locator("#done-button, button:has-text('Save'), button:has-text('Publish')").first
                done_btn.click(timeout=10000)
                time_sleep(4000)

                context.close()
                logger.info(f"Successfully published YouTube Short: {yt_link}")
                return {
                    "success": True,
                    "url": yt_link,
                    "title": clean_title,
                    "message": "YouTube Short published successfully!"
                }

        except Exception as e:
            logger.error(f"Playwright YouTube upload failed: {e}")
            return {"success": False, "error": f"Upload error: {e}"}

    def publish_to_instagram(
        self,
        video_url_or_path: str,
        caption: str = ""
    ) -> Dict[str, Any]:
        """
        Uploads an MP4 video directly to Instagram Reels using Playwright.
        """
        from playwright.sync_api import sync_playwright

        vid_file = Path(video_url_or_path).resolve()
        if not vid_file.exists():
            return {"success": False, "error": f"Video file not found: {video_url_or_path}"}

        profile_dir = self.profiles_dir / "instagram"
        if not (profile_dir.exists() and any(profile_dir.iterdir())):
            return {
                "success": False,
                "error": "Instagram account not logged in. Click 'Open Instagram Login Window' first."
            }

        # Ensure profile locks from lingering sessions are released cleanly
        try:
            release_profile_lock("instagram", self.profiles_dir)
            import time
            time.sleep(0.5)
        except Exception as e:
            logger.debug(f"Profile lock release note: {e}")

        logger.info(f"Starting automated Instagram Reel upload for: {vid_file.name}")

        try:
            channel = get_installed_browser_channel()
            launch_kwargs = {
                "user_data_dir": str(profile_dir),
                "headless": False,  # Visible browser ensures Instagram video encoder and modal render without crashing
                "viewport": {"width": 1440, "height": 960},
                "ignore_default_args": ["--enable-automation"],
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars"
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
                context.add_init_script(STEALTH_SCRIPT)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://www.instagram.com/", timeout=60000)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass

                time_sleep = page.wait_for_timeout
                time_sleep(2000)

                # Dismiss any 'Save login info', 'Turn on notifications', or cookie prompts
                dismiss_selectors = [
                    "button:has-text('Not Now')",
                    "button:has-text('Not now')",
                    "button:has-text('Cancel')",
                    "button:has-text('Decline optional cookies')",
                    "button:has-text('Only allow essential cookies')",
                    "button:has-text('Allow essential and optional cookies')",
                    "button:has-text('Allow all cookies')",
                    "button:has-text('Close')",
                    "[aria-label='Close']"
                ]
                for d_sel in dismiss_selectors:
                    try:
                        d_btn = page.locator(d_sel).first
                        if d_btn.is_visible(timeout=1000):
                            d_btn.click()
                            time_sleep(500)
                    except Exception:
                        pass

                # Verify if logged in
                if "accounts/login" in page.url:
                    context.close()
                    return {
                        "success": False,
                        "error": "Instagram session expired. Please click 'Open Instagram Login Window' to sign in."
                    }

                # Ensure navigation bar or primary app icons are loaded
                try:
                    page.wait_for_selector("svg[aria-label='Home'], svg[aria-label='Instagram'], nav, div[role='navigation']", timeout=20000)
                except Exception:
                    logger.debug("Instagram navigation container wait completed or timed out.")

                # 1. Click Create button (Check comprehensive desktop and mobile selectors)
                create_selectors = [
                    "svg[aria-label='New post']",
                    "svg[aria-label='New Post']",
                    "svg[aria-label='Create']",
                    "svg[aria-label='Post']",
                    "[aria-label='New post']",
                    "[aria-label='New Post']",
                    "[aria-label='Create']",
                    "a[href='#']:has-text('Create')",
                    "div[role='button']:has-text('Create')",
                    "span:text-is('Create')",
                    "span:has-text('Create')",
                    "a:has-text('Create')"
                ]

                create_clicked = False
                for c_sel in create_selectors:
                    try:
                        loc = page.locator(c_sel).first
                        if loc.is_visible(timeout=1500):
                            loc.click()
                            create_clicked = True
                            logger.info(f"Clicked Instagram Create button via selector: {c_sel}")
                            time_sleep(1500)
                            break
                    except Exception:
                        continue

                if not create_clicked:
                    # Final fallback: click via combined selector with generous timeout
                    fallback_loc = page.locator(", ".join(create_selectors)).first
                    fallback_loc.click(timeout=20000)
                    time_sleep(1500)

                # If "Post" sub-option appears in the create menu
                for post_sel in ["span:text-is('Post')", "span:has-text('Post')", "div[role='button']:has-text('Post')"]:
                    try:
                        post_sub = page.locator(post_sel).first
                        if post_sub.is_visible(timeout=1500):
                            post_sub.click()
                            time_sleep(1500)
                            break
                    except Exception:
                        pass

                # 2. Attach File
                file_input = page.locator("input[type='file']").first
                file_input.set_input_files(str(vid_file))
                logger.info("Attached video to Instagram upload modal.")
                time_sleep(3000)

                # 3. Handle Aspect Ratio (Select 9:16 or original)
                try:
                    crop_btn = page.locator("svg[aria-label='Select crop']").first
                    if crop_btn.is_visible():
                        crop_btn.click()
                        time_sleep(500)
                        nine_sixteen = page.locator("button:has-text('9:16'), span:has-text('9:16')").first
                        if nine_sixteen.is_visible():
                            nine_sixteen.click()
                            time_sleep(500)
                except Exception:
                    pass

                # 4. Click Next (to filter/cover)
                next_btn1 = page.locator("div[role='button']:has-text('Next')").first
                next_btn1.click(timeout=10000)
                time_sleep(2000)

                # Click Next (to caption)
                next_btn2 = page.locator("div[role='button']:has-text('Next')").first
                next_btn2.click(timeout=10000)
                time_sleep(2000)

                # 5. Type Caption
                caption_area = page.locator("div[aria-label='Write a caption...'], div[contenteditable='true']").first
                if caption_area.is_visible():
                    caption_area.click()
                    caption_area.type(caption[:2000], delay=5)

                time_sleep(1000)

                # 6. Click Share
                share_btn = page.locator("div[role='button']:has-text('Share')").first
                share_btn.click(timeout=10000)

                # Wait for confirmation: "Your reel has been shared"
                page.wait_for_selector("span:has-text('Your reel has been shared'), span:has-text('Your post has been shared')", timeout=60000)
                time_sleep(2000)

                context.close()
                logger.info("Successfully published Instagram Reel!")
                return {
                    "success": True,
                    "url": "https://www.instagram.com/",
                    "message": "Instagram Reel shared successfully!"
                }

        except Exception as e:
            logger.error(f"Playwright Instagram upload failed: {e}")
            return {"success": False, "error": f"Instagram upload error: {e}"}


# Singleton instance
publisher = PlaywrightPublisher()
