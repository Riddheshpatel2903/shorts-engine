"""
ViralShorts Pro - Multi-Modal AI Video Studio.
Professional 3-Section Architecture:
1. 🎬 Viral Shorts Studio: Link / File -> Intelligent Highlight & Reaction Discovery -> Facecam & Speaker Tracking Framing -> Approval -> 9:16 Short Render & 1-Click Social Publish
2. 🎞️ Long Video Generator: Link / File -> Discover Stream & Podcast Highlight Chapters -> Interactive Chapter Selection & Titles -> Merged 16:9 Long Video with Transitions, Chapter Lower-Thirds & Normalized Audio -> YouTube Publishing with Clickable Timestamps
3. 📁 Video Library & Storage: Unified Gallery for all Shorts & Long Videos, Single-Click Deletion for Unwanted Clips, Automated Background Memory Purge, and Disk Space Telemetry
"""

import sys
import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from config import (
    BASE_DIR,
    HW_PROFILE,
    OUTPUT_DIR,
    PROCESSING_DIR,
    DOWNLOADS_DIR,
    WORKSPACE_DIR,
    logger
)
from core.downloader import VideoDownloader
from core.video_analyzer import VideoAnalyzer
from core.face_detector import FaceDetector
from core.transcriber import AudioTranscriber
from core.moment_detector import MomentDetector, classify_video_niche
from core.clip_selector import ClipSelector
from core.subtitles import SubtitleGenerator, SUBTITLE_PRESETS
from core.exporter import VideoExporter, exporter
from core.ai_brain import ai_brain
from core.cleaner import workspace_cleaner
from core.publisher import publisher
from core.autoclip_precision import autoclip_aligner, autoclip_cutter
from core.chat_analyzer import chat_analyzer
from core.long_video_generator import long_video_generator
from core.scheduler import scheduler, DAILY_SLOTS

face_detector = FaceDetector()

# Automatic memory cleaner on startup/turn: silently purge temporary audio and .ass fragments
try:
    workspace_cleaner.auto_purge_temp_cache(max_age_hours=0.5)
except Exception:
    pass

# Page Configuration
st.set_page_config(
    page_title="ViralShorts Pro Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Time format helper
def format_time(seconds: float) -> str:
    s = int(max(0, seconds))
    m = s // 60
    h = m // 60
    m = m % 60
    sec = s % 60
    if h > 0:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

# Word extraction helper
def get_words_for_window(transcript: Dict[str, Any], start_t: float, end_t: float) -> List[Dict[str, Any]]:
    words = []
    if not transcript:
        return words
    for seg in transcript.get("segments", []):
        if seg.get("end", 0) < start_t or seg.get("start", 0) > end_t:
            continue
        for w in seg.get("words", []):
            if w.get("end", 0) >= start_t and w.get("start", 0) <= end_t:
                words.append(w)
    return words

# Video Library and Display Helpers
def get_rendered_videos(pattern: str = "*.mp4") -> List[Path]:
    """Scans OUTPUT_DIR for valid rendered MP4s sorted newest first."""
    if not OUTPUT_DIR.exists():
        return []
    videos = [p for p in OUTPUT_DIR.glob(pattern) if p.is_file() and p.stat().st_size > 0]
    videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return videos

def render_video_player(video_path: Path, key_prefix: str = "") -> bool:
    """Safely reads and renders an MP4 video using bytes to avoid browser stream restrictions."""
    if not video_path or not video_path.exists():
        st.warning(f"Video file not found: {video_path}")
        return False
    try:
        with open(video_path, "rb") as vf:
            video_bytes = vf.read()
        st.video(video_bytes, format="video/mp4")
        st.download_button(
            label=f"⬇️ Download {video_path.name}",
            data=video_bytes,
            file_name=video_path.name,
            mime="video/mp4",
            use_container_width=True,
            key=f"{key_prefix}_dl_{video_path.name}"
        )
        return True
    except Exception as e:
        st.error(f"Error loading video {video_path.name}: {e}")
        return False

def render_publish_status_banner():
    """Renders prominent status messages when auto-publishing completes."""
    msg = st.session_state.get("publish_status_msg")
    if not msg:
        return
    if isinstance(msg, dict):
        yt = msg.get("youtube")
        ig = msg.get("instagram")
        if yt and isinstance(yt, dict):
            if yt.get("success"):
                st.success(f"🚀 Published to YouTube Shorts: [{yt.get('url')}]({yt.get('url')})")
            elif yt.get("error"):
                st.info(f"YouTube Upload Note: {yt.get('error')}")
        if ig and isinstance(ig, dict):
            if ig.get("success"):
                st.success(f"🚀 Published to Instagram Reels: [{ig.get('url')}]({ig.get('url')})")
            elif ig.get("error"):
                st.info(f"Instagram Upload Note: {ig.get('error')}")

# Modern Professional SaaS CSS (Stitch Velocity White & Royal Blue Theme)
st.markdown("""
<style>
    /* Global Base */
    .stApp {
        background-color: #f8fafc !important;
        color: #0f172a !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    
    /* Studio Card */
    .pro-card {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 20px 24px !important;
        margin-bottom: 20px !important;
        box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.05), 0 1px 2px -1px rgba(15, 23, 42, 0.05) !important;
    }
    .pro-card-header {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        margin-bottom: 12px !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        border-bottom: 1px solid #f1f5f9 !important;
        padding-bottom: 8px !important;
    }
    
    /* Professional Badges */
    .pro-badge {
        display: inline-block !important;
        padding: 3px 10px !important;
        border-radius: 6px !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.02em !important;
        text-transform: uppercase !important;
    }
    .badge-blue { background: #eff6ff !important; color: #2563eb !important; border: 1px solid #bfdbfe !important; }
    .badge-green { background: #ecfdf5 !important; color: #059669 !important; border: 1px solid #a7f3d0 !important; }
    .badge-amber { background: #fffbeb !important; color: #d97706 !important; border: 1px solid #fde68a !important; }
    .badge-purple { background: #faf5ff !important; color: #7c3aed !important; border: 1px solid #ddd6fe !important; }
    .badge-red { background: #fef2f2 !important; color: #dc2626 !important; border: 1px solid #fecaca !important; }
    .badge-pink { background: #fdf2f8 !important; color: #db2777 !important; border: 1px solid #fbcfe8 !important; }
    
    /* Sidebar Navigation */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0 !important;
    }

    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    }

    /* Primary Buttons */
    button[kind="primary"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
        box-shadow: 0 1px 2px 0 rgba(37, 99, 235, 0.2) !important;
    }
    button[kind="primary"]:hover {
        background-color: #1d4ed8 !important;
    }

    /* Secondary Buttons */
    button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }
    button[kind="secondary"]:hover {
        background-color: #f8fafc !important;
        border-color: #94a3b8 !important;
        color: #2563eb !important;
    }

    /* Calendar & Tray Styling */
    .cal-cell {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 10px;
        min-height: 120px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
    }
    .cal-slot-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 3px solid #2563eb;
        border-radius: 6px;
        padding: 6px 8px;
        margin-bottom: 6px;
    }
    .short-item-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .short-item-card:hover {
        border-color: #93c5fd;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.08);
    }
</style>
""", unsafe_allow_html=True)

# State initialization
if "nav_tab" not in st.session_state:
    st.session_state.nav_tab = "🎬 Viral Shorts Studio"
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "selected_clip_window" not in st.session_state:
    st.session_state.selected_clip_window = {"start": 0.0, "end": 35.0}
if "generated_short" not in st.session_state:
    st.session_state.generated_short = None
if "publish_status_msg" not in st.session_state:
    st.session_state.publish_status_msg = None

# Long Video State
if "long_analysis_result" not in st.session_state:
    st.session_state.long_analysis_result = None
if "long_chapters" not in st.session_state:
    st.session_state.long_chapters = []
if "generated_long_video" not in st.session_state:
    st.session_state.generated_long_video = None
if "long_yt_meta" not in st.session_state:
    st.session_state.long_yt_meta = None

# Calendar & Scheduling State
if "calendar_week_offset" not in st.session_state:
    st.session_state.calendar_week_offset = 0
if "target_schedule_slot" not in st.session_state:
    st.session_state.target_schedule_slot = None
if "calendar_platform_filter" not in st.session_state:
    st.session_state.calendar_platform_filter = "All Platforms"

# Storage telemetry
storage_info = workspace_cleaner.get_storage_stats()
social_status = publisher.get_status()
all_rendered_videos = get_rendered_videos("*.mp4")


# =======================================================
# LEFT SIDEBAR NAVIGATION & SETTINGS
# =======================================================
with st.sidebar:
    st.markdown("### ViralShorts Pro")
    st.caption("AI-Powered Video Studio")

    # Robust Streamlit Native Radio Navigation
    nav_options = [
        "🎬 Viral Shorts Studio",
        "⚡ Auto-Catch Viral Reels",
        "🎞️ Long Video Generator",
        "📅 Publishing Calendar & Library"
    ]

    # Initialize widget state if missing
    if "main_nav_radio" not in st.session_state:
        init_nav = st.session_state.get("nav_tab", nav_options[0])
        if any(k in str(init_nav) for k in ["Calendar", "Library", "Publishing"]):
            init_nav = nav_options[3]
        elif any(k in str(init_nav) for k in ["Long Video", "🎞️"]):
            init_nav = nav_options[2]
        elif any(k in str(init_nav) for k in ["Auto-Catch", "⚡"]):
            init_nav = nav_options[1]
        elif init_nav not in nav_options:
            init_nav = nav_options[0]
        st.session_state.main_nav_radio = init_nav

    selected_section = st.radio(
        "Studio Sections:",
        options=nav_options,
        key="main_nav_radio"
    )
    st.session_state.nav_tab = selected_section

    st.markdown(f"**Rendered Library:** `{len(all_rendered_videos)} videos ready`")
    st.divider()

    # Automated Social Media Publishing (Playwright Browser Sessions)
    with st.expander("🚀 Social Media Accounts & Publishing", expanded=False):
        st.caption("Sign in once to save cookies. Automatic 1-click publishing for your channels.")

        # 1. YouTube Shorts / Videos
        st.markdown("#### 📺 YouTube Studio")
        yt_conn = social_status.get("youtube_connected", False)
        st.markdown(f"Status: **{'🟢 Ready (Logged In)' if yt_conn else '⚪ Not Logged In'}**")

        c_yt_act1, c_yt_act2 = st.columns([1.5, 1])
        with c_yt_act1:
            if st.button("🌐 YouTube Login", key="btn_yt_login_pw", use_container_width=True):
                res = publisher.open_login_browser("youtube")
                st.info(res.get("message", "Browser window opened."))
        with c_yt_act2:
            yt_priv = st.selectbox(
                "Upload Privacy:",
                options=["public", "unlisted", "private"],
                index=0 if social_status.get("youtube_privacy") == "public" else (1 if social_status.get("youtube_privacy") == "unlisted" else 2),
                key="yt_priv_select"
            )
            if yt_priv != social_status.get("youtube_privacy"):
                publisher.update_settings(youtube_privacy=yt_priv)

        st.divider()

        # 2. Instagram Reels
        st.markdown("#### 📸 Instagram Reels")
        ig_conn = social_status.get("instagram_connected", False)
        st.markdown(f"Status: **{'🟢 Ready (Logged In)' if ig_conn else '⚪ Not Logged In'}**")

        if st.button("🌐 Instagram Login", key="btn_ig_login_pw", use_container_width=True):
            res = publisher.open_login_browser("instagram")
            st.info(res.get("message", "Browser window opened."))

        st.divider()

        # Auto-publish toggle
        auto_post_toggle = st.checkbox("⚡ Auto-publish Shorts upon render (YouTube & Instagram)", value=social_status.get("auto_publish", True), key="chk_autopub")
        if auto_post_toggle != social_status.get("auto_publish"):
            publisher.update_settings(auto_publish_on_render=auto_post_toggle)
            st.rerun()

        if st.button("🔄 Refresh Login Status", use_container_width=True, key="btn_refresh_status"):
            st.rerun()

        if st.button("🧹 Unlock Profiles (Fix Session Errors)", use_container_width=True, key="btn_unlock_profiles"):
            publisher.unlock_profiles()
            st.success("Browser profile locks cleared and zombie sessions closed!")
            st.rerun()

    # Quick Storage Monitor in Sidebar
    with st.expander("💾 Quick Storage Telemetry", expanded=False):
        reclaim_gb = storage_info["downloads_size_gb"]
        temp_mb = storage_info["temp_size_mb"]
        st.markdown(f"**Source Downloads:** `{reclaim_gb:.2f} GB`")
        st.markdown(f"**Temp Audio/Ass Cache:** `{temp_mb:.1f} MB`")
        if st.button("🧹 Quick Cache Purge", use_container_width=True):
            res = workspace_cleaner.clean_temporary_files()
            st.success(f"Freed {res['freed_mb']:.1f} MB cache.")
            st.rerun()

    st.caption("Engine: faster-whisper int8 • FFmpeg NVENC/libx264")


# =======================================================
# TOP HEADER & SECTION NAVIGATION BAR
# =======================================================
with st.container():
    st.markdown("<div class='pro-card' style='padding: 12px 18px; margin-bottom: 16px;'>", unsafe_allow_html=True)
    c_brand, c_tabs = st.columns([1, 2.5])
    with c_brand:
        st.markdown("<div style='font-size: 1.25rem; font-weight: 800; color: #0f172a; padding-top: 4px;'>⚡ ViralShorts <span style='color: #2563eb;'>Studio</span></div>", unsafe_allow_html=True)
    with c_tabs:
        tc1, tc2, tc3, tc4 = st.columns(4)
        with tc1:
            if st.button("🎬 Viral Shorts", key="top_nav_shorts", use_container_width=True, type="primary" if "Shorts" in st.session_state.nav_tab else "secondary"):
                st.session_state.main_nav_radio = "🎬 Viral Shorts Studio"
                st.session_state.nav_tab = "🎬 Viral Shorts Studio"
                st.rerun()
        with tc2:
            if st.button("⚡ Catch Reels", key="top_nav_reels", use_container_width=True, type="primary" if "Auto-Catch" in st.session_state.nav_tab else "secondary"):
                st.session_state.main_nav_radio = "⚡ Auto-Catch Viral Reels"
                st.session_state.nav_tab = "⚡ Auto-Catch Viral Reels"
                st.rerun()
        with tc3:
            if st.button("🎞️ Long Videos", key="top_nav_long", use_container_width=True, type="primary" if "Long Video" in st.session_state.nav_tab else "secondary"):
                st.session_state.main_nav_radio = "🎞️ Long Video Generator"
                st.session_state.nav_tab = "🎞️ Long Video Generator"
                st.rerun()
        with tc4:
            if st.button("📅 Calendar & Library", key="top_nav_calendar", use_container_width=True, type="primary" if any(k in st.session_state.nav_tab for k in ["Calendar", "Library", "Publishing"]) else "secondary"):
                st.session_state.main_nav_radio = "📅 Publishing Calendar & Library"
                st.session_state.nav_tab = "📅 Publishing Calendar & Library"
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# =======================================================
# SECTION 1: 🎬 VIRAL SHORTS STUDIO
# =======================================================
if st.session_state.nav_tab in ["🎬 Viral Shorts Studio", "Clip Studio"]:
    st.markdown("## 🎬 Viral Shorts Studio")
    st.caption("Turn long videos, streams, and podcasts into viral 9:16 Shorts with smart face/speaker centering, punchline decay preservation, and auto-publishing.")

    # Step 1: Source Ingestion
    with st.container():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Source Ingestion & Auto-Batch Generation</span><span class='pro-badge badge-blue'>Step 1</span></div>", unsafe_allow_html=True)

        col_opt1, col_opt2 = st.columns([1.2, 0.8])
        with col_opt1:
            genre_choice = st.selectbox(
                "🎯 Viral Clipping Focus & Content Objective:",
                options=[
                    "🔥 Uncensored Roasts, Drama & Controversial Topics (Savage / Unhinged)",
                    "😂 Peak Humor, Banter & Standup Jokes (Prioritize Comedy & Punchlines)",
                    "⚡ Auto-Discover Best 15 Viral Highlights (All-Round Multi-Topic)",
                    "🎮 Clutch Gameplay & High Hype Action (Squad Wipes & Flicks)",
                    "💬 Superchats, Controversy & Drama (Viewer Callouts)",
                    "💡 Wisdom, Best Advice & Education (Talking Head)"
                ],
                index=0,
                key="shorts_genre_objective",
                help="Configures AI Brain (Ollama / Semantic NLP) to search for uncensored roasts, jokes, controversy, or clutch hype."
            )
        with col_opt2:
            num_shorts_target = st.slider(
                "🔢 Shorts to Auto-Generate in Batch:",
                min_value=1,
                max_value=20,
                value=15,
                step=1,
                key="shorts_batch_count",
                help="Automatically extracts and renders up to 15 distinct, non-overlapping shorts from the video in 1 click."
            )

        workflow_mode = st.radio(
            "⚡ Production Workflow Mode:",
            options=[
                "🚀 1-Click Fully Automatic (Auto-render all 15 Shorts directly - Zero manual clicking)",
                "🔍 Manual Review & Single Clip Approval (Fine-tune trim handles & framing)"
            ],
            index=0,
            horizontal=True,
            key="shorts_workflow_mode",
            help="1-Click Mode automatically generates all 15 shorts directly into your library ready to post. Manual Review opens the trim handle editor."
        )

        # Autoposting control & platform status banner
        col_pub_opt1, col_pub_opt2 = st.columns([1.2, 0.8])
        with col_pub_opt1:
            auto_publish_active = st.checkbox(
                "🚀 Auto-Post to YouTube Shorts & Instagram Reels upon render",
                value=social_status.get("auto_publish", True),
                key="chk_autopub_main",
                help="Automatically publishes generated viral shorts directly to your connected YouTube Shorts & Instagram Reels accounts."
            )
            if auto_publish_active != social_status.get("auto_publish"):
                publisher.update_settings(auto_publish_on_render=auto_publish_active)
        with col_pub_opt2:
            yt_on = social_status.get("youtube_connected", False)
            ig_on = social_status.get("instagram_connected", False)
            if yt_on and ig_on:
                st.success("🟢 Ready: YouTube & Instagram Connected")
            elif yt_on:
                st.info("🟢 Ready: YouTube Connected (IG not connected)")
            elif ig_on:
                st.info("🟢 Ready: Instagram Connected (YT not connected)")
            else:
                st.warning("⚪ Note: Sign in via sidebar to enable live posting")

        c_in_type1, c_in_type2 = st.tabs(["Online Video Link (YouTube / Twitch / Kick / Reels)", "Upload Local Video / Direct File Path"])

        source_input_path = None
        source_url_target = None

        with c_in_type1:
            url_val = st.text_input(
                "Enter Video or Stream URL:",
                placeholder="https://www.youtube.com/watch?v=... (YouTube Live, Twitch, Kick, or VOD)",
                label_visibility="collapsed",
                key="shorts_url_input"
            )

            c_mode_col1, c_mode_col2 = st.columns([1.2, 0.8])
            with c_mode_col1:
                capture_mode = st.radio(
                    "Ingestion Strategy:",
                    options=["⚡ Live Rolling Fragment (Instant ~3s)", "📥 Full Video Download"],
                    horizontal=True,
                    help="Live Rolling Fragment captures recent stream footage in ~3s without downloading multi-hour broadcasts."
                )
            with c_mode_col2:
                if capture_mode.startswith("⚡"):
                    frag_duration = st.selectbox(
                        "Fragment Window:",
                        options=[60, 90, 120, 180, 300],
                        index=2,
                        format_func=lambda s: f"{s}s ({s//60}m {s%60}s) Buffer",
                        key="shorts_frag_dur"
                    )
                else:
                    frag_duration = 120

            col_btn1, col_btn2 = st.columns([1.2, 0.8])
            with col_btn1:
                if capture_mode.startswith("⚡"):
                    btn_text = f"⚡ Grab Live Fragment ({frag_duration}s) & Auto-Clip"
                elif workflow_mode.startswith("🚀"):
                    btn_text = f"🚀 Auto-Generate Top {num_shorts_target} Viral Shorts (1-Click Batch)"
                else:
                    btn_text = f"🔍 Analyze & Select Top {num_shorts_target} Moments"
                do_analyze = st.button(btn_text, type="primary", use_container_width=True, key="btn_shorts_analyze")

            with col_btn2:
                do_inspect = st.button("🔍 Check Stream Info", use_container_width=True, key="btn_shorts_inspect")

            if do_inspect and url_val and url_val.strip():
                with st.spinner("Checking live broadcast status & scouting active creator debates..."):
                    try:
                        downloader = VideoDownloader()
                        info_check = downloader.get_info(url_val.strip())
                        from core.social_trend_scout import social_trend_scout
                        trend_info = social_trend_scout.scout_creator_trends(info_check)
                        live_badge = "🔴 LIVE BROADCAST NOW" if info_check.get("is_live") else "📼 Pre-recorded / VOD"
                        st.info(
                            f"**{live_badge}** | **Title:** `{info_check.get('title')[:60]}` | "
                            f"**Creator:** `{trend_info.get('creator') or info_check.get('uploader')}` | "
                            f"**Duration:** `{format_time(info_check.get('duration', 0))}`"
                        )
                        if trend_info.get("hot_debates"):
                            st.markdown(
                                f"🌐 **Social Media Trend Radar Active:** "
                                f"Scouted {len(trend_info['hot_debates'])} active controversies & debates for **{trend_info['creator']}**! "
                                f"Clipping will automatically match these trending topics:"
                            )
                            for d_item in trend_info["hot_debates"][:3]:
                                st.caption(f"🔥 *{d_item}*")
                    except Exception as e:
                        st.error(f"Could not inspect stream URL: {e}")

            if do_analyze and url_val and url_val.strip():
                downloader = VideoDownloader()
                if capture_mode.startswith("⚡"):
                    with st.spinner(f"Snatching {frag_duration}s live rolling fragment without downloading full stream..."):
                        meta = downloader.capture_live_fragment(url_val.strip(), duration_sec=frag_duration)
                        source_input_path = meta["filepath"]
                        source_url_target = meta
                else:
                    with st.spinner("Downloading stream metadata and extracting audio..."):
                        try:
                            meta = downloader.download(url_val.strip())
                            source_input_path = meta["filepath"]
                            source_url_target = meta
                        except Exception as e:
                            st.warning(f"Full download was reset by server ({e}). Auto-recovering with fast rolling stream fragment...")
                            try:
                                meta = downloader.capture_live_fragment(url_val.strip(), duration_sec=180)
                                source_input_path = meta["filepath"]
                                source_url_target = meta
                                st.success(f"Auto-recovered! Snatched recent 180s stream buffer from `{meta.get('title')}`.")
                            except Exception as e2:
                                st.error(f"Download issue: {e}\n\n💡 Tip: For live streams or recent live broadcasts, select '⚡ Live Rolling Fragment' above to snatch clips instantly!")

        with c_in_type2:
            st.caption("Upload files up to 4GB, or paste local path for instant 0s loading on massive files (e.g. 50GB OBS recordings).")
            up_file = st.file_uploader("Select recording (.mp4, .mov, .mkv - Up to 4GB):", type=["mp4", "mov", "mkv"], key="shorts_file_up")
            if up_file:
                file_mb = round(len(up_file.getvalue()) / (1024 * 1024), 1) if hasattr(up_file, "getvalue") else 0
                st.caption(f"📁 Selected: `{up_file.name}` ({file_mb} MB)")
                up_btn_text = f"🚀 Auto-Generate Top {num_shorts_target} Viral Shorts (1-Click)" if workflow_mode.startswith("🚀") else "Analyze Uploaded File"
                if st.button(up_btn_text, type="primary", use_container_width=True, key="btn_shorts_analyze_up"):
                    save_loc = DOWNLOADS_DIR / up_file.name
                    with open(save_loc, "wb") as f:
                        f.write(up_file.getbuffer())
                    source_input_path = str(save_loc)
                    source_url_target = {"id": up_file.name, "title": up_file.name, "filepath": str(save_loc)}

            st.markdown("---")
            local_path_input = st.text_input(
                "📁 Or Enter Local Video Path (Instant 0s Load, any size e.g. 10GB+):",
                placeholder=r"e.g. C:\Users\patel\Videos\gameplay_recording.mp4",
                key="shorts_local_path"
            )
            if local_path_input and local_path_input.strip():
                clean_p = Path(local_path_input.strip().strip('"').strip("'"))
                loc_btn_text = f"🚀 Auto-Generate Top {num_shorts_target} Viral Shorts from Local File (1-Click)" if workflow_mode.startswith("🚀") else "Load Local Video File"
                if st.button(loc_btn_text, key="btn_load_local_shorts", use_container_width=True, type="primary" if workflow_mode.startswith("🚀") else "secondary"):
                    if clean_p.exists() and clean_p.is_file():
                        source_input_path = str(clean_p.resolve())
                        source_url_target = {"id": clean_p.stem, "title": clean_p.stem, "filepath": str(clean_p.resolve())}
                        st.success(f"Loaded `{clean_p.name}` directly from disk!")
                    else:
                        st.error(f"File not found: {clean_p}")

        # Perform analysis if path resolved
        if source_input_path:
            with st.spinner("Analyzing audio energy spikes, speech cadence, and camera framing..."):
                analyzer = VideoAnalyzer()
                analysis = analyzer.analyze(source_input_path)
                probe = analysis.get("probe", {})
                dur = float(probe.get("duration", 0.0))

                transcriber = AudioTranscriber()
                scan_len = min(dur, 600.0) if dur > 0 else 300.0
                transcript = transcriber.transcribe(source_input_path, start_time=0.0, duration=scan_len)

                detector = MomentDetector()

                # Ultra-fast acoustic energy reaction peak scanner across ENTIRE video duration
                try:
                    acoustic_peaks = detector.find_audio_energy_peaks(source_input_path, top_n=6, window_duration=35.0)
                except Exception as e:
                    logger.debug(f"Acoustic peak scanner fallback: {e}")
                    acoustic_peaks = []

                # Multi-Peak Deep Transcription:
                # If broadcast exceeds 600s and peaks are discovered in the later part of the video,
                # transcribe focused 45s slices around them so they receive real words, karaoke subtitles, and humor scoring!
                if dur > 600.0 and acoustic_peaks:
                    existing_segments = transcript.get("segments", [])
                    max_existing_t = max((s["end"] for s in existing_segments), default=0.0)
                    for pk in acoustic_peaks:
                        pk_start = float(pk["start"])
                        if pk_start > max_existing_t:
                            try:
                                pk_slice = transcriber.transcribe(source_input_path, start_time=pk_start, duration=float(pk["duration"]))
                                if pk_slice and pk_slice.get("segments"):
                                    transcript["segments"].extend(pk_slice["segments"])
                                    logger.info(f"Deep-transcribed peak slice at {pk_start:.1f}s ({len(pk_slice['segments'])} segments).")
                            except Exception as pe:
                                logger.debug(f"Slice transcription error at {pk_start}: {pe}")
                    transcript["segments"].sort(key=lambda s: s["start"])

                from core.social_trend_scout import social_trend_scout
                meta_payload = source_url_target or {"title": Path(source_input_path).stem}
                trend_profile = social_trend_scout.scout_creator_trends(meta_payload)
                if trend_profile.get("hot_debates"):
                    st.toast(f"🌐 Trend Radar: Targeting active debates for {trend_profile['creator']}!", icon="🔥")

                segments = detector.analyze_moments(source_input_path, transcript, trend_profile=trend_profile)

                # Determine genre focus from user selection
                chosen_genre_raw = st.session_state.get("shorts_genre_objective", "🔥")
                if "Roast" in chosen_genre_raw or "Controversial" in chosen_genre_raw or "🔥" in chosen_genre_raw:
                    target_genre = "uncensored"
                elif "Humor" in chosen_genre_raw or "Comedy" in chosen_genre_raw or "😂" in chosen_genre_raw:
                    target_genre = "comedy"
                elif "Clutch" in chosen_genre_raw or "🎮" in chosen_genre_raw:
                    target_genre = "gaming"
                elif "Superchat" in chosen_genre_raw or "💬" in chosen_genre_raw:
                    target_genre = "superchat"
                elif "Wisdom" in chosen_genre_raw or "💡" in chosen_genre_raw:
                    target_genre = "advice"
                else:
                    target_genre = "all"

                target_count = int(st.session_state.get("shorts_batch_count", 15))

                # Use AI Brain with Ollama semantic moment extraction if available
                from core.ai_brain import ai_brain
                ai_moments = ai_brain.detect_uncensored_viral_moments(
                    transcript_segments=segments,
                    num_moments=target_count,
                    focus_genre=target_genre
                )

                selector = ClipSelector(min_duration=20.0, max_duration=55.0, genre_focus=target_genre)
                moments = selector.select_clips(
                    segments,
                    num_shorts=target_count,
                    genre_focus=target_genre,
                    transcript=transcript,
                    extra_candidates=ai_moments or acoustic_peaks,
                    trend_profile=trend_profile
                )

                is_auto_mode = st.session_state.get("shorts_workflow_mode", "🚀").startswith("🚀")

                if is_auto_mode and moments:
                    # 🚀 1-CLICK AUTOMATIC BATCH GENERATION (ZERO MANUAL APPROVALS)
                    st.toast(f"Starting 1-Click Auto-Generation of {len(moments)} Viral Shorts...", icon="🚀")
                    status_box = st.status(f"🚀 Auto-Rendering Top {len(moments)} Viral Shorts in 1080x1920...", expanded=True)
                    exporter = VideoExporter()
                    prog_bar = st.progress(0.0)

                    def batch_progress_ui(cur, total, msg):
                        status_box.write(f"🎬 **[{cur}/{total}]** Rendering {msg} with karaoke subtitles, motion graphics & meme SFX...")
                        prog_bar.progress(cur / total)

                    layout_info = analysis.get("layout", {})
                    batch_rendered = exporter.batch_render_shorts(
                        source_path=source_input_path,
                        clips=moments,
                        layout_info=layout_info,
                        transcript_data=transcript,
                        style_preset="hormozi",
                        enable_motion_graphics=True,
                        enable_sfx=True,
                        interactive_overlay=None,
                        punchline_badge=None,
                        progress_callback=batch_progress_ui
                    )

                    if batch_rendered:
                        # Auto-publish to YouTube Shorts and Instagram Reels if enabled
                        is_autopub_on = publisher.creds.get("auto_publish_on_render", True)
                        status_social = publisher.check_status()
                        has_connected = status_social.get("youtube_connected") or status_social.get("instagram_connected")

                        if is_autopub_on and has_connected:
                            status_box.write("🚀 **Auto-Publishing generated shorts to YouTube Shorts & Instagram Reels...**")
                            # Auto-publish top shorts from the batch (up to top 3 automatically to stay safe from platform burst rate limits)
                            top_publish_count = min(3, len(batch_rendered))
                            for p_idx, p_item in enumerate(batch_rendered[:top_publish_count]):
                                status_box.write(f"📲 Publishing Short #{p_idx+1} ('{p_item.get('title', '')[:35]}...') to connected accounts...")
                                pub_res = publisher.auto_publish_if_enabled(
                                    video_path=p_item["filepath"],
                                    social_copy={
                                        "title": p_item.get("title", ""),
                                        "caption": p_item.get("caption", ""),
                                        "instagram_caption": p_item.get("caption", ""),
                                        "hashtags": p_item.get("hashtags", "")
                                    }
                                )
                                p_item["publish_status"] = pub_res

                        status_box.update(label=f"🎉 Successfully Auto-Generated {len(batch_rendered)} Viral Shorts!", state="complete", expanded=False)
                        st.session_state.batch_generation_results = {
                            "source_title": source_url_target.get("title", "Video"),
                            "source_path": source_input_path,
                            "results": batch_rendered
                        }
                        st.session_state.analysis_result = None
                        st.rerun()
                    else:
                        status_box.update(label="⚠️ No shorts could be rendered from the selected clips.", state="error", expanded=True)
                        st.error("Batch rendering did not complete. Switching to review mode so you can preview candidates.")
                        st.session_state.analysis_result = {
                            "source_path": source_input_path,
                            "metadata": source_url_target,
                            "analysis": analysis,
                            "transcript": transcript,
                            "moments": moments,
                            "duration": dur
                        }
                        st.rerun()

                else:
                    st.session_state.analysis_result = {
                        "source_path": source_input_path,
                        "metadata": source_url_target,
                        "analysis": analysis,
                        "transcript": transcript,
                        "moments": moments,
                        "duration": dur
                    }
                    if moments:
                        st.session_state.selected_clip_window = {
                            "start": moments[0]["start"],
                            "end": moments[0]["end"]
                        }
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Batch Auto-Generation Deliverables Gallery
    if st.session_state.get("batch_generation_results"):
        b_data = st.session_state.batch_generation_results
        res_list = b_data.get("results", [])
        src_name = b_data.get("source_title", "Video")

        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='pro-card-header'><span>🎉 Auto-Generated Viral Shorts Batch ({len(res_list)} Shorts)</span>"
            f"<span class='pro-badge badge-green'>100% Ready to Post</span></div>",
            unsafe_allow_html=True
        )
        st.success(f"Successfully auto-generated **{len(res_list)} Viral Shorts** from `{src_name[:65]}` without any manual approvals!")

        c_gal_btn1, c_gal_btn2, c_gal_btn3 = st.columns([1, 1, 1])
        with c_gal_btn1:
            if st.button("🔄 Generate Another Video / Batch", use_container_width=True, key="btn_reset_batch_gallery"):
                st.session_state.batch_generation_results = None
                st.session_state.analysis_result = None
                st.rerun()
        with c_gal_btn2:
            if st.button("🚀 Auto-Post All Shorts Now", use_container_width=True, key="btn_batch_autopost_all"):
                with st.spinner("Publishing batch shorts to YouTube Shorts & Instagram Reels..."):
                    for g_idx, g_item in enumerate(res_list):
                        c_title = st.session_state.get(f"title_inp_{g_idx}", g_item.get("title", ""))
                        c_tags = st.session_state.get(f"hash_inp_{g_idx}", g_item.get("hashtags", ""))
                        c_cap = st.session_state.get(f"cap_inp_{g_idx}", g_item.get("caption", ""))
                        p_res = publisher.auto_publish_if_enabled(
                            video_path=g_item["filepath"],
                            social_copy={"title": c_title, "caption": c_cap, "instagram_caption": c_cap, "hashtags": c_tags}
                        )
                        g_item["publish_status"] = p_res
                    st.success("Batch publish completed for connected channels!")
                    st.rerun()
        with c_gal_btn3:
            st.caption("📁 Deliverables stored in `workspace/output/` and `workspace/library/`.")

        grid_cols = st.columns(3)
        for g_idx, g_item in enumerate(res_list):
            with grid_cols[g_idx % 3]:
                st.markdown(f"**Short #{g_idx+1}: {g_item.get('category_label', '⚡ Viral Highlight')}**")
                vid_p = Path(g_item["filepath"])
                if vid_p.exists():
                    st.video(str(vid_p))
                    with open(vid_p, "rb") as f_data:
                        st.download_button(
                            f"📥 Download Short #{g_idx+1} (MP4)",
                            data=f_data.read(),
                            file_name=vid_p.name,
                            mime="video/mp4",
                            key=f"dl_batch_short_{g_idx}",
                            use_container_width=True
                        )
                st.caption(f"⭐ **Score:** `{g_item.get('viral_score', 90):.0f}%` | ⏱️ `{g_item.get('duration', 30):.1f}s` | 🎯 `{g_item.get('start', 0):.1f}s - {g_item.get('end', 0):.1f}s`")

                # Show Publish Status if available
                p_status = g_item.get("publish_status")
                if p_status and isinstance(p_status, dict):
                    yt_stat = p_status.get("youtube")
                    ig_stat = p_status.get("instagram")
                    if yt_stat and yt_stat.get("success"):
                        st.markdown(f"✅ **YouTube:** [Shorts Link]({yt_stat.get('url', '#')})")
                    elif yt_stat and yt_stat.get("error"):
                        st.caption(f"⚠️ YouTube: {yt_stat.get('error')[:60]}")
                    if ig_stat and ig_stat.get("success"):
                        st.markdown(f"✅ **Instagram:** [Reels Shared]({ig_stat.get('url', '#')})")
                    elif ig_stat and ig_stat.get("error"):
                        st.caption(f"⚠️ Instagram: {ig_stat.get('error')[:60]}")

                # 1-Click Publishing Buttons for this Short
                c_pub_yt, c_pub_ig = st.columns(2)
                with c_pub_yt:
                    if st.button("🚀 Post YouTube", key=f"btn_pub_yt_batch_{g_idx}", use_container_width=True):
                        with st.spinner(f"Publishing Short #{g_idx+1} to YouTube Shorts..."):
                            cur_t = st.session_state.get(f"title_inp_{g_idx}", g_item.get("title", ""))
                            cur_h = st.session_state.get(f"hash_inp_{g_idx}", g_item.get("hashtags", ""))
                            cur_c = st.session_state.get(f"cap_inp_{g_idx}", g_item.get("caption", ""))
                            y_res = publisher.publish_to_youtube(
                                video_path=g_item["filepath"],
                                title=cur_t,
                                description=cur_c,
                                tags=cur_h
                            )
                            if "publish_status" not in g_item or not isinstance(g_item["publish_status"], dict):
                                g_item["publish_status"] = {}
                            g_item["publish_status"]["youtube"] = y_res
                            if y_res.get("success"):
                                st.toast(f"Short #{g_idx+1} published to YouTube Shorts!", icon="🚀")
                            else:
                                st.error(f"YouTube Error: {y_res.get('error')}")
                            st.rerun()

                with c_pub_ig:
                    if st.button("🚀 Post Instagram", key=f"btn_pub_ig_batch_{g_idx}", use_container_width=True):
                        with st.spinner(f"Publishing Short #{g_idx+1} to Instagram Reels..."):
                            cur_h = st.session_state.get(f"hash_inp_{g_idx}", g_item.get("hashtags", ""))
                            cur_c = st.session_state.get(f"cap_inp_{g_idx}", g_item.get("caption", ""))
                            full_cap = f"{cur_c}\n\n{cur_h}".strip()
                            i_res = publisher.publish_to_instagram(
                                video_url_or_path=g_item["filepath"],
                                caption=full_cap
                            )
                            if "publish_status" not in g_item or not isinstance(g_item["publish_status"], dict):
                                g_item["publish_status"] = {}
                            g_item["publish_status"]["instagram"] = i_res
                            if i_res.get("success"):
                                st.toast(f"Short #{g_idx+1} shared to Instagram Reels!", icon="🚀")
                            else:
                                st.error(f"Instagram Error: {i_res.get('error')}")
                            st.rerun()

                with st.expander("📋 Social Copy (Title, Hashtags & Caption)", expanded=False):
                    st.text_input("Title:", value=g_item.get("title", ""), key=f"title_inp_{g_idx}")
                    st.text_input("Hashtags:", value=g_item.get("hashtags", ""), key=f"hash_inp_{g_idx}")
                    st.text_area("Instagram Caption:", value=g_item.get("caption", ""), height=70, key=f"cap_inp_{g_idx}")

        st.markdown("</div>", unsafe_allow_html=True)

    # Step 2: Interactive Review, Trim Handles & Approval
    if st.session_state.analysis_result:
        data = st.session_state.analysis_result
        meta = data["metadata"]
        analysis = data["analysis"]
        moments = data["moments"]
        total_dur = max(30.0, data["duration"])

        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>AI Highlight Detection & Review Handles</span><span class='pro-badge badge-amber'>Step 2: User Approval Required</span></div>", unsafe_allow_html=True)

        col_rev_left, col_rev_right = st.columns([1.2, 0.8])

        with col_rev_left:
            src_tag = "🔴 [LIVE FRAGMENT]" if (meta.get("is_fragment") or meta.get("is_live")) else "🎬 [VOD]"
            st.markdown(f"**Source:** `{src_tag}` `{meta.get('title', 'Video')[:50]}` | **Duration:** `{format_time(total_dur)}`")
            layout_cls = analysis.get("layout", {}).get("classification", "GENERAL")
            st.markdown(f"**Detected Camera Layout:** `{layout_cls}`")

            if moments:
                st.write("Select an AI-detected moment candidate to populate trim handles:")
                m_labels = [f"#{i+1} [{m['category_label']}] {format_time(m['start'])} - {format_time(m['end'])} (Score: {m['viral_score']:.0f}%)" for i, m in enumerate(moments)]
                selected_mom_idx = st.selectbox(
                    "Candidate Moments:",
                    options=range(len(moments)),
                    format_func=lambda i: m_labels[i],
                    key="sel_candidate_moment_idx"
                )
                selected_mom = moments[selected_mom_idx]

                # Update trim window whenever candidate selection changes
                last_mom_key = "_active_selected_mom_idx"
                if st.session_state.get(last_mom_key) != selected_mom_idx:
                    st.session_state[last_mom_key] = selected_mom_idx
                    st.session_state.selected_clip_window["start"] = float(selected_mom["start"])
                    st.session_state.selected_clip_window["end"] = float(selected_mom["end"])

                st.caption(f"💡 **Why selected:** {selected_mom.get('why_viral', 'High acoustic energy surge')}")

                # Live Social Copy for this candidate moment
                cand_spoken = selected_mom.get("text", "")
                if cand_spoken:
                    with st.expander("📋 Social Copy Preview for Selected Candidate Moment", expanded=True):
                        st.markdown(f"**🎙️ Spoken Words in this Moment:** *\"{cand_spoken[:140]}...\"*")
                        cand_meta = ai_brain.generate_viral_metadata(
                            clip_text=cand_spoken,
                            niche=selected_mom.get("category", "COMEDY"),
                            title_hint=selected_mom.get("hook_text", "")
                        )
                        st.text_input("YouTube Shorts Title:", value=cand_meta.get("title", ""), key=f"preview_title_mom_{selected_mom_idx}")
                        st.text_area("Instagram Caption:", value=cand_meta.get("instagram_caption", ""), height=70, key=f"preview_cap_mom_{selected_mom_idx}")
                        st.text_input("Hashtags:", value=cand_meta.get("hashtags", ""), key=f"preview_tags_mom_{selected_mom_idx}")
            else:
                selected_mom_idx = 0
                selected_mom = {}

            # AutoClip: Superchat & Live Chat Spike Highlights
            sc_list = chat_analyzer.detect_transcript_superchats(data.get("transcript", {}))
            chat_candidates = list(Path(data["source_path"]).parent.glob(f"{Path(data['source_path']).stem}*.live_chat.json"))
            if chat_candidates:
                parsed_sc = [m for m in chat_analyzer.parse_chat_file(chat_candidates[0]) if m.get("is_superchat")]
                if parsed_sc:
                    sc_list = parsed_sc + sc_list

            burn_sc_card = False
            active_sc_item = None
            if sc_list:
                with st.expander(f"💬 AutoClip Superchats Detected ({len(sc_list)} moments)", expanded=False):
                    st.caption("Viewer donations & Superchat controversies extracted from live stream:")
                    for sc_idx, sc_item in enumerate(sc_list[:5]):
                        amt = sc_item.get("amount_text") or f"${sc_item.get('amount', 20)}"
                        donor = sc_item.get("donor") or sc_item.get("author", "Viewer")
                        q = sc_item.get("question") or sc_item.get("message", "Superchat")
                        t_m = format_time(sc_item.get("start", sc_item.get("time", 0.0)))

                        c_sc_txt, c_sc_btn = st.columns([3, 1])
                        with c_sc_txt:
                            st.markdown(f"**💬 {amt} from {donor}:** *\"{q[:50]}\"* (`{t_m}`)")
                        with c_sc_btn:
                            if st.button("🎯 Jump", key=f"btn_jump_sc_{sc_idx}"):
                                sc_start = max(0.0, float(sc_item.get("start", sc_item.get("time", 0.0))))
                                st.session_state.selected_clip_window["start"] = sc_start
                                st.session_state.selected_clip_window["end"] = min(float(total_dur), sc_start + 35.0)
                                st.session_state.active_superchat_card = {
                                    "donor": donor,
                                    "amount_text": amt,
                                    "question": q,
                                    "duration": 6.0
                                }
                                st.toast(f"Jumped to Superchat from {donor}!", icon="💬")
                                st.rerun()

                    burn_sc_card = st.checkbox("💬 Overlay Superchat Card at top of Short", value=True, key="chk_burn_sc_card")
                    active_sc_item = getattr(st.session_state, "active_superchat_card", sc_list[0])

            # Precise Manual Trim Handles
            st.markdown("##### Trim Handles & Boundary Adjustment")
            cur_s = st.session_state.selected_clip_window["start"]
            cur_e = st.session_state.selected_clip_window["end"]
            active_mom_k = st.session_state.get("_active_selected_mom_idx", 0)

            s_col1, s_col2 = st.columns(2)
            with s_col1:
                start_val = st.number_input("Start Time (seconds):", min_value=0.0, max_value=float(total_dur), value=float(cur_s), step=1.0, key=f"inp_s_{active_mom_k}")
            with s_col2:
                end_val = st.number_input("End Time (seconds):", min_value=float(start_val) + 5.0, max_value=float(total_dur), value=max(float(start_val) + 5.0, float(cur_e)), step=1.0, key=f"inp_e_{active_mom_k}")

            clip_len = end_val - start_val
            c_info, c_snap = st.columns([1.4, 1])
            with c_info:
                st.markdown(f"**Active Clip Duration:** `{clip_len:.1f}s` (Recommended: 25s - 50s for Shorts)")
            with c_snap:
                if st.button("⚡ AutoClip Precision Snap", help="Snaps cut timestamps to exact speech pause with punchline laughter preservation"):
                    snapped = autoclip_aligner.snap_boundaries(data["transcript"], start_val, end_val, is_comedy_or_reaction=True)
                    st.session_state.selected_clip_window["start"] = snapped["start"]
                    st.session_state.selected_clip_window["end"] = snapped["end"]
                    st.toast(f"⚡ Snapped to speech boundary: {snapped['start']}s -> {snapped['end']}s", icon="✅")
                    st.rerun()

            # Custom Hook Title & Subtitle Styling
            hook_banner_text = st.text_input("Top Motion Hook Banner Text:", value=selected_mom.get("hook_text", "VIRAL MOMENT") if moments else "VIRAL MOMENT")
            style_preset = st.selectbox("Subtitle Motion Preset:", options=list(SUBTITLE_PRESETS.keys()), format_func=lambda k: SUBTITLE_PRESETS[k]["name"])

        with col_rev_right:
            st.markdown("##### Intelligent Framing & Layout")

            # Pinpoint clip framing analysis: checks whether a person is in frame, looking at camera, or pure gameplay
            clip_framing = face_detector.analyze_clip_framing(data["source_path"], start_val, clip_len)
            rec_mode = clip_framing.get("recommended_layout", "FULL_VERTICAL_STRIP")

            layout_options = [
                "AUTO",
                "FULL_VERTICAL_STRIP",
                "CINEMATIC_BLUR",
                "STREAMER_SPLIT",
                "STREAMER_ZOOMED_GAME",
                "PODCAST_SPLIT"
            ]

            layout_format = {
                "AUTO": f"🤖 Auto-Adaptive ({rec_mode})",
                "CINEMATIC_BLUR": "🎬 Normal Video on Screen (Clean 16:9 View + Ambient Backdrop)",
                "STREAMER_SPLIT": "✂️ Streamer Dual-Split (Facecam Top + Stream Content Bottom)",
                "FULL_VERTICAL_STRIP": "📱 Full-Screen Vertical 9:16 (Centered Action)",
                "STREAMER_ZOOMED_GAME": "✂️ Dual View (Facecam Top + Zoomed Stream Action)",
                "PODCAST_SPLIT": "🎙️ Manual Podcast Split (Host Top / Guest Bottom)"
            }

            comp_mode = st.selectbox(
                "Vertical 9:16 Canvas Layout:",
                options=layout_options,
                format_func=lambda x: layout_format.get(x, x),
                index=0,
                help="Intelligently adapts: Full Vertical Strip (person centered with golden-ratio headroom), Cinematic Blur, or Dual Split."
            )

            # Visual Subject & Automatic Speaker Centering Indicator
            src_w = int(data["analysis"]["probe"].get("width", 1920))
            src_h = int(data["analysis"]["probe"].get("height", 1080))
            ai_speaker_cx = int(clip_framing.get("tracked_person_cx", src_w // 2))
            crop_half = int((src_h * (1080 / 1920)) / 2)
            auto_crop_start = max(0, min(src_w - crop_half * 2, ai_speaker_cx - crop_half))

            clip_tag = f"{selected_mom_idx}_{int(start_val)}_{int(clip_len)}"
            override_key = f"override_manual_{clip_tag}"
            manual_cx_key = f"manual_cx_val_{clip_tag}"

            # Automatic Active-Speaker Tracking Status Display
            if clip_framing.get("person_in_frame"):
                if clip_framing.get("person_looking_in_frame"):
                    p_badge = "🟢 Speaking Person (Looking Forward)"
                else:
                    p_badge = "🟡 Person in Frame (Angled / Away)"

                st.success(
                    f"🎯 **100% Automatic Speaker Tracking Active**\n\n"
                    f"**Subject:** {p_badge} | Detected at **`X={ai_speaker_cx}px`** ➔ **Auto-Centered at 540px** in 9:16 Short "
                    f"*(Crop Window: `[{auto_crop_start}px - {auto_crop_start + crop_half*2}px]`)*"
                )
                if clip_framing.get("crop_x_expr") and any(op in str(clip_framing.get("crop_x_expr")) for op in ("lt", "gt", "if", "t")):
                    st.info(f"⚡ **Dynamic Conversational Camera Cuts:** {clip_framing.get('reason')}")
            else:
                st.info(
                    f"🎮 **Automatic Action Centering Active**\n\n"
                    f"Pure gameplay / action detected ➔ Auto-centered at **`X={ai_speaker_cx}px`** (540px in 9:16 Short)."
                )

            # Centering Controls: Optional Manual Override (Collapsed by default, zero user effort needed)
            with st.expander("⚙️ Manual Framing Override (Optional)", expanded=False):
                st.caption("Auto-tracking centers the active speaker automatically. Enable this only if you wish to override the AI centering:")
                manual_override = st.checkbox("Enable manual positioning override", value=False, key=override_key)

                if manual_cx_key not in st.session_state:
                    st.session_state[manual_cx_key] = ai_speaker_cx

                if manual_override:
                    c_pre1, c_pre2, c_pre3, c_pre4 = st.columns(4)
                    with c_pre1:
                        if st.button("👈 Left (25%)", key=f"btn_left_{clip_tag}"):
                            st.session_state[manual_cx_key] = int(src_w * 0.25)
                            st.rerun()
                    with c_pre2:
                        if st.button("🎯 Reset to AI", key=f"btn_ai_{clip_tag}"):
                            st.session_state[manual_cx_key] = ai_speaker_cx
                            st.rerun()
                    with c_pre3:
                        if st.button("👉 Right (75%)", key=f"btn_right_{clip_tag}"):
                            st.session_state[manual_cx_key] = int(src_w * 0.75)
                            st.rerun()
                    with c_pre4:
                        if st.button("⏺️ Center (50%)", key=f"btn_mid_{clip_tag}"):
                            st.session_state[manual_cx_key] = int(src_w * 0.50)
                            st.rerun()

                    user_speaker_cx = st.slider(
                        "Manual Focus X-Position in Source:",
                        min_value=0,
                        max_value=src_w,
                        value=int(st.session_state[manual_cx_key]),
                        step=10,
                        key=f"slider_{clip_tag}"
                    )
                    st.session_state[manual_cx_key] = user_speaker_cx
                    m_crop_start = max(0, min(src_w - crop_half * 2, user_speaker_cx - crop_half))
                    st.caption(f"📐 **Manual Crop Window:** `[{m_crop_start}px - {m_crop_start + crop_half*2}px]` ➡️ **Subject Centered at 540px**")
                else:
                    st.caption("*(Using AI Automatic Active-Speaker Tracking with Golden-Ratio Headroom)*")

            # Motion Graphics & Sound Design Controls
            st.markdown("##### 🎨 Motion Graphics & Sound Design")
            is_comm = bool(
                selected_mom.get("is_comedy_or_reaction") or
                selected_mom.get("category") == "COMEDY_HUMOR" or
                selected_mom.get("comedy_score", 0) >= 45.0 or
                "funny" in str(selected_mom.get("why_viral", "")).lower() or
                "humor" in str(selected_mom.get("why_viral", "")).lower() or
                "laughter" in str(selected_mom.get("why_viral", "")).lower()
            )

            col_mg1, col_mg2 = st.columns(2)
            with col_mg1:
                enable_mg = st.checkbox(
                    "🔥 Motion Graphics (Top Hook Card + Progress Bar)",
                    value=True,
                    key=f"chk_mg_{clip_tag}",
                    help="Adds a glassmorphic top Hook banner and glowing retention progress bar at the bottom."
                )
            with col_mg2:
                enable_sfx = st.checkbox(
                    "🔊 Viral Meme SFX (Vine Boom, Whoosh, Bruh, Ding)",
                    value=True,
                    key=f"chk_sfx_{clip_tag}",
                    help="Intelligently syncs meme sound effects to punchlines, shocks, and hook moments."
                )

            if enable_sfx:
                from core.sfx_engine import sfx_engine
                preview_sfx = sfx_engine.detect_sfx_cues(
                    transcript=data.get("transcript", {}),
                    clip_start=start_val,
                    clip_end=end_val,
                    is_comedy=is_comm
                )
                if preview_sfx:
                    sfx_badges = " ".join([f"<span class='pro-badge badge-purple'>{ev.get('name', 'SFX')} ({ev['rel_time']}s)</span>" for ev in preview_sfx])
                    st.markdown(f"**Sound Design:** {sfx_badges}", unsafe_allow_html=True)
                else:
                    st.caption("*(Intro whoosh active)*")

            # Interactive Audience Call-To-Action & Punchline Reaction Stamp
            st.markdown("##### 💬 Interactive Audience Overlay & Reaction Stamp")
            col_ia1, col_ia2 = st.columns([1.2, 0.8])
            with col_ia1:
                ia_options = [
                    "None",
                    "💀 WAIT FOR THE END...",
                    "💬 W OR L? DROP A COMMENT 👇",
                    "🔥 RATE THIS PLAY 1-10 👇",
                    "😂 WHO IS AT FAULT HERE? 👇",
                    "⚡ TAG A FRIEND WHO DOES THIS 🤣",
                    "✍️ Custom Interactive Prompt..."
                ]
                default_ia_idx = 0  # Default to None (clean video with captions only)
                ia_choice = st.selectbox(
                    "Interactive Floating CTA Card:",
                    options=ia_options,
                    index=default_ia_idx,
                    key=f"sel_ia_{clip_tag}",
                    help="Displays a floating glassmorphic engagement card at the bottom to drive viral viewer comments and watch-time."
                )
                if ia_choice.startswith("✍️"):
                    custom_ia = st.text_input("Enter Custom Interactive Prompt:", value="WHAT WOULD YOU DO? 👇", key=f"inp_custom_ia_{clip_tag}")
                    final_ia_text = custom_ia.strip()
                elif ia_choice == "None":
                    final_ia_text = None
                else:
                    final_ia_text = ia_choice

            with col_ia2:
                badge_options = [
                    "None",
                    "💀 DEAD",
                    "😂 NO WAY",
                    "🤡 CAUGHT IN 4K",
                    "🔥 VIOLATION",
                    "👑 GOAT"
                ]
                badge_choice = st.selectbox(
                    "Punchline Meme Reaction Stamp:",
                    options=badge_options,
                    index=0,  # Default to None (clean video)
                    key=f"sel_badge_{clip_tag}",
                    help="Pops up a meme reaction stamp right when the punchline / funniest joke lands."
                )
                if badge_choice == "None":
                    final_badge = None
                else:
                    final_badge = badge_choice.replace("💀", "").replace("😂", "").replace("🤡", "").replace("🔥", "").replace("👑", "").strip()

            st.caption(f"💡 **Framing Note:** {clip_framing.get('reason', '')}")

            # Confirmation & Approval Button
            st.write("")
            st.markdown("**Confirm Content Readiness:**")
            approved = st.button("Approve & Render Short (1080x1920)", type="primary", use_container_width=True)

            if approved:
                with st.spinner("Rendering 1080x1920 Short with animated subtitles, motion graphics, and meme SFX..."):
                    subtitle_gen = SubtitleGenerator()
                    exporter = VideoExporter()

                    clip_info = {
                        "start": start_val,
                        "end": end_val,
                        "duration": clip_len,
                        "hook_text": hook_banner_text,
                        "interactive_overlay": final_ia_text if 'final_ia_text' in locals() else None,
                        "punchline_badge": final_badge if 'final_badge' in locals() else None,
                        "punchline_time": selected_mom.get("punchline_time"),
                        "is_comedy_or_reaction": is_comm,
                        "superchat_card": active_sc_item if burn_sc_card else None
                    }

                    transcript_data = data["transcript"]
                    clip_words = get_words_for_window(transcript_data, start_val, end_val)
                    clean_stem = "".join([c if c.isalnum() else "_" for c in Path(data["source_path"]).stem])[:25]
                    out_fname = f"short_{clean_stem}_{int(start_val)}s.mp4"
                    ass_path = PROCESSING_DIR / f"approved_{int(start_val)}.ass"

                    subtitle_gen.generate_ass(
                        clip_words=clip_words,
                        clip_start=start_val,
                        output_ass_path=ass_path,
                        margin_v=320,
                        font_size=72,
                        style_preset=style_preset
                    )

                    # Merge pinpoint clip framing into layout info so editor tracks person accurately
                    active_layout = {**analysis["layout"], **clip_framing}
                    if st.session_state.get(override_key, False):
                        final_speaker_cx = int(st.session_state.get(manual_cx_key, ai_speaker_cx))
                        active_layout["crop_x_expr"] = None
                    else:
                        final_speaker_cx = ai_speaker_cx
                    active_layout["tracked_person_cx"] = final_speaker_cx
                    active_layout["person_cx"] = final_speaker_cx

                    out_path = exporter.render_clip(
                        source_path=data["source_path"],
                        clip_info=clip_info,
                        layout_info=active_layout,
                        subtitle_path=ass_path if clip_words else None,
                        output_filename=out_fname,
                        template=comp_mode,
                        enable_motion_graphics=enable_mg,
                        enable_sfx=enable_sfx,
                        transcript=transcript_data
                    )

                    # Generate social copy strictly from the speech within trimmed window
                    trimmed_words = [w["word"] for w in clip_words] if clip_words else []
                    exact_clip_text = " ".join(trimmed_words) if trimmed_words else (selected_mom.get("text") or meta.get("title", ""))

                    prev_t = st.session_state.get(f"preview_title_mom_{selected_mom_idx}")
                    prev_c = st.session_state.get(f"preview_cap_mom_{selected_mom_idx}")
                    prev_h = st.session_state.get(f"preview_tags_mom_{selected_mom_idx}")

                    if prev_t and prev_c:
                        social_copy = {
                            "title": prev_t,
                            "instagram_caption": prev_c,
                            "caption": prev_c,
                            "hashtags": prev_h or "#shorts #viral #reels"
                        }
                    else:
                        social_copy = ai_brain.generate_viral_metadata(
                            clip_text=exact_clip_text,
                            niche=selected_mom.get("category", "COMEDY") if moments else "VIRAL",
                            title_hint=selected_mom.get("hook_text", meta.get("title", "")),
                            source_metadata=meta
                        )

                    st.session_state.generated_short = {
                        "path": str(out_path),
                        "filename": out_fname,
                        "social_copy": social_copy
                    }
                    st.session_state._fresh_rendered_short_path = str(out_path)

                    # Auto-publish if user enabled it in settings
                    if publisher.creds.get("auto_publish_on_render"):
                        pub_res = publisher.auto_publish_if_enabled(str(out_path), social_copy)
                        st.session_state.publish_status_msg = pub_res

                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Step 3: Render Deliverable & Output Display for Viral Shorts
    clip_renders = get_rendered_videos("short_*.mp4") or get_rendered_videos("*.mp4")

    if clip_renders:
        clip_path_strs = [str(p) for p in clip_renders]

        default_sel = str(st.session_state.generated_short["path"]) if (st.session_state.generated_short and Path(st.session_state.generated_short["path"]).exists()) else clip_path_strs[0]
        if "selected_preview_short_path" not in st.session_state or st.session_state.selected_preview_short_path not in clip_path_strs:
            st.session_state.selected_preview_short_path = default_sel

        # If a short was freshly generated in Step 2, prioritize it
        if st.session_state.get("_fresh_rendered_short_path"):
            st.session_state.selected_preview_short_path = st.session_state.pop("_fresh_rendered_short_path")

        sel_index = clip_path_strs.index(st.session_state.selected_preview_short_path) if st.session_state.selected_preview_short_path in clip_path_strs else 0

        render_publish_status_banner()
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Rendered Short Deliverable & Player</span><span class='pro-badge badge-green'>Ready to Publish</span></div>", unsafe_allow_html=True)

        if len(clip_renders) > 1:
            chosen_short_str = st.selectbox(
                "Select Rendered Short to Preview:",
                options=clip_path_strs,
                index=sel_index,
                format_func=lambda p_str: f"{Path(p_str).name} ({Path(p_str).stat().st_size / (1024*1024):.1f} MB)",
                key="shorts_studio_file_selector"
            )
            if chosen_short_str != st.session_state.selected_preview_short_path:
                st.session_state.selected_preview_short_path = chosen_short_str
                st.rerun()

        active_clip_file = Path(st.session_state.selected_preview_short_path)
        # Load 100% accurate, content-specific metadata for this specific short
        active_clip_meta = exporter.get_clip_metadata(active_clip_file)

        c_out_vid, c_out_meta = st.columns([1, 1.2])
        with c_out_vid:
            render_video_player(active_clip_file, key_prefix="shorts_studio")
        with c_out_meta:
            st.markdown("**YouTube Shorts Title:**")
            st.code(active_clip_meta.get("title", active_clip_file.stem), language=None)
            st.markdown("**Instagram Reels Caption & Hashtags:**")
            st.code(f"{active_clip_meta.get('instagram_caption', '') or active_clip_meta.get('caption', '')}\n\n{active_clip_meta.get('hashtags', '')}", language=None)

            col_pub1, col_pub2 = st.columns(2)
            with col_pub1:
                if st.button("🚀 Publish to YouTube Shorts Now", key="pub_yt_shorts_now", use_container_width=True):
                    yt_res = publisher.publish_to_youtube(
                        video_path=str(active_clip_file),
                        title=active_clip_meta.get("title", active_clip_file.stem),
                        description=active_clip_meta.get("instagram_caption", "") or active_clip_meta.get("caption", ""),
                        tags=active_clip_meta.get("hashtags", "")
                    )
                    if yt_res.get("success"):
                        st.success(f"Published to YouTube Shorts: {yt_res.get('url')}")
                    else:
                        st.error(f"YouTube Error: {yt_res.get('error')}")

            with col_pub2:
                if st.button("🚀 Publish to Instagram Reels Now", key="pub_ig_shorts_now", use_container_width=True):
                    full_cap_ig = f"{active_clip_meta.get('instagram_caption', '') or active_clip_meta.get('caption', '')}\n\n{active_clip_meta.get('hashtags', '')}".strip()
                    ig_res = publisher.publish_to_instagram(
                        video_url_or_path=str(active_clip_file),
                        caption=full_cap_ig
                    )
                    if ig_res.get("success"):
                        st.success(f"Published to Instagram Reel: {ig_res.get('url')}")
                    else:
                        st.error(f"Instagram Error: {ig_res.get('error')}")

        st.markdown("</div>", unsafe_allow_html=True)
    elif not st.session_state.analysis_result:
        st.info("No clips rendered yet. Ingest a video above or select '📁 Video Library & Storage' to see past renders.")


# =======================================================
# SECTION 2: ⚡ AUTO-CATCH VIRAL REELS & REPOST ENGINE
# =======================================================
elif st.session_state.nav_tab in ["⚡ Auto-Catch Viral Reels", "Auto-Catch Viral Reels"]:
    st.markdown("## ⚡ Auto-Catch Viral Reels & Repost Engine")
    st.caption("Auto-catch trending viral Instagram Reels, TikToks, or YouTube Shorts, generate 100% relevant AI captions from spoken words, and auto-upload directly to your connected channels.")

    from core.reels_curator import reels_curator, NICHE_SEARCH_QUERIES

    with st.container():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>⚡ 0-Click Auto-Catch Viral Reels & Repost</span><span class='pro-badge badge-blue'>Auto-Discovery Engine</span></div>", unsafe_allow_html=True)

        col_niche, col_opts = st.columns([1.5, 1])
        with col_niche:
            selected_niche = st.selectbox(
                "Select Viral Content Niche / Algorithm Category:",
                options=list(NICHE_SEARCH_QUERIES.keys()),
                index=0,
                key="sel_curator_niche"
            )
            st.caption("🤖 The engine autonomously scans social media feeds, selects the highest-engagement 9:16 vertical video, transcribes spoken dialogue, writes content-relevant captions, and publishes.")

        with col_opts:
            st.markdown("**Social Reposting Channels:**")
            cur_do_yt = st.checkbox("🚀 Auto-Upload to YouTube Shorts", value=social_status.get("youtube_connected", False), key="chk_cur_yt")
            cur_do_ig = st.checkbox("🚀 Auto-Upload to Instagram Reels", value=social_status.get("instagram_connected", False), key="chk_cur_ig")

        do_auto_discover_btn = st.button("🔥 Auto-Discover & Catch Top Viral Reel (No Link Needed)", type="primary", use_container_width=True, key="btn_auto_discover_curator")

        if do_auto_discover_btn:
            cur_status_box = st.status(f"⚡ Auto-Discovering & Catching Top '{selected_niche}' Reel...", expanded=True)

            def curator_ui_progress(msg: str):
                cur_status_box.write(f"📲 {msg}")

            try:
                cur_result = reels_curator.auto_discover_and_curate(
                    niche=selected_niche,
                    upload_youtube=cur_do_yt,
                    upload_instagram=cur_do_ig,
                    progress_callback=curator_ui_progress
                )
                if cur_result.get("success"):
                    cur_status_box.update(label="🎉 Successfully Discovered, Curated & Saved Viral Reel!", state="complete", expanded=False)
                    st.session_state.curated_reel_result = cur_result
                    st.rerun()
                else:
                    cur_status_box.update(label="⚠️ Error during auto-discovery pipeline.", state="error", expanded=True)
                    st.error(f"Curation error: {cur_result.get('error', 'Unknown error')}")
            except Exception as e:
                cur_status_box.update(label="⚠️ Error occurred during processing.", state="error", expanded=True)
                st.error(f"Execution failure: {e}")

        st.markdown("---")
        with st.expander("🔗 Or Enter Custom Link / Creator Handle (@creator) [Optional Override]", expanded=False):
            reel_target_url = st.text_input(
                "Custom Video URL or Handle:",
                placeholder="e.g. https://www.instagram.com/reel/C... or https://www.tiktok.com/@... or @creators_handle",
                key="inp_curator_url"
            )
            if st.button("🚀 Catch From Custom Link", key="btn_run_custom_link", use_container_width=True) and reel_target_url.strip():
                cur_status_box2 = st.status("⚡ Running Viral Reel Curation from Link...", expanded=True)

                def curator_ui_progress2(msg: str):
                    cur_status_box2.write(f"📲 {msg}")

                try:
                    cur_result = reels_curator.curate_and_auto_repost(
                        source_url=reel_target_url.strip(),
                        upload_youtube=cur_do_yt,
                        upload_instagram=cur_do_ig,
                        progress_callback=curator_ui_progress2
                    )
                    if cur_result.get("success"):
                        cur_status_box2.update(label="🎉 Successfully Curated & Processed Viral Reel!", state="complete", expanded=False)
                        st.session_state.curated_reel_result = cur_result
                        st.rerun()
                    else:
                        cur_status_box2.update(label="⚠️ Error during curation pipeline.", state="error", expanded=True)
                        st.error(f"Curation error: {cur_result.get('error', 'Unknown error')}")
                except Exception as e:
                    cur_status_box2.update(label="⚠️ Error occurred during processing.", state="error", expanded=True)
                    st.error(f"Execution failure: {e}")

        st.markdown("</div>", unsafe_allow_html=True)

    # Display Curated Deliverable & Social Links
    if st.session_state.get("curated_reel_result"):
        c_res = st.session_state.curated_reel_result
        dl_info = c_res.get("download", {})
        content_info = c_res.get("content", {})
        up_info = c_res.get("upload_results", {})

        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>🎉 Curated Viral Reel & Social Copy</span><span class='pro-badge badge-green'>Ready / Published</span></div>", unsafe_allow_html=True)

        col_c_vid, col_c_meta = st.columns([1, 1.2])
        with col_c_vid:
            v_p = Path(content_info.get("filepath", dl_info.get("filepath", "")))
            if v_p.exists():
                st.video(str(v_p))
                with open(v_p, "rb") as f_dl:
                    st.download_button("📥 Download Curated Video (MP4)", data=f_dl.read(), file_name=v_p.name, mime="video/mp4", use_container_width=True)
            st.caption(f"**Original Title:** `{dl_info.get('title', 'Reel')[:60]}` | **Creator:** `{dl_info.get('uploader', 'Creator')}`")

        with col_c_meta:
            st.markdown("#### 🎯 AI-Generated Relevant Content")
            t_box = st.text_input("Title (YouTube Shorts):", value=content_info.get("title", ""), key="cur_title_inp")
            cap_box = st.text_area("Instagram Caption:", value=content_info.get("caption", ""), height=80, key="cur_cap_inp")
            tags_box = st.text_input("Hashtags:", value=content_info.get("hashtags", ""), key="cur_tags_inp")

            if content_info.get("transcript"):
                with st.expander("🎙️ Spoken Speech Transcript", expanded=False):
                    st.write(content_info["transcript"])

            # Upload Status & Instant Action Buttons
            if up_info:
                st.markdown("#### 🚀 Live Publication Status")
                yt_res = up_info.get("youtube")
                ig_res = up_info.get("instagram")
                if yt_res:
                    if yt_res.get("success"):
                        st.success(f"✅ Published to YouTube Shorts: [{yt_res.get('url')}]({yt_res.get('url')})")
                    else:
                        st.info(f"YouTube Upload Note: {yt_res.get('error')}")
                if ig_res:
                    if ig_res.get("success"):
                        st.success(f"✅ Published to Instagram Reels: [{ig_res.get('url')}]({ig_res.get('url')})")
                    else:
                        st.info(f"Instagram Upload Note: {ig_res.get('error')}")

            c_cur_post_yt, c_cur_post_ig = st.columns(2)
            with c_cur_post_yt:
                if st.button("🚀 Post YouTube Now", key="btn_cur_post_yt_manual", use_container_width=True):
                    with st.spinner("Posting to YouTube Shorts (Browser visible on screen)..."):
                        y_res = publisher.publish_to_youtube(
                            video_path=content_info.get("filepath", dl_info.get("filepath")),
                            title=t_box,
                            description=cap_box,
                            tags=tags_box
                        )
                        if y_res.get("success"):
                            st.success(f"Published to YouTube Shorts: {y_res.get('url')}")
                        else:
                            st.error(f"YouTube Error: {y_res.get('error')}")
            with c_cur_post_ig:
                if st.button("🚀 Post Instagram Now", key="btn_cur_post_ig_manual", use_container_width=True):
                    with st.spinner("Posting to Instagram Reels (Browser visible on screen)..."):
                        full_c = f"{cap_box}\n\n{tags_box}".strip()
                        i_res = publisher.publish_to_instagram(
                            video_url_or_path=content_info.get("filepath", dl_info.get("filepath")),
                            caption=full_c
                        )
                        if i_res.get("success"):
                            st.success(f"Published to Instagram Reels: {i_res.get('url')}")
                        else:
                            st.error(f"Instagram Error: {i_res.get('error')}")

        st.markdown("</div>", unsafe_allow_html=True)


# =======================================================
# SECTION 3: 🎞️ LONG VIDEO GENERATOR
# =======================================================
elif st.session_state.nav_tab in ["🎞️ Long Video Generator", "Long Video Generator"]:
    st.markdown("## 🎞️ Long-Format Highlight Video Generator")
    st.caption("Ingest long streams, podcasts, or recordings, automatically discover top highlight moments, select and reorder chapters, and merge them into a single 16:9 widescreen YouTube compilation with chapter titles and clickable timestamps.")

    # Step 1: Input Ingestion for Long Video
    with st.container():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Source Stream or Recording Ingestion</span><span class='pro-badge badge-blue'>Step 1</span></div>", unsafe_allow_html=True)

        l_tab1, l_tab2 = st.tabs(["Online Video Link (YouTube / Twitch / Kick)", "Upload Local Video / Direct File Path"])

        long_src_path = None
        long_src_target = None

        with l_tab1:
            l_url_val = st.text_input(
                "Enter Stream or VOD URL:",
                placeholder="https://www.youtube.com/watch?v=... (Full Stream, Podcast, or Gameplay VOD)",
                key="long_url_input"
            )

            col_l_cfg1, col_l_cfg2 = st.columns([1, 1])
            with col_l_cfg1:
                target_chapter_count = st.slider("Target Number of Highlight Chapters:", min_value=3, max_value=12, value=6, key="long_num_chapters")
            with col_l_cfg2:
                chapter_dur_range = st.select_slider(
                    "Chapter Target Duration (seconds):",
                    options=[30, 45, 60, 90, 120, 150],
                    value=(45, 90),
                    key="long_chapter_dur_range"
                )

            if st.button("📥 Download & Scan Stream for Top Highlights", type="primary", use_container_width=True, key="btn_long_scan"):
                if l_url_val and l_url_val.strip():
                    downloader = VideoDownloader()
                    with st.spinner("Downloading stream metadata and analyzing audio..."):
                        try:
                            meta = downloader.download(l_url_val.strip())
                            long_src_path = meta["filepath"]
                            long_src_target = meta
                        except Exception as e:
                            st.warning(f"Full download was reset ({e}). Capturing recent 300s stream buffer...")
                            try:
                                meta = downloader.capture_live_fragment(l_url_val.strip(), duration_sec=300)
                                long_src_path = meta["filepath"]
                                long_src_target = meta
                            except Exception as e2:
                                st.error(f"Download failed: {e}")

        with l_tab2:
            st.caption("Upload files up to 4GB, or paste local path for instant 0-second loading on massive files (e.g. 50GB recordings).")
            up_file_l = st.file_uploader("Select stream recording (.mp4, .mov, .mkv - Up to 4GB):", type=["mp4", "mov", "mkv"], key="long_file_up")
            if up_file_l:
                if st.button("Analyze Uploaded File for Highlights", type="primary", use_container_width=True, key="btn_long_up_scan"):
                    save_loc = DOWNLOADS_DIR / up_file_l.name
                    with open(save_loc, "wb") as f:
                        f.write(up_file_l.getbuffer())
                    long_src_path = str(save_loc)
                    long_src_target = {"id": up_file_l.name, "title": up_file_l.name, "filepath": str(save_loc)}

            st.markdown("---")
            l_local_path = st.text_input(
                "📁 Or Enter Local Video Path (Instant 0s Load, any size e.g. 10GB+):",
                placeholder=r"e.g. C:\Users\patel\Videos\full_stream_vod.mp4",
                key="long_local_path"
            )
            if l_local_path and l_local_path.strip():
                clean_lp = Path(l_local_path.strip().strip('"').strip("'"))
                if st.button("Load Local Video File for Long Highlights", key="btn_load_local_long", use_container_width=True):
                    if clean_lp.exists() and clean_lp.is_file():
                        long_src_path = str(clean_lp.resolve())
                        long_src_target = {"id": clean_lp.stem, "title": clean_lp.stem, "filepath": str(clean_lp.resolve())}
                        st.success(f"Loaded `{clean_lp.name}` directly from disk!")
                    else:
                        st.error(f"File not found: {clean_lp}")

        # Scan and detect highlight chapters
        if long_src_path:
            with st.spinner("Scanning entire video for climax reactions, clutch plays, and high-energy chapters..."):
                analyzer = VideoAnalyzer()
                analysis = analyzer.analyze(long_src_path)
                probe = analysis.get("probe", {})
                dur = float(probe.get("duration", 0.0))

                transcriber = AudioTranscriber()
                scan_len = min(dur, 900.0) if dur > 0 else 600.0
                transcript = transcriber.transcribe(long_src_path, start_time=0.0, duration=scan_len)

                detected_chapters = long_video_generator.detect_highlight_chapters(
                    video_path=long_src_path,
                    transcript=transcript,
                    duration=dur,
                    target_count=target_chapter_count if 'target_chapter_count' in locals() else 6,
                    min_chapter_duration=float(chapter_dur_range[0]) if 'chapter_dur_range' in locals() else 40.0,
                    max_chapter_duration=float(chapter_dur_range[1]) if 'chapter_dur_range' in locals() else 95.0
                )

                st.session_state.long_analysis_result = {
                    "source_path": long_src_path,
                    "metadata": long_src_target,
                    "analysis": analysis,
                    "transcript": transcript,
                    "duration": dur
                }
                st.session_state.long_chapters = detected_chapters
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Step 2: Interactive Chapter Selection, Reordering & Editing
    if st.session_state.long_analysis_result and st.session_state.long_chapters:
        l_data = st.session_state.long_analysis_result
        l_meta = l_data["metadata"]
        chapters = st.session_state.long_chapters

        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Interactive Chapter Selection & Customization</span><span class='pro-badge badge-amber'>Step 2</span></div>", unsafe_allow_html=True)

        st.markdown(f"**Source Video:** `{l_meta.get('title', 'Video')[:60]}` | **Total Source Length:** `{format_time(l_data['duration'])}`")
        st.caption("Select which highlight chapters to include. You can edit the chapter titles — they will appear on-screen as broadcast lower-thirds and in the YouTube timestamps!")

        updated_chapters = []
        for idx, ch in enumerate(chapters):
            c_tag = ch.get("tag", "🔥 HIGHLIGHT")
            c_start = float(ch["start"])
            c_end = float(ch["end"])
            c_dur = float(ch["duration"])

            col_ck, col_time, col_title = st.columns([0.6, 1.8, 3.6])
            with col_ck:
                is_sel = st.checkbox(
                    "Include",
                    value=ch.get("selected", True),
                    key=f"ch_sel_{idx}",
                    label_visibility="collapsed"
                )
            with col_time:
                st.markdown(f"**Chapter {idx+1}** `{format_time(c_start)} - {format_time(c_end)}` (`{c_dur:.0f}s`)\n\n<span class='pro-badge badge-blue'>{c_tag}</span>", unsafe_allow_html=True)
            with col_title:
                new_title = st.text_input(
                    f"Chapter {idx+1} Title (Lower-Third Banner):",
                    value=ch.get("title", f"Highlight Scene {idx+1}"),
                    key=f"ch_title_{idx}",
                    label_visibility="collapsed"
                )

            updated_chapters.append({
                **ch,
                "selected": is_sel,
                "title": new_title
            })

        st.session_state.long_chapters = updated_chapters

        # Calculate total merged video duration
        selected_chs = [c for c in updated_chapters if c.get("selected")]
        total_merged_s = sum(float(c["duration"]) for c in selected_chs)

        st.markdown(f"📊 **Selected Chapters:** `{len(selected_chs)} of {len(chapters)}` | **Estimated Final Video Runtime:** `{format_time(total_merged_s)}` (`{total_merged_s:.1f}s`)")

        # Step 3: Merger Options & Render
        st.divider()
        st.markdown("##### Broadcast Assembly & Polish Options")

        col_opt1, col_opt2 = st.columns([1.2, 1.8])
        with col_opt1:
            trans_opt = st.selectbox(
                "Transition Between Chapters:",
                options=["dip_to_black", "crossfade", "clean_cut"],
                format_func=lambda x: "🎬 Dip to Black (YouTube Standard)" if x == "dip_to_black" else ("✨ Smooth Crossfade" if x == "crossfade" else "✂️ Clean Cut"),
                key="long_trans_opt"
            )
        with col_opt2:
            c_sub1, c_sub2 = st.columns(2)
            with c_sub1:
                add_lower_thirds = st.checkbox("🏷️ Broadcast Title Cards", value=True, key="long_add_title_cards", help="Displays an aesthetic lower-third chapter title banner for the first 3.5 seconds of each segment.")
                long_enable_sfx = st.checkbox("🔊 Transition Sound FX (Whoosh & Chimes)", value=True, key="long_enable_sfx", help="Mixes cinematic whooshes during transitions and chimes when chapter cards reveal.")
            with c_sub2:
                norm_audio = st.checkbox("🔊 EBU R128 Audio Normalization", value=True, key="long_norm_audio", help="Equalizes loudness across all clips to standard -16 LUFS broadcast level.")

        st.write("")
        if st.button("🎞️ Compile & Render 16:9 Long-Format Highlight Video", type="primary", use_container_width=True, key="btn_compile_long"):
            if not selected_chs:
                st.warning("Please select at least one chapter to compile.")
            else:
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                def update_prog(ratio, txt):
                    progress_bar.progress(min(1.0, max(0.0, ratio)))
                    status_text.text(txt)

                with st.spinner("Extracting chapters, adding title cards, and compiling 16:9 video..."):
                    clean_title = "".join([c if c.isalnum() else "_" for c in Path(l_data["source_path"]).stem])[:25]
                    out_filename = f"long_highlight_{clean_title}_{len(selected_chs)}chapters.mp4"
                    target_out = OUTPUT_DIR / out_filename

                    render_res = long_video_generator.render_merged_video(
                        source_video=l_data["source_path"],
                        chapters=selected_chs,
                        output_path=str(target_out),
                        transition_type=trans_opt,
                        add_lower_thirds=add_lower_thirds,
                        normalize_audio=norm_audio,
                        enable_sfx=long_enable_sfx,
                        progress_callback=update_prog
                    )

                    yt_meta = long_video_generator.generate_youtube_metadata(
                        source_title=l_meta.get("title", clean_title),
                        chapters=selected_chs
                    )

                    st.session_state.generated_long_video = {
                        "path": str(target_out),
                        "filename": out_filename,
                        "duration": render_res["duration"],
                        "file_size_mb": render_res["file_size_mb"]
                    }
                    st.session_state.long_yt_meta = yt_meta
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Step 4: Finished Long Video Deliverable & YouTube Publishing
    long_renders = get_rendered_videos("long_*.mp4")
    active_long_file = None
    active_long_meta = None

    if st.session_state.generated_long_video and Path(st.session_state.generated_long_video["path"]).exists():
        active_long_file = Path(st.session_state.generated_long_video["path"])
        active_long_meta = st.session_state.long_yt_meta
    elif long_renders:
        active_long_file = long_renders[0]
        active_long_meta = long_video_generator.generate_youtube_metadata(
            source_title=active_long_file.stem,
            chapters=[]
        )

    if active_long_file and active_long_file.exists():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Rendered Long-Format Highlight Video (16:9 Widescreen)</span><span class='pro-badge badge-green'>Ready to Publish</span></div>", unsafe_allow_html=True)

        col_lv1, col_lv2 = st.columns([1.3, 1])
        with col_lv1:
            render_video_player(active_long_file, key_prefix="long_studio")
        with col_lv2:
            st.markdown(f"**File Size:** `{active_long_file.stat().st_size / (1024*1024):.2f} MB`")
            st.markdown(f"**Resolution:** `1920x1080 (16:9 Full HD)`")

            if active_long_meta:
                st.markdown("**YouTube Video Title:**")
                st.code(active_long_meta.get("title", active_long_file.stem), language=None)

                st.markdown("**YouTube Description with Clickable Chapter Timestamps:**")
                st.code(active_long_meta.get("description", ""), language=None)

            if st.button("🚀 Publish Full Long Video to YouTube Channel", key="pub_yt_long_full", type="primary", use_container_width=True):
                with st.spinner("Uploading 16:9 Long Video to YouTube with chapters..."):
                    yt_res = publisher.publish_to_youtube(
                        video_path=str(active_long_file),
                        title=active_long_meta.get("title", active_long_file.stem) if active_long_meta else active_long_file.stem,
                        description=active_long_meta.get("description", "") if active_long_meta else "",
                        tags=", ".join(active_long_meta.get("tags", [])) if active_long_meta else ""
                    )
                    if yt_res.get("success"):
                        st.success(f"🚀 Long Video Successfully Published to YouTube: [{yt_res.get('url')}]({yt_res.get('url')})")
                    else:
                        st.error(f"YouTube Upload Note: {yt_res.get('error')}")

        st.markdown("</div>", unsafe_allow_html=True)
    elif not st.session_state.long_analysis_result:
        st.info("No long-format videos generated yet. Enter a stream or video URL above and click 'Download & Scan Stream for Top Highlights' to start.")


# =======================================================
# SECTION 3: 📅 CONTENT PUBLISHING CALENDAR & VIDEO LIBRARY
# =======================================================
elif (
    st.session_state.nav_tab in ["📅 Publishing Calendar & Library", "📁 Video Library & Storage", "Exports & Video Library"]
    or any(k in str(st.session_state.get("nav_tab", "")) for k in ["Calendar", "Library", "Publishing", "📅", "📁"])
):
    from datetime import datetime, date, timedelta
    from core.scheduler import scheduler, DAILY_SLOTS

    st.markdown("## 📅 Content Publishing Calendar & Video Library")
    st.caption("Plan, schedule, and auto-publish YouTube Shorts and Instagram Reels with 100% topic-accurate AI captions stored directly with each video.")

    # 1. Calendar Time Window & Controls
    today = date.today()
    week_offset = st.session_state.get("calendar_week_offset", 0)
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]

    schedule_data = scheduler.get_schedule()
    all_available_shorts = scheduler.list_all_available_shorts()
    unscheduled_shorts = [s for s in all_available_shorts if not s["is_scheduled"]]

    # Header Control Bar
    st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
    c_ctrl1, c_ctrl2, c_ctrl3 = st.columns([1.5, 1, 1.2])

    with c_ctrl1:
        c_nav_p, c_nav_t, c_nav_n = st.columns([1, 2, 1])
        with c_nav_p:
            if st.button("◀ Prev Week", key="cal_prev_week", use_container_width=True):
                st.session_state.calendar_week_offset = week_offset - 1
                st.rerun()
        with c_nav_t:
            st.markdown(f"<div style='text-align: center; font-weight: 700; padding-top: 6px; color: #0f172a; font-size: 0.95rem;'>{start_of_week.strftime('%b %d')} – {end_of_week.strftime('%b %d, %Y')}</div>", unsafe_allow_html=True)
        with c_nav_n:
            if st.button("Next Week ▶", key="cal_next_week", use_container_width=True):
                st.session_state.calendar_week_offset = week_offset + 1
                st.rerun()

    with c_ctrl2:
        if st.button("📅 Jump to Today", key="cal_today_jump", use_container_width=True):
            st.session_state.calendar_week_offset = 0
            st.rerun()

    with c_ctrl3:
        if st.button("⚡ Auto-Fill Week (Ready Shorts)", key="cal_autofill_week", type="primary", use_container_width=True):
            filled = scheduler.auto_fill_week(start_date_str=start_of_week.strftime("%Y-%m-%d"))
            if filled > 0:
                st.toast(f"🎉 Auto-scheduled {filled} viral shorts across upcoming empty slots!", icon="📅")
            else:
                st.toast("No empty upcoming slots or no unscheduled shorts available.", icon="ℹ️")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # 2. Main 2-Column Split: Calendar (Left 63%) + Ready Shorts Tray (Right 37%)
    col_calendar, col_tray = st.columns([1.65, 1.0])

    # ==========================================
    # LEFT COLUMN: 7-DAY INTERACTIVE CALENDAR
    # ==========================================
    with col_calendar:
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='pro-card-header'><span>Interactive Content Calendar</span><span class='pro-badge badge-blue'>{len(schedule_data)} Total Scheduled</span></div>", unsafe_allow_html=True)

        # 7 Weekday Columns
        day_cols = st.columns(7)
        weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for idx, (d_col, day_obj) in enumerate(zip(day_cols, week_days)):
            day_str = day_obj.strftime("%Y-%m-%d")
            is_today = (day_obj == today)

            with d_col:
                header_style = "background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;" if is_today else "background: #f8fafc; color: #475569; border: 1px solid #e2e8f0;"
                st.markdown(
                    f"<div style='border-radius: 8px; padding: 6px 4px; text-align: center; margin-bottom: 8px; {header_style}'>"
                    f"<div style='font-size: 0.72rem; text-transform: uppercase; font-weight: 700;'>{weekday_names[idx]}</div>"
                    f"<div style='font-size: 1rem; font-weight: 800;'>{day_obj.day}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # Time slots for each day
                for slot_time in DAILY_SLOTS:
                    slot_key = scheduler.make_slot_key(day_str, slot_time)
                    slot_entry = schedule_data.get(slot_key)

                    if slot_entry:
                        v_name = slot_entry.get("title", slot_entry.get("video_name", "Short"))[:18]
                        status = slot_entry.get("status", "scheduled")
                        is_pub = (status == "published")
                        badge_color = "#059669" if is_pub else "#2563eb"
                        slot_bg = "#ecfdf5" if is_pub else "#eff6ff"
                        slot_border = "#a7f3d0" if is_pub else "#bfdbfe"

                        st.markdown(
                            f"<div style='background: {slot_bg}; border: 1px solid {slot_border}; border-left: 3px solid {badge_color}; border-radius: 6px; padding: 6px 4px; margin-bottom: 6px;'>"
                            f"<div style='font-size: 0.68rem; font-weight: 700; color: #64748b; display: flex; justify-content: space-between;'>"
                            f"<span>{slot_time}</span><span>{'✅' if is_pub else '📅'}</span>"
                            f"</div>"
                            f"<div style='font-size: 0.75rem; font-weight: 700; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;' title='{slot_entry.get('title')}'>{v_name}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"<div style='background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; padding: 6px 2px; margin-bottom: 6px; text-align: center; color: #94a3b8; font-size: 0.68rem;'>"
                            f"{slot_time}"
                            f"</div>",
                            unsafe_allow_html=True
                        )

        # Scheduled Slots Quick Action & Publishing Bar
        active_week_slots = [
            (k, v) for k, v in schedule_data.items()
            if any(day_obj.strftime("%Y-%m-%d") in k for day_obj in week_days)
        ]
        if active_week_slots:
            with st.expander(f"📋 Scheduled Slots This Week ({len(active_week_slots)} Active)", expanded=True):
                for slot_key, slot_entry in active_week_slots:
                    c_sl_info, c_sl_acts = st.columns([2, 1.2])
                    with c_sl_info:
                        st.markdown(f"**{slot_entry.get('date')} • {slot_entry.get('time_slot')}** — {slot_entry.get('title')}")
                        st.caption(f"📝 *{slot_entry.get('caption', '')[:120]}...*")
                    with c_sl_acts:
                        c_p_now, c_u_now = st.columns(2)
                        with c_p_now:
                            if st.button("🚀 Post Now", key=f"mgr_post_{slot_key}", use_container_width=True):
                                with st.spinner("Publishing scheduled video..."):
                                    res = scheduler.publish_slot_now(slot_key)
                                    if res.get("success"):
                                        st.success("Published successfully!")
                                    else:
                                        st.error(f"Publish note: {res.get('error', 'Check account login')}")
                                    st.rerun()
                        with c_u_now:
                            if st.button("❌ Remove", key=f"mgr_rm_{slot_key}", type="secondary", use_container_width=True):
                                scheduler.unschedule_slot(slot_entry.get("date"), slot_entry.get("time_slot"))
                                st.toast("Unscheduled slot", icon="🗑️")
                                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # Quick Manual Slot Booking Form
        with st.expander("➕ Schedule Any Short to Specific Date & Time Slot", expanded=False):
            if not unscheduled_shorts:
                st.info("No unscheduled shorts ready in library. Generate new shorts in Section 1 or catch viral reels in Section 2.")
            else:
                c_sb1, c_sb2, c_sb3 = st.columns([1.5, 1, 1])
                with c_sb1:
                    chosen_short_item = st.selectbox(
                        "Select Ready Short to Schedule:",
                        options=unscheduled_shorts,
                        format_func=lambda s: f"{s['title'][:40]} ({s['size_mb']} MB)",
                        key="sel_manual_sched_short"
                    )
                with c_sb2:
                    chosen_date = st.date_input("Target Date:", value=today, key="inp_manual_sched_date")
                with c_sb3:
                    chosen_slot = st.selectbox("Target Slot:", options=DAILY_SLOTS, key="sel_manual_sched_slot")

                if st.button("📅 Confirm & Schedule Short", type="primary", use_container_width=True, key="btn_confirm_manual_sched"):
                    date_key_str = chosen_date.strftime("%Y-%m-%d")
                    res = scheduler.schedule_short(
                        date_str=date_key_str,
                        time_slot=chosen_slot,
                        video_path=chosen_short_item["path"],
                        platforms=["youtube", "instagram"]
                    )
                    if res.get("success"):
                        st.success(f"🎉 Successfully scheduled '{chosen_short_item['title']}' for {chosen_slot} on {date_key_str}!")
                        st.rerun()

    # ==========================================
    # RIGHT COLUMN: READY UNSCHEDULED SHORTS TRAY
    # ==========================================
    with col_tray:
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='pro-card-header'>"
            f"<span>Ready to Publish</span>"
            f"<span class='pro-badge badge-green'>{len(unscheduled_shorts)} Ready</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        tray_search = st.text_input("🔍 Search ready shorts...", placeholder="Search by title or topic...", key="tray_search_query")

        display_shorts = unscheduled_shorts
        if tray_search and tray_search.strip():
            q = tray_search.strip().lower()
            display_shorts = [s for s in unscheduled_shorts if q in s["title"].lower() or q in s["caption"].lower()]

        if not display_shorts:
            st.info("No unscheduled shorts found. Renders from Section 1 & Section 2 automatically show up here.")
        else:
            for s_idx, s_item in enumerate(display_shorts):
                s_path = Path(s_item["path"])
                s_title = s_item["title"]
                s_score = s_item["viral_score"]

                st.markdown(
                    f"<div class='short-item-card'>"
                    f"<div style='display: flex; justify-content: space-between; align-items: start; gap: 8px; margin-bottom: 6px;'>"
                    f"<div style='font-size: 0.88rem; font-weight: 700; color: #0f172a; line-height: 1.3;'>{s_title[:45]}</div>"
                    f"<span class='pro-badge badge-blue'>{s_score}% Viral</span>"
                    f"</div>"
                    f"<div style='font-size: 0.74rem; color: #64748b; margin-bottom: 8px;'>"
                    f"📁 <code>{s_item['name']}</code> • {s_item['size_mb']} MB"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # Expandable preview player and schedule actions
                with st.expander(f"🎬 Preview & Schedule: {s_title[:28]}...", expanded=False):
                    render_video_player(s_path, key_prefix=f"tray_prev_{s_path.stem}")

                    # Stored content-accurate caption display
                    st.markdown("**📝 Stored AI Caption & Hashtags:**")
                    st.caption(f"{s_item.get('caption', '')[:140]}...")
                    st.code(s_item.get("hashtags", "#shorts #viral"), language=None)

                    # 1-Click Schedule Action
                    st.markdown("**📅 Schedule to Upcoming Slot:**")
                    c_sc_d, c_sc_t = st.columns(2)
                    with c_sc_d:
                        sc_date = st.date_input("Date:", value=today, key=f"tray_d_{s_idx}_{s_path.stem}")
                    with c_sc_t:
                        sc_time = st.selectbox("Slot:", options=DAILY_SLOTS, key=f"tray_t_{s_idx}_{s_path.stem}")

                    if st.button("📅 Schedule Video to Slot", key=f"btn_sched_tray_{s_idx}_{s_path.stem}", type="primary", use_container_width=True):
                        d_str = sc_date.strftime("%Y-%m-%d")
                        res = scheduler.schedule_short(
                            date_str=d_str,
                            time_slot=sc_time,
                            video_path=str(s_path)
                        )
                        if res.get("success"):
                            st.toast(f"Scheduled '{s_title[:30]}' to {sc_time} on {d_str}!", icon="📅")
                            st.rerun()

                    # Quick Direct Post & Delete
                    c_dir_yt, c_dir_del = st.columns(2)
                    with c_dir_yt:
                        if st.button("🚀 Post YouTube Now", key=f"btn_tray_yt_{s_path.stem}", use_container_width=True):
                            res = publisher.publish_to_youtube(
                                video_path=str(s_path),
                                title=s_item["title"],
                                description=s_item["caption"],
                                tags=s_item["hashtags"]
                            )
                            if res.get("success"):
                                st.success(f"Published: {res.get('url')}")
                            else:
                                st.error(f"Error: {res.get('error')}")
                    with c_dir_del:
                        if st.button("🗑️ Delete Short", key=f"btn_tray_del_{s_path.stem}", type="secondary", use_container_width=True):
                            if workspace_cleaner.delete_single_deliverable(str(s_path)):
                                st.toast(f"Deleted {s_item['name']}", icon="🗑️")
                                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # 3. Disk Storage & Deep Memory Clean Telemetry
    storage_info = workspace_cleaner.get_storage_stats()
    all_deliverables = workspace_cleaner.list_generated_deliverables()

    with st.expander("💾 Disk Storage Telemetry & Memory Purge Manager", expanded=False):
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.metric(
                label="Raw Source Videos",
                value=f"{storage_info['downloads_size_gb']:.2f} GB",
                delta=f"{storage_info['downloads_count']} downloaded files"
            )
        with c_m2:
            st.metric(
                label="Temp Processing Cache",
                value=f"{storage_info['temp_size_mb']:.1f} MB",
                delta=f"{storage_info['temp_count']} temp audio/ass files"
            )
        with c_m3:
            st.metric(
                label="Rendered Video Deliverables",
                value=f"{storage_info['output_size_mb']:.1f} MB",
                delta=f"{len(all_deliverables)} finished videos"
            )

        st.write("")
        col_cl1, col_cl2 = st.columns(2)
        with col_cl1:
            if st.button("🧹 Clean Temporary Processing Cache Now", use_container_width=True, key="btn_clean_temp_cache"):
                res = workspace_cleaner.clean_temporary_files()
                st.success(f"Cleaned {res['deleted_count']} temporary files. Freed {res['freed_mb']:.1f} MB.")
                st.rerun()
        with col_cl2:
            if st.button("🚀 Deep Purge Raw Source Videos (Free GBs)", use_container_width=True, key="btn_purge_downloads", help="Deletes heavy downloaded stream source videos while keeping your rendered Shorts and Long videos 100% safe."):
                res = workspace_cleaner.clean_all_downloads(preserve_test_sample=True)
                st.success(f"Purged {res['deleted_count']} bulky downloads. Freed {res['freed_gb']:.2f} GB of disk space!")
                st.rerun()
else:
    st.info("Select a studio section from the top navigation bar or the sidebar to begin.")
