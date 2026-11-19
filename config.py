"""
Configuration module for ViralShortsEngine.
Manages hardware detection, directory paths, video processing profiles,
and subtitle styling parameters.
"""

import os
import sys

# Prevent HF Hub xet hang on Windows
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import shutil
import subprocess
import logging
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
CORE_DIR = BASE_DIR / "core"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
WORKSPACE_DIR = BASE_DIR / "workspace"
DOWNLOADS_DIR = WORKSPACE_DIR / "downloads"
PROCESSING_DIR = WORKSPACE_DIR / "processing"
OUTPUT_DIR = WORKSPACE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Ensure all essential directories exist
for directory in [ASSETS_DIR, FONTS_DIR, WORKSPACE_DIR, DOWNLOADS_DIR, PROCESSING_DIR, OUTPUT_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Logging Setup
LOG_FILE = LOGS_DIR / "engine.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ViralShortsEngine.Config")


def detect_ffmpeg_binaries():
    """Verify and locate ffmpeg and ffprobe."""
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    return ffmpeg_bin, ffprobe_bin


def detect_hardware():
    """
    Detect NVIDIA GPU, VRAM, and FFmpeg NVENC encoder support.
    Returns:
        dict: Hardware profile with device, compute_type, video_encoder, and whisper_model.
    """
    profile = {
        "gpu_detected": False,
        "gpu_name": "None",
        "vram_mb": 0,
        "nvenc_supported": False,
        "video_encoder": "libx264",
        "device": "cpu",
        "compute_type": "int8",
        "whisper_model": "small",
        "threads": max(1, os.cpu_count() or 4)
    }

    # 1. Test nvidia-smi
    try:
        smi_out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        if smi_out:
            lines = smi_out.splitlines()
            if lines:
                parts = lines[0].split(",")
                profile["gpu_detected"] = True
                profile["gpu_name"] = parts[0].strip()
                if len(parts) > 1:
                    profile["vram_mb"] = int(float(parts[1].strip()))
    except Exception:
        profile["gpu_detected"] = False

    # 2. Test FFmpeg NVENC support
    try:
        encoders_out = subprocess.check_output(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        if "h264_nvenc" in encoders_out and profile["gpu_detected"]:
            profile["nvenc_supported"] = True
    except Exception:
        profile["nvenc_supported"] = False

    # 3. Configure optimal encoding and Whisper settings
    if profile["gpu_detected"] and profile["nvenc_supported"]:
        profile["video_encoder"] = "h264_nvenc"
        profile["device"] = "cuda"
        profile["compute_type"] = "float16"
        if profile["vram_mb"] >= 10000:
            profile["whisper_model"] = "large-v3"
        elif profile["vram_mb"] >= 5000:
            profile["whisper_model"] = "medium"
        else:
            profile["whisper_model"] = "small"
    else:
        profile["video_encoder"] = "libx264"
        profile["device"] = "cpu"
        profile["compute_type"] = "int8"
        profile["whisper_model"] = "small"

    return profile


# Active Hardware Profile
HW_PROFILE = detect_hardware()

# Target Video Specifications (9:16 Viral Canvas)
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
TARGET_FPS = 30
AUDIO_SAMPLE_RATE = 44100
AUDIO_BITRATE = "192k"

# Clip Duration Constraints (seconds)
MIN_CLIP_DURATION = 20.0
DEFAULT_MIN_DURATION = 35.0
DEFAULT_MAX_DURATION = 45.0
MAX_CLIP_DURATION = 60.0
EXTENDED_CLIP_DURATION = 90.0

# Subtitle Styling Settings (Word-by-word Karaoke)
SUBTITLE_CONFIG = {
    "font_name": "Arial Black",  # Universal high-impact bold font
    "font_size": 72,
    "primary_color": "&H00FFFFFF",      # Pure White (AABBGGRR in ASS)
    "highlight_color": "&H0000E5FF",    # Electric Yellow / Gold
    "outline_color": "&H00000000",      # Thick Black Outline
    "back_color": "&H80000000",         # Semi-transparent shadow
    "outline_width": 4.5,
    "shadow_depth": 2.0,
    "margin_v": 320,                    # Safe vertical margin from bottom
    "max_words_per_line": 4,            # Punchy short lines
    "max_lines": 2
}

# FFmpeg Encoding Options
ENCODING_CONFIG = {
    "gpu_encoder": "h264_nvenc",
    "gpu_preset": "p5",
    "gpu_cq": 23,
    "cpu_encoder": "libx264",
    "cpu_preset": "veryfast",
    "cpu_crf": 22,
    "audio_encoder": "aac",
    "audio_bitrate": "192k",
    "faststart": True
}