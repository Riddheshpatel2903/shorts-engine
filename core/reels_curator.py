"""
Viral Reels & Shorts Scraper, Content Adaptation, and Automated Reposter Engine.

Features:
1. Catches and downloads viral Instagram Reels, TikToks, and YouTube Shorts in full 1080x1920 9:16 vertical MP4 format.
2. Transcribes video audio with faster-whisper to understand the exact speech and topic.
3. Automatically generates 100% relevant, high-retention viral titles, captions, and trending hashtags with AI Brain / Ollama.
4. Automatically uploads the curated reel directly to your connected YouTube Shorts and Instagram Reels channels with live visible browser windows.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from config import WORKSPACE_DIR, DOWNLOADS_DIR
from core.downloader import VideoDownloader
from core.transcriber import AudioTranscriber
from core.ai_brain import ai_brain
from core.publisher import publisher

logger = logging.getLogger("ViralShortsEngine.ReelsCurator")

REELS_OUTPUT_DIR = Path(WORKSPACE_DIR) / "downloads" / "viral_reels"
REELS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ViralReelsCuratorEngine:
    """
    Automated Viral Reels Scraper, Transcriber, AI Caption Writer, and Social Reposter.
    """

    def __init__(self):
        self.output_dir = REELS_OUTPUT_DIR
        self.downloader = VideoDownloader(output_dir=self.output_dir)
        self.transcriber = AudioTranscriber()

    def normalize_source_url(self, raw_input: str) -> str:
        """Normalizes URLs or handles into valid downloadable links."""
        url = raw_input.strip()
        # If user entered an Instagram handle (e.g. @username or username)
        if url.startswith("@"):
            username = url[1:].strip()
            return f"https://www.instagram.com/{username}/reels/"
        elif not url.startswith("http") and "/" not in url and "." not in url:
            return f"https://www.instagram.com/{url}/reels/"
        return url

    def download_viral_reel(
        self,
        source_url: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Downloads a viral Instagram Reel, TikTok video, or YouTube Short.
        """
        clean_url = self.normalize_source_url(source_url)
        if progress_callback:
            progress_callback(f"Connecting to {clean_url} & extracting viral media streams...")

        logger.info(f"Downloading viral reel from: {clean_url}")
        try:
            # 1. Fetch metadata first
            info = self.downloader.get_info(clean_url)
            orig_title = info.get("title", "Viral Reel")
            duration = float(info.get("duration", 30.0))
            uploader = info.get("uploader", info.get("channel", "Creator"))

            if progress_callback:
                progress_callback(f"Downloading vertical 9:16 video: '{orig_title[:45]}...' ({duration:.1f}s)")

            # 2. Download the vertical video in highest quality MP4
            downloaded_path = self.downloader.download_video(clean_url)
            if not downloaded_path or not Path(downloaded_path).exists():
                raise RuntimeError("Downloader returned no valid output file.")

            final_path = Path(downloaded_path)
            logger.info(f"Viral reel downloaded successfully to: {final_path}")

            return {
                "success": True,
                "filepath": str(final_path),
                "filename": final_path.name,
                "title": orig_title,
                "uploader": uploader,
                "duration": duration,
                "original_url": clean_url,
                "raw_info": info
            }

        except Exception as e:
            logger.error(f"Failed to download viral reel: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_url": clean_url
            }

    def transcribe_and_generate_captions(
        self,
        video_path: str,
        original_meta: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Transcribes the video audio using faster-whisper and generates
        100% topic-relevant titles, Instagram captions, and hashtags.
        """
        v_path = Path(video_path)
        if not v_path.exists():
            return {"success": False, "error": f"Video file not found: {video_path}"}

        if progress_callback:
            progress_callback("Transcribing video speech with faster-whisper (word timestamps)...")

        meta = original_meta or {}
        orig_title = meta.get("title", v_path.stem)

        # 1. Transcribe audio to understand spoken topic
        full_transcript = ""
        try:
            t_res = self.transcriber.transcribe(str(v_path))
            full_transcript = t_res.get("full_transcript", "").strip()
            logger.info(f"Transcribed {len(full_transcript)} characters of speech from reel.")
        except Exception as e:
            logger.warning(f"Whisper transcription failed ({e}), falling back to metadata blueprint.")

        if progress_callback:
            progress_callback("AI Brain generating 100% relevant viral hook, caption & trending hashtags...")

        # 2. Generate relevant social copy based on the ACTUAL speech
        effective_text = full_transcript if full_transcript else orig_title
        social_copy = ai_brain.generate_viral_metadata(
            clip_text=effective_text,
            niche="VIRAL_REELS",
            title_hint=orig_title,
            source_metadata=meta.get("raw_info")
        )

        return {
            "success": True,
            "filepath": str(v_path),
            "transcript": full_transcript,
            "title": social_copy.get("title", f"{orig_title[:60]} #Shorts"),
            "caption": social_copy.get("instagram_caption", f"{orig_title}\n\nDrop your thoughts below! 👇"),
            "instagram_caption": social_copy.get("instagram_caption", f"{orig_title}\n\nDrop your thoughts below! 👇"),
            "hashtags": social_copy.get("hashtags", "#shorts #viral #reels #trending"),
            "hook_overlay": social_copy.get("hook_overlay", "WAIT FOR THIS ⚠️")
        }

    def repost_to_channels(
        self,
        video_path: str,
        social_copy: Dict[str, Any],
        upload_youtube: bool = True,
        upload_instagram: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Uploads the curated viral reel directly to YouTube Shorts and Instagram Reels
        with the browser window running visibly so user can monitor.
        """
        v_path = Path(video_path)
        if not v_path.exists():
            return {"success": False, "error": f"Video not found: {video_path}"}

        results = {}
        status = publisher.check_status()

        # YouTube Shorts upload
        if upload_youtube:
            if not status.get("youtube_connected"):
                results["youtube"] = {
                    "success": False,
                    "error": "YouTube account not logged in. Log in via sidebar first."
                }
            else:
                if progress_callback:
                    progress_callback("🚀 Uploading to YouTube Shorts via visible browser session...")
                y_res = publisher.publish_to_youtube(
                    video_path=str(v_path),
                    title=social_copy.get("title", v_path.stem),
                    description=social_copy.get("instagram_caption", "") or social_copy.get("caption", ""),
                    tags=social_copy.get("hashtags", "")
                )
                results["youtube"] = y_res

        # Instagram Reels upload
        if upload_instagram:
            if not status.get("instagram_connected"):
                results["instagram"] = {
                    "success": False,
                    "error": "Instagram account not logged in. Log in via sidebar first."
                }
            else:
                if progress_callback:
                    progress_callback("🚀 Uploading to Instagram Reels via visible browser session...")
                full_ig_caption = f"{social_copy.get('instagram_caption', '')}\n\n{social_copy.get('hashtags', '')}".strip()
                i_res = publisher.publish_to_instagram(
                    video_url_or_path=str(v_path),
                    caption=full_ig_caption
                )
                results["instagram"] = i_res

        return results

    def curate_and_auto_repost(
        self,
        source_url: str,
        upload_youtube: bool = True,
        upload_instagram: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        1-Click Full Automation:
        1. Download Reel from URL or creator account.
        2. Transcribe spoken audio.
        3. Generate relevant viral caption & hashtags.
        4. Auto-upload to connected YouTube Shorts & Instagram Reels accounts.
        """
        # Step 1: Download
        dl_res = self.download_viral_reel(source_url, progress_callback=progress_callback)
        if not dl_res.get("success"):
            return dl_res

        # Step 2 & 3: Transcribe & Generate Captions
        cap_res = self.transcribe_and_generate_captions(
            video_path=dl_res["filepath"],
            original_meta=dl_res,
            progress_callback=progress_callback
        )
        if not cap_res.get("success"):
            return cap_res

        # Step 4: Auto-upload if accounts are active
        upload_results = {}
        if upload_youtube or upload_instagram:
            upload_results = self.repost_to_channels(
                video_path=dl_res["filepath"],
                social_copy=cap_res,
                upload_youtube=upload_youtube,
                upload_instagram=upload_instagram,
                progress_callback=progress_callback
            )

        return {
            "success": True,
            "download": dl_res,
            "content": cap_res,
            "upload_results": upload_results
        }


# Global singleton instance
reels_curator = ViralReelsCuratorEngine()
