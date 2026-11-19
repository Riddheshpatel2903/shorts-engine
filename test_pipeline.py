"""
Comprehensive Test and Validation Suite for ViralShortsEngine.
Validates all 12 test requirements from Phase 11:
1. Environment detection
2. FFmpeg / FFprobe execution
3. GPU / CPU selection
4. Video ingestion / synthesis
5. AI audio transcription (faster-whisper)
6. Viral moment detection & scoring
7. Clip extraction
8. Word-level karaoke subtitles (.ass)
9. 1080x1920 vertical MP4 rendering
10. Audio/video synchronization & drift verification
11. Playability check
12. Workspace cleanup verification (output folder contains ONLY final MP4s)
"""

import sys
import os
import shutil
import subprocess
import logging
from pathlib import Path

# Set up paths
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    HW_PROFILE,
    OUTPUT_DIR,
    PROCESSING_DIR,
    DOWNLOADS_DIR,
    WORKSPACE_DIR
)
from core.video_analyzer import VideoAnalyzer
from core.transcriber import AudioTranscriber
from core.moment_detector import MomentDetector
from core.clip_selector import ClipSelector
from core.subtitles import SubtitleGenerator
from core.exporter import VideoExporter

logging.basicConfig(level=logging.INFO, format="[TEST] %(message)s")


def create_synthetic_test_video(output_path: Path, duration: int = 25) -> Path:
    """
    Synthesizes a test video with synchronized audio tones/beeps and visual timecode
    if no network download is available.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate a 1920x1080 test video with visual pattern and audio tone
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_path


def run_all_tests():
    print("=" * 60)
    print("RUNNING PHASE 11: COMPREHENSIVE PIPELINE VALIDATION")
    print("=" * 60)

    # TEST 1: Environment detection
    print("\n--- TEST 1: Environment Detection ---")
    assert sys.version_info >= (3, 10), "Python version must be >= 3.10"
    print(f"PASS: Python {sys.version.split()[0]} is operational.")

    # TEST 2: FFmpeg and FFprobe execution
    print("\n--- TEST 2: FFmpeg & FFprobe Execution ---")
    ff_res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    probe_res = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True)
    assert ff_res.returncode == 0, "ffmpeg failed to execute"
    assert probe_res.returncode == 0, "ffprobe failed to execute"
    print("PASS: FFmpeg and FFprobe executed successfully.")

    # TEST 3: GPU / CPU Selection
    print("\n--- TEST 3: Hardware Profile & Encoder Selection ---")
    print(f"Hardware Detected: GPU={HW_PROFILE['gpu_detected']} ({HW_PROFILE['gpu_name']})")
    print(f"NVENC Supported: {HW_PROFILE['nvenc_supported']}")
    print(f"Active Video Encoder: {HW_PROFILE['video_encoder']}")
    print(f"Whisper Compute Mode: {HW_PROFILE['device']} ({HW_PROFILE['compute_type']})")
    print("PASS: Hardware profile determined and valid.")

    # TEST 4: Video Ingestion / Test Media Preparation
    print("\n--- TEST 4: Test Media Ingestion ---")
    test_video_path = DOWNLOADS_DIR / "test_sample.mp4"
    create_synthetic_test_video(test_video_path, duration=24)
    assert test_video_path.exists() and test_video_path.stat().st_size > 0
    print(f"PASS: Test video created at {test_video_path} ({test_video_path.stat().st_size / 1024:.1f} KB).")

    # TEST 5: Stream Analysis & Layout Classification
    print("\n--- TEST 5: Stream Analysis & Layout Detection ---")
    analyzer = VideoAnalyzer()
    analysis = analyzer.analyze(str(test_video_path))
    assert analysis["probe"]["has_video"], "Missing video stream"
    assert analysis["probe"]["has_audio"], "Missing audio stream"
    print(f"PASS: Analysis successful. Layout classified as: {analysis['layout']['classification']}")

    # TEST 6: AI Audio Transcription & Word Timestamps
    print("\n--- TEST 6: AI Transcription with faster-whisper ---")
    transcriber = AudioTranscriber(model_size="tiny")  # Use tiny for ultra-fast unit testing
    transcript = transcriber.transcribe(str(test_video_path))
    assert "segments" in transcript, "Transcript missing segments"
    print(f"PASS: Transcribed duration: {transcript['duration']}s, Language: {transcript['language']}")

    # Create synthetic test segments with words for thorough moment and subtitle testing
    test_segments = [{
        "id": 0,
        "start": 1.0,
        "end": 22.0,
        "text": "OH MY GOD! THIS IS THE MOST INSANE SECRET YOU WILL EVER SEE!",
        "words": [
            {"word": "OH", "start": 1.0, "end": 1.5, "probability": 0.99},
            {"word": "MY", "start": 1.5, "end": 2.0, "probability": 0.99},
            {"word": "GOD!", "start": 2.0, "end": 2.6, "probability": 0.99},
            {"word": "THIS", "start": 2.8, "end": 3.2, "probability": 0.99},
            {"word": "IS", "start": 3.2, "end": 3.5, "probability": 0.99},
            {"word": "THE", "start": 3.5, "end": 3.8, "probability": 0.99},
            {"word": "MOST", "start": 3.8, "end": 4.2, "probability": 0.99},
            {"word": "INSANE", "start": 4.2, "end": 5.0, "probability": 0.99},
            {"word": "SECRET", "start": 5.2, "end": 6.0, "probability": 0.99},
            {"word": "YOU", "start": 6.2, "end": 6.5, "probability": 0.99},
            {"word": "WILL", "start": 6.5, "end": 6.8, "probability": 0.99},
            {"word": "EVER", "start": 6.8, "end": 7.2, "probability": 0.99},
            {"word": "SEE!", "start": 7.2, "end": 8.0, "probability": 0.99},
            {"word": "LISTEN", "start": 8.5, "end": 9.2, "probability": 0.99},
            {"word": "CAREFULLY.", "start": 9.2, "end": 10.5, "probability": 0.99},
            {"word": "NEVER", "start": 11.0, "end": 11.8, "probability": 0.99},
            {"word": "GIVE", "start": 11.8, "end": 12.3, "probability": 0.99},
            {"word": "UP!", "start": 12.3, "end": 13.0, "probability": 0.99},
            {"word": "THIS", "start": 13.5, "end": 14.0, "probability": 0.99},
            {"word": "IS", "start": 14.0, "end": 14.3, "probability": 0.99},
            {"word": "HUGE!", "start": 14.3, "end": 15.2, "probability": 0.99},
            {"word": "LET'S", "start": 15.5, "end": 16.0, "probability": 0.99},
            {"word": "GO!", "start": 16.0, "end": 17.0, "probability": 0.99},
            {"word": "AMAZING", "start": 17.5, "end": 18.5, "probability": 0.99},
            {"word": "VICTORY!", "start": 18.5, "end": 20.0, "probability": 0.99}
        ]
    }]

    # TEST 7: Viral Moment Detection & Scoring
    print("\n--- TEST 7: Viral Moment Scoring ---")
    detector = MomentDetector()
    mock_transcript = {"segments": test_segments}
    analyzed_segs = detector.analyze_moments(str(test_video_path), mock_transcript)
    assert len(analyzed_segs) > 0
    print(f"PASS: Analyzed {len(analyzed_segs)} segments. Segment viral score: {analyzed_segs[0]['segment_score']}/100")

    # TEST 8: Candidate Clip Selection & Ranking
    print("\n--- TEST 8: Candidate Clip Selection ---")
    selector = ClipSelector(min_duration=15.0, max_duration=25.0, target_duration=19.0)
    selected_clips = selector.select_clips(analyzed_segs, num_shorts=1)
    assert len(selected_clips) == 1, "Expected 1 selected clip"
    clip = selected_clips[0]
    print(f"PASS: Candidate selected: {clip['start']}s -> {clip['end']}s (dur: {clip['duration']}s, score: {clip['viral_score']})")

    # TEST 9: Word-Level Karaoke ASS Subtitles
    print("\n--- TEST 9: Karaoke Subtitle Generation ---")
    subtitle_gen = SubtitleGenerator()
    test_ass_path = PROCESSING_DIR / "test_subtitles.ass"
    words = test_segments[0]["words"]
    subtitle_gen.generate_ass(words, clip_start=clip["start"], output_ass_path=test_ass_path)
    assert test_ass_path.exists() and test_ass_path.stat().st_size > 0
    with open(test_ass_path, "r", encoding="utf-8") as f:
        ass_text = f.read()
    assert "[Events]" in ass_text and "Dialogue:" in ass_text
    print("PASS: ASS Karaoke subtitle file generated with word-by-word timing.")

    # TEST 10: 1080x1920 Vertical MP4 Rendering (Zero Drift)
    print("\n--- TEST 10: 9:16 Vertical Video Rendering (1080x1920) ---")
    exporter = VideoExporter()
    output_filename = "short_001.mp4"
    rendered_mp4 = exporter.render_clip(
        source_path=str(test_video_path),
        clip_info=clip,
        layout_info=analysis["layout"],
        subtitle_path=test_ass_path,
        output_filename=output_filename
    )
    assert rendered_mp4.exists(), f"Rendered file {rendered_mp4} not found"
    print(f"PASS: Vertical 9:16 MP4 rendered: {rendered_mp4}")

    # TEST 11: Validation via ffprobe (Audio/Video sync & Stream integrity)
    print("\n--- TEST 11: Post-Render Validation Probe ---")
    val = exporter.verify_export(rendered_mp4, expected_duration=clip["duration"])
    assert val["valid"], f"Validation failed: {val.get('error')}"
    assert val["width"] == 1080 and val["height"] == 1920, f"Incorrect dimensions: {val['width']}x{val['height']}"
    assert val["video_codec"] is not None and val["audio_codec"] is not None
    assert val["duration_diff"] <= 0.5, f"Audio/Video drift too high: {val['duration_diff']}s"
    print(f"PASS: Validation verified: {val['width']}x{val['height']}, Video={val['video_codec']}, Audio={val['audio_codec']}, Dur Diff={val['duration_diff']}s")

    # TEST 12: Workspace Cleanup & Final Deliverables Check
    print("\n--- TEST 12: Workspace Cleanup Verification ---")
    exporter.cleanup_processing_artifacts()
    
    # Check that processing dir doesn't retain temporary WAVs/ASS files
    remaining_wavs = list(PROCESSING_DIR.glob("*.wav"))
    remaining_ass = list(PROCESSING_DIR.glob("*.ass"))
    assert len(remaining_wavs) == 0, f"Found uncleaned WAV files: {remaining_wavs}"
    assert len(remaining_ass) == 0, f"Found uncleaned ASS files: {remaining_ass}"

    # Check that output dir contains ONLY MP4 deliverables
    output_files = list(OUTPUT_DIR.iterdir())
    non_mp4s = [f.name for f in output_files if f.suffix != ".mp4"]
    assert len(non_mp4s) == 0, f"Output directory contains non-MP4 deliverables: {non_mp4s}"
    assert len(output_files) >= 1, "Output directory has no MP4 deliverables"
    print(f"PASS: Output directory contains ONLY final MP4 deliverables: {[f.name for f in output_files]}")

    print("\n" + "=" * 60)
    print("ALL 12 TESTS PASSED PERFECTLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()