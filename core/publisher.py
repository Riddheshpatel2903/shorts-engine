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

logger = logging.getLogger("ViralShortsEngine.Publisher")

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = Path(WORKSPACE_DIR) / "browser_profile"
SETTINGS_FILE = Path(WORKSPACE_DIR) / "social_settings.json"


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
            "auto_publish_on_render": False
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
            "auto_publish": self.settings.get("auto_publish_on_render", False)
        }

    # Alias for compatibility
    get_status = check_status

    @property
    def creds(self) -> Dict[str, Any]:
        return {
            "auto_publish_on_render": self.settings.get("auto_publish_on_render", False),
            "youtube": {"privacy": self.settings.get("youtube_privacy", "public")},
            "instagram": {}
        }

    def auto_publish_if_enabled(self, video_path: str, social_copy: Dict[str, Any]) -> Dict[str, Any]:
        """Uploads automatically if auto_publish_on_render is enabled and profiles are active."""
        if not self.settings.get("auto_publish_on_render"):
            return {"status": "skipped", "message": "Auto-publish disabled."}

        results = {}
        status = self.check_status()
        if status.get("youtube_connected"):
            results["youtube"] = self.publish_to_youtube(
                video_path=video_path,
                title=social_copy.get("title", "Viral Short #shorts"),
                description=social_copy.get("instagram_caption", ""),
                tags=social_copy.get("hashtags", "")
            )
        if status.get("instagram_connected"):
            results["instagram"] = self.publish_to_instagram(
                video_url_or_path=video_path,
                caption=f"{social_copy.get('instagram_caption', '')}\n\n{social_copy.get('hashtags', '')}"
            )
        return results

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

        logger.info(f"Starting automated YouTube upload for: {vid_file.name}")

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=True,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.new_page()
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

        logger.info(f"Starting automated Instagram Reel upload for: {vid_file.name}")

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=True,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.new_page()
                page.goto("https://www.instagram.com/", timeout=60000)
                page.wait_for_load_state("networkidle")

                # Verify if logged in
                if "accounts/login" in page.url:
                    context.close()
                    return {
                        "success": False,
                        "error": "Instagram session expired. Please click 'Open Instagram Login Window' to sign in."
                    }

                time_sleep = page.wait_for_timeout

                # 1. Click Create button
                create_nav = page.locator("svg[aria-label='New post'], [aria-label='Create'], span:has-text('Create')").first
                create_nav.click(timeout=15000)
                time_sleep(1500)

                # If "Post" sub-option appears
                post_sub = page.locator("span:has-text('Post')").first
                if post_sub.is_visible():
                    post_sub.click()
                    time_sleep(1500)

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
