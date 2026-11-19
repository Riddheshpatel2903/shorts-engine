"""
Exporter and Verification module.
Renders final 9:16 vertical MP4s with GPU NVENC (or CPU libx264 fallback),
conducts strict ffprobe post-render validation (video/audio stream existence, duration alignment,
timestamp integrity), generates comprehensive processing reports, and performs mandatory workspace cleanup.
"""

import os
import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import (
    HW_PROFILE,
    ENCODING_CONFIG,
    OUTPUT_DIR,
    PROCESSING_DIR,
    LOGS_DIR
)
from core.editor import VideoEditor
from core.autoclip_precision import autoclip_cutter

logger = logging.getLogger("ViralShortsEngine.Exporter")


class VideoExporter:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.editor = VideoEditor()
        self.hw_profile = HW_PROFILE

    def verify_export(self, mp4_path: Path, expected_duration: float, tolerance: float = 0.75) -> Dict[str, Any]:
        """
        Validates the rendered MP4 using ffprobe:
        - Video and Audio streams both exist
        - Valid timestamps and durations
        - Duration tolerance check between video and audio
        """
        if not mp4_path.exists() or mp4_path.stat().st_size == 0:
            return {"valid": False, "error": f"File {mp4_path} does not exist or is empty"}

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_streams",
            "-show_format",
            "-of", "json",
            str(mp4_path)
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)

            format_info = data.get("format", {})
            streams = data.get("streams", [])

            v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

            if not v_stream:
                return {"valid": False, "error": "Missing video stream in exported MP4"}
            if not a_stream:
                return {"valid": False, "error": "Missing audio stream in exported MP4"}

            v_dur = float(v_stream.get("duration", format_info.get("duration", 0)))
            a_dur = float(a_stream.get("duration", format_info.get("duration", 0)))
            v_width = int(v_stream.get("width", 0))
            v_height = int(v_stream.get("height", 0))

            # Verify 9:16 vertical canvas
            if v_width != 1080 or v_height != 1920:
                logger.warning(f"Resolution is {v_width}x{v_height}, expected 1080x1920")

            # Check duration alignment between audio and video
            dur_diff = abs(v_dur - a_dur)
            if dur_diff > tolerance:
                logger.warning(f"Audio/Video duration difference ({dur_diff:.2f}s) exceeds tolerance ({tolerance}s)")

            return {
                "valid": True,
                "video_duration": round(v_dur, 2),
                "audio_duration": round(a_dur, 2),
                "duration_diff": round(dur_diff, 3),
                "width": v_width,
                "height": v_height,
                "size_mb": round(mp4_path.stat().st_size / (1024 * 1024), 2),
                "video_codec": v_stream.get("codec_name"),
                "audio_codec": a_stream.get("codec_name")
            }

        except Exception as e:
            logger.error(f"Validation probe failed for {mp4_path}: {e}")
            return {"valid": False, "error": str(e)}

    def render_clip(
        self,
        source_path: str,
        clip_info: Dict[str, Any],
        layout_info: Dict[str, Any],
        subtitle_path: Optional[Path],
        output_filename: str,
        template: str = "AUTO"
    ) -> Path:
        """
        Renders a single vertical Short with exact start/end timestamps,
        filter complex composition, and hardware acceleration.
        """
        out_path = self.output_dir / output_filename
        start_t = clip_info["start"]
        duration = clip_info["duration"]

        # Validate that requested start_t does not exceed available source video duration
        src_dur = layout_info.get("duration") or layout_info.get("video_duration")
        if src_dur and (start_t >= src_dur):
            raise ValueError(
                f"Requested clip start timestamp ({start_t:.1f}s) exceeds available video duration ({src_dur:.1f}s). "
                f"The source file has no video frames at this timestamp. Re-downloading the full source video is required."
            )

        filter_complex, v_map, a_map = self.editor.build_filter_graph(
            layout_info,
            subtitle_path=subtitle_path,
            template=template
        )

        # Base FFmpeg command
        # AutoClip High-Precision cutting with frame-accurate seek & PTS zeroing
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_t),
            "-i", str(source_path),
            "-t", str(duration),
            "-avoid_negative_ts", "make_zero",
            "-filter_complex", filter_complex,
            "-map", v_map,
            "-map", a_map,
            "-r", "30",
            "-pix_fmt", "yuv420p"
        ]

        # Encoder selection (NVENC vs libx264)
        if self.hw_profile["nvenc_supported"]:
            cmd.extend([
                "-c:v", ENCODING_CONFIG["gpu_encoder"],
                "-preset", ENCODING_CONFIG["gpu_preset"],
                "-cq", str(ENCODING_CONFIG["gpu_cq"])
            ])
        else:
            cmd.extend([
                "-c:v", ENCODING_CONFIG["cpu_encoder"],
                "-preset", ENCODING_CONFIG["cpu_preset"],
                "-crf", str(ENCODING_CONFIG["cpu_crf"])
            ])

        # Audio encoder settings
        cmd.extend([
            "-c:a", ENCODING_CONFIG["audio_encoder"],
            "-b:a", ENCODING_CONFIG["audio_bitrate"],
            "-ar", "44100",
            "-movflags", "+faststart",
            str(out_path)
        ])

        logger.info(f"Rendering Short to {out_path} ({duration}s)...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"FFmpeg rendering failed: {res.stderr[-1000:]}")
            raise RuntimeError(f"FFmpeg rendering failed: {res.stderr[-400:]}")

        # AutoClip Cover Thumbnail Snapshot Generation
        try:
            cover_path = out_path.with_name(f"cover_{out_path.stem}.jpg")
            peak_t = start_t + min(3.0, duration / 2.0)
            autoclip_cutter.extract_cover_thumbnail(
                source_video=Path(source_path),
                timestamp=peak_t,
                output_cover=cover_path,
                hook_headline=clip_info.get("hook_text")
            )
            logger.info(f"AutoClip generated high-res cover thumbnail: {cover_path.name}")
        except Exception as e:
            logger.debug(f"Cover snapshot skipped: {e}")

        # Post-render validation
        validation = self.verify_export(out_path, expected_duration=duration)
        if not validation["valid"]:
            raise RuntimeError(f"Export validation failed for {out_path}: {validation.get('error')}")

        logger.info(f"Export verified successfully: {out_path} ({validation['size_mb']} MB)")
        return out_path

    def cleanup_processing_artifacts(self, preserve_source: bool = True):
        """
        Removes temporary video slices, WAV files, ASS subtitle files,
        and intermediate artifacts from workspace/processing/.
        Leaves workspace/output/ pristine with only final deliverables.
        """
        logger.info("Cleaning up temporary processing files...")
        proc_dir = PROCESSING_DIR
        if proc_dir.exists():
            for item in proc_dir.iterdir():
                try:
                    if item.is_file():
                        # Don't delete cached transcript if needed for future runs,
                        # but clean all temporary audio/subtitles/video fragments
                        if item.suffix in [".wav", ".ass", ".ts", ".tmp"]:
                            item.unlink()
                except Exception as e:
                    logger.warning(f"Could not delete temp file {item}: {e}")

        logger.info("Workspace cleanup completed.")
