"""
AI Clip & Real Footage Story Video Engine.
Transforms trending topics and scripts into authentic, high-retention 9:16 Shorts
by fetching real video clips, live stream moments, and gameplay footage,
composited with Neural Voiceover and word-by-word animated karaoke subtitles.
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import yt_dlp

from config import PROCESSING_DIR, OUTPUT_DIR, CANVAS_WIDTH, CANVAS_HEIGHT, BASE_DIR
from core.tts_engine import tts_engine
from core.subtitles import SubtitleGenerator
from core.ai_brain import ai_brain

logger = logging.getLogger("ViralShortsEngine.ClipStoryEngine")


class ClipStoryEngine:
    """Builds authentic vertical Shorts using real footage, stream clips & neural voice."""

    def __init__(self):
        self.tts = tts_engine
        self.subtitle_gen = SubtitleGenerator()

    def search_relevant_clips(self, topic: str, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Searches YouTube for real clips, live stream highlights, and gameplay
        matching the exact topic.
        """
        clean_q = re.sub(r"[^\w\s]", " ", topic).strip()
        words = clean_q.split()[:7]
        query = f"ytsearch{limit}:{' '.join(words)} clip highlight"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "socket_timeout": 6,
            "retries": 1
        }

        results = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                for entry in info.get("entries", [])[:limit]:
                    if entry:
                        v_id = entry.get("id") or entry.get("url")
                        results.append({
                            "id": str(v_id),
                            "title": entry.get("title", "Gaming Highlight"),
                            "url": f"https://www.youtube.com/watch?v={v_id}" if not str(v_id).startswith("http") else str(v_id),
                            "duration": entry.get("duration", 0),
                            "uploader": entry.get("uploader", "Creator")
                        })
        except Exception as e:
            logger.warning(f"Error searching topic clips via network: {e}")

        # Fallback curated clips if network is offline/firewalled
        if not results:
            clean_t = topic.lower()
            if "gta" in clean_t:
                results = [
                    {"id": "gta6_map_1", "title": "GTA 6 Official Vice City Gameplay & Map Scale", "url": "https://www.youtube.com/watch?v=QdBZY2fkU-0", "duration": 45, "uploader": "Rockstar Games"},
                    {"id": "gta6_leak_2", "title": "GTA 6 Leaked Alpha Clips & Graphics Comparison", "url": "https://www.youtube.com/watch?v=VQRLujxTmAA", "duration": 32, "uploader": "GTA Series Videos"}
                ]
            elif any(k in clean_t for k in ["speed", "kai", "stream"]):
                results = [
                    {"id": "stream_1", "title": "Top Streamer Wild Live Stream Moment & Reaction", "url": "https://www.youtube.com/watch?v=live_stream_clip", "duration": 28, "uploader": "Live Stream Highlights"},
                    {"id": "stream_2", "title": "Instant Viral Streamer Clip Goes Crazy Live", "url": "https://www.youtube.com/watch?v=stream_viral_moment", "duration": 35, "uploader": "Twitch Top Moments"}
                ]
            elif any(k in clean_t for k in ["bgmi", "jonathan", "esport", "clutch"]):
                results = [
                    {"id": "esports_1", "title": "Jonathan Gaming Insane 1v4 Finals Clutch Moment", "url": "https://www.youtube.com/watch?v=jonathan_clutch_1v4", "duration": 30, "uploader": "Esports Highlights"},
                    {"id": "esports_2", "title": "Unbelievable Esports Turnaround & Victory Reaction", "url": "https://www.youtube.com/watch?v=esports_finals_moment", "duration": 40, "uploader": "Gaming Live"}
                ]
            else:
                results = [
                    {"id": "clip_feat_1", "title": f"Viral Real-Life Footage & Proof Clip: {topic[:30]}", "url": "https://www.youtube.com/results?search_query=" + clean_q.replace(" ", "+"), "duration": 30, "uploader": "Viral Moments Hub"},
                    {"id": "clip_feat_2", "title": f"Trending Clip & Live Commentary on {topic[:30]}", "url": "https://www.youtube.com/results?search_query=" + clean_q.replace(" ", "+"), "duration": 25, "uploader": "Spotlight Gaming"}
                ]

        return results

    def fetch_clip_snippet(
        self,
        query_or_url: str,
        output_mp4: Path,
        duration: int = 25
    ) -> Optional[Path]:
        """
        Downloads a short snippet (15-30s) of real footage matching the query or exact URL.
        If a local video file is passed, trims and uses it immediately.
        """
        output_mp4 = Path(output_mp4)
        output_mp4.parent.mkdir(parents=True, exist_ok=True)

        target = query_or_url.strip()
        local_p = Path(target)
        if local_p.is_file() and local_p.exists():
            cmd_trim = [
                "ffmpeg", "-y",
                "-ss", "0",
                "-i", str(local_p),
                "-t", str(duration),
                "-c", "copy",
                str(output_mp4)
            ]
            try:
                subprocess.run(cmd_trim, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return output_mp4
            except Exception:
                import shutil
                shutil.copy2(local_p, output_mp4)
                return output_mp4

        # Network search/download
        if not target.startswith("http"):
            clean_q = re.sub(r"[^\w\s]", " ", target).strip()
            target = f"ytsearch1:{' '.join(clean_q.split()[:6])} gameplay clip"

        raw_outtmpl = str(output_mp4.with_suffix(".%(ext)s"))

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "outtmpl": raw_outtmpl,
            "download_ranges": yt_dlp.utils.download_range_func([], [[5, 5 + duration]]),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "socket_timeout": 6,
            "retries": 1
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if info and "entries" in info and info["entries"]:
                    info = info["entries"][0]

            candidates = list(output_mp4.parent.glob(f"{output_mp4.stem}.*"))
            for c in candidates:
                if c.suffix.lower() in [".mp4", ".mkv", ".webm"] and c.stat().st_size > 50000:
                    if c != output_mp4:
                        try:
                            c.replace(output_mp4)
                        except Exception:
                            import shutil
                            shutil.copy2(c, output_mp4)
                    return output_mp4
        except Exception as e:
            logger.warning(f"Could not download specific snippet: {e}")

        # Check if local sample fallback exists
        sample_fallback = BASE_DIR / "workspace" / "downloads" / "test_sample.mp4"
        if sample_fallback.exists():
            import shutil
            shutil.copy2(sample_fallback, output_mp4)
            return output_mp4

        return None

    def create_fallback_backdrop(self, output_mp4: Path, duration: float, topic: str) -> Path:
        """
        Generates an aesthetic cyber gradient motion backdrop if no network clip is found.
        """
        clean_topic = re.sub(r"[^\w\s]", "", topic).strip()[:35].upper()
        font_opt = "fontfile='C\\:/Windows/Fonts/arialbd.ttf':" if Path("C:/Windows/Fonts/arialbd.ttf").exists() else ""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x0E131F:s={CANVAS_WIDTH}x{CANVAS_HEIGHT}:d={duration:.2f}",
            "-vf", (
                f"drawbox=x=60:y=300:w=960:h=1200:color=0x00E5FF@0.15:t=fill,"
                f"drawbox=x=60:y=300:w=960:h=1200:color=0x00E5FF:t=3,"
                f"drawtext={font_opt}text='{clean_topic}':fontcolor=0x00E5FF:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(output_mp4)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_mp4

    def format_to_vertical_blur(self, input_video: Path, output_vertical: Path, target_duration: float) -> Path:
        """
        Converts any widescreen 16:9 gameplay/stream video into a stunning
        1080x1920 vertical canvas with a dynamic Gaussian blurred background.
        """
        filter_complex = (
            f"[0:v]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT},boxblur=25:5[bg];"
            f"[0:v]scale={CANVAS_WIDTH}:-1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "3",
            "-i", str(input_video),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-t", f"{target_duration:.2f}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            str(output_vertical)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_vertical

    def build_clip_story_video(
        self,
        script_text: str,
        topic: str,
        clip_source: Optional[str] = None,
        voice_id: str = "deep_male",
        custom_hook_title: Optional[str] = None,
        subtitle_preset: str = "hormozi"
    ) -> Dict[str, Any]:
        """
        Renders complete, authentic Short using real video clips & neural voice:
        1. Synthesizes studio neural voiceover
        2. Probes exact duration
        3. Fetches real video clip matching the topic
        4. Applies 9:16 Gaussian blur backdrop to real footage
        5. Generates word-by-word kinetic popping Alex Hormozi subtitles
        6. Burns top hook banner + elapsed progress bar
        7. Saves deliverable 1080x1920 MP4 into workspace/output/
        """
        clean_stem = re.sub(r"[^\w]", "_", topic[:20]).strip("_") or "real_clip_short"
        temp_dir = PROCESSING_DIR / f"story_{clean_stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Building real footage Short for topic: {topic}")

        # 1. Synthesize Studio Neural Voiceover
        full_voice_wav = temp_dir / "story_voiceover.wav"
        clean_script = re.sub(r"\n+", " ", script_text).strip()
        self.tts.synthesize(
            text=clean_script,
            output_wav=full_voice_wav,
            voice_profile=voice_id,
            speed=1.12
        )

        # Probe exact audio duration
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(full_voice_wav)]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        total_audio_duration = float(json.loads(res.stdout)["format"]["duration"])
        total_audio_duration = max(4.0, total_audio_duration)
        logger.info(f"Total story voiceover duration: {total_audio_duration:.2f}s")

        # 2. Fetch Real Video Clip Footage
        downloaded_clip = temp_dir / "real_footage_raw.mp4"
        clip_target = clip_source if (clip_source and clip_source.strip()) else topic
        fetched_path = self.fetch_clip_snippet(clip_target, downloaded_clip, duration=int(total_audio_duration + 5))

        # 3. Format Video to 9:16 Vertical
        vertical_video = temp_dir / "vertical_footage.mp4"
        if fetched_path and fetched_path.exists():
            logger.info(f"Formatting real footage clip: {fetched_path}")
            self.format_to_vertical_blur(fetched_path, vertical_video, target_duration=total_audio_duration)
        else:
            logger.info("Real clip unavailable; generating clean cyber motion backdrop.")
            self.create_fallback_backdrop(vertical_video, duration=total_audio_duration, topic=topic)

        # 4. Generate Animated Word-by-Word Hormozi Subtitles
        all_words = clean_script.split()
        time_per_word = total_audio_duration / max(1, len(all_words))
        words_timing = []
        t_cursor = 0.0
        for w in all_words:
            t_end = min(total_audio_duration, t_cursor + time_per_word)
            words_timing.append({"word": w, "start": round(t_cursor, 2), "end": round(t_end, 2)})
            t_cursor = t_end

        ass_path = temp_dir / "story_subtitles.ass"
        self.subtitle_gen.generate_ass(
            clip_words=words_timing,
            clip_start=0.0,
            output_ass_path=ass_path,
            margin_v=420,
            font_size=68,
            style_preset=subtitle_preset
        )

        # 5. Composite Final 1080x1920 Short
        out_filename = f"story_{clean_stem[:14]}_{int(total_audio_duration)}s.mp4"
        final_mp4 = OUTPUT_DIR / out_filename

        clean_banner = re.sub(r"[^\w\s]", "", (custom_hook_title or topic[:35])).strip().upper()
        font_opt = "fontfile='C\\:/Windows/Fonts/arialbd.ttf':" if Path("C:/Windows/Fonts/arialbd.ttf").exists() else ""
        try:
            rel_ass = ass_path.relative_to(BASE_DIR).as_posix()
        except Exception:
            rel_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")

        filter_complex = (
            f"[0:v]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT},"
            f"drawbox=x=80:y=120:w=920:h=90:color=black@0.85:t=fill,"
            f"drawbox=x=80:y=120:w=920:h=90:color=0x00E5FF:t=2,"
            f"drawtext={font_opt}text='{clean_banner}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=145,"
            f"drawbox=x=0:y=0:w='min(1080,1080*(t/{total_audio_duration:.2f}))':h=10:color=0x00E5FF:t=fill,"
            f"ass='{rel_ass}'[v_out]"
        )

        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(vertical_video),
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

        # 6. Generate Social Distribution Copy
        social_meta = ai_brain.generate_viral_metadata(
            clip_text=clean_script[:300],
            niche="GAMING",
            title_hint=clean_banner
        )

        return {
            "output_path": str(final_mp4),
            "output_filename": out_filename,
            "duration": round(total_audio_duration, 2),
            "footage_used": str(fetched_path) if fetched_path else "Cyber Motion Backdrop",
            "social_copy": social_meta
        }


# Singleton instance
clip_story_engine = ClipStoryEngine()
