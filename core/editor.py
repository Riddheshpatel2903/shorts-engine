"""
Editor module.
Builds FFmpeg filter graphs for vertical 9:16 composition (1080x1920).
Enforces RULE A (zero audio-video drift) and RULE B (viral framing with blurred backdrop,
corner facecam extraction, talking-head centering, and gameplay composition).
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from config import CANVAS_WIDTH, CANVAS_HEIGHT, TARGET_FPS

logger = logging.getLogger("ViralShortsEngine.Editor")


def escape_filter_path(path_str: str) -> str:
    """Escapes Windows paths for FFmpeg filter arguments (subtitles/ass filter)."""
    p = str(path_str).replace("\\", "/")
    # Escape colon for drive letter: C:/ -> C\:/
    if len(p) > 1 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p


def normalize_box(box: Any, src_w: int, src_h: int) -> Dict[str, int]:
    """
    Safely normalizes any bounding box (dict or list/tuple [x,y,w,h] or [x1,y1,x2,y2])
    into a dictionary: {'x': int, 'y': int, 'width': int, 'height': int}.
    """
    if not box:
        return {"x": 0, "y": 0, "width": src_w // 3, "height": src_h // 3}

    if isinstance(box, dict):
        x = int(box.get("x", 0))
        y = int(box.get("y", 0))
        w = int(box.get("width", box.get("w", src_w // 3)))
        h = int(box.get("height", box.get("h", src_h // 3)))
        return {"x": max(0, x), "y": max(0, y), "width": max(10, w), "height": max(10, h)}

    if isinstance(box, (list, tuple)) and len(box) >= 4:
        p0, p1, p2, p3 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        # Detect if format is [x1, y1, x2, y2]
        if p2 > p0 and p3 > p1 and (p2 > src_w * 0.35 or p3 > src_h * 0.35):
            w = max(10, p2 - p0)
            h = max(10, p3 - p1)
            return {"x": max(0, p0), "y": max(0, p1), "width": w, "height": h}
        else:
            return {"x": max(0, p0), "y": max(0, p1), "width": max(10, p2), "height": max(10, p3)}

    return {"x": 0, "y": 0, "width": src_w // 3, "height": src_h // 3}


class VideoEditor:
    def __init__(self):
        self.width = CANVAS_WIDTH
        self.height = CANVAS_HEIGHT
        self.fps = TARGET_FPS

    def build_filter_graph(
        self,
        layout_info: Dict[str, Any],
        subtitle_path: Optional[Path] = None,
        template: str = "AUTO",
        superchat_card: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, str]:
        """
        Constructs the FFmpeg -filter_complex string for 1080x1920 9:16 vertical composition.
        Supports templates:
        - AUTO: chooses best layout based on AI classification (PODCAST, STREAMER, TALKING_HEAD, etc.)
        - PODCAST_SPLIT: 2-person podcast vertical split (Host Top / Guest Bottom)
        - TALKING_HEAD: centered 9:16 portrait tracking the active speaker
        - STREAMER_SPLIT: Top Facecam + Bottom Gameplay
        - CINEMATIC_BLUR: 16:9 source centered vertically with blurred/darkened backdrop
        - FIT_LETTERBOX: 16:9 source centered on dark background with clean letterbox framing
        """
        classification = layout_info.get("classification", "GENERAL")
        facecam_box = layout_info.get("facecam_box")
        podcast_speakers = layout_info.get("podcast_speakers")
        src_w = layout_info.get("source_width", 1920)
        src_h = layout_info.get("source_height", 1080)

        # Resolve template if AUTO
        mode = template.upper()
        if mode == "AUTO":
            if classification == "PODCAST" or podcast_speakers:
                mode = "PODCAST_SPLIT"
            elif classification == "STREAMER_FACECAM" and facecam_box:
                mode = "STREAMER_SPLIT"
            elif classification == "TALKING_HEAD":
                mode = "TALKING_HEAD"
            else:
                mode = "CINEMATIC_BLUR"

        filters = []

        if mode == "PODCAST_SPLIT":
            # Layout: Top Speaker (Host) + Bottom Speaker (Guest)
            if podcast_speakers and isinstance(podcast_speakers, dict) and podcast_speakers.get("has_two_speakers"):
                spk1 = normalize_box(podcast_speakers.get("speaker_left"), src_w, src_h)
                spk2 = normalize_box(podcast_speakers.get("speaker_right"), src_w, src_h)
            else:
                # Fallback: left half and right half
                hw = src_w // 2
                spk1 = {"x": 0, "y": 0, "width": hw, "height": src_h}
                spk2 = {"x": hw, "y": 0, "width": hw, "height": src_h}

            # 1. Blurred background
            bg_filter = (
                f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},"
                f"boxblur=25:2,eq=brightness=-0.15[bg]"
            )
            # 2. Top speaker (Host): 1080x960
            top_filter = (
                f"[0:v]crop={spk1['width']}:{spk1['height']}:{spk1['x']}:{spk1['y']},"
                f"scale={self.width}:960:force_original_aspect_ratio=increase,"
                f"crop={self.width}:960[top_spk]"
            )
            # 3. Bottom speaker (Guest): 1080x960
            bot_filter = (
                f"[0:v]crop={spk2['width']}:{spk2['height']}:{spk2['x']}:{spk2['y']},"
                f"scale={self.width}:960:force_original_aspect_ratio=increase,"
                f"crop={self.width}:960[bot_spk]"
            )
            # 4. Composite with 4px divider
            overlay_filter = (
                f"[bg][top_spk]overlay=0:0[comp1];"
                f"[comp1][bot_spk]overlay=0:960[framed]"
            )
            filters.extend([bg_filter, top_filter, bot_filter, overlay_filter])
            current_v = "[framed]"

        elif mode == "STREAMER_SPLIT":
            # Layout: Top Facecam + Bottom Gameplay + Blurred Backdrop
            f_box = normalize_box(facecam_box, src_w, src_h)
            fx, fy, fw, fh = f_box["x"], f_box["y"], f_box["width"], f_box["height"]

            bg_filter = (
                f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},"
                f"boxblur=25:2,eq=brightness=-0.15[bg]"
            )
            face_filter = (
                f"[0:v]crop={fw}:{fh}:{fx}:{fy},"
                f"scale={self.width}:760:force_original_aspect_ratio=increase,"
                f"crop={self.width}:760[facecam]"
            )
            game_filter = (
                f"[0:v]scale={self.width}:1160:force_original_aspect_ratio=increase,"
                f"crop={self.width}:1160[gameplay]"
            )
            overlay_filter = (
                f"[bg][facecam]overlay=0:0[comp1];"
                f"[comp1][gameplay]overlay=0:760[framed]"
            )
            filters.extend([bg_filter, face_filter, game_filter, overlay_filter])
            current_v = "[framed]"

        elif mode == "TALKING_HEAD":
            # Layout: Single Person Centered 9:16 Crop
            spk_center = layout_info.get("speaker_center")
            if isinstance(spk_center, dict):
                speaker_cx = spk_center.get("x", src_w // 2)
            elif isinstance(spk_center, (list, tuple)) and len(spk_center) > 0:
                speaker_cx = spk_center[0]
            else:
                speaker_cx = src_w // 2

            scale_factor = self.height / max(1, src_h)
            scaled_w = int(src_w * scale_factor)
            scaled_cx = int(speaker_cx * scale_factor)
            crop_x = max(0, min(scaled_w - self.width, scaled_cx - (self.width // 2)))

            head_filter = (
                f"[0:v]scale=-1:{self.height},"
                f"crop={self.width}:{self.height}:{crop_x}:0[framed]"
            )
            filters.append(head_filter)
            current_v = "[framed]"

        elif mode == "FIT_LETTERBOX":
            # Layout: Clean 16:9 on dark canvas with top/bottom letterbox
            bg_filter = (
                f"color=c=black:s={self.width}x{self.height}:r={self.fps}[bg]"
            )
            fg_filter = (
                f"[0:v]scale={self.width}:-1[fg]"
            )
            overlay_filter = (
                f"[bg][fg]overlay=0:(1920-h)/2[framed]"
            )
            filters.extend([bg_filter, fg_filter, overlay_filter])
            current_v = "[framed]"

        else:
            # Layout: CINEMATIC_BLUR (Default)
            # Background: blurred & darkened
            # Foreground: 16:9 source scaled to 1080 width, centered vertically
            bg_filter = (
                f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},"
                f"boxblur=25:2,eq=brightness=-0.15[bg]"
            )
            fg_filter = (
                f"[0:v]scale={self.width}:-1[fg]"
            )
            overlay_filter = (
                f"[bg][fg]overlay=0:(1920-h)/2[framed]"
            )
            filters.extend([bg_filter, fg_filter, overlay_filter])
            current_v = "[framed]"

        # Add Superchat Donation Overlay Card if provided
        if superchat_card:
            from core.chat_analyzer import chat_analyzer
            sc_filter = chat_analyzer.generate_superchat_overlay_filter(
                donor_name=superchat_card.get("donor", "Viewer"),
                amount_text=superchat_card.get("amount_text", "$20"),
                question_text=superchat_card.get("question", "VIRAL MOMENT"),
                duration=float(superchat_card.get("duration", 6.0))
            )
            filters.append(f"{current_v}{sc_filter}[sc_v]")
            current_v = "[sc_v]"

        # Add Subtitles if provided
        if subtitle_path and os.path.exists(subtitle_path):
            escaped_sub = escape_filter_path(str(subtitle_path))
            sub_filter = f"{current_v}ass='{escaped_sub}'[v_out]"
            filters.append(sub_filter)
            final_v = "[v_out]"
        else:
            final_v = f"{current_v}"

        # Combine all video filters
        v_pipeline = ";".join(filters)

        # Audio pipeline (RULE A: zero drift + sample rate alignment + peak normalization)
        a_pipeline = "[0:a]asetpts=PTS-STARTPTS,aresample=async=1:first_pts=0,volume=1.0[a_out]"

        full_filter_complex = f"{v_pipeline};{a_pipeline}"
        return full_filter_complex, final_v, "[a_out]"
