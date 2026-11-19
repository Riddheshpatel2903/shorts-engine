"""
Downloader module using yt-dlp.
Handles downloading YouTube videos, livestreams, Twitch VODs/clips, and direct URLs.
Extracts metadata, supports cookie authentication, and ensures synchronized video+audio streams.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yt_dlp

from config import BASE_DIR, WORKSPACE_DIR, DOWNLOADS_DIR

logger = logging.getLogger("ViralShortsEngine.Downloader")


class VideoDownloader:
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        cookies_file: Optional[str] = None,
        cookies_from_browser: Optional[str] = None
    ):
        self.output_dir = Path(output_dir) if output_dir else DOWNLOADS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = cookies_file
        self.cookies_from_browser = cookies_from_browser

        # Auto-detect cookies.txt in project root or workspace if not explicitly provided
        if not self.cookies_file and not self.cookies_from_browser:
            for candidate in [
                BASE_DIR / "cookies.txt",
                WORKSPACE_DIR / "cookies.txt",
                Path("cookies.txt")
            ]:
                if candidate.exists() and candidate.stat().st_size > 0:
                    self.cookies_file = str(candidate.resolve())
                    logger.info(f"Auto-detected cookies file: {self.cookies_file}")
                    break

    @staticmethod
    def detect_platform(url: str) -> Dict[str, str]:
        """Detects streaming platform from URL."""
        url_lower = url.lower()
        if "instagram.com" in url_lower:
            return {"platform": "Instagram", "icon": "📸", "type": "Instagram Reel / Clip"}
        elif "tiktok.com" in url_lower:
            return {"platform": "TikTok", "icon": "🎵", "type": "TikTok Video / Clip"}
        elif "twitch.tv" in url_lower:
            return {"platform": "Twitch", "icon": "🟣", "type": "Twitch VOD / Clip / Stream"}
        elif "kick.com" in url_lower:
            return {"platform": "Kick", "icon": "🟢", "type": "Kick Stream / VOD / Clip"}
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            return {"platform": "YouTube", "icon": "🔴", "type": "YouTube Video / Short / Live"}
        elif any(ext in url_lower for ext in [".m3u8", ".mpd"]):
            return {"platform": "LiveStream", "icon": "📡", "type": "Direct HLS / DASH Live Stream"}
        elif ".mp4" in url_lower or ".mov" in url_lower or ".mkv" in url_lower:
            return {"platform": "DirectFile", "icon": "🌐", "type": "Direct Web Video File"}
        else:
            return {"platform": "WebVideo", "icon": "🎬", "type": "Web Video Source"}

    def _configure_opts(self, base_opts: Dict[str, Any]) -> Dict[str, Any]:
        """Applies cookies and extractor arguments to yt-dlp options."""
        import shutil
        opts = base_opts.copy()

        # Auto-configure Node.js runtime if present on the system
        node_exe = shutil.which("node")
        if node_exe:
            opts["js_runtimes"] = {"node": {"path": node_exe}}
            opts["remote_components"] = ["ejs:github"]

        # Support live streams and VODs across Twitch, Kick, and YouTube
        opts["live_from_start"] = True
        opts["hls_prefer_native"] = True

        # Apply cookies file if available
        if self.cookies_file and os.path.exists(self.cookies_file):
            opts["cookiefile"] = str(self.cookies_file)
            logger.info(f"Using cookies file: {self.cookies_file}")
        elif self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
            logger.info(f"Using cookies from browser: {self.cookies_from_browser}")
        else:
            # Fallback player client sequence when unauthenticated
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android", "web"]
                },
                "twitch": {
                    "disable_ads": True
                }
            }

        return opts

    def get_info(self, url: str) -> Dict[str, Any]:
        """
        Extract video metadata without downloading.
        """
        ydl_opts = self._configure_opts({
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return {
                    "id": info.get("id", "unknown"),
                    "title": info.get("title", "Untitled Video"),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", "Unknown Uploader"),
                    "fps": info.get("fps", 30),
                    "width": info.get("width", 1920),
                    "height": info.get("height", 1080),
                    "thumbnail": info.get("thumbnail", ""),
                    "description": info.get("description", "")[:500],
                    "extractor": info.get("extractor", ""),
                    "webpage_url": info.get("webpage_url", url),
                }
            except Exception as e:
                logger.error(f"Error extracting metadata from {url}: {e}")
                raise

    def download(self, url: str, progress_hook: Optional[callable] = None) -> Dict[str, Any]:
        """
        Download video and audio streams, merging them into a synchronized MP4.
        Returns metadata and output filepath.
        """
        logger.info(f"Initiating download for URL: {url}")
        
        outtmpl = str(self.output_dir / "%(id)s.%(ext)s")

        ydl_opts = self._configure_opts({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/bestvideo*+bestaudio*/best[ext=mp4]/best*",
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4",
            }],
        })

        if progress_hook:
            ydl_opts["progress_hooks"] = [progress_hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # If a search query was used (e.g. ytsearch1:...), unwrap the entries
            if info and "entries" in info:
                entries = [e for e in info.get("entries", []) if e]
                if entries:
                    info = entries[0]

            video_id = info.get("id", "video")
            expected_filepath = self.output_dir / f"{video_id}.mp4"

            # Fallback if filename differs
            if not expected_filepath.exists():
                candidates = list(self.output_dir.glob(f"{video_id}.*"))
                if candidates:
                    expected_filepath = candidates[0]

            logger.info(f"Download complete: {expected_filepath}")

            return {
                "id": video_id,
                "title": info.get("title", "Untitled Video"),
                "duration": info.get("duration", 0),
                "filepath": str(expected_filepath),
                "fps": info.get("fps", 30),
                "width": info.get("width", 1920),
                "height": info.get("height", 1080),
                "uploader": info.get("uploader", "Unknown"),
                "thumbnail": info.get("thumbnail", ""),
                "webpage_url": info.get("webpage_url", url),
            }
