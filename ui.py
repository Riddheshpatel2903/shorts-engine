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
from core.exporter import VideoExporter
from core.ai_brain import ai_brain
from core.cleaner import workspace_cleaner
from core.publisher import publisher
from core.autoclip_precision import autoclip_aligner, autoclip_cutter
from core.chat_analyzer import chat_analyzer
from core.long_video_generator import long_video_generator

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

# Modern Professional SaaS CSS
st.markdown("""
<style>
    /* Global Base */
    .stApp {
        background-color: #0b0d13;
        color: #e2e8f0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Studio Card */
    .pro-card {
        background: #121622;
        border: 1px solid #202738;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    .pro-card-header {
        font-size: 0.95rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    /* Professional Badges */
    .pro-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .badge-blue { background: #1e293b; color: #38bdf8; border: 1px solid #0284c744; }
    .badge-green { background: #064e3b; color: #34d399; border: 1px solid #05966944; }
    .badge-amber { background: #451a03; color: #fbbf24; border: 1px solid #d9770644; }
    .badge-purple { background: #3b0764; color: #c084fc; border: 1px solid #a855f744; }
    
    /* Sidebar Navigation */
    section[data-testid="stSidebar"] {
        background-color: #0e111a;
        border-right: 1px solid #1c2230;
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

    # Mapping to handle legacy state gracefully
    current_tab = st.session_state.nav_tab
    if current_tab in ["Clip Studio", "🎬 Viral Shorts Studio"]:
        nav_index = 0
    elif current_tab in ["Long Video Generator", "🎞️ Long Video Generator"]:
        nav_index = 1
    elif current_tab in ["Exports & Video Library", "📁 Video Library & Storage", "Daily Feeds & Scripts", "Topic to Video Studio"]:
        nav_index = 2
    else:
        nav_index = 0

    # EXACTLY 3 SECTIONS AS REQUESTED
    st.session_state.nav_tab = st.radio(
        "Studio Sections:",
        options=[
            "🎬 Viral Shorts Studio",
            "🎞️ Long Video Generator",
            "📁 Video Library & Storage"
        ],
        index=nav_index
    )

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
        auto_post_toggle = st.checkbox("⚡ Auto-publish Shorts upon render", value=social_status.get("auto_publish", False), key="chk_autopub")
        if auto_post_toggle != social_status.get("auto_publish"):
            publisher.update_settings(auto_publish_on_render=auto_post_toggle)
            st.rerun()

        if st.button("🔄 Refresh Login Status", use_container_width=True, key="btn_refresh_status"):
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
# SECTION 1: 🎬 VIRAL SHORTS STUDIO
# =======================================================
if st.session_state.nav_tab in ["🎬 Viral Shorts Studio", "Clip Studio"]:
    st.markdown("## 🎬 Viral Shorts Studio")
    st.caption("Turn long videos, streams, and podcasts into viral 9:16 Shorts with smart face/speaker centering, punchline decay preservation, and auto-publishing.")

    # Step 1: Source Ingestion
    with st.container():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Source Ingestion</span><span class='pro-badge badge-blue'>Step 1</span></div>", unsafe_allow_html=True)

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
                else:
                    btn_text = "📥 Download & Analyze Full Video"
                do_analyze = st.button(btn_text, type="primary", use_container_width=True, key="btn_shorts_analyze")

            with col_btn2:
                do_inspect = st.button("🔍 Check Stream Info", use_container_width=True, key="btn_shorts_inspect")

            if do_inspect and url_val and url_val.strip():
                with st.spinner("Checking live broadcast status..."):
                    try:
                        downloader = VideoDownloader()
                        info_check = downloader.get_info(url_val.strip())
                        live_badge = "🔴 LIVE BROADCAST NOW" if info_check.get("is_live") else "📼 Pre-recorded / VOD"
                        st.info(
                            f"**{live_badge}** | **Title:** `{info_check.get('title')[:60]}` | "
                            f"**Streamer:** `{info_check.get('uploader')}` | "
                            f"**Duration:** `{format_time(info_check.get('duration', 0))}`"
                        )
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
                if st.button("Analyze Uploaded File", type="primary", use_container_width=True, key="btn_shorts_analyze_up"):
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
                if st.button("Load Local Video File", key="btn_load_local_shorts", use_container_width=True):
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
                segments = detector.analyze_moments(source_input_path, transcript)

                # Ultra-fast acoustic energy reaction peak scanner across ENTIRE video duration
                try:
                    acoustic_peaks = detector.find_audio_energy_peaks(source_input_path, top_n=6, window_duration=35.0)
                except Exception as e:
                    logger.debug(f"Acoustic peak scanner fallback: {e}")
                    acoustic_peaks = []

                selector = ClipSelector(min_duration=20.0, max_duration=55.0, genre_focus="all")
                moments = selector.select_clips(
                    segments,
                    num_shorts=5,
                    genre_focus="all",
                    transcript=transcript,
                    extra_candidates=acoustic_peaks
                )

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
                "FULL_VERTICAL_STRIP": "📱 Full Vertical Strip (Person Centered + Headroom Tracked)",
                "CINEMATIC_BLUR": "🎬 Cinematic 16:9 (Full Game View + Blurred Backdrop)",
                "STREAMER_SPLIT": "✂️ Pro Gamer Dual-View (Facecam Top + Full Game HUD)",
                "STREAMER_ZOOMED_GAME": "✂️ Dual View (Facecam Top + Zoomed Game Action)",
                "PODCAST_SPLIT": "🎙️ Podcast Split (Host Top / Guest Bottom)"
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

            st.caption(f"💡 **Framing Note:** {clip_framing.get('reason', '')}")

            # Confirmation & Approval Button
            st.write("")
            st.markdown("**Confirm Content Readiness:**")
            approved = st.button("Approve & Render Short (1080x1920)", type="primary", use_container_width=True)

            if approved:
                with st.spinner("Rendering 1080x1920 Short with animated subtitles..."):
                    subtitle_gen = SubtitleGenerator()
                    exporter = VideoExporter()

                    clip_info = {
                        "start": start_val,
                        "end": end_val,
                        "duration": clip_len,
                        "hook_text": hook_banner_text,
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
                        template=comp_mode
                    )

                    # Generate social copy
                    social_copy = ai_brain.generate_viral_metadata(
                        clip_text=selected_mom.get("text", "") if moments else meta.get("title", ""),
                        niche="GAMING",
                        title_hint=meta.get("title", ""),
                        source_metadata=meta
                    )

                    st.session_state.generated_short = {
                        "path": str(out_path),
                        "filename": out_fname,
                        "social_copy": social_copy
                    }

                    # Auto-publish if user enabled it in settings
                    if publisher.creds.get("auto_publish_on_render"):
                        pub_res = publisher.auto_publish_if_enabled(str(out_path), social_copy)
                        st.session_state.publish_status_msg = pub_res

                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Step 3: Render Deliverable & Output Display for Viral Shorts
    clip_renders = get_rendered_videos("short_*.mp4") or get_rendered_videos("*.mp4")
    active_clip_file = None
    active_clip_meta = None

    if st.session_state.generated_short and Path(st.session_state.generated_short["path"]).exists():
        active_clip_file = Path(st.session_state.generated_short["path"])
        active_clip_meta = st.session_state.generated_short.get("social_copy", {})
    elif clip_renders:
        active_clip_file = clip_renders[0]
        active_clip_meta = ai_brain.generate_viral_metadata(clip_text=active_clip_file.stem, niche="GAMING")

    render_publish_status_banner()
    if active_clip_file and active_clip_file.exists():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Rendered Short Deliverable & Player</span><span class='pro-badge badge-green'>Ready to Publish</span></div>", unsafe_allow_html=True)

        if len(clip_renders) > 1:
            clip_choice = st.selectbox(
                "Select Rendered Short to Preview:",
                options=clip_renders,
                format_func=lambda p: f"{p.name} ({p.stat().st_size / (1024*1024):.1f} MB)",
                key="shorts_studio_file_selector"
            )
            if clip_choice != active_clip_file:
                active_clip_file = clip_choice
                active_clip_meta = ai_brain.generate_viral_metadata(clip_text=active_clip_file.stem, niche="GAMING")

        c_out_vid, c_out_meta = st.columns([1, 1.2])
        with c_out_vid:
            render_video_player(active_clip_file, key_prefix="shorts_studio")
        with c_out_meta:
            st.markdown("**YouTube Shorts Title:**")
            st.code(active_clip_meta.get("title", active_clip_file.stem), language=None)
            st.markdown("**Instagram Reels Caption & Hashtags:**")
            st.code(f"{active_clip_meta.get('instagram_caption', '')}\n\n{active_clip_meta.get('hashtags', '')}", language=None)

            col_pub1, col_pub2 = st.columns(2)
            with col_pub1:
                if st.button("🚀 Publish to YouTube Shorts Now", key="pub_yt_shorts_now", use_container_width=True):
                    yt_res = publisher.publish_to_youtube(
                        video_path=str(active_clip_file),
                        title=active_clip_meta.get("title", active_clip_file.stem),
                        description=active_clip_meta.get("instagram_caption", ""),
                        tags=active_clip_meta.get("hashtags", "")
                    )
                    if yt_res.get("success"):
                        st.success(f"Published to YouTube Shorts: {yt_res.get('url')}")
                    else:
                        st.error(f"YouTube Error: {yt_res.get('error')}")

            with col_pub2:
                if st.button("🚀 Publish to Instagram Reels Now", key="pub_ig_shorts_now", use_container_width=True):
                    ig_res = publisher.publish_to_instagram(
                        video_url_or_path=str(active_clip_file),
                        caption=f"{active_clip_meta.get('instagram_caption', '')}\n\n{active_clip_meta.get('hashtags', '')}"
                    )
                    if ig_res.get("success"):
                        st.success(f"Published to Instagram Reel: {ig_res.get('url')}")
                    else:
                        st.error(f"Instagram Error: {ig_res.get('error')}")

        st.markdown("</div>", unsafe_allow_html=True)
    elif not st.session_state.analysis_result:
        st.info("No clips rendered yet. Ingest a video above or select '📁 Video Library & Storage' to see past renders.")


# =======================================================
# SECTION 2: 🎞️ LONG VIDEO GENERATOR
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

        col_opt1, col_opt2, col_opt3 = st.columns(3)
        with col_opt1:
            trans_opt = st.selectbox(
                "Transition Between Chapters:",
                options=["dip_to_black", "crossfade", "clean_cut"],
                format_func=lambda x: "🎬 Dip to Black (YouTube Standard)" if x == "dip_to_black" else ("✨ Smooth Crossfade" if x == "crossfade" else "✂️ Clean Cut"),
                key="long_trans_opt"
            )
        with col_opt2:
            add_lower_thirds = st.checkbox("🏷️ Add On-Screen Chapter Title Cards", value=True, key="long_add_title_cards", help="Displays an aesthetic lower-third chapter title banner for the first 3.5 seconds of each segment.")
        with col_opt3:
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
# SECTION 3: 📁 VIDEO LIBRARY & STORAGE / MEMORY MANAGER
# =======================================================
elif st.session_state.nav_tab in ["📁 Video Library & Storage", "Exports & Video Library"]:
    st.markdown("## 📁 Video Library & Storage Manager")
    st.caption("Manage all rendered Shorts & Long videos, preview and delete unwanted clips with a single click, and automatically clear temporary cache files to keep your computer fast.")

    # Storage Telemetry Cards
    storage_info = workspace_cleaner.get_storage_stats()
    all_deliverables = workspace_cleaner.list_generated_deliverables()

    st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
    st.markdown("<div class='pro-card-header'><span>Disk Space Telemetry & Automated Memory Clean</span><span class='pro-badge badge-green'>Active Auto-Purge</span></div>", unsafe_allow_html=True)

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

    st.caption("💡 *Notice: Temporary audio chunks and .ass caches are automatically cleared in the background on startup.*")
    st.markdown("</div>", unsafe_allow_html=True)

    # Deliverables Gallery
    st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='pro-card-header'><span>Rendered Videos Gallery ({len(all_deliverables)} Total)</span><span class='pro-badge badge-blue'>Deliverables</span></div>", unsafe_allow_html=True)

    if not all_deliverables:
        st.info("No rendered videos found yet. Use Section 1 to generate viral Shorts or Section 2 to generate Long-format highlight videos.")
    else:
        # Filter options
        filter_type = st.radio(
            "Filter Videos by Category:",
            options=["All Videos", "🎬 Viral Shorts (9:16)", "🎞️ Long Format Videos (16:9)"],
            horizontal=True,
            key="lib_filter_radio"
        )

        filtered = all_deliverables
        if filter_type == "🎬 Viral Shorts (9:16)":
            filtered = [d for d in all_deliverables if not d["is_long_video"]]
        elif filter_type == "🎞️ Long Format Videos (16:9)":
            filtered = [d for d in all_deliverables if d["is_long_video"]]

        st.write("")

        for v_item in filtered:
            v_path = Path(v_item["path"])
            v_name = v_item["name"]
            v_size = v_item["size_mb"]
            is_long = v_item["is_long_video"]
            badge_class = "badge-purple" if is_long else "badge-green"

            with st.container():
                st.markdown(
                    f"<div style='background: #0f131d; border: 1px solid #1c2230; border-radius: 8px; padding: 14px; margin-bottom: 12px;'>"
                    f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>"
                    f"<strong>{v_name}</strong>"
                    f"<span class='pro-badge {badge_class}'>{v_item['category']}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                c_v_play, c_v_actions = st.columns([1.2, 1])

                with c_v_play:
                    render_video_player(v_path, key_prefix=f"lib_item_{v_path.stem}")

                with c_v_actions:
                    st.markdown(f"**Size:** `{v_size:.2f} MB`")
                    st.markdown(f"**Path:** `{v_path}`")

                    # Social quick publish
                    meta_copy = ai_brain.generate_viral_metadata(clip_text=v_path.stem, niche="GAMING")
                    c_act_yt, c_act_ig = st.columns(2)
                    with c_act_yt:
                        if st.button("🚀 YouTube", key=f"lib_pub_yt_{v_path.stem}", use_container_width=True):
                            res = publisher.publish_to_youtube(
                                video_path=str(v_path),
                                title=meta_copy.get("title", v_path.stem),
                                description=meta_copy.get("instagram_caption", ""),
                                tags=meta_copy.get("hashtags", "")
                            )
                            if res.get("success"):
                                st.success(f"Published: {res.get('url')}")
                            else:
                                st.error(f"Error: {res.get('error')}")

                    with c_act_ig:
                        if not is_long:
                            if st.button("🚀 Instagram", key=f"lib_pub_ig_{v_path.stem}", use_container_width=True):
                                res = publisher.publish_to_instagram(
                                    video_url_or_path=str(v_path),
                                    caption=f"{meta_copy.get('instagram_caption', '')}\n\n{meta_copy.get('hashtags', '')}"
                                )
                                if res.get("success"):
                                    st.success(f"Published: {res.get('url')}")
                                else:
                                    st.error(f"Error: {res.get('error')}")
                        else:
                            st.caption("*(16:9 Format for YouTube / Facebook)*")

                    st.markdown("---")
                    # Single-Click Video Deletion for Unwanted Shorts / Videos
                    if st.button("🗑️ Delete Video from Disk", key=f"btn_del_vid_{v_path.stem}", type="secondary", use_container_width=True):
                        if workspace_cleaner.delete_single_deliverable(str(v_path)):
                            st.toast(f"Deleted {v_name} and freed {v_size:.1f} MB!", icon="🗑️")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete {v_name}")

                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
