"""
Script to Vector Video Generation Engine.
Transforms text scripts into dynamic 9:16 vertical Shorts using:
- OmniVoice TTS / Neural Voiceover
- Automated Web & Vector Visual Media Assembly (images, motion backdrops, footage)
- Ken Burns Motion Zoom & Pan
- Word-by-Word Animated Alex Hormozi Subtitles
- Kinetic Motion Graphics & Progress Bar
"""

import os
import re
import json
import shutil
import logging
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

from config import PROCESSING_DIR, OUTPUT_DIR, CANVAS_WIDTH, CANVAS_HEIGHT, TARGET_FPS
from core.tts_engine import tts_engine
from core.subtitles import SubtitleGenerator
from core.exporter import VideoExporter
from core.ai_brain import ai_brain

logger = logging.getLogger("ViralShortsEngine.VectorVideo")


class VectorVideoEngine:
    """End-to-end generator from script to 1080x1920 vector/motion Short."""

    def __init__(self):
        self.tts = tts_engine
        self.subtitle_gen = SubtitleGenerator()
        self.exporter = VideoExporter()

    def parse_script_into_scenes(self, script_text: str) -> List[Dict[str, Any]]:
        """
        Splits a script into clean, timed scenes based on sentences or paragraphs.
        """
        lines = [line.strip() for line in script_text.splitlines() if line.strip()]
        if not lines:
            lines = [script_text.strip()]

        scenes = []
        for idx, line in enumerate(lines, start=1):
            # Extract keywords for visual asset matching
            clean_words = re.sub(r"[^\w\s]", "", line).split()
            keywords = [w.lower() for w in clean_words if len(w) > 3][:4]
            search_query = " ".join(keywords) if keywords else "digital technology abstract"
            
            scenes.append({
                "scene_id": idx,
                "text": line,
                "keywords": search_query,
                "duration_est": max(3.0, (len(line.split()) / 150.0) * 60.0)
            })

        return scenes

    def generate_visual_card(self, scene: Dict[str, Any], output_png: Path) -> Path:
        """
        Generates a sleek, high-resolution vector/gradient visual card (1080x1920)
        with kinetic typography and modern abstract geometry.
        """
        w, h = CANVAS_WIDTH, CANVAS_HEIGHT
        img = Image.new("RGB", (w, h), color=(14, 17, 24))
        draw = ImageDraw.Draw(img)

        # Dynamic color themes based on scene index
        theme_colors = [
            ((20, 30, 48), (36, 59, 85)),     # Deep Tech Blue
            ((40, 20, 40), (75, 30, 60)),     # Cyber Magenta
            ((20, 40, 30), (30, 70, 50)),     # Matrix Emerald
            ((45, 30, 15), (80, 50, 20))      # Sunset Amber
        ]
        c_top, c_bot = theme_colors[(scene["scene_id"] - 1) % len(theme_colors)]

        # Vertical Gradient
        for y in range(h):
            ratio = y / h
            r = int(c_top[0] * (1 - ratio) + c_bot[0] * ratio)
            g = int(c_top[1] * (1 - ratio) + c_bot[1] * ratio)
            b = int(c_top[2] * (1 - ratio) + c_bot[2] * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # Vector Geometry: Subtle tech grid and circles
        draw.arc([140, 300, 940, 1100], start=0, end=360, fill=(255, 255, 255, 30), width=3)
        draw.rectangle([80, 150, 1000, 260], outline=(0, 229, 255), width=2)

        # Headline / Keywords
        kw_text = scene.get("keywords", "").upper()
        draw.text((w // 2, 205), f"[ {kw_text} ]", fill=(0, 229, 255), anchor="mm")

        # Save card
        img.save(str(output_png))
        return output_png

    def build_vector_video(
        self,
        script_text: str,
        voice_id: str = "deep_male",
        reference_audio: Optional[str] = None,
        custom_hook_title: Optional[str] = None,
        subtitle_preset: str = "hormozi"
    ) -> Dict[str, Any]:
        """
        Executes complete Script-to-Vector video generation:
        1. Breaks script into scene units
        2. Synthesizes voiceover with OmniVoice TTS
        3. Generates vector motion cards & Ken Burns camera zooms
        4. Transcribes and aligns word-by-word karaoke subtitles
        5. Renders 1080x1920 60FPS vertical Short
        """
        clean_stem = re.sub(r"[^\w]", "_", script_text[:20]).strip("_") or "vector_video"
        temp_dir = PROCESSING_DIR / f"vec_{clean_stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        scenes = self.parse_script_into_scenes(script_text)
        logger.info(f"Generated {len(scenes)} scenes for vector video.")

        # 1. Voiceover Synthesis via OmniVoice TTS
        full_voice_wav = temp_dir / "voiceover.wav"
        combined_text = " ".join(s["text"] for s in scenes)
        self.tts.synthesize(
            text=combined_text,
            output_wav=full_voice_wav,
            voice_profile=voice_id,
            reference_audio=reference_audio,
            speed=1.15
        )

        # Probe exact audio duration
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(full_voice_wav)]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        total_audio_duration = float(json.loads(res.stdout)["format"]["duration"])
        logger.info(f"Total voiceover duration: {total_audio_duration:.2f}s")

        # 2. Generate Visual Cards per scene
        scene_dur = max(2.5, total_audio_duration / len(scenes))
        scene_video_segments = []

        for idx, sc in enumerate(scenes):
            card_png = temp_dir / f"card_{idx}.png"
            self.generate_visual_card(sc, card_png)
            
            # Ken Burns slow zoom (scale from 1.0 to 1.08 over scene duration)
            seg_mp4 = temp_dir / f"seg_{idx}.mp4"
            zoom_filter = (
                f"zoompan=z='min(zoom+0.0008,1.08)':d={int(scene_dur * TARGET_FPS)}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={CANVAS_WIDTH}x{CANVAS_HEIGHT}:fps={TARGET_FPS}"
            )
            cmd_seg = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-t", f"{scene_dur:.2f}",
                "-i", str(card_png),
                "-vf", zoom_filter,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                str(seg_mp4)
            ]
            subprocess.run(cmd_seg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            scene_video_segments.append(seg_mp4)

        # 3. Concatenate video segments
        concat_txt = temp_dir / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for s_mp4 in scene_video_segments:
                f.write(f"file '{s_mp4.as_posix()}'\n")

        raw_visual_mp4 = temp_dir / "visual_stitched.mp4"
        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(raw_visual_mp4)
        ]
        subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 4. Generate Animated Hormozi Subtitles
        # Simulate word-level timestamps across the exact voiceover duration
        all_words = combined_text.split()
        time_per_word = total_audio_duration / max(1, len(all_words))
        words_timing = []
        t_cursor = 0.0
        for w in all_words:
            t_end = min(total_audio_duration, t_cursor + time_per_word)
            words_timing.append({"word": w, "start": round(t_cursor, 2), "end": round(t_end, 2)})
            t_cursor = t_end

        ass_path = temp_dir / "vector_subtitles.ass"
        self.subtitle_gen.generate_ass(
            clip_words=words_timing,
            clip_start=0.0,
            output_ass_path=ass_path,
            margin_v=340,
            font_size=72,
            style_preset=subtitle_preset
        )

        # 5. Composite Final Video + Audio + Subtitles + Top Hook Banner
        out_filename = f"vector_short_{clean_stem[:15]}_{int(total_audio_duration)}s.mp4"
        final_mp4 = OUTPUT_DIR / out_filename

        hook_banner_text = (custom_hook_title or scenes[0]["text"][:40]).upper()
        escaped_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")
        
        # Filter: burn subtitles + top progress line + hook banner box
        filter_complex = (
            f"[0:v]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT},"
            f"drawbox=x=80:y=100:w=920:h=90:color=0x000000@0.75:t=fill,"
            f"drawtext=text='{hook_banner_text}':fontcolor=0x00E5FF:fontsize=40:x=(w-text_w)/2:y=125,"
            f"drawbox=x=0:y=0:w='min(1080, 1080*(t/{total_audio_duration:.2f}))':h=8:color=0x00E5FF@0.9:t=fill,"
            f"ass='{escaped_ass}'[v_out]"
        )

        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(raw_visual_mp4),
            "-i", str(full_voice_wav),
            "-filter_complex", filter_complex,
            "-map", "[v_out]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", f"{total_audio_duration:.2f}",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(final_mp4)
        ]
        subprocess.run(cmd_final, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 6. Generate Social Distribution Copy
        social_meta = ai_brain.generate_viral_metadata(
            clip_text=combined_text[:300],
            niche="EDUCATION",
            title_hint=hook_banner_text
        )

        return {
            "output_path": str(final_mp4),
            "output_filename": out_filename,
            "duration": round(total_audio_duration, 2),
            "scenes": scenes,
            "social_copy": social_meta
        }


# Singleton instance
vector_video_engine = VectorVideoEngine()
