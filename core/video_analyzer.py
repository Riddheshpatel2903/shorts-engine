"""
Video Analyzer module.
Performs deep stream inspection via ffprobe and runs layout classification.
"""

import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from core.face_detector import FaceDetector

logger = logging.getLogger("ViralShortsEngine.VideoAnalyzer")


class VideoAnalyzer:
    def __init__(self):
        self.face_detector = FaceDetector()

    def probe_media(self, file_path: str) -> Dict[str, Any]:
        """
        Deep inspection of video and audio streams using ffprobe.
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(file_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            probe_data = json.loads(result.stdout)
            
            format_info = probe_data.get("format", {})
            streams = probe_data.get("streams", [])

            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

            width = int(video_stream.get("width", 1920)) if video_stream else 1920
            height = int(video_stream.get("height", 1080)) if video_stream else 1080
            format_duration = float(format_info.get("duration", 0))

            v_dur = float(video_stream.get("duration", format_duration)) if video_stream else 0.0
            a_dur = float(audio_stream.get("duration", format_duration)) if audio_stream else 0.0
            duration = min(v_dur, a_dur) if (v_dur > 0 and a_dur > 0) else format_duration

            # Calculate FPS
            fps = 30.0
            if video_stream:
                r_frame_rate = video_stream.get("r_frame_rate", "30/1")
                if "/" in r_frame_rate:
                    num, den = r_frame_rate.split("/")
                    fps = float(num) / max(1.0, float(den))
                else:
                    fps = float(r_frame_rate)

            is_truncated = False
            if v_dur > 0 and a_dur > 0 and abs(v_dur - a_dur) > 15.0:
                logger.warning(
                    f"Mismatched stream durations: video={v_dur:.1f}s, audio={a_dur:.1f}s. "
                    f"Effective usable duration capped at {duration:.1f}s."
                )
                if v_dur < a_dur * 0.8:
                    is_truncated = True

            return {
                "duration": round(duration, 2),
                "video_duration": round(v_dur, 2),
                "audio_duration": round(a_dur, 2),
                "is_truncated": is_truncated,
                "width": width,
                "height": height,
                "aspect_ratio": round(width / max(1, height), 2),
                "fps": round(fps, 2),
                "video_codec": video_stream.get("codec_name") if video_stream else None,
                "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
                "has_video": video_stream is not None,
                "has_audio": audio_stream is not None,
                "bitrate": format_info.get("bit_rate"),
                "size_bytes": format_info.get("size")
            }
        except Exception as e:
            logger.error(f"FFprobe inspection failed for {file_path}: {e}")
            raise

    def analyze(self, video_path: str) -> Dict[str, Any]:
        """
        Combines stream metadata probe and facial layout classification.
        """
        logger.info(f"Analyzing video streams and visual layout for: {video_path}")
        probe_info = self.probe_media(video_path)
        layout_info = self.face_detector.classify_source(video_path)

        return {
            "probe": probe_info,
            "layout": layout_info
        }
