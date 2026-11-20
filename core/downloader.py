"""
Downloader module using yt-dlp.
Handles downloading YouTube videos, livestreams, Twitch VODs/clips, and direct URLs.
Extracts metadata, supports cookie authentication, and ensures synchronized video+audio streams.
"""

import os
import sys
import logging
import time
import re
import subprocess
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

        # Connection resilience and anti-throttling options
        # Prevents ConnectionResetError (10054) and YouTube CDN TCP disconnects
        opts.setdefault("retries", 15)
        opts.setdefault("fragment_retries", 15)
        opts.setdefault("skip_unavailable_fragments", True)
        opts.setdefault("socket_timeout", 30)
        opts.setdefault("http_chunk_size", 10485760)  # 10MB chunking prevents CDN resets
        opts.setdefault("concurrent_fragment_downloads", 2)
        opts.setdefault("file_access_retries", 5)
        opts.setdefault("continuedl", True)  # Resume partial downloads

        # Apply cookies file if available
        if self.cookies_file and os.path.exists(self.cookies_file):
            opts["cookiefile"] = str(self.cookies_file)
            logger.info(f"Using cookies file: {self.cookies_file}")
        elif self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
            logger.info(f"Using cookies from browser: {self.cookies_from_browser}")
        else:
            # Fallback player client sequence when unauthenticated: prefer web and mweb to avoid android throttle
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["web", "mweb", "android"],
                    "player_skip": ["configs", "webpage"]
                },
                "twitch": {
                    "disable_ads": True
                }
            }

        return opts

    def get_info(self, url: str) -> Dict[str, Any]:
        """
        Extract video metadata without downloading. Detects live broadcast status and stream manifests.
        """
        ydl_opts = self._configure_opts({
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                # If a playlist or search entry, pick first
                if info and "entries" in info:
                    entries = [e for e in info.get("entries", []) if e]
                    if entries:
                        info = entries[0]

                is_live = bool(info.get("is_live") or info.get("live_status") in ("is_live", "post_live") or (info.get("duration") is None and not info.get("is_upcoming")))
                live_status = info.get("live_status", "is_live" if is_live else "not_live")

                # Try getting direct stream manifest URL (e.g. HLS m3u8)
                stream_url = info.get("url")
                if not stream_url and "formats" in info:
                    for f in reversed(info.get("formats", [])):
                        f_url = f.get("url", "")
                        if f_url and (".m3u8" in f_url or f.get("protocol") in ("m3u8", "m3u8_native", "https")):
                            stream_url = f_url
                            break

                return {
                    "id": info.get("id", "unknown"),
                    "title": info.get("title", "Untitled Video"),
                    "duration": float(info.get("duration") or 0.0),
                    "uploader": info.get("uploader", "Unknown Uploader"),
                    "fps": info.get("fps", 30) or 30,
                    "width": info.get("width", 1920) or 1920,
                    "height": info.get("height", 1080) or 1080,
                    "thumbnail": info.get("thumbnail", ""),
                    "description": info.get("description", "")[:500],
                    "extractor": info.get("extractor", ""),
                    "webpage_url": info.get("webpage_url", url),
                    "is_live": is_live,
                    "live_status": live_status,
                    "stream_url": stream_url,
                    "view_count": info.get("concurrent_view_count") or info.get("view_count", 0),
                }
            except Exception as e:
                logger.error(f"Error extracting metadata from {url}: {e}")
                raise

    def capture_live_fragment(
        self,
        url: str,
        duration_sec: int = 120,
        start_sec: Optional[float] = None,
        progress_hook: Optional[callable] = None,
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Captures a rolling live stream fragment (e.g. 60s, 120s, 180s) or a VOD segment
        directly from the live HLS/DASH manifest without downloading the entire stream.
        Saves disk space, eliminates hours of wait time, and enables clipping while the streamer is live!
        """
        logger.info(f"Capturing live fragment: URL={url}, duration={duration_sec}s, start_sec={start_sec}")

        # 1. Fetch metadata
        meta = self.get_info(url)
        video_id = meta.get("id", "stream")
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', meta.get("title", "live")[:30]).strip("_")
        ts_stamp = int(time.time())

        if not output_filename:
            output_filename = f"live_{clean_title}_{duration_sec}s_{ts_stamp}.mp4"

        expected_filepath = self.output_dir / output_filename
        expected_filepath.parent.mkdir(parents=True, exist_ok=True)

        stream_url = meta.get("stream_url")
        captured = False

        # Attempt 1: Ultra-fast direct FFmpeg stream copy from live HLS manifest
        if stream_url and (".m3u8" in stream_url or "manifest" in stream_url):
            try:
                logger.info(f"Attempting ultra-fast direct FFmpeg copy from stream manifest...")
                cmd = ["ffmpeg", "-y"]
                if start_sec is not None and start_sec > 0:
                    cmd.extend(["-ss", str(start_sec)])

                cmd.extend([
                    "-reconnect", "1",
                    "-reconnect_at_eof", "1",
                    "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "3",
                    "-i", stream_url,
                    "-t", str(duration_sec),
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(expected_filepath)
                ])

                res = subprocess.run(cmd, capture_output=True, text=True, timeout=max(60, duration_sec + 30))
                if expected_filepath.exists() and expected_filepath.stat().st_size > 100_000:
                    logger.info(f"Direct FFmpeg live fragment capture successful: {expected_filepath} ({expected_filepath.stat().st_size} bytes)")
                    captured = True
            except Exception as e:
                logger.debug(f"Direct FFmpeg capture attempt skipped/failed: {e}")

        # Attempt 2: Universal yt-dlp with FFmpeg external downloader limited to duration_sec
        if not captured:
            logger.info("Attempting yt-dlp live head capture with ffmpeg external downloader...")
            ffmpeg_args = ["-t", str(duration_sec)]
            if start_sec is not None and start_sec > 0:
                ffmpeg_args.extend(["-ss", str(start_sec)])

            ydl_opts = self._configure_opts({
                "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080][ext=mp4]/best[height<=1080]/best",
                "outtmpl": str(expected_filepath.with_suffix(".%(ext)s")),
                "noplaylist": True,
                "live_from_start": False,  # DO NOT download from beginning! Start at live edge!
                "external_downloader": {"default": "ffmpeg"},
                "external_downloader_args": {
                    "ffmpeg_i": ffmpeg_args
                },
                "postprocessors": [{
                    "key": "FFmpegVideoRemuxer",
                    "preferedformat": "mp4",
                }],
                "quiet": False,
                "no_warnings": True,
                "socket_timeout": 20,
            })
            if progress_hook:
                ydl_opts["progress_hooks"] = [progress_hook]

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Resolve resulting file
                if not expected_filepath.exists():
                    candidates = list(self.output_dir.glob(f"{expected_filepath.stem}*"))
                    if candidates:
                        expected_filepath = candidates[0]
                        captured = True
                else:
                    captured = True
            except Exception as e:
                logger.error(f"yt-dlp live head capture encountered an error: {e}")

        # Attempt 3: If still not captured, try download_ranges
        if not captured or not expected_filepath.exists() or expected_filepath.stat().st_size < 10000:
            logger.info("Attempting yt-dlp download_ranges fallback...")
            s_val = start_sec if start_sec is not None else 0.0
            ydl_opts = self._configure_opts({
                "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                "outtmpl": str(expected_filepath.with_suffix(".%(ext)s")),
                "download_ranges": yt_dlp.utils.download_range_func([], [[s_val, s_val + duration_sec]]),
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": False,
                "no_warnings": True,
            })
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not expected_filepath.exists():
                candidates = list(self.output_dir.glob(f"{expected_filepath.stem}*"))
                if candidates:
                    expected_filepath = candidates[0]

        # Probe final duration if file was created
        real_dur = float(duration_sec)
        if expected_filepath.exists():
            try:
                import cv2
                cap = cv2.VideoCapture(str(expected_filepath))
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                fcount = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                if fcount > 0 and fps > 0:
                    real_dur = round(fcount / fps, 2)
                cap.release()
            except Exception:
                pass

        # Try to fetch live chat replay in the background
        self.download_live_chat(url, expected_filepath)

        return {
            "id": video_id,
            "title": f"{meta.get('title', 'Live Stream')} ({duration_sec}s Live Fragment)",
            "duration": real_dur,
            "filepath": str(expected_filepath),
            "fps": meta.get("fps", 30),
            "width": meta.get("width", 1920),
            "height": meta.get("height", 1080),
            "uploader": meta.get("uploader", "Streamer"),
            "thumbnail": meta.get("thumbnail", ""),
            "webpage_url": meta.get("webpage_url", url),
            "is_live": True,
            "is_fragment": True,
        }

    def download(self, url: str, progress_hook: Optional[callable] = None) -> Dict[str, Any]:
        """
        Download video and audio streams, merging them into a synchronized MP4.
        If URL is an active live stream, automatically captures a 120s rolling fragment
        to avoid downloading hours of live broadcast.
        """
        logger.info(f"Initiating download for URL: {url}")

        # Check if URL is an active live stream to protect against multi-hour downloads
        try:
            info_preview = self.get_info(url)
            if info_preview.get("is_live"):
                logger.info(f"Target URL is an ACTIVE LIVE STREAM! Auto-routing to 120s rolling fragment grabber.")
                return self.capture_live_fragment(url, duration_sec=120, progress_hook=progress_hook)
        except Exception as e:
            logger.debug(f"Pre-check for live stream skipped: {e}")

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

        info = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as e:
            logger.warning(f"Primary download attempt encountered network issue ({e}). Retrying with resilient progressive stream...")
            fallback_opts = ydl_opts.copy()
            # Fallback to single stream MP4 (up to 1080p) to avoid multi-stream socket resets
            fallback_opts["format"] = "best[height<=1080][ext=mp4]/best[height<=1080]/best[ext=mp4]/best"
            fallback_opts["http_chunk_size"] = 5242880  # 5MB chunks
            fallback_opts["retries"] = 25
            fallback_opts["fragment_retries"] = 25
            fallback_opts["continuedl"] = True
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
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

    def download_live_chat(self, url: str, output_path: Path) -> Optional[Path]:
        """
        Attempts to fetch live chat replay (.live_chat.json) for livestreams and VODs.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        outtmpl = str(output_path.with_suffix(".%(ext)s"))

        ydl_opts = self._configure_opts({
            "skip_download": True,
            "write_sub": True,
            "sub_langs": ["live_chat"],
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 6
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Look for live_chat.json file
            candidates = list(output_path.parent.glob(f"{output_path.stem}*.live_chat.json"))
            if candidates and candidates[0].stat().st_size > 100:
                return candidates[0]
        except Exception as e:
            logger.debug(f"Live chat replay not available or failed to download: {e}")

        return None
