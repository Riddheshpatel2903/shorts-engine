"""
Video Series Fragmenter Engine for ViralShortsEngine.
Takes a long video (via URL or local file) and fragments it into continuous 30-40s parts
(Part 1, Part 2, ...) with NO extra effects, filters, or overlays.
Pure, high-quality, continuous video splitting with automatic 30-minute interval calendar scheduling.
"""

import os
import sys
import re
import json
import math
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Callable

from config import WORKSPACE_DIR, OUTPUT_DIR, DOWNLOADS_DIR
from core.downloader import VideoDownloader
from core.scheduler import scheduler, DAILY_SLOTS

logger = logging.getLogger("ViralShortsEngine.Fragmenter")


def get_video_duration(video_path: Path) -> float:
    """Uses ffprobe to get precise duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        logger.error(f"Error getting duration for {video_path}: {e}")
        return 0.0


def clean_slug_filename(name: str) -> str:
    """Creates a clean, safe filename prefix."""
    s = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", s)[:40]


class VideoSeriesFragmenter:
    """
    Splits video into pure, clean continuous segments (e.g. 35s each)
    labeled Part 1, Part 2, ... and auto-schedules them every 30 minutes.
    """

    def __init__(self):
        self.output_dir = Path(OUTPUT_DIR)
        self.downloads_dir = Path(DOWNLOADS_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.downloader = VideoDownloader()

    def fragment_video(
        self,
        video_url_or_path: str,
        part_duration: float = 35.0,
        make_vertical_916: bool = True,
        title_prefix: Optional[str] = None,
        auto_schedule_30min: bool = True,
        schedule_start_date: Optional[str] = None,
        schedule_start_slot: str = "09:00 AM",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Dict[str, Any]:
        """
        Main pipeline:
        1. Resolve or download source video.
        2. Detect duration with ffprobe.
        3. Cut contiguous 30-40s segments sequentially (Part 1, Part 2, ...).
        4. Save sidecar metadata (.meta.json).
        5. Auto-schedule every 30 mins in the 12-hour calendar if enabled.
        """
        source_path = None
        base_title = "Video Series"

        # 1. Resolve source
        if video_url_or_path.startswith("http://") or video_url_or_path.startswith("https://"):
            if progress_callback:
                progress_callback("⬇️ Downloading source video from URL...", 0.1)
            dl_res = self.downloader.download(video_url_or_path)
            if not dl_res or not dl_res.get("success") or not dl_res.get("filepath"):
                return {"success": False, "error": f"Failed to download video from URL: {video_url_or_path}"}
            source_path = Path(dl_res["filepath"])
            base_title = dl_res.get("title") or source_path.stem
        else:
            source_path = Path(video_url_or_path).resolve()
            if not source_path.exists():
                return {"success": False, "error": f"Source video file not found: {video_url_or_path}"}
            base_title = title_prefix or source_path.stem

        if title_prefix:
            base_title = title_prefix

        # Clean title & slug
        clean_prefix = clean_slug_filename(base_title)

        # 2. Probe Duration
        if progress_callback:
            progress_callback("🔍 Probing video streams and timeline duration...", 0.2)

        total_duration = get_video_duration(source_path)
        if total_duration <= 0:
            return {"success": False, "error": f"Could not determine duration for video: {source_path}"}

        # Clamp part duration between 20s and 60s (default 35s)
        part_dur = max(20.0, min(60.0, float(part_duration)))
        num_parts = max(1, math.ceil(total_duration / part_dur))

        logger.info(f"Splitting video '{base_title}' ({total_duration:.1f}s) into {num_parts} parts (~{part_dur:.1f}s each)")
        if progress_callback:
            progress_callback(f"✂️ Fragmenting into {num_parts} parts (~{part_dur:.0f}s each, clean cut, no extra effects)...", 0.3)

        generated_parts = []
        errors = []

        # 3. Continuous clean fragmentation loop
        for idx in range(1, num_parts + 1):
            start_sec = (idx - 1) * part_dur
            end_sec = min(total_duration, start_sec + part_dur)
            actual_dur = end_sec - start_sec

            # Avoid tiny trailing fragments under 8 seconds: merge with previous if applicable
            if idx > 1 and actual_dur < 8.0:
                logger.info(f"Trailing fragment ({actual_dur:.1f}s) is too short; skipping separate part.")
                break

            out_filename = f"{clean_prefix}_part_{idx:02d}.mp4"
            out_file = self.output_dir / out_filename

            part_pct = 0.3 + (0.5 * (idx / num_parts))
            if progress_callback:
                progress_callback(f"✂️ Rendering Part {idx}/{num_parts} [{start_sec:.0f}s - {end_sec:.0f}s]...", part_pct)

            # Build clean FFmpeg command (NO extra effects, crisp video & audio cut)
            if make_vertical_916:
                # Scale & center-crop to 1080x1920 (9:16 Shorts/Reels ratio)
                vf_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_sec),
                    "-to", str(end_sec),
                    "-i", str(source_path),
                    "-vf", vf_filter,
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "20",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-avoid_negative_ts", "make_zero",
                    str(out_file)
                ]
            else:
                # Keep original aspect ratio
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_sec),
                    "-to", str(end_sec),
                    "-i", str(source_path),
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "20",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-avoid_negative_ts", "make_zero",
                    str(out_file)
                ]

            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as err:
                logger.error(f"FFmpeg error rendering part {idx}: {err.stderr}")
                errors.append(f"Part {idx}: {err}")
                continue

            # Save clean sidecar metadata (.meta.json)
            part_title = f"{base_title} - Part {idx} #shorts"
            part_caption = (
                f"Part {idx} of {num_parts}: {base_title}.\n\n"
                f"Next part posting in 30 minutes! Follow for the full series 👇"
            )
            part_hashtags = f"#shorts #series #part{idx} #viral #trending #reels"

            meta_file = out_file.with_suffix(".meta.json")
            try:
                with open(meta_file, "w", encoding="utf-8") as mf:
                    json.dump({
                        "title": part_title,
                        "caption": part_caption,
                        "instagram_caption": part_caption,
                        "hashtags": part_hashtags,
                        "part_index": idx,
                        "total_parts": num_parts,
                        "duration": round(actual_dur, 2),
                        "video_path": str(out_file),
                        "created_at": datetime.now().isoformat()
                    }, mf, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"Could not write meta for part {idx}: {e}")

            sz_mb = out_file.stat().st_size / (1024 * 1024) if out_file.exists() else 0.0
            generated_parts.append({
                "part_index": idx,
                "title": part_title,
                "caption": part_caption,
                "hashtags": part_hashtags,
                "duration": round(actual_dur, 1),
                "filepath": str(out_file),
                "filename": out_file.name,
                "size_mb": round(sz_mb, 2)
            })

        if not generated_parts:
            return {"success": False, "error": f"Failed to generate parts. Errors: {errors}"}

        # 4. Auto-Schedule Every 30 Minutes
        scheduled_slots = []
        if auto_schedule_30min:
            if progress_callback:
                progress_callback("📅 Auto-scheduling series parts every 30 minutes across calendar...", 0.9)

            scheduled_slots = self.auto_schedule_series_every_30min(
                parts=generated_parts,
                start_date=schedule_start_date,
                start_slot=schedule_start_slot
            )

        if progress_callback:
            progress_callback(f"🎉 Successfully fragmented into {len(generated_parts)} series parts!", 1.0)

        return {
            "success": True,
            "base_title": base_title,
            "total_duration": round(total_duration, 1),
            "total_parts": len(generated_parts),
            "parts": generated_parts,
            "scheduled_slots": scheduled_slots
        }

    def auto_schedule_series_every_30min(
        self,
        parts: List[Dict[str, Any]],
        start_date: Optional[str] = None,
        start_slot: str = "09:00 AM"
    ) -> List[Dict[str, Any]]:
        """
        Sequentially books series parts across upcoming daytime 30-min slots
        (09:00 AM to 09:00 PM) for Today, Tomorrow, and Day After Tomorrow.
        """
        today_date = date.today()
        cur_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else today_date

        # 12-Hour daytime slots every 30 minutes from morning to night
        from core.scheduler import DAILY_SLOTS

        slot_list = list(DAILY_SLOTS)
        start_idx = 0
        if start_slot in slot_list:
            start_idx = slot_list.index(start_slot)

        booked = []
        cur_slot_idx = start_idx

        for part in parts:
            d_str = cur_date.strftime("%Y-%m-%d")
            t_slot = slot_list[cur_slot_idx]

            res = scheduler.schedule_short(
                date_str=d_str,
                time_slot=t_slot,
                video_path=part["filepath"],
                custom_title=part["title"],
                custom_caption=part["caption"],
                custom_tags=part["hashtags"]
            )
            if res.get("success"):
                booked.append({
                    "part": part["part_index"],
                    "date": d_str,
                    "time_slot": t_slot,
                    "title": part["title"]
                })

            # Advance to next 30-min slot
            cur_slot_idx += 1
            if cur_slot_idx >= len(slot_list):
                # End of 12-hour daytime window (reached 9:00 PM): roll over to next morning at 9:00 AM
                cur_slot_idx = 0
                cur_date += timedelta(days=1)

        return booked


# Global singleton instance
video_fragmenter = VideoSeriesFragmenter()
