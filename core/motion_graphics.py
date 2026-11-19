"""
Motion Graphics & Screen Recording Highlight Editor Module.
Takes screen recordings, gameplay clips, OBS captures, or uploaded videos,
automatically detects high-energy moments (acoustic bursts, speech cadence acceleration),
and composites a polished 9:16 vertical Short with:
- Animated Top Hook Banner (Neon/Gradient Pill)
- Real-time Progress Bar
- Alex Hormozi Animated Karaoke Subtitles
- Dynamic 9:16 Auto-Crop Framing
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import PROCESSING_DIR, OUTPUT_DIR
from core.video_analyzer import VideoAnalyzer
from core.transcriber import AudioTranscriber
from core.moment_detector import MomentDetector
from core.clip_selector import ClipSelector
from core.subtitles import SubtitleGenerator
from core.exporter import VideoExporter
from core.ai_brain import ai_brain

logger = logging.getLogger("ViralShortsEngine.MotionGraphics")


class ScreenRecordingEditor:
    """Specialized engine for screen recordings and custom video highlight creation."""

    def __init__(self):
        self.analyzer = VideoAnalyzer()
        self.transcriber = AudioTranscriber()
        self.detector = MomentDetector()
        self.subtitle_gen = SubtitleGenerator()
        self.exporter = VideoExporter()

    def process_recording(
        self,
        video_path: str,
        niche: str = "GAMING",
        custom_hook_text: Optional[str] = None,
        subtitle_preset: str = "hormozi",
        target_duration: float = 35.0
    ) -> Dict[str, Any]:
        """
        End-to-end highlight extraction & motion graphic compositor for screen recordings:
        1. Ingests video & detects orientation / facecam
        2. Transcribes & computes multi-modal acoustic loudness spikes
        3. Isolates the #1 highlight moment
        4. Applies motion graphics & animated subtitles
        5. Generates high-converting social copy
        """
        src = Path(video_path)
        if not src.exists():
            raise FileNotFoundError(f"Source video not found: {video_path}")

        logger.info(f"Processing screen recording: {src.name}")

        # 1. Analyze Streams & Layout
        analysis = self.analyzer.analyze(str(src))
        probe = analysis.get("probe", {})
        dur = float(probe.get("duration", 30.0))

        # 2. Transcribe Audio
        scan_len = min(dur, 600.0) if dur > 0 else 180.0
        transcript = self.transcriber.transcribe(str(src), start_time=0.0, duration=scan_len)

        # 3. Detect Highlight Moments
        analyzed_segments = self.detector.analyze_moments(str(src), transcript)
        genre_map = {"GAMING": "gaming", "EDUCATION": "education", "GEOPOLITICS": "geopolitics"}
        selector = ClipSelector(min_duration=20.0, max_duration=55.0, target_duration=target_duration, genre_focus=genre_map.get(niche, "all"))
        candidates = selector.select_clips(analyzed_segments, num_shorts=3, genre_focus=genre_map.get(niche, "all"))

        if candidates:
            best_clip = candidates[0]
        else:
            clip_len = min(35.0, dur if dur > 0 else 35.0)
            best_clip = {
                "start": 0.0,
                "end": clip_len,
                "duration": clip_len,
                "viral_score": 90.0,
                "category": "SCREEN_RECORDING_HIGHLIGHT",
                "category_label": "⚡ Highlight Moment",
                "hook_text": custom_hook_text or "HIGHLIGHT MOMENT 🎯",
                "text": transcript.get("text", "")[:200],
                "audio_score": 85.0,
                "wpm": 140.0,
                "why_viral": "Screen recording highlight with high motion and audio activity.",
                "radar": {"Acoustic Peak": 85, "Speech Velocity": 80, "Hook Potency": 90, "Viral Resonance": 90}
            }

        # 4. Generate Subtitles with Top Hook Motion Banner
        hook_banner = custom_hook_text if custom_hook_text else best_clip.get("hook_text", "EPIC MOMENT 💥")
        clip_words = []
        for seg in transcript.get("segments", []):
            if seg.get("end", 0) < best_clip["start"] or seg.get("start", 0) > best_clip["end"]:
                continue
            for w in seg.get("words", []):
                if w.get("end", 0) >= best_clip["start"] and w.get("start", 0) <= best_clip["end"]:
                    clip_words.append(w)

        ass_path = PROCESSING_DIR / f"highlight_sub_{src.stem[:12]}.ass"
        self.subtitle_gen.generate_ass(
            clip_words=clip_words,
            clip_start=best_clip["start"],
            output_ass_path=ass_path,
            margin_v=320,
            font_size=72,
            style_preset=subtitle_preset
        )

        # Inject Top Hook Banner into ASS subtitle file as permanent banner header
        if hook_banner and ass_path.exists():
            try:
                with open(ass_path, "r", encoding="utf-8") as f:
                    ass_content = f.read()

                # Add top banner style and dialogue event
                banner_style = "\nStyle: HookBanner,Montserrat,52,&H00FFFFFF,&H000000FF,&H0000E5FF,&HE0000000,-1,0,0,0,100,100,0,0,3,4,2,8,20,20,120,1\n"
                if "[V4+ Styles]" in ass_content and "Style: HookBanner" not in ass_content:
                    ass_content = ass_content.replace("[V4+ Styles]\n", f"[V4+ Styles]{banner_style}")

                # Format time range for hook banner (visible during first 8 seconds or full clip)
                banner_dur = min(8.0, best_clip["duration"])
                b_start = "0:00:00.00"
                b_m = int(banner_dur // 60)
                b_s = banner_dur % 60
                b_end = f"0:{b_m:02d}:{b_s:05.2f}"
                banner_event = f"\nDialogue: 1,{b_start},{b_end},HookBanner,,0,0,0,,{{\\b1\\c&H00E5FF&}}⚡ {hook_banner.upper()} ⚡\n"
                
                if "[Events]" in ass_content:
                    ass_content += banner_event

                with open(ass_path, "w", encoding="utf-8") as f:
                    f.write(ass_content)
            except Exception as e:
                logger.warning(f"Could not inject hook banner into ASS: {e}")

        # 5. Render Vertical 9:16 Video
        clean_name = "".join([c if c.isalnum() else "_" for c in src.stem])[:25]
        out_fname = f"edit_{clean_name}_{int(best_clip['start'])}s.mp4"
        out_path = self.exporter.render_clip(
            source_path=str(src),
            clip_info=best_clip,
            layout_info=analysis["layout"],
            subtitle_path=ass_path if clip_words or hook_banner else None,
            output_filename=out_fname,
            template="AUTO"
        )

        # 6. Generate Viral Social Copy
        social_copy = ai_brain.generate_viral_metadata(
            clip_text=best_clip.get("text", "") or src.stem,
            niche=niche,
            title_hint=hook_banner
        )

        return {
            "output_path": str(out_path),
            "output_filename": out_fname,
            "clip_info": best_clip,
            "social_copy": social_copy,
            "analysis": analysis,
            "all_candidates": candidates
        }


# Singleton instance
motion_editor = ScreenRecordingEditor()
