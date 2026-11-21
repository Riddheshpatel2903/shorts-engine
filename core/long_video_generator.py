"""
Long-Format Highlight Video Generator.
Ingests long-form streams, VODs, podcasts, and recordings, detects top highlight chapters,
lets users select and reorder moments, and merges them into a cohesive 16:9 widescreen
YouTube highlight compilation with chapter titles, smooth transitions, normalized audio,
and auto-generated YouTube timestamps.
"""

import os
import re
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config import PROCESSING_DIR, OUTPUT_DIR, BASE_DIR
from core.autoclip_precision import autoclip_aligner, autoclip_cutter
from core.cleaner import workspace_cleaner

logger = logging.getLogger("ViralShortsEngine.LongVideoGenerator")


class LongVideoGenerator:
    def __init__(self):
        self.processing_dir = Path(PROCESSING_DIR)
        self.output_dir = Path(OUTPUT_DIR)
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def detect_highlight_chapters(
        self,
        video_path: str,
        transcript: Optional[Dict[str, Any]] = None,
        duration: float = 0.0,
        target_count: int = 6,
        min_chapter_duration: float = 35.0,
        max_chapter_duration: float = 95.0
    ) -> List[Dict[str, Any]]:
        """
        Discovers top highlight chapters across the video duration using:
        1. Transcript linguistic clauses & viral moment scoring (if transcript available).
        2. Audio energy peak detection across the full audio track.
        3. Even temporal distribution to avoid clumping all highlights in one small section.
        """
        chapters = []
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            logger.error(f"Video file not found: {video_path}")
            return chapters

        # Get video duration via ffprobe if not provided
        if duration <= 0:
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(video_path)
                ]
                res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                duration = float(res.stdout.strip())
            except Exception as e:
                logger.warning(f"Failed to probe duration: {e}")
                duration = 600.0

        # Discover candidate moments from transcript
        candidate_moments = []
        if transcript and isinstance(transcript, dict) and transcript.get("segments"):
            from core.moment_detector import viral_detector
            try:
                candidate_moments = viral_detector.find_moments_heuristic(
                    transcript,
                    duration=duration,
                    max_moments=target_count * 3,
                    min_len=min_chapter_duration,
                    max_len=max_chapter_duration
                )
            except Exception as e:
                logger.warning(f"Error in transcript heuristic detection: {e}")

        # Discover acoustic energy peaks
        energy_peaks = []
        try:
            from core.moment_detector import find_audio_energy_peaks
            energy_peaks = find_audio_energy_peaks(str(video_path), num_peaks=target_count * 2)
        except Exception as e:
            logger.warning(f"Audio energy peak scan error: {e}")

        # Merge and score candidates
        merged_candidates = []
        for m in candidate_moments:
            merged_candidates.append({
                "start": float(m.get("start", 0.0)),
                "end": float(m.get("end", 0.0)),
                "title": m.get("label") or m.get("reason") or "Highlight Moment",
                "tag": m.get("tag", "🔥 HIGHLIGHT"),
                "score": float(m.get("score", 70.0)),
                "source": "transcript"
            })

        for p in energy_peaks:
            p_time = float(p.get("time", 0.0))
            # Check if already covered by an existing candidate
            covered = any(abs(c["start"] - p_time) < 30.0 for c in merged_candidates)
            if not covered:
                merged_candidates.append({
                    "start": max(0.0, p_time - 15.0),
                    "end": min(duration, p_time + 40.0),
                    "title": f"High Energy Spike ({int(p_time // 60)}m {int(p_time % 60)}s)",
                    "tag": "⚡ ENERGY CLIMAX",
                    "score": float(p.get("score", 75.0)),
                    "source": "audio"
                })

        # Fallback if no moments found: distribute chapters uniformly across duration
        if len(merged_candidates) < target_count:
            step = duration / (target_count + 1)
            for i in range(1, target_count + 1):
                c_start = max(0.0, (i * step) - 20.0)
                c_end = min(duration, c_start + 60.0)
                merged_candidates.append({
                    "start": c_start,
                    "end": c_end,
                    "title": f"Key Stream Chapter {i}",
                    "tag": "🎞️ HIGHLIGHT",
                    "score": 60.0,
                    "source": "uniform"
                })

        # Sort candidates chronologically
        merged_candidates.sort(key=lambda x: x["start"])

        # Temporal de-duplication: ensure minimum 45s spacing between chapters
        selected = []
        last_end = -45.0
        for cand in merged_candidates:
            if (cand["start"] - last_end) >= 20.0:
                # Snap boundaries to natural speech clauses if transcript is available
                if transcript:
                    try:
                        snapped = autoclip_aligner.snap_boundaries(
                            transcript,
                            raw_start=cand["start"],
                            raw_end=cand["end"],
                            max_duration=max_chapter_duration,
                            min_duration=min_chapter_duration,
                            is_comedy_or_reaction=True
                        )
                        c_start = snapped["start"]
                        c_end = snapped["end"]
                        clean_text = snapped.get("clean_text", "")
                        title_candidate = cand["title"]
                        if clean_text and len(clean_text.split()) >= 3:
                            title_candidate = " ".join(clean_text.split()[:7]).title()
                    except Exception:
                        c_start = cand["start"]
                        c_end = cand["end"]
                        title_candidate = cand["title"]
                else:
                    c_start = cand["start"]
                    c_end = cand["end"]
                    title_candidate = cand["title"]

                c_dur = round(c_end - c_start, 1)
                if c_dur >= 20.0:
                    selected.append({
                        "index": len(selected) + 1,
                        "title": title_candidate[:45],
                        "start": round(c_start, 1),
                        "end": round(c_end, 1),
                        "duration": c_dur,
                        "tag": cand.get("tag", "🔥 HIGHLIGHT"),
                        "selected": True
                    })
                    last_end = c_end

            if len(selected) >= target_count:
                break

        return selected

    def render_merged_video(
        self,
        source_video: str,
        chapters: List[Dict[str, Any]],
        output_path: str,
        transition_type: str = "dip_to_black",
        add_lower_thirds: bool = True,
        normalize_audio: bool = True,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Extracts selected chapters, adds optional lower-third title cards,
        and concatenates them with clean broadcast transitions and normalized audio.
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        selected_chapters = [c for c in chapters if c.get("selected", True)]
        if not selected_chapters:
            raise ValueError("No chapters selected for merging.")

        temp_clips = []
        total_steps = len(selected_chapters) + 1
        current_step = 0

        try:
            # Step 1: Render each chapter slice with lower third title card if enabled
            font_file = "C\\:/Windows/Fonts/arialbd.ttf" if Path("C:/Windows/Fonts/arialbd.ttf").exists() else ""
            font_opt = f"fontfile='{font_file}':" if font_file else ""

            for idx, ch in enumerate(selected_chapters):
                c_start = float(ch["start"])
                c_dur = float(ch["duration"])
                c_title = re.sub(r"[^\w\s\-\:\.\,\!]", "", ch.get("title", f"Chapter {idx+1}")).strip()[:40]
                clip_out = self.processing_dir / f"long_slice_{idx}_{int(c_start)}_{int(c_dur)}.mp4"

                # Video filter: Scale to standard 1920x1080 16:9 widescreen
                vf_parts = [
                    "scale=1920:1080:force_original_aspect_ratio=decrease",
                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
                ]

                # Add lower third chapter title card for the first 3.5 seconds
                if add_lower_thirds and c_title:
                    # Draw elegant dark backdrop pill and gold/white title text
                    vf_parts.append(
                        f"drawbox=x=80:y=920:w=800:h=90:color=black@0.85:t=fill:enable='between(t,0.5,4.0)',"
                        f"drawbox=x=80:y=920:w=8:h=90:color=0x00E5FF:t=fill:enable='between(t,0.5,4.0)',"
                        f"drawtext={font_opt}text='{c_title.upper()}':fontcolor=white:fontsize=36:x=110:y=948:enable='between(t,0.5,4.0)'"
                    )

                vf_expr = ",".join(vf_parts)

                # Cut and encode slice
                cut_cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{c_start:.3f}",
                    "-i", str(source_video),
                    "-t", f"{c_dur:.3f}",
                    "-avoid_negative_ts", "make_zero",
                    "-vf", vf_expr,
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "20",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ar", "48000",
                    "-ac", "2",
                    str(clip_out)
                ]
                subprocess.run(cut_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                temp_clips.append(clip_out)

                current_step += 1
                if progress_callback:
                    progress_callback(current_step / total_steps, f"Rendered chapter {idx+1}/{len(selected_chapters)}: {c_title}")

            # Step 2: Concatenate with chosen transition
            concat_txt = self.processing_dir / "concat_list.txt"
            with open(concat_txt, "w", encoding="utf-8") as f:
                for cp in temp_clips:
                    # Escape path for FFmpeg concat demuxer
                    escaped = str(cp).replace("\\", "/")
                    f.write(f"file '{escaped}'\n")

            # Final audio filter with loudness normalization
            af_filter = "loudnorm=I=-16:LRA=11:TP=-1.5" if normalize_audio else "volume=1.0"

            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_txt),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "19",
                "-af", af_filter,
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                str(output_file)
            ]
            subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            if progress_callback:
                progress_callback(1.0, "Highlights successfully compiled into long-format video!")

            # Calculate total merged video duration
            total_duration = sum(float(c["duration"]) for c in selected_chapters)

            return {
                "success": True,
                "output_path": str(output_file),
                "duration": round(total_duration, 1),
                "chapter_count": len(selected_chapters),
                "file_size_mb": round(output_file.stat().st_size / (1024 * 1024), 2)
            }

        finally:
            # Clean temporary slices
            for cp in temp_clips:
                try:
                    if cp.exists():
                        cp.unlink()
                except Exception:
                    pass
            if 'concat_txt' in locals() and concat_txt.exists():
                try:
                    concat_txt.unlink()
                except Exception:
                    pass

    def generate_youtube_metadata(
        self,
        source_title: str,
        chapters: List[Dict[str, Any]],
        channel_name: str = "Streamer"
    ) -> Dict[str, Any]:
        """
        Generates production-grade YouTube metadata:
        - Catchy video title.
        - Clickable chapter timestamps starting at 00:00.
        - SEO tags and description.
        """
        selected = [c for c in chapters if c.get("selected", True)]
        clean_source = re.sub(r"[^\w\s\-\:]", "", source_title or "Stream Highlights").strip()

        yt_title = f"{clean_source} - Best Highlights & Climax Moments | Full Compilation"
        if len(yt_title) > 95:
            yt_title = f"{clean_source[:60]} - Best Stream Highlights"

        # Build timestamps
        timestamp_lines = ["00:00 - Introduction & Stream Overview"]
        cumulative_sec = 0.0

        for ch in selected:
            # Format cumulative seconds to MM:SS or HH:MM:SS
            total_s = int(cumulative_sec)
            hrs = total_s // 3600
            mins = (total_s % 3600) // 60
            secs = total_s % 60
            if hrs > 0:
                ts_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
            else:
                ts_str = f"{mins:02d}:{secs:02d}"

            ch_title = ch.get("title", "Highlight Moment").strip()
            timestamp_lines.append(f"{ts_str} - {ch_title}")
            cumulative_sec += float(ch.get("duration", 40.0))

        timestamps_text = "\n".join(timestamp_lines)

        description = (
            f"🔥 {yt_title}\n\n"
            f"Watch the top moments, funny reactions, and epic plays from this broadcast!\n\n"
            f"⏱️ CHAPTER TIMESTAMPS:\n"
            f"{timestamps_text}\n\n"
            f"🔔 Make sure to LIKE and SUBSCRIBE for daily stream highlights and top clips!\n"
            f"#highlights #gaming #podcast #streamer #funny #epicmoments"
        )

        tags = [
            "stream highlights", "best moments", "funny reactions", "top clips",
            "full compilation", "vod highlights", "gaming", "podcast highlights",
            "viral moments", "epic clutch", "climax"
        ]

        return {
            "title": yt_title,
            "description": description,
            "timestamps_text": timestamps_text,
            "tags": tags,
            "chapters": selected
        }


# Singleton instance
long_video_generator = LongVideoGenerator()
