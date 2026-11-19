"""
Subtitle generator module.
Creates professional animated word-by-word karaoke subtitles in ASS (Advanced SubStation Alpha) format.
Features dynamic scale pop, electric yellow highlight, high-contrast outlines, and safe-margin framing.
"""

import math
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import SUBTITLE_CONFIG

logger = logging.getLogger("ViralShortsEngine.Subtitles")


def format_ass_time(seconds: float) -> str:
    """Converts seconds into ASS format H:MM:SS.cs"""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 0
        s += 1
        if s >= 60:
            s = 0
            m += 1
            if m >= 60:
                m = 0
                h += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


SUBTITLE_PRESETS = {
    "hormozi": {
        "name": "🔥 Alex Hormozi (Bold Neon Yellow)",
        "font_name": "Arial Black",
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H0000E5FF",   # Electric Yellow
        "outline_color": "&H00000000",
        "back_color": "&H80000000",
        "outline_width": 5.0,
        "shadow_depth": 2.0,
        "scale_pop": 115,
        "max_words_per_line": 3,
        "uppercase": True
    },
    "mrbeast": {
        "name": "⚡ MrBeast (Neon Toxic Green)",
        "font_name": "Impact",
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H0033FF00",   # Neon Toxic Green
        "outline_color": "&H00000000",
        "back_color": "&H90000000",
        "outline_width": 6.0,
        "shadow_depth": 3.0,
        "scale_pop": 120,
        "max_words_per_line": 3,
        "uppercase": True
    },
    "aesthetic": {
        "name": "✨ Clean Aesthetic (Minimalist Cyan)",
        "font_name": "Arial",
        "primary_color": "&H00F5F5F5",
        "highlight_color": "&H00FFF000",   # Soft Cyan
        "outline_color": "&H00222222",
        "back_color": "&H40000000",
        "outline_width": 2.5,
        "shadow_depth": 1.5,
        "scale_pop": 106,
        "max_words_per_line": 4,
        "uppercase": False
    },
    "motivation": {
        "name": "🔴 Crimson Rage (Motivational Red)",
        "font_name": "Arial Black",
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H001133FF",   # Fiery Red
        "outline_color": "&H00000000",
        "back_color": "&H90000000",
        "outline_width": 5.5,
        "shadow_depth": 2.5,
        "scale_pop": 116,
        "max_words_per_line": 3,
        "uppercase": True
    },
    "classic_box": {
        "name": "💬 Closed Caption (Yellow on Dark)",
        "font_name": "Trebuchet MS",
        "primary_color": "&H0000FFFF",
        "highlight_color": "&H0000FFFF",
        "outline_color": "&H90000000",
        "back_color": "&HB0000000",
        "outline_width": 2.5,
        "shadow_depth": 1.0,
        "scale_pop": 100,
        "max_words_per_line": 4,
        "uppercase": False
    }
}


class SubtitleGenerator:
    def __init__(self, config_overrides: Optional[Dict[str, Any]] = None):
        self.config = SUBTITLE_CONFIG.copy()
        if config_overrides:
            self.config.update(config_overrides)

    def generate_ass(
        self,
        clip_words: List[Dict[str, Any]],
        clip_start: float,
        output_ass_path: Path,
        margin_v: Optional[int] = None,
        font_size: Optional[int] = None,
        style_preset: str = "hormozi"
    ) -> Path:
        """
        Generates an ASS subtitle file with animated word-by-word karaoke highlighting.
        Supports customizable typography presets: hormozi, mrbeast, aesthetic, motivation, classic_box.
        """
        output_ass_path = Path(output_ass_path)
        output_ass_path.parent.mkdir(parents=True, exist_ok=True)

        preset = SUBTITLE_PRESETS.get(style_preset.lower(), SUBTITLE_PRESETS["hormozi"])

        font_name = preset.get("font_name", "Arial Black")
        size = font_size or self.config.get("font_size", 72)
        v_margin = margin_v if margin_v is not None else self.config.get("margin_v", 320)
        max_words_per_chunk = preset.get("max_words_per_line", 3)

        primary_color = preset.get("primary_color", "&H00FFFFFF")
        highlight_color = preset.get("highlight_color", "&H0000E5FF")
        outline_color = preset.get("outline_color", "&H00000000")
        back_color = preset.get("back_color", "&H80000000")
        outline_w = preset.get("outline_width", 5.0)
        shadow_d = preset.get("shadow_depth", 2.0)
        scale_pop = preset.get("scale_pop", 115)
        uppercase = preset.get("uppercase", True)

        # ASS Header
        ass_content = [
            "[Script Info]",
            f"Title: ViralShorts Karaoke Subtitles - {preset['name']}",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{font_name},{size},{primary_color},{highlight_color},{outline_color},{back_color},-1,0,0,0,100,100,0,0,1,{outline_w},{shadow_d},2,50,50,{v_margin},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        if not clip_words:
            # Write empty subtitle file if no words
            with open(output_ass_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ass_content) + "\n")
            return output_ass_path

        # Group words into short punchy chunks (2-4 words)
        chunks = []
        current_chunk = []
        for w in clip_words:
            rel_start = max(0.0, w["start"] - clip_start)
            rel_end = max(rel_start + 0.05, w["end"] - clip_start)
            raw_w = w["word"].strip()
            word_str = raw_w.upper() if uppercase else raw_w

            if not word_str:
                continue

            current_chunk.append({
                "word": word_str,
                "start": rel_start,
                "end": rel_end
            })

            has_punc = bool(word_str and word_str[-1] in ".!?")
            if len(current_chunk) >= max_words_per_chunk or has_punc:
                chunks.append(current_chunk)
                current_chunk = []

        if current_chunk:
            chunks.append(current_chunk)

        # For each chunk, generate events highlighting each word in turn
        for chunk in chunks:
            for idx, active_word in enumerate(chunk):
                ev_start = format_ass_time(active_word["start"])
                ev_end = format_ass_time(active_word["end"])

                line_parts = []
                for j, item in enumerate(chunk):
                    if j == idx:
                        # Highlighted active word with dynamic scale pop
                        line_parts.append(
                            f"{{\\c{highlight_color}\\fscx{scale_pop}\\fscy{scale_pop}}}{item['word']}{{\\r}}"
                        )
                    else:
                        # Default primary word
                        line_parts.append(
                            f"{{\\c{primary_color}}}{item['word']}"
                        )

                dialogue_text = " ".join(line_parts)
                dialogue_line = (
                    f"Dialogue: 0,{ev_start},{ev_end},Default,,0,0,0,,{dialogue_text}"
                )
                ass_content.append(dialogue_line)

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_content) + "\n")

        logger.info(f"Generated ASS karaoke subtitles ({preset['name']}): {output_ass_path}")
        return output_ass_path
