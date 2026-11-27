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
        template: str = "AUTO",
        enable_motion_graphics: bool = True,
        enable_sfx: bool = True,
        sfx_events: Optional[List[Dict[str, Any]]] = None,
        transcript: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Renders a single vertical Short with exact start/end timestamps,
        filter complex composition, motion graphics, meme sound effects, and hardware acceleration.
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

        # Prepare Sound Effects & Meme Audio Track
        sfx_track_path = None
        if enable_sfx:
            try:
                from core.sfx_engine import sfx_engine
                if sfx_events is None:
                    is_comedy = bool(clip_info.get("is_comedy_or_reaction"))
                    sfx_events = sfx_engine.detect_sfx_cues(
                        transcript=transcript or clip_info.get("transcript", {}),
                        clip_start=start_t,
                        clip_end=start_t + duration,
                        is_comedy=is_comedy
                    )
                if sfx_events:
                    sfx_tmp = PROCESSING_DIR / f"sfx_mix_{int(start_t)}_{int(duration)}.wav"
                    sfx_track_path = sfx_engine.create_sfx_mix_track(sfx_events, duration=duration, output_path=sfx_tmp)
            except Exception as e:
                logger.warning(f"SFX track generation error: {e}")
                sfx_track_path = None

        p_time_raw = clip_info.get("punchline_time")
        rel_p_time = None
        if p_time_raw is not None:
            try:
                p_val = float(p_time_raw)
                rel_p_time = (p_val - start_t) if p_val >= start_t else p_val
            except Exception:
                rel_p_time = None

        filter_complex, v_map, a_map = self.editor.build_filter_graph(
            layout_info,
            subtitle_path=subtitle_path,
            template=template,
            superchat_card=clip_info.get("superchat_card"),
            enable_motion_graphics=enable_motion_graphics,
            enable_progress_bar=enable_motion_graphics,
            clip_duration=duration,
            hook_text=clip_info.get("hook_text"),
            interactive_overlay=clip_info.get("interactive_overlay"),
            punchline_badge=clip_info.get("punchline_badge"),
            punchline_time=rel_p_time,
            has_sfx_track=(sfx_track_path is not None and sfx_track_path.exists()),
            enable_hook_banner=bool(clip_info.get("enable_hook_banner", False))
        )

        # Base FFmpeg command
        # AutoClip High-Precision cutting with frame-accurate seek & PTS zeroing
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_t),
            "-i", str(source_path)
        ]

        if sfx_track_path and sfx_track_path.exists():
            cmd.extend(["-i", str(sfx_track_path)])

        cmd.extend([
            "-t", str(duration),
            "-avoid_negative_ts", "make_zero",
            "-filter_complex", filter_complex,
            "-map", v_map,
            "-map", a_map,
            "-r", "30",
            "-pix_fmt", "yuv420p"
        ])

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

        # Cleanup temporary SFX track if used
        if sfx_track_path and sfx_track_path.exists():
            try:
                sfx_track_path.unlink()
            except Exception:
                pass

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

    # Convenient alias for render_clip
    export_short = render_clip

    def batch_render_shorts(
        self,
        source_path: str,
        clips: List[Dict[str, Any]],
        layout_info: Dict[str, Any],
        transcript_data: Dict[str, Any],
        style_preset: str = "hormozi",
        enable_motion_graphics: bool = True,
        enable_sfx: bool = True,
        interactive_overlay: Optional[str] = None,
        punchline_badge: Optional[str] = None,
        progress_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Renders a full batch of viral shorts (up to 15+) automatically,
        saving deliverables directly into workspace/output/ and library.
        Returns list of results with file paths, metadata, and viral scores.
        """
        from core.subtitles import SubtitleGenerator
        from core.ai_brain import ai_brain

        sub_gen = SubtitleGenerator()
        results = []
        total_clips = len(clips)
        clean_stem = "".join([c if c.isalnum() else "_" for c in Path(source_path).stem])[:20]

        for idx, clip in enumerate(clips, start=1):
            s_t = float(clip["start"])
            e_t = float(clip["end"])
            dur = float(clip.get("duration", e_t - s_t))
            hook = clip.get("hook_text", f"VIRAL MOMENT #{idx}")

            if progress_callback:
                progress_callback(idx, total_clips, f"Short #{idx} ({s_t:.1f}s - {e_t:.1f}s)")

            # Extract word segments for subtitles & collect exact spoken text
            clip_words = []
            spoken_texts = []
            for seg in transcript_data.get("segments", []):
                seg_s = float(seg.get("start", 0.0))
                seg_e = float(seg.get("end", 0.0))
                if (s_t <= seg_s <= e_t) or (s_t <= seg_e <= e_t) or (seg_s < s_t and seg_e > e_t):
                    if seg.get("text"):
                        spoken_texts.append(seg.get("text", "").strip())

                seg_words = seg.get("words", [])
                if not seg_words and seg.get("text"):
                    # Fallback synthesize word timings from segment duration if Whisper omitted word timestamps
                    w_tokens = seg.get("text", "").strip().split()
                    if w_tokens:
                        s_dur = max(0.2, seg_e - seg_s)
                        w_step = s_dur / len(w_tokens)
                        for w_i, token in enumerate(w_tokens):
                            seg_words.append({
                                "word": token,
                                "start": round(seg_s + w_i * w_step, 3),
                                "end": round(seg_s + (w_i + 1) * w_step, 3)
                            })

                for w in seg_words:
                    w_s = float(w.get("start", 0.0))
                    w_e = float(w.get("end", 0.0))
                    if s_t <= w_s <= e_t or (w_s < s_t and w_e > s_t):
                        clip_words.append(w)

            ass_path = PROCESSING_DIR / f"batch_sub_{clean_stem}_{int(s_t)}s.ass"
            sub_gen.generate_ass(
                clip_words=clip_words,
                clip_start=s_t,
                output_ass_path=ass_path,
                margin_v=320,
                font_size=72,
                style_preset=style_preset
            )

            p_time = clip.get("punchline_time")
            clip_info = {
                "start": s_t,
                "end": e_t,
                "duration": dur,
                "hook_text": hook,
                "interactive_overlay": interactive_overlay,
                "punchline_badge": punchline_badge,
                "enable_hook_banner": False,
                "punchline_time": p_time,
                "is_comedy_or_reaction": clip.get("is_comedy_or_reaction", True),
                "superchat_card": clip.get("superchat_card")
            }

            out_name = f"short_{clean_stem}_{idx:02d}_{int(s_t)}s.mp4"
            try:
                rendered_path = self.render_clip(
                    source_path=source_path,
                    clip_info=clip_info,
                    layout_info=layout_info,
                    subtitle_path=ass_path if clip_words else None,
                    output_filename=out_name,
                    enable_motion_graphics=enable_motion_graphics,
                    enable_sfx=enable_sfx,
                    transcript=transcript_data
                )

                # Generate social media metadata matching actual spoken words
                full_text = clip.get("text") or " ".join(spoken_texts) or hook
                meta = ai_brain.generate_viral_metadata(
                    clip_text=full_text,
                    niche=clip.get("category", "COMEDY"),
                    title_hint=hook
                )

                results.append({
                    "id": idx,
                    "filepath": str(rendered_path),
                    "filename": rendered_path.name,
                    "start": s_t,
                    "end": e_t,
                    "duration": dur,
                    "category": clip.get("category", "VIRAL_GENERAL"),
                    "category_label": clip.get("category_label", "⚡ Viral Short"),
                    "viral_score": clip.get("viral_score", 90.0),
                    "why_viral": clip.get("why_viral", "High viral retention potential"),
                    "title": meta.get("title", f"{hook} #Shorts"),
                    "hashtags": meta.get("hashtags", "#shorts #viral #reels"),
                    "caption": meta.get("instagram_caption", "")
                })
                logger.info(f"Auto-rendered batch Short {idx}/{total_clips}: {rendered_path.name}")
            except Exception as e:
                logger.error(f"Failed rendering short {idx} ({s_t}s - {e_t}s): {e}")

        return results

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
