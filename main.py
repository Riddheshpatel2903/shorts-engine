"""
Master Orchestration CLI and Entrypoint for ViralShortsEngine.
Coordinates the end-to-end pipeline:
1. Video download and stream merging
2. Layout and face detection analysis
3. AI audio transcription with word-level timestamps
4. Viral moment detection (Comedy, Advice, Motivation, High-Energy)
5. Word-by-word animated karaoke subtitles
6. High-quality 9:16 vertical video rendering
7. ffprobe validation, processing report generation, and cleanup
"""

import sys
import os
import json
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    HW_PROFILE,
    WORKSPACE_DIR,
    OUTPUT_DIR,
    PROCESSING_DIR,
    LOGS_DIR,
    logger
)
from core.downloader import VideoDownloader
from core.video_analyzer import VideoAnalyzer
from core.transcriber import AudioTranscriber
from core.moment_detector import MomentDetector
from core.clip_selector import ClipSelector
from core.subtitles import SubtitleGenerator
from core.exporter import VideoExporter


def run_pipeline(
    url_or_path: str,
    num_shorts: int = 3,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    target_duration: float = 40.0,
    genre: str = "auto",
    manual_start: float = None,
    manual_end: float = None,
    layout_override: str = None,
    subtitle_margin_v: int = 320,
    subtitle_font_size: int = 72,
    cookies_file: str = None,
    cleanup: bool = True
):
    """
    Executes the full automated AI viral clipping workflow.
    """
    logger.info("=" * 60)
    logger.info("VIRAL SHORTS ENGINE: PIPELINE START")
    logger.info(f"Target: {url_or_path}")
    logger.info(f"Genre Focus: {genre.upper()}")
    logger.info(f"Mode: {'GPU (NVENC)' if HW_PROFILE['nvenc_supported'] else 'CPU (libx264)'}")
    logger.info("=" * 60)

    downloader = VideoDownloader(cookies_file=cookies_file)
    analyzer = VideoAnalyzer()
    transcriber = AudioTranscriber()
    moment_detector = MomentDetector()
    clip_selector = ClipSelector(
        min_duration=min_duration,
        max_duration=max_duration,
        target_duration=target_duration,
        genre_focus=genre
    )
    subtitle_gen = SubtitleGenerator()
    exporter = VideoExporter()

    # Step 1: Ingestion (Download or local file)
    if os.path.exists(url_or_path):
        logger.info(f"Using local source file: {url_or_path}")
        video_path = Path(url_or_path)
        meta = {
            "id": video_path.stem,
            "title": video_path.stem,
            "filepath": str(video_path),
            "webpage_url": "local_file"
        }
    else:
        logger.info(f"Downloading stream from: {url_or_path}")
        meta = downloader.download(url_or_path)
        video_path = Path(meta["filepath"])

    # Step 2: Stream inspection and layout classification
    analysis = analyzer.analyze(str(video_path))
    layout_info = analysis["layout"]
    if layout_override:
        layout_info["classification"] = layout_override
        logger.info(f"Layout overridden by user to: {layout_override}")
    else:
        logger.info(f"Detected layout: {layout_info['classification']} (confidence: {layout_info.get('confidence', 0):.2f})")

    total_video_duration = analysis["probe"].get("duration", 60.0)

    # Step 3: Transcription
    transcript_data = transcriber.transcribe(str(video_path))
    segments = transcript_data.get("segments", [])
    logger.info(f"Transcribed {len(segments)} segments in language '{transcript_data.get('language')}'")

    # Step 4: Viral moment detection & clip selection
    if manual_start is not None and manual_end is not None:
        logger.info(f"Manual clip specified: {manual_start}s to {manual_end}s")
        manual_words = []
        for s in segments:
            for w in s.get("words", []):
                if manual_start <= w["start"] <= manual_end:
                    manual_words.append(w)
        
        selected_clips = [{
            "start": round(manual_start, 2),
            "end": round(manual_end, 2),
            "duration": round(manual_end - manual_start, 2),
            "viral_score": 95.0,
            "category": "MANUAL",
            "category_label": "✂️ Custom Manual Selection",
            "text": " ".join(w["word"] for w in manual_words),
            "segments": [{"words": manual_words}],
            "hook_text": "Manual clip selection"
        }]
    else:
        if segments:
            logger.info(f"Analyzing speech dynamics, laughter acoustic bursts, and '{genre}' viral patterns...")
            analyzed_segments = moment_detector.analyze_moments(str(video_path), transcript_data)
            selected_clips = clip_selector.select_clips(analyzed_segments, num_shorts=num_shorts, genre_focus=genre)
        else:
            logger.info("No speech detected. Generating intelligent visual/audio slice candidate...")
            clip_dur = min(target_duration, total_video_duration)
            selected_clips = [{
                "start": 0.0,
                "end": round(clip_dur, 2),
                "duration": round(clip_dur, 2),
                "viral_score": 75.0,
                "category": "VIRAL_GENERAL",
                "category_label": "⚡ High Action Moment",
                "text": "",
                "segments": [],
                "hook_text": "High action moment"
            }]

    logger.info(f"Processing {len(selected_clips)} viral candidate clips...")

    # Step 5: Render and export each clip
    generated_shorts = []
    for idx, clip in enumerate(selected_clips, start=1):
        filename = f"short_{idx:03d}.mp4"
        ass_path = PROCESSING_DIR / f"subtitles_{idx:03d}.ass"

        # Collect words in this clip
        clip_words = []
        for s in clip.get("segments", []):
            clip_words.extend(s.get("words", []))

        # Generate word-by-word karaoke ASS file
        subtitle_gen.generate_ass(
            clip_words=clip_words,
            clip_start=clip["start"],
            output_ass_path=ass_path,
            margin_v=subtitle_margin_v,
            font_size=subtitle_font_size
        )

        # Render clip with framing, drift-free sync, and burned karaoke subtitles
        out_file = exporter.render_clip(
            source_path=str(video_path),
            clip_info=clip,
            layout_info=layout_info,
            subtitle_path=ass_path if clip_words else None,
            output_filename=filename
        )

        # Validation stats
        validation = exporter.verify_export(out_file, expected_duration=clip["duration"])

        generated_shorts.append({
            "filename": filename,
            "filepath": str(out_file),
            "start": clip["start"],
            "end": clip["end"],
            "duration": clip["duration"],
            "viral_score": clip["viral_score"],
            "category": clip.get("category", "VIRAL_GENERAL"),
            "category_label": clip.get("category_label", "⚡ Viral Highlight"),
            "comedy_score": clip.get("comedy_score", 0.0),
            "advice_score": clip.get("advice_score", 0.0),
            "motivation_score": clip.get("motivation_score", 0.0),
            "hook_text": clip.get("hook_text", ""),
            "validation": validation
        })

    # Step 6: Generate comprehensive processing report
    report = {
        "source_title": meta.get("title"),
        "source_url": meta.get("webpage_url"),
        "language": transcript_data.get("language"),
        "genre_focus": genre,
        "layout_classification": layout_info.get("classification"),
        "hardware_profile": HW_PROFILE,
        "total_shorts_generated": len(generated_shorts),
        "shorts": generated_shorts
    }

    report_path = WORKSPACE_DIR / "processing_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"Processing report saved to: {report_path}")

    # Step 7: Mandatory workspace cleanup
    if cleanup:
        exporter.cleanup_processing_artifacts()

    logger.info("=" * 60)
    logger.info(f"COMPLETED! {len(generated_shorts)} Shorts rendered in: {OUTPUT_DIR}")
    logger.info("=" * 60)
    return report


def main():
    parser = argparse.ArgumentParser(description="ViralShortsEngine: AI-Powered 9:16 Video Clipper")
    parser.add_argument("--url", type=str, help="YouTube or Twitch video URL")
    parser.add_argument("--file", type=str, help="Path to local video file")
    parser.add_argument("--shorts", type=int, default=3, help="Number of viral shorts to generate")
    parser.add_argument("--genre", type=str, choices=["auto", "comedy", "advice", "motivation"], default="auto", help="Viral category focus: auto (best blend), comedy (laughing moments), advice (educational insights), motivation (inspirational mindset)")
    parser.add_argument("--min-duration", type=float, default=20.0, help="Minimum clip duration in seconds")
    parser.add_argument("--max-duration", type=float, default=60.0, help="Maximum clip duration in seconds")
    parser.add_argument("--target-duration", type=float, default=40.0, help="Target clip duration in seconds")
    parser.add_argument("--manual-start", type=float, default=None, help="Manual clip start timestamp")
    parser.add_argument("--manual-end", type=float, default=None, help="Manual clip end timestamp")
    parser.add_argument("--layout", type=str, choices=["STREAMER_FACECAM", "TALKING_HEAD", "GAMEPLAY", "GENERAL"], default=None, help="Layout classification override")
    parser.add_argument("--cookies", type=str, default=None, help="Path to Netscape cookies.txt file")
    parser.add_argument("--ui", action="store_true", help="Launch Streamlit Web UI")
    parser.add_argument("--no-cleanup", action="store_true", help="Preserve intermediate processing files")

    args = parser.parse_args()

    if args.ui:
        import subprocess
        ui_script = Path(__file__).resolve().parent / "ui.py"
        subprocess.run(["streamlit", "run", str(ui_script)])
        return

    target = args.url or args.file
    if not target:
        print("Please provide a --url, a --file, or launch with --ui.")
        parser.print_help()
        sys.exit(1)

    run_pipeline(
        url_or_path=target,
        num_shorts=args.shorts,
        genre=args.genre,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        target_duration=args.target_duration,
        manual_start=args.manual_start,
        manual_end=args.manual_end,
        layout_override=args.layout,
        cookies_file=args.cookies,
        cleanup=not args.no_cleanup
    )


if __name__ == "__main__":
    main()
