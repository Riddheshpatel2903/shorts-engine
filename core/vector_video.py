"""
Vector & Motion Video Studio Generation Engine.
Transforms text scripts into cinematic 1080x1920 vertical Shorts featuring:
- Neural Edge TTS human voiceover (natural pauses & high retention)
- Dynamic neon cyber graphic cards with tech grid and corner brackets
- Word-by-word animated pop karaoke subtitles (Alex Hormozi style)
- Sleek cyber glowing borders, progress bar & top hook banner
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

from config import PROCESSING_DIR, OUTPUT_DIR, CANVAS_WIDTH, CANVAS_HEIGHT, BASE_DIR
from core.tts_engine import tts_engine
from core.subtitles import SubtitleGenerator
from core.exporter import VideoExporter
from core.ai_brain import ai_brain

logger = logging.getLogger("ViralShortsEngine.VectorVideo")


class VectorVideoEngine:
    """End-to-end generator from script to 1080x1920 animated motion Short."""

    def __init__(self):
        self.tts = tts_engine
        self.subtitle_gen = SubtitleGenerator()
        self.exporter = VideoExporter()

    def parse_script_into_scenes(self, script_text: str) -> List[Dict[str, Any]]:
        """Splits a script into distinct narrative scene beats."""
        raw_lines = [line.strip() for line in script_text.splitlines() if line.strip()]
        if not raw_lines:
            raw_lines = [script_text.strip()]

        scenes = []
        for idx, line in enumerate(raw_lines, start=1):
            clean_words = re.sub(r"[^\w\s]", "", line).split()
            keywords = [w.upper() for w in clean_words if len(w) > 3][:3]
            kw_display = " • ".join(keywords) if keywords else "EXCLUSIVE UPDATE"

            scenes.append({
                "scene_id": idx,
                "text": line,
                "keywords": kw_display,
                "duration_est": max(3.0, (len(clean_words) / 140.0) * 60.0)
            })
        return scenes

    def generate_scene_card(self, scene: Dict[str, Any], output_png: Path, scene_index: int, total_scenes: int) -> Path:
        """
        Generates a high-resolution 1080x1920 graphic card with cyber glowing borders,
        neon accents, scene counters, and bold keyword banners.
        """
        w, h = CANVAS_WIDTH, CANVAS_HEIGHT
        img = Image.new("RGBA", (w, h), color=(10, 12, 18, 255))
        draw = ImageDraw.Draw(img)

        # Dynamic neon color palettes based on scene
        palettes = [
            ((0, 229, 255), (14, 25, 45)),    # Cyan / Cyber Blue
            ((255, 46, 99), (45, 12, 28)),    # Electric Neon Pink
            ((0, 230, 118), (12, 40, 24)),    # Matrix Neon Emerald
            ((255, 171, 0), (45, 30, 10)),    # Solar Amber / Gold
            ((179, 136, 255), (30, 15, 48))   # Cyber Purple
        ]
        neon_color, bg_color = palettes[(scene_index - 1) % len(palettes)]

        # 1. Subtle Radial / Gradient Glow
        for y in range(0, h, 2):
            ratio = y / h
            r = int(bg_color[0] * (1 - ratio * 0.5))
            g = int(bg_color[1] * (1 - ratio * 0.5))
            b = int(bg_color[2] * (1 - ratio * 0.5))
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255), width=2)

        # 2. Tech Grid lines (vertical and horizontal subtle ambient lines)
        grid_alpha = (255, 255, 255, 15)
        for gx in range(60, w, 120):
            draw.line([(gx, 0), (gx, h)], fill=grid_alpha, width=1)
        for gy in range(80, h, 140):
            draw.line([(0, gy), (w, gy)], fill=grid_alpha, width=1)

        # 3. Center Graphic Showcase Card (1080x1920 layout)
        card_box = [70, 380, w - 70, 1420]
        draw.rectangle(card_box, fill=(15, 18, 26, 230), outline=neon_color, width=3)

        # Decorative corner brackets
        corner_len = 35
        # Top-left
        draw.line([(60, 370), (60 + corner_len, 370)], fill=neon_color, width=5)
        draw.line([(60, 370), (60, 370 + corner_len)], fill=neon_color, width=5)
        # Top-right
        draw.line([(w - 60, 370), (w - 60 - corner_len, 370)], fill=neon_color, width=5)
        draw.line([(w - 60, 370), (w - 60, 370 + corner_len)], fill=neon_color, width=5)
        # Bottom-left
        draw.line([(60, 1430), (60 + corner_len, 1430)], fill=neon_color, width=5)
        draw.line([(60, 1430), (60, 1430 - corner_len)], fill=neon_color, width=5)
        # Bottom-right
        draw.line([(w - 60, 1430), (w - 60 - corner_len, 1430)], fill=neon_color, width=5)
        draw.line([(w - 60, 1430), (w - 60, 1430 - corner_len)], fill=neon_color, width=5)

        # 4. Scene Tracker Pill
        pill_box = [w // 2 - 140, 420, w // 2 + 140, 475]
        draw.rounded_rectangle(pill_box, radius=12, fill=neon_color)
        draw.text((w // 2, 448), f"PART {scene_index} / {total_scenes}", fill=(0, 0, 0), anchor="mm")

        # 5. Bold Focal Keywords Banner
        kw_box = [110, 520, w - 110, 620]
        draw.rounded_rectangle(kw_box, radius=8, fill=(0, 0, 0, 210), outline=(255, 255, 255, 60), width=1)
        draw.text((w // 2, 570), f"⚡ {scene.get('keywords', '')}", fill=neon_color, anchor="mm")

        # 6. Central Narrative Focus Text
        scene_text = scene.get("text", "")
        words = scene_text.split()
        chunked_lines = []
        curr_chunk = []
        for word in words:
            curr_chunk.append(word)
            if len(curr_chunk) >= 5:
                chunked_lines.append(" ".join(curr_chunk))
                curr_chunk = []
        if curr_chunk:
            chunked_lines.append(" ".join(curr_chunk))

        y_text_start = 720
        for line in chunked_lines[:6]:
            draw.text((w // 2, y_text_start), line, fill=(255, 255, 255), anchor="mm")
            y_text_start += 70

        # Save card
        output_png.parent.mkdir(parents=True, exist_ok=True)
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
        Renders complete, studio-quality 1080x1920 Short in seconds:
        1. Synthesizes human neural voiceover using Edge TTS
        2. Builds animated motion cards with cyber grid and neon accents
        3. Burns word-by-word kinetic popping karaoke subtitles
        4. Adds top elapsed progress bar & viral hook headline banner
        """
        clean_stem = re.sub(r"[^\w]", "_", script_text[:20]).strip("_") or "vector_short"
        temp_dir = PROCESSING_DIR / f"vec_{clean_stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        scenes = self.parse_script_into_scenes(script_text)
        logger.info(f"Loaded {len(scenes)} scenes for vector video.")

        # 1. Synthesize Studio Voiceover
        full_voice_wav = temp_dir / "voiceover.wav"
        combined_text = " ".join(s["text"] for s in scenes)
        self.tts.synthesize(
            text=combined_text,
            output_wav=full_voice_wav,
            voice_profile=voice_id,
            speed=1.12
        )

        # Probe exact audio duration
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(full_voice_wav)]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        total_audio_duration = float(json.loads(res.stdout)["format"]["duration"])
        total_audio_duration = max(3.0, total_audio_duration)
        logger.info(f"Synthesized neural voiceover duration: {total_audio_duration:.2f}s")

        # 2. Generate Scene Graphic Cards (Ultrafast render)
        scene_dur = max(2.5, total_audio_duration / len(scenes))
        scene_video_segments = []

        for idx, sc in enumerate(scenes, start=1):
            card_png = temp_dir / f"card_{idx}.png"
            self.generate_scene_card(sc, card_png, scene_index=idx, total_scenes=len(scenes))

            seg_mp4 = temp_dir / f"seg_{idx}.mp4"
            cmd_seg = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-t", f"{scene_dur:.2f}",
                "-i", str(card_png),
                "-vf", f"scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
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

        # 4. Generate Animated Word-by-Word Hormozi Subtitles
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
            margin_v=420,
            font_size=68,
            style_preset=subtitle_preset
        )

        # 5. Composite Final 1080x1920 Short with Neon Banner & Subtitles
        out_filename = f"vector_short_{clean_stem[:14]}_{int(total_audio_duration)}s.mp4"
        final_mp4 = OUTPUT_DIR / out_filename

        clean_banner = re.sub(r"[^\w\s]", "", (custom_hook_title or scenes[0]["text"][:40])).strip().upper()
        # Use relative POSIX path for ass filter to avoid Windows drive-letter colon conflicts
        try:
            rel_ass = ass_path.relative_to(BASE_DIR).as_posix()
        except Exception:
            rel_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")

        filter_complex = (
            f"[0:v]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT},"
            f"drawbox=x=80:y=120:w=920:h=90:color=black@0.85:t=fill,"
            f"drawbox=x=80:y=120:w=920:h=90:color=0x00E5FF:t=2,"
            f"drawbox=x=0:y=0:w='min(1080,1080*(t/{total_audio_duration:.2f}))':h=10:color=0x00E5FF:t=fill,"
            f"ass='{rel_ass}'[v_out]"
        )

        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(raw_visual_mp4),
            "-i", str(full_voice_wav),
            "-filter_complex", filter_complex,
            "-map", "[v_out]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", f"{total_audio_duration:.2f}",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(final_mp4)
        ]
        subprocess.run(cmd_final, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 6. Generate Viral Social Copy (Title, Description, Hashtags)
        social_meta = ai_brain.generate_viral_metadata(
            clip_text=combined_text[:300],
            niche="GAMING",
            title_hint=clean_banner
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
