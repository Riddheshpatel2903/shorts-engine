"""
Editor module.
Builds FFmpeg filter graphs for vertical 9:16 composition (1080x1920).
Enforces RULE A (zero audio-video drift) and RULE B (viral framing with blurred backdrop,
corner facecam extraction, talking-head centering, and gameplay composition).
"""

import os
import re
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
        superchat_card: Optional[Dict[str, Any]] = None,
        enable_motion_graphics: bool = True,
        enable_progress_bar: bool = True,
        clip_duration: float = 30.0,
        hook_text: Optional[str] = None,
        has_sfx_track: bool = False
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
        Includes professional motion graphics:
        - Retention Bottom Progress Bar (TikTok / Reels engagement standard)
        - Glassmorphic Top Hook Card Banner
        - High-Fidelity Audio SFX track mixer
        """
        classification = layout_info.get("classification", "GENERAL")
        facecam_box = layout_info.get("facecam_box")
        podcast_speakers = layout_info.get("podcast_speakers")
        src_w = layout_info.get("source_width", 1920)
        src_h = layout_info.get("source_height", 1080)

        # Resolve template if AUTO
        mode = template.upper()
        if mode == "AUTO":
            recommended = layout_info.get("recommended_layout")
            if recommended and recommended.upper() in ("FULL_VERTICAL_STRIP", "STREAMER_SPLIT", "PODCAST_SPLIT", "CINEMATIC_BLUR"):
                mode = recommended.upper()
            elif src_h >= src_w:
                mode = "FULL_VERTICAL_STRIP"
            elif classification == "PODCAST" or podcast_speakers:
                mode = "PODCAST_SPLIT"
            elif classification == "STREAMER_FACECAM" and facecam_box:
                mode = "STREAMER_SPLIT"
            elif classification == "TALKING_HEAD" or layout_info.get("person_in_frame"):
                mode = "FULL_VERTICAL_STRIP"
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

        elif mode in ("STREAMER_SPLIT", "STREAMER_PRO", "STREAMER_FULL_GAME", "STREAMER_ZOOMED_GAME"):
            # Layout: Pro Streamer Dual-View (Top Facecam + Bottom Gameplay + Blurred Backdrop)
            f_box = normalize_box(facecam_box, src_w, src_h)
            fx, fy, fw, fh = f_box["x"], f_box["y"], f_box["width"], f_box["height"]

            # 1. Canvas blurred motion backdrop
            bg_filter = (
                f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},"
                f"boxblur=25:5,eq=brightness=-0.15[bg]"
            )

            # 2. Top Facecam: crop with headroom, scale to 1080x760
            face_filter = (
                f"[0:v]crop={fw}:{fh}:{fx}:{fy},"
                f"scale={self.width}:760:force_original_aspect_ratio=increase,"
                f"crop={self.width}:760[facecam]"
            )

            if mode == "STREAMER_ZOOMED_GAME":
                # Action-zoomed gameplay filling full bottom 1080x1160 area
                game_filter = (
                    f"[0:v]scale={self.width}:1160:force_original_aspect_ratio=increase,"
                    f"crop={self.width}:1160[gameplay]"
                )
                overlay_filter = (
                    f"[bg][facecam]overlay=0:0[comp1];"
                    f"[comp1]drawbox=x=0:y=756:w={self.width}:h=4:color=0x00E5FF@0.9:t=fill[comp2];"
                    f"[comp2][gameplay]overlay=0:760[framed]"
                )
                filters.extend([bg_filter, face_filter, game_filter, overlay_filter])
            else:
                # Pro Gamer Default: Uncropped Full 16:9 Game Screen in bottom area
                # Preserves 100% of game HUD, minimap, radar, crosshairs, and killfeed!
                game_filter = (
                    f"[0:v]scale={self.width}:-1[gameplay]"
                )
                game_y = 760 + (1160 - 608) // 2  # y = 1036
                overlay_filter = (
                    f"[bg][facecam]overlay=0:0[comp1];"
                    f"[comp1]drawbox=x=0:y=756:w={self.width}:h=4:color=0x00E5FF@0.9:t=fill[comp2];"
                    f"[comp2][gameplay]overlay=0:{game_y}[comp3];"
                    f"[comp3]drawbox=x=0:y={game_y-2}:w={self.width}:h=2:color=white@0.6:t=fill,"
                    f"drawbox=x=0:y={game_y+608}:w={self.width}:h=2:color=white@0.6:t=fill[framed]"
                )
                filters.extend([bg_filter, face_filter, game_filter, overlay_filter])

            current_v = "[framed]"

        elif mode in ("FULL_VERTICAL_STRIP", "SMART_VERTICAL_CROP", "TALKING_HEAD"):
            # Layout: Full 9:16 vertical strip (1080x1920) without split-screen
            # Precisely tracks person looking in frame (head + body centered), or centers action if pure gameplay
            if src_h >= src_w:
                # Video is already vertical (e.g. mobile recording / Reels)
                strip_filter = (
                    f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                    f"crop={self.width}:{self.height}[framed]"
                )
            else:
                # 16:9 widescreen source
                target_ratio = self.width / self.height  # 1080 / 1920 = 0.5625
                zoom_factor = min(1.3, max(1.0, float(layout_info.get("zoom_factor", 1.0))))
                
                crop_h = int(src_h / zoom_factor)
                crop_w = int(crop_h * target_ratio)
                crop_w = crop_w - (crop_w % 2)
                crop_h = crop_h - (crop_h % 2)

                # Determine horizontal center (dynamic active-speaker switching expression or static coordinate)
                dynamic_x = layout_info.get("crop_x_expr")
                person_cx = (
                    layout_info.get("tracked_person_cx") or
                    layout_info.get("person_cx") or
                    (layout_info.get("speaker_center", [src_w // 2])[0] if isinstance(layout_info.get("speaker_center"), (list, tuple)) else None) or
                    (layout_info.get("speaker_center", {}).get("x") if isinstance(layout_info.get("speaker_center"), dict) else None) or
                    (src_w // 2)
                )
                
                person_cy = (
                    layout_info.get("tracked_person_cy") or
                    (layout_info.get("speaker_center", [0, src_h // 2])[1] if isinstance(layout_info.get("speaker_center"), (list, tuple)) and len(layout_info.get("speaker_center")) > 1 else None) or
                    (layout_info.get("speaker_center", {}).get("y") if isinstance(layout_info.get("speaker_center"), dict) else None) or
                    int(src_h * 0.40)
                )

                if dynamic_x and any(op in str(dynamic_x) for op in ("lt", "gt", "if", "t")):
                    x_target = f"'{dynamic_x}'"
                else:
                    crop_x = int(person_cx - crop_w / 2)
                    crop_x = max(0, min(src_w - crop_w, crop_x))
                    crop_x = crop_x - (crop_x % 2)
                    x_target = str(crop_x)

                # Smart vertical headroom: place face at 30-35% from top of 9:16 frame
                ideal_y = int(person_cy - crop_h * 0.33)
                crop_y = max(0, min(src_h - crop_h, ideal_y))
                crop_y = crop_y - (crop_y % 2)
                y_target = str(crop_y)

                strip_filter = (
                    f"[0:v]crop={crop_w}:{crop_h}:{x_target}:{y_target},"
                    f"scale={self.width}:{self.height}:flags=lanczos[framed]"
                )

            filters.append(strip_filter)
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
            # Layout: CINEMATIC_BLUR (Default for wide gameplay & landscapes)
            # Background: high-aesthetic blurred motion backdrop
            # Foreground: 16:9 source scaled to 1080 width, centered vertically with crisp accent edge dividers
            bg_filter = (
                f"[0:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},"
                f"boxblur=25:5,eq=brightness=-0.15[bg]"
            )
            fg_filter = (
                f"[0:v]scale={self.width}:-1[fg]"
            )
            # 16:9 at 1080 width is 1080x608, centered at y = (1920 - 608) // 2 = 656
            game_y = (self.height - 608) // 2
            overlay_filter = (
                f"[bg][fg]overlay=0:{game_y}[comp1];"
                f"[comp1]drawbox=x=0:y={game_y-2}:w={self.width}:h=2:color=0x00E5FF@0.7:t=fill,"
                f"drawbox=x=0:y={game_y+608}:w={self.width}:h=2:color=0x00E5FF@0.7:t=fill[framed]"
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
            sub_filter = f"{current_v}ass='{escaped_sub}'[v_sub]"
            filters.append(sub_filter)
            current_v = "[v_sub]"

        # Add Professional Motion Graphics (Retention Progress Bar & Floating Top Hook Card)
        if enable_motion_graphics:
            # 1. Top Glassmorphic Hook Banner (First 5 seconds)
            if hook_text and hook_text.strip():
                clean_hook = re.sub(r"[^\w\s\-\:\.\,\!]", "", hook_text).strip().upper()[:36]
                if clean_hook:
                    font_file = "C\\:/Windows/Fonts/arialbd.ttf" if Path("C:/Windows/Fonts/arialbd.ttf").exists() else ""
                    font_opt = f"fontfile='{font_file}':" if font_file else ""
                    hook_banner_filter = (
                        f"{current_v}drawbox=x=60:y=180:w=960:h=120:color=black@0.85:t=fill:enable='between(t\\,0.2\\,5.5)',"
                        f"drawbox=x=60:y=180:w=960:h=120:color=0x00E5FF@0.95:t=3:enable='between(t\\,0.2\\,5.5)',"
                        f"drawbox=x=60:y=180:w=12:h=120:color=0x00E5FF@0.95:t=fill:enable='between(t\\,0.2\\,5.5)',"
                        f"drawtext={font_opt}text='{clean_hook}':fontcolor=white:fontsize=46:x=(w-text_w)/2:y=218:enable='between(t\\,0.2\\,5.5)'[hook_v]"
                    )
                    filters.append(hook_banner_filter)
                    current_v = "[hook_v]"

            # 2. Bottom Glowing Retention Progress Bar (0 to 1080px across clip duration)
            if enable_progress_bar and clip_duration > 0:
                dur_val = max(1.0, float(clip_duration))
                pbar_filter = (
                    f"{current_v}drawbox=x=0:y={self.height-14}:w='min({self.width}\\,(t/{dur_val:.2f})*{self.width})':h=14:color=0x00E5FF@0.95:t=fill,"
                    f"drawbox=x=0:y={self.height-16}:w='min({self.width}\\,(t/{dur_val:.2f})*{self.width})':h=2:color=white@0.85:t=fill[pbar_v]"
                )
                filters.append(pbar_filter)
                current_v = "[pbar_v]"

        final_v = f"{current_v}"

        # Combine all video filters
        v_pipeline = ";".join(filters)

        # Audio pipeline (Zero drift + sample rate alignment + SFX composite mix)
        if has_sfx_track:
            a_pipeline = "[0:a]volume=1.0,aresample=44100[a0];[1:a]volume=1.0,aresample=44100[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2,volume=1.0[a_out]"
        else:
            a_pipeline = "[0:a]asetpts=PTS-STARTPTS,aresample=async=1:first_pts=0,volume=1.0[a_out]"

        full_filter_complex = f"{v_pipeline};{a_pipeline}"
        return full_filter_complex, final_v, "[a_out]"
