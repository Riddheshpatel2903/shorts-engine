"""
Content Publishing Calendar & Slot Scheduler Engine.

Features:
1. Manages calendar slots (e.g. 09:00 AM, 12:00 PM, 06:00 PM) across days and weeks.
2. Tracks persistent schedule registry in workspace/publishing_schedule.json.
3. Automatically attaches stored .meta.json captions and titles with each scheduled video.
4. Auto-fills upcoming empty slots with ready unscheduled shorts.
5. Executes visible automated publishing to YouTube Shorts and Instagram Reels.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import WORKSPACE_DIR, OUTPUT_DIR, DOWNLOADS_DIR
from core.exporter import exporter
from core.publisher import publisher

logger = logging.getLogger("ViralShortsEngine.Scheduler")

SCHEDULE_FILE = Path(WORKSPACE_DIR) / "publishing_schedule.json"
DAILY_SLOTS = ["09:00 AM", "12:00 PM", "06:00 PM"]


class ContentScheduler:
    """
    Publishing Calendar & Schedule Management Engine.
    """

    def __init__(self):
        self.schedule_file = SCHEDULE_FILE
        self._ensure_file()

    def _ensure_file(self):
        if not self.schedule_file.exists():
            self._save({})

    def _load(self) -> Dict[str, Any]:
        try:
            if self.schedule_file.exists():
                with open(self.schedule_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read publishing schedule: {e}")
        return {}

    def _save(self, data: Dict[str, Any]):
        try:
            with open(self.schedule_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save publishing schedule: {e}")

    @staticmethod
    def make_slot_key(date_str: str, time_slot: str) -> str:
        """Constructs a unique identifier for a calendar slot."""
        clean_time = time_slot.replace(" ", "").replace(":", "")
        return f"{date_str}_{clean_time}"

    def get_schedule(self) -> Dict[str, Any]:
        """Returns the full publishing schedule dictionary."""
        return self._load()

    def get_slot(self, date_str: str, time_slot: str) -> Optional[Dict[str, Any]]:
        """Gets slot details by date and time slot."""
        key = self.make_slot_key(date_str, time_slot)
        return self._load().get(key)

    def schedule_short(
        self,
        date_str: str,
        time_slot: str,
        video_path: str,
        platforms: Optional[List[str]] = None,
        custom_title: Optional[str] = None,
        custom_caption: Optional[str] = None,
        custom_tags: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedules a short to a calendar date & time slot.
        Loads stored .meta.json caption and title automatically unless overridden.
        """
        v_path = Path(video_path)
        if not v_path.exists():
            return {"success": False, "error": f"Video file not found: {video_path}"}

        # 1. Retrieve stored content-accurate metadata from sidecar .meta.json
        stored_meta = exporter.get_clip_metadata(v_path)
        effective_title = custom_title or stored_meta.get("title") or v_path.stem
        effective_caption = custom_caption or stored_meta.get("instagram_caption") or stored_meta.get("caption") or effective_title
        effective_tags = custom_tags or stored_meta.get("hashtags") or "#shorts #viral #reels"

        chosen_platforms = platforms or ["youtube", "instagram"]
        slot_key = self.make_slot_key(date_str, time_slot)

        schedule = self._load()
        slot_data = {
            "slot_key": slot_key,
            "date": date_str,
            "time_slot": time_slot,
            "video_path": str(v_path),
            "video_name": v_path.name,
            "title": effective_title,
            "caption": effective_caption,
            "hashtags": effective_tags,
            "platforms": chosen_platforms,
            "status": "scheduled",  # scheduled | published | failed
            "scheduled_at": datetime.now().isoformat(),
            "published_at": None,
            "urls": {}
        }

        schedule[slot_key] = slot_data
        self._save(schedule)
        logger.info(f"Scheduled '{v_path.name}' to slot {slot_key} ({chosen_platforms})")

        return {"success": True, "slot": slot_data}

    def unschedule_slot(self, date_str: str, time_slot: str) -> bool:
        """Removes a scheduled video from a time slot."""
        slot_key = self.make_slot_key(date_str, time_slot)
        schedule = self._load()
        if slot_key in schedule:
            del schedule[slot_key]
            self._save(schedule)
            logger.info(f"Unscheduled slot: {slot_key}")
            return True
        return False

    def list_all_available_shorts(self) -> List[Dict[str, Any]]:
        """
        Scans workspace/output and workspace/downloads/viral_reels for 9:16 Shorts.
        Enriches each short with its stored .meta.json, size, and scheduling status.
        """
        schedule = self._load()
        scheduled_paths = {entry.get("video_path") for entry in schedule.values() if entry.get("video_path")}

        candidates: List[Path] = []
        # Search output directory
        if OUTPUT_DIR.exists():
            for p in OUTPUT_DIR.glob("*.mp4"):
                if p.is_file() and p.stat().st_size > 0:
                    candidates.append(p)

        # Search curated reels directory
        curated_dir = Path(DOWNLOADS_DIR) / "viral_reels"
        if curated_dir.exists():
            for p in curated_dir.glob("*.mp4"):
                if p.is_file() and p.stat().st_size > 0:
                    candidates.append(p)

        # De-duplicate
        unique_paths = list({p.resolve(): p for p in candidates}.values())
        unique_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        results = []
        for p in unique_paths:
            # Check if it is a 16:9 long video
            is_long = "long_" in p.name.lower() or "compilation" in p.name.lower()
            if is_long:
                continue

            meta = exporter.get_clip_metadata(p)
            str_path = str(p)
            is_scheduled = str_path in scheduled_paths

            # Extract viral score hint
            viral_score = meta.get("viral_score", 92)
            if not isinstance(viral_score, (int, float)):
                viral_score = 92

            size_mb = p.stat().st_size / (1024 * 1024)

            results.append({
                "path": str_path,
                "name": p.name,
                "stem": p.stem,
                "size_mb": round(size_mb, 2),
                "is_scheduled": is_scheduled,
                "title": meta.get("title") or p.stem,
                "caption": meta.get("instagram_caption") or meta.get("caption") or "",
                "hashtags": meta.get("hashtags") or "#shorts #viral #reels",
                "viral_score": int(viral_score),
                "mtime": p.stat().st_mtime
            })

        return results

    def list_unscheduled_shorts(self) -> List[Dict[str, Any]]:
        """Returns only the ready shorts that have not been scheduled yet."""
        return [s for s in self.list_all_available_shorts() if not s["is_scheduled"]]

    def auto_fill_week(self, start_date_str: Optional[str] = None) -> int:
        """
        Auto-populates empty upcoming calendar slots over the next 7 days
        with ready unscheduled viral shorts. Returns count of newly scheduled shorts.
        """
        unscheduled = self.list_unscheduled_shorts()
        if not unscheduled:
            return 0

        schedule = self._load()
        start = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else date.today()

        scheduled_count = 0
        u_idx = 0

        for day_offset in range(7):
            current_date = start + timedelta(days=day_offset)
            date_key = current_date.strftime("%Y-%m-%d")

            for slot_time in DAILY_SLOTS:
                if u_idx >= len(unscheduled):
                    break

                slot_key = self.make_slot_key(date_key, slot_time)
                if slot_key not in schedule:
                    short_item = unscheduled[u_idx]
                    self.schedule_short(
                        date_str=date_key,
                        time_slot=slot_time,
                        video_path=short_item["path"],
                        platforms=["youtube", "instagram"],
                        custom_title=short_item.get("title"),
                        custom_caption=short_item.get("caption"),
                        custom_tags=short_item.get("hashtags")
                    )
                    scheduled_count += 1
                    u_idx += 1

            if u_idx >= len(unscheduled):
                break

        return scheduled_count

    def publish_slot_now(self, slot_key: str) -> Dict[str, Any]:
        """
        Immediately publishes the video in the specified scheduled slot
        using stored .meta.json captions and titles.
        """
        schedule = self._load()
        slot = schedule.get(slot_key)
        if not slot:
            return {"success": False, "error": f"Slot '{slot_key}' not found in schedule."}

        v_path = Path(slot["video_path"])
        if not v_path.exists():
            return {"success": False, "error": f"Video deliverable missing: {v_path}"}

        platforms = slot.get("platforms", ["youtube", "instagram"])
        results = {}

        # 1. YouTube Shorts Upload
        if "youtube" in platforms:
            yt_res = publisher.publish_to_youtube(
                video_path=str(v_path),
                title=slot.get("title", v_path.stem),
                description=slot.get("caption", ""),
                tags=slot.get("hashtags", "")
            )
            results["youtube"] = yt_res
            if yt_res.get("success"):
                slot.setdefault("urls", {})["youtube"] = yt_res.get("url")

        # 2. Instagram Reels Upload
        if "instagram" in platforms:
            full_caption = f"{slot.get('caption', '')}\n\n{slot.get('hashtags', '')}".strip()
            ig_res = publisher.publish_to_instagram(
                video_url_or_path=str(v_path),
                caption=full_caption
            )
            results["instagram"] = ig_res
            if ig_res.get("success"):
                slot.setdefault("urls", {})["instagram"] = ig_res.get("url")

        # Update slot status
        has_success = any(r.get("success") for r in results.values() if isinstance(r, dict))
        slot["status"] = "published" if has_success else "failed"
        slot["published_at"] = datetime.now().isoformat()
        slot["publish_results"] = results

        schedule[slot_key] = slot
        self._save(schedule)

        return {"success": has_success, "slot": slot, "results": results}


# Global singleton instance
scheduler = ContentScheduler()
