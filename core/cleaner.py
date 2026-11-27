"""
Workspace and Disk Storage Cleaner for ViralShortsEngine.
Scans and cleans temporary audio files, ASS subtitles, fragmented yt-dlp downloads,
and accumulated multi-gigabyte source videos to keep disk usage light and fast.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List

from config import WORKSPACE_DIR, PROCESSING_DIR, DOWNLOADS_DIR, OUTPUT_DIR, LOGS_DIR

logger = logging.getLogger("ViralShortsEngine.Cleaner")


class WorkspaceCleaner:
    def __init__(self):
        self.processing_dir = Path(PROCESSING_DIR)
        self.downloads_dir = Path(DOWNLOADS_DIR)
        self.output_dir = Path(OUTPUT_DIR)
        self.logs_dir = Path(LOGS_DIR)

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Calculates space used across processing, downloads, and output directories.
        """
        temp_size = 0
        temp_count = 0
        downloads_size = 0
        downloads_count = 0
        output_size = 0
        output_count = 0
        video_files = []

        # Scan processing dir
        if self.processing_dir.exists():
            try:
                for f in self.processing_dir.iterdir():
                    if f.is_file():
                        sz = f.stat().st_size
                        temp_size += sz
                        temp_count += 1
            except Exception as e:
                logger.debug(f"Error scanning processing_dir: {e}")

        # Scan downloads dir
        if self.downloads_dir.exists():
            try:
                for f in self.downloads_dir.iterdir():
                    if f.is_file():
                        sz = f.stat().st_size
                        if f.suffix.lower() in [".part", ".ytdl", ".tmp"] or ".part-" in f.name:
                            temp_size += sz
                            temp_count += 1
                        else:
                            downloads_size += sz
                            downloads_count += 1
                            video_files.append({"name": f.name, "path": str(f), "size_mb": round(sz / (1024*1024), 1)})
            except Exception as e:
                logger.debug(f"Error scanning downloads_dir: {e}")

        # Scan output dir
        if self.output_dir.exists():
            try:
                for f in self.output_dir.iterdir():
                    if f.is_file() and f.suffix.lower() == ".mp4":
                        output_size += f.stat().st_size
                        output_count += 1
            except Exception as e:
                logger.debug(f"Error scanning output_dir: {e}")

        total_reclaimable_mb = (temp_size + downloads_size) / (1024 * 1024)

        return {
            "temp_size_mb": round(temp_size / (1024 * 1024), 2),
            "temp_count": temp_count,
            "downloads_size_mb": round(downloads_size / (1024 * 1024), 2),
            "downloads_size_gb": round(downloads_size / (1024 * 1024 * 1024), 2),
            "downloads_count": downloads_count,
            "download_files": sorted(video_files, key=lambda x: x["size_mb"], reverse=True),
            "output_size_mb": round(output_size / (1024 * 1024), 2),
            "output_count": output_count,
            "total_reclaimable_mb": round(total_reclaimable_mb, 2),
            "total_reclaimable_gb": round(total_reclaimable_mb / 1024, 2)
        }

    def clean_temporary_files(self) -> Dict[str, Any]:
        """
        Deletes all intermediate .wav audio slices, .ass subtitles, .part downloads,
        and .tmp files from processing and downloads folders.
        """
        deleted_count = 0
        freed_bytes = 0

        # Clean processing dir (.wav, .ass, .tmp, .ts, .json intermediate caches)
        if self.processing_dir.exists():
            try:
                for f in list(self.processing_dir.iterdir()):
                    if f.is_file():
                        try:
                            sz = f.stat().st_size
                            f.unlink()
                            deleted_count += 1
                            freed_bytes += sz
                        except Exception as e:
                            logger.warning(f"Could not delete temp file {f.name}: {e}")
            except Exception as e:
                logger.warning(f"Error accessing processing dir: {e}")

        # Clean fragmented downloads in downloads dir (.part, .ytdl)
        if self.downloads_dir.exists():
            try:
                for f in list(self.downloads_dir.iterdir()):
                    if f.is_file() and (f.suffix.lower() in [".part", ".ytdl", ".tmp"] or ".part-" in f.name):
                        try:
                            sz = f.stat().st_size
                            f.unlink()
                            deleted_count += 1
                            freed_bytes += sz
                        except Exception as e:
                            logger.warning(f"Could not delete partial download {f.name}: {e}")
            except Exception as e:
                logger.warning(f"Error accessing downloads dir: {e}")

        freed_mb = freed_bytes / (1024 * 1024)
        logger.info(f"Cleaned {deleted_count} temporary files, freed {freed_mb:.1f} MB.")
        return {
            "deleted_count": deleted_count,
            "freed_mb": round(freed_mb, 2),
            "freed_gb": round(freed_mb / 1024, 2)
        }

    def clean_all_downloads(self, preserve_test_sample: bool = True) -> Dict[str, Any]:
        """
        Deep Purge: Deletes all bulky downloaded source videos (.mp4, .mkv, .mov)
        from downloads_dir, reclaiming 15-20+ Gigabytes of storage immediately.
        """
        deleted_count = 0
        freed_bytes = 0

        if not self.downloads_dir.exists():
            return {"deleted_count": 0, "freed_mb": 0.0, "freed_gb": 0.0}

        try:
            for f in list(self.downloads_dir.iterdir()):
                if f.is_file():
                    if preserve_test_sample and f.name == "test_sample.mp4":
                        continue
                    try:
                        sz = f.stat().st_size
                        f.unlink()
                        deleted_count += 1
                        freed_bytes += sz
                        logger.info(f"Purged heavy video: {f.name} ({sz / (1024*1024):.1f} MB)")
                    except Exception as e:
                        logger.warning(f"Could not purge {f.name}: {e}")
        except Exception as e:
            logger.warning(f"Error purging downloads: {e}")

        freed_mb = freed_bytes / (1024 * 1024)
        return {
            "deleted_count": deleted_count,
            "freed_mb": round(freed_mb, 2),
            "freed_gb": round(freed_mb / 1024, 2)
        }

    def delete_single_file(self, file_path: str) -> bool:
        """Deletes a specific file if it exists."""
        try:
            p = Path(file_path)
            if p.exists() and p.is_file():
                p.unlink()
                return True
        except Exception as e:
            logger.warning(f"Failed to delete {file_path}: {e}")
        return False

    def list_generated_deliverables(self) -> List[Dict[str, Any]]:
        """
        Lists all finished, exported MP4 videos from output_dir with file details,
        size in MB, modification time, and categorization (Short vs Long Video).
        """
        deliverables = []
        if not self.output_dir.exists():
            return deliverables

        try:
            for f in self.output_dir.iterdir():
                if f.is_file() and f.suffix.lower() == ".mp4":
                    stat = f.stat()
                    sz_mb = round(stat.st_size / (1024 * 1024), 2)
                    is_long = "long" in f.name.lower() or "compilation" in f.name.lower() or "highlight" in f.name.lower()
                    
                    # Check for cover image thumbnail
                    cover_cand = f.with_suffix(".jpg")
                    cover_png = f.with_suffix(".png")
                    cover_path = str(cover_cand) if cover_cand.exists() else (str(cover_png) if cover_png.exists() else None)

                    deliverables.append({
                        "name": f.name,
                        "path": str(f),
                        "size_mb": sz_mb,
                        "mtime": stat.st_mtime,
                        "is_long_video": is_long,
                        "category": "🎞️ Long Format Video" if is_long else "🎬 Viral Short (9:16)",
                        "cover_path": cover_path
                    })
        except Exception as e:
            logger.warning(f"Error listing deliverables: {e}")

        # Sort by most recently generated first
        deliverables.sort(key=lambda x: x["mtime"], reverse=True)
        return deliverables

    def delete_single_deliverable(self, video_path: str) -> bool:
        """
        Deletes a specific generated video, its associated thumbnail preview,
        and its sidecar .meta.json file cleanly.
        """
        try:
            p = Path(video_path)
            if p.exists() and p.is_file():
                p.unlink()
                # Also delete associated thumbnail cover and metadata sidecar
                for thumb_ext in [".jpg", ".png", ".jpeg", ".meta.json"]:
                    thumb = p.with_suffix(thumb_ext)
                    if thumb.exists():
                        try:
                            thumb.unlink()
                        except Exception:
                            pass
                # Check for cover_ prefix thumbnail in the same folder
                cover_cand = p.parent / f"cover_{p.stem}.jpg"
                if cover_cand.exists():
                    try:
                        cover_cand.unlink()
                    except Exception:
                        pass
                logger.info(f"Deleted deliverable and sidecars: {p.name}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete deliverable {video_path}: {e}")
        return False

    def auto_purge_temp_cache(self, max_age_hours: float = 1.0) -> int:
        """
        Silent auto-cleaner: automatically purges temporary audio chunks, .ass files,
        and .part fragments older than max_age_hours or on startup to keep disk light.
        """
        purged = 0
        if not self.processing_dir.exists():
            return 0

        import time
        now = time.time()
        cutoff = now - (max_age_hours * 3600)

        try:
            for f in self.processing_dir.iterdir():
                if f.is_file():
                    # Purge temporary files
                    if f.suffix.lower() in [".wav", ".ass", ".tmp", ".ts", ".part"] or f.stat().st_mtime < cutoff:
                        try:
                            f.unlink()
                            purged += 1
                        except Exception:
                            pass
        except Exception:
            pass

        return purged


# Singleton instance
workspace_cleaner = WorkspaceCleaner()
