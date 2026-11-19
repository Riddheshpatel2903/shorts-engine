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


# Singleton instance
workspace_cleaner = WorkspaceCleaner()
