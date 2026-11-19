"""
ViralShorts Pro - Multi-Modal AI Video Studio.
Professional 4-Tab Architecture:
1. Clip Studio: Link/Upload -> Deep Analysis -> Manual Trim & Framing Review -> User Approval -> Render & Video Player
2. Daily Feeds & Scripts: Multi-Category Live Feeds (Memes, Social Media, Gaming, News, Sports) -> Checklist -> AI Script Engine -> 1-Click Video Render & Player
3. Script to Vector Video: Script to Vector Video with OmniVoice TTS, Motion Graphics & Visuals -> Render & Video Player
4. Exports & Video Library: Comprehensive media library displaying all rendered 1080x1920 MP4s with playback, download & social publishing
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
from core.feed_manager import feed_manager
from core.tts_engine import tts_engine
from core.vector_video import vector_video_engine
from core.publisher import publisher

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
            label=f"Download {video_path.name}",
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
    
    /* Code & Copy Blocks */
    .pro-code-box {
        background: #090b10;
        border: 1px solid #1c2230;
        border-radius: 6px;
        padding: 10px 14px;
        font-family: monospace;
        font-size: 0.82rem;
        color: #cbd5e1;
        margin: 6px 0;
    }
    
    /* Sidebar Navigation */
    section[data-testid="stSidebar"] {
        background-color: #0e111a;
        border-right: 1px solid #1c2230;
    }
</style>
""", unsafe_allow_html=True)

# State initialization
if "nav_tab" not in st.session_state:
    st.session_state.nav_tab = "Clip Studio"
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "selected_clip_window" not in st.session_state:
    st.session_state.selected_clip_window = {"start": 0.0, "end": 35.0}
if "generated_short" not in st.session_state:
    st.session_state.generated_short = None
if "generated_script" not in st.session_state:
    st.session_state.generated_script = None
if "script_feed_topic" not in st.session_state:
    st.session_state.script_feed_topic = None
if "feed_video_result" not in st.session_state:
    st.session_state.feed_video_result = None
if "vector_video_result" not in st.session_state:
    st.session_state.vector_video_result = None
if "publish_status_msg" not in st.session_state:
    st.session_state.publish_status_msg = None
if "vector_topic_input" not in st.session_state:
    st.session_state.vector_topic_input = "GTA 6 Leaked Vice City Map & Release Window"
if "vector_script_data" not in st.session_state:
    st.session_state.vector_script_data = None
if "vector_angle_counter" not in st.session_state:
    st.session_state.vector_angle_counter = 0
if "last_vector_topic" not in st.session_state:
    st.session_state.last_vector_topic = ""

# Storage telemetry
storage_info = workspace_cleaner.get_storage_stats()
social_status = publisher.get_status()
all_rendered_videos = get_rendered_videos("*.mp4")


# =======================================================
# LEFT SIDEBAR NAVIGATION & SETTINGS
# =======================================================
with st.sidebar:
    st.markdown("### ViralShorts Pro")
    st.caption("AI-Powered Short Video Studio")

    # Main Navigation
    st.session_state.nav_tab = st.radio(
        "Navigation",
        options=[
            "Clip Studio",
            "Daily Feeds & Scripts",
            "Script to Vector Video",
            "Exports & Video Library"
        ],
        label_visibility="collapsed"
    )

    st.markdown(f"**Rendered Shorts:** `{len(all_rendered_videos)} ready`")

    st.divider()

    # Automated Social Media Publishing (Playwright Browser Sessions)
    with st.expander("🚀 Automated Social Publishing (Browser Playwright)", expanded=False):
        st.caption("Zero API keys, zero developer setup. Click to log in once in standard browser; your session stays saved locally!")

        # 1. YouTube Shorts
        st.markdown("#### 📺 YouTube Shorts")
        yt_conn = social_status.get("youtube_connected", False)
        st.markdown(f"Status: **{'🟢 Ready (Logged In)' if yt_conn else '⚪ Not Logged In'}**")

        c_yt_act1, c_yt_act2 = st.columns([1.5, 1])
        with c_yt_act1:
            if st.button("🌐 Open YouTube Login Window", key="btn_yt_login_pw", use_container_width=True):
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

        st.caption("💡 Click 'Open YouTube Login Window', sign in to Google/YouTube Studio, then close the browser window.")

        st.divider()

        # 2. Instagram Reels
        st.markdown("#### 📸 Instagram Reels")
        ig_conn = social_status.get("instagram_connected", False)
        st.markdown(f"Status: **{'🟢 Ready (Logged In)' if ig_conn else '⚪ Not Logged In'}**")

        if st.button("🌐 Open Instagram Login Window", key="btn_ig_login_pw", use_container_width=True):
            res = publisher.open_login_browser("instagram")
            st.info(res.get("message", "Browser window opened."))

        st.caption("💡 Click 'Open Instagram Login Window', log into your Instagram account, then close the browser window.")

        st.divider()

        # Auto-publish toggle
        auto_post_toggle = st.checkbox("Auto-publish to YouTube & Instagram upon render", value=social_status.get("auto_publish", False), key="chk_autopub")
        if auto_post_toggle != social_status.get("auto_publish"):
            publisher.update_settings(auto_publish_on_render=auto_post_toggle)
            st.rerun()

        if st.button("🔄 Refresh Login Status", use_container_width=True, key="btn_refresh_status"):
            st.rerun()

    # Disk Storage Manager
    with st.expander("Disk Storage & Cleanup", expanded=False):
        reclaim_gb = storage_info["downloads_size_gb"]
        temp_mb = storage_info["temp_size_mb"]
        st.markdown(f"**Downloaded Videos:** `{reclaim_gb:.2f} GB` ({storage_info['downloads_count']} files)")
        st.markdown(f"**Temp Processing Cache:** `{temp_mb:.1f} MB`")

        if st.button("Purge Raw Downloads (Free GBs)", use_container_width=True):
            res = workspace_cleaner.clean_all_downloads(preserve_test_sample=True)
            st.success(f"Purged {res['deleted_count']} files. Freed {res['freed_gb']:.2f} GB.")
            st.rerun()

        if st.button("Clean Temporary Cache", use_container_width=True):
            res = workspace_cleaner.clean_temporary_files()
            st.success(f"Freed {res['freed_mb']:.1f} MB temporary cache.")
            st.rerun()

    st.caption("Engine: faster-whisper int8 • FFmpeg NVENC/libx264")


# =======================================================
# RIGHT PANE: 80% WORKSPACE AREA
# =======================================================

# -------------------------------------------------------
# TAB 1: CLIP STUDIO (LINK/UPLOAD -> REVIEW -> APPROVE -> DELIVERABLE)
# -------------------------------------------------------
if st.session_state.nav_tab == "Clip Studio":
    st.markdown("## Clip Studio")
    st.caption("Convert long videos and streams into 9:16 Shorts with multi-modal AI moment detection and full approval control.")

    # Step 1: Input Ingestion
    with st.container():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Source Ingestion</span><span class='pro-badge badge-blue'>Step 1</span></div>", unsafe_allow_html=True)
        
        c_in_type1, c_in_type2 = st.tabs(["Online Video Link (YouTube / Reels / Kick)", "Upload Local Video / Recording"])
        
        source_input_path = None
        source_url_target = None

        with c_in_type1:
            url_val = st.text_input("Enter Video or Stream URL:", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
            if st.button("Analyze Video Stream", type="primary"):
                if url_val and url_val.strip():
                    with st.spinner("Downloading stream metadata and extracting audio..."):
                        downloader = VideoDownloader()
                        meta = downloader.download(url_val.strip())
                        source_input_path = meta["filepath"]
                        source_url_target = meta

        with c_in_type2:
            up_file = st.file_uploader("Select recording (.mp4, .mov, .mkv):", type=["mp4", "mov", "mkv"])
            if up_file and st.button("Analyze Uploaded File", type="primary"):
                save_loc = DOWNLOADS_DIR / up_file.name
                with open(save_loc, "wb") as f:
                    f.write(up_file.getbuffer())
                source_input_path = str(save_loc)
                source_url_target = {"id": up_file.name, "title": up_file.name, "filepath": str(save_loc)}

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
                selector = ClipSelector(min_duration=20.0, max_duration=55.0, genre_focus="all")
                moments = selector.select_clips(segments, num_shorts=3, genre_focus="all")

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
            st.markdown(f"**Source:** `{meta.get('title', 'Video')[:50]}` | **Duration:** `{format_time(total_dur)}`")
            layout_cls = analysis.get("layout", {}).get("classification", "GENERAL")
            st.markdown(f"**Detected Camera Layout:** `{layout_cls}`")

            if moments:
                st.write("Select an AI-detected moment candidate to populate trim handles:")
                m_labels = [f"#{i+1} [{m['category_label']}] {format_time(m['start'])} - {format_time(m['end'])} (Score: {m['viral_score']:.0f}%)" for i, m in enumerate(moments)]
                pick_idx = st.selectbox("Candidate Moments:", options=range(len(moments)), format_func=lambda i: m_labels[i])
                selected_mom = moments[pick_idx]
                st.caption(f"Why selected: {selected_mom.get('why_viral', 'High acoustic energy surge')}")
            else:
                selected_mom = {}

            # Precise Manual Trim Handles
            st.markdown("##### Trim Handles & Boundary Adjustment")
            cur_s = st.session_state.selected_clip_window["start"]
            cur_e = st.session_state.selected_clip_window["end"]

            s_col1, s_col2 = st.columns(2)
            with s_col1:
                start_val = st.number_input("Start Time (seconds):", min_value=0.0, max_value=float(total_dur), value=float(cur_s), step=1.0)
            with s_col2:
                end_val = st.number_input("End Time (seconds):", min_value=float(start_val) + 5.0, max_value=float(total_dur), value=max(float(start_val) + 5.0, float(cur_e)), step=1.0)

            clip_len = end_val - start_val
            st.markdown(f"**Active Clip Duration:** `{clip_len:.1f}s` (Recommended: 25s - 50s for Shorts)")

            # Custom Hook Title & Subtitle Styling
            hook_banner_text = st.text_input("Top Motion Hook Banner Text:", value=selected_mom.get("hook_text", "VIRAL MOMENT") if moments else "VIRAL MOMENT")
            style_preset = st.selectbox("Subtitle Motion Preset:", options=list(SUBTITLE_PRESETS.keys()), format_func=lambda k: SUBTITLE_PRESETS[k]["name"])

        with col_rev_right:
            st.markdown("##### Composition Settings")
            comp_mode = st.selectbox(
                "Vertical 9:16 Canvas Layout:",
                options=["AUTO", "STREAMER_SPLIT", "TALKING_HEAD", "CINEMATIC_BLUR"],
                format_func=lambda x: "Auto (Facecam Top + Gameplay Bottom)" if x in ["AUTO", "STREAMER_SPLIT"] and layout_cls == "STREAMER_FACECAM" else x
            )

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
                        "hook_text": hook_banner_text
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

                    out_path = exporter.render_clip(
                        source_path=data["source_path"],
                        clip_info=clip_info,
                        layout_info=analysis["layout"],
                        subtitle_path=ass_path if clip_words else None,
                        output_filename=out_fname,
                        template=comp_mode
                    )

                    # Generate social copy by inspecting original video's tags & description
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

    # Step 3: Render Deliverable & Output Display for Clip Studio
    clip_renders = get_rendered_videos("short_*.mp4") or get_rendered_videos("*.mp4")
    active_clip_file = None
    active_clip_meta = None

    if st.session_state.generated_short and Path(st.session_state.generated_short["path"]).exists():
        active_clip_file = Path(st.session_state.generated_short["path"])
        active_clip_meta = st.session_state.generated_short.get("social_copy", {})
    elif clip_renders:
        active_clip_file = clip_renders[0]
        active_clip_meta = ai_brain.generate_viral_metadata(clip_text=active_clip_file.stem, niche="GAMING")

    if active_clip_file and active_clip_file.exists():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Rendered Short Deliverable & Player</span><span class='pro-badge badge-green'>Ready to Publish</span></div>", unsafe_allow_html=True)

        if len(clip_renders) > 1:
            clip_choice = st.selectbox(
                "Select Rendered Clip to Preview:",
                options=clip_renders,
                format_func=lambda p: f"{p.name} ({p.stat().st_size / (1024*1024):.1f} MB)",
                key="clip_studio_file_selector"
            )
            if clip_choice != active_clip_file:
                active_clip_file = clip_choice
                active_clip_meta = ai_brain.generate_viral_metadata(clip_text=active_clip_file.stem, niche="GAMING")

        c_out_vid, c_out_meta = st.columns([1, 1.2])
        with c_out_vid:
            render_video_player(active_clip_file, key_prefix="clip_studio")
        with c_out_meta:
            st.markdown("**YouTube Shorts Title:**")
            st.code(active_clip_meta.get("title", active_clip_file.stem), language=None)
            st.markdown("**Instagram Reels Caption & Hashtags:**")
            st.code(f"{active_clip_meta.get('instagram_caption', '')}\n\n{active_clip_meta.get('hashtags', '')}", language=None)

            col_pub1, col_pub2 = st.columns(2)
            with col_pub1:
                if st.button("Publish to YouTube Shorts Now", key="pub_yt_clip_studio", use_container_width=True):
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
                if st.button("Publish to Instagram Reels Now", key="pub_ig_clip_studio", use_container_width=True):
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
        st.info("No clips rendered yet. Ingest a video above or select 'Exports & Video Library' to see past renders.")


# -------------------------------------------------------
# TAB 2: DAILY FEEDS & SCRIPTS (MULTI-CATEGORY + VIDEO RENDER)
# -------------------------------------------------------
elif st.session_state.nav_tab == "Daily Feeds & Scripts":
    st.markdown("## Daily Viral Feeds & Script Studio")
    st.caption("Live high-voltage gaming feeds: GTA 6 updates, live stream moments (Speed, Kai, xQc), creator drama & esports clutches.")

    if "feed_category_filter" not in st.session_state:
        st.session_state.feed_category_filter = "ALL"

    cat_col1, cat_col2, cat_col3, cat_col4, cat_col5, cat_col6 = st.columns(6)
    with cat_col1:
        if st.button("🔥 All Gaming", use_container_width=True):
            st.session_state.feed_category_filter = "ALL"
            st.rerun()
    with cat_col2:
        if st.button("🎮 GTA 6 & Releases", use_container_width=True):
            st.session_state.feed_category_filter = "GTA6_GAMES"
            st.rerun()
    with cat_col3:
        if st.button("🔴 Top Streamers", use_container_width=True):
            st.session_state.feed_category_filter = "STREAMERS"
            st.rerun()
    with cat_col4:
        if st.button("⚡ Drama & Bans", use_container_width=True):
            st.session_state.feed_category_filter = "DRAMA_BANS"
            st.rerun()
    with cat_col5:
        if st.button("🏆 Esports & BGMI", use_container_width=True):
            st.session_state.feed_category_filter = "ESPORTS"
            st.rerun()
    with cat_col6:
        if st.button("😂 Memes & Rage", use_container_width=True):
            st.session_state.feed_category_filter = "MEMES"
            st.rerun()

    active_category = st.session_state.feed_category_filter

    # Fetch live stories
    stories = feed_manager.fetch_category_feed(category=active_category, limit=8)

    st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='pro-card-header'><span>Live Real-Time Stories ({len(stories)} active topics)</span><span class='pro-badge badge-blue'>Select Topic</span></div>", unsafe_allow_html=True)

    selected_story = None
    for idx, st_item in enumerate(stories):
        c_sel, c_txt = st.columns([0.1, 0.9])
        with c_sel:
            is_picked = st.checkbox("", key=f"feed_chk_{st_item['id']}")
            if is_picked:
                selected_story = st_item
        with c_txt:
            st.markdown(f"**{st_item['title']}**")
            st.caption(f"{st_item['category_label']} • {st_item['source']} • {st_item['freshness']}")
        st.divider()

    st.markdown("</div>", unsafe_allow_html=True)

    # Script Generation Panel
    if selected_story or st.session_state.script_feed_topic:
        current_topic = selected_story["title"] if selected_story else st.session_state.script_feed_topic
        st.session_state.script_feed_topic = current_topic

        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>AI Vertical Script Generator</span><span class='pro-badge badge-amber'>Script Engine</span></div>", unsafe_allow_html=True)

        col_tone, col_regen = st.columns([2, 1])
        with col_tone:
            tone_setting = st.selectbox(
                "Script Narrative Tone:",
                options=["Dramatic & High Tension", "Humorous & Sarcastic", "Investigative Case Study", "Energetic & Fast-Paced"]
            )
        with col_regen:
            st.write("")
            regen_clicked = st.button("Regenerate Alternative Script", use_container_width=True)

        if regen_clicked or not st.session_state.generated_script:
            script_data = feed_manager.generate_vertical_script(
                topic=current_topic,
                category=active_category,
                tone=tone_setting
            )
            st.session_state.generated_script = script_data

        if st.session_state.generated_script:
            s_data = st.session_state.generated_script
            st.markdown(f"**Top Hook Banner:** `{s_data.get('hook_banner', 'THE REAL STORY')}`")

            final_script_text = st.text_area(
                "Script Narrative (35-40s):",
                value=s_data.get("script_text", ""),
                height=160
            )

            # Direct 1-Click Video Render Button + Forwarding Options
            st.write("")
            c_rend, c_act1, c_act2 = st.columns([1.4, 1, 1])
            with c_rend:
                if st.button("Render Short Video Now (1080x1920)", type="primary", use_container_width=True):
                    with st.spinner("Synthesizing OmniVoice narration & rendering 1080x1920 video..."):
                        feed_vid_res = vector_video_engine.build_vector_video(
                            script_text=final_script_text,
                            voice_id="en_us_male_deep",
                            custom_hook_title=s_data.get("hook_banner", "THE REAL STORY"),
                            subtitle_preset="alex_hormozi"
                        )
                        st.session_state.feed_video_result = feed_vid_res
                        if publisher.creds.get("auto_publish_on_render"):
                            publisher.auto_publish_if_enabled(feed_vid_res["output_path"], feed_vid_res["social_copy"])
                        st.rerun()

            with c_act1:
                if st.button("Send to Vector Video Studio", use_container_width=True):
                    st.session_state.vector_script_buffer = final_script_text
                    st.session_state.nav_tab = "Script to Vector Video"
                    st.rerun()
            with c_act2:
                if st.button("Search & Cut Stream Highlights", use_container_width=True):
                    st.session_state.nav_tab = "Clip Studio"
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Deliverable display for Tab 2 (Feed Generated Video)
    feed_renders = get_rendered_videos("vector_short_*.mp4") or get_rendered_videos("*.mp4")
    cur_feed_vid = None
    cur_feed_meta = None

    if st.session_state.feed_video_result and Path(st.session_state.feed_video_result["output_path"]).exists():
        cur_feed_vid = Path(st.session_state.feed_video_result["output_path"])
        cur_feed_meta = st.session_state.feed_video_result.get("social_copy", {})
    elif feed_renders:
        cur_feed_vid = feed_renders[0]
        cur_feed_meta = ai_brain.generate_viral_metadata(clip_text=cur_feed_vid.stem, niche="NEWS")

    if cur_feed_vid and cur_feed_vid.exists():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Rendered Feed Video Deliverable</span><span class='pro-badge badge-green'>Ready to Publish</span></div>", unsafe_allow_html=True)

        if len(feed_renders) > 1:
            f_pick = st.selectbox(
                "Select Feed Video to Preview:",
                options=feed_renders,
                format_func=lambda p: f"{p.name} ({p.stat().st_size / (1024*1024):.1f} MB)",
                key="feed_studio_file_selector"
            )
            if f_pick != cur_feed_vid:
                cur_feed_vid = f_pick
                cur_feed_meta = ai_brain.generate_viral_metadata(clip_text=cur_feed_vid.stem, niche="NEWS")

        c_f_vid, c_f_meta = st.columns([1, 1.2])
        with c_f_vid:
            render_video_player(cur_feed_vid, key_prefix="feed_studio")
        with c_f_meta:
            st.markdown("**Viral Video Title:**")
            st.code(cur_feed_meta.get("title", cur_feed_vid.stem), language=None)
            st.markdown("**Captions & Hashtags:**")
            st.code(f"{cur_feed_meta.get('instagram_caption', '')}\n\n{cur_feed_meta.get('hashtags', '')}", language=None)

            col_fp1, col_fp2 = st.columns(2)
            with col_fp1:
                if st.button("Publish to YouTube Shorts", key="pub_yt_feed_btn", use_container_width=True):
                    yt_p = publisher.publish_to_youtube(
                        video_path=str(cur_feed_vid),
                        title=cur_feed_meta.get("title", cur_feed_vid.stem),
                        description=cur_feed_meta.get("instagram_caption", ""),
                        tags=cur_feed_meta.get("hashtags", "")
                    )
                    if yt_p.get("success"):
                        st.success(f"Published to YouTube Shorts: {yt_p.get('url')}")
                    else:
                        st.error(f"Error: {yt_p.get('error')}")
            with col_fp2:
                if st.button("Publish to Instagram Reels", key="pub_ig_feed_btn", use_container_width=True):
                    ig_p = publisher.publish_to_instagram(
                        video_url_or_path=str(cur_feed_vid),
                        caption=f"{cur_feed_meta.get('instagram_caption', '')}\n\n{cur_feed_meta.get('hashtags', '')}"
                    )
                    if ig_p.get("success"):
                        st.success(f"Published to Instagram Reel: {ig_p.get('url')}")
                    else:
                        st.error(f"Error: {ig_p.get('error')}")

        st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------------------------------
# TAB 3: TOPIC TO VIDEO ENGINE (AUTO-SCRIPT + REDO + RENDER)
# -------------------------------------------------------
elif st.session_state.nav_tab == "Script to Vector Video":
    st.markdown("## Topic-to-Video Studio")
    st.caption("Enter any topic or pick from live trending feeds. The AI auto-generates a viral script with 1-click redo control, then renders a complete 1080x1920 Short.")

    # Check if a custom script was forwarded from Tab 2
    if hasattr(st.session_state, "vector_script_buffer") and st.session_state.vector_script_buffer:
        forwarded_text = st.session_state.vector_script_buffer
        del st.session_state.vector_script_buffer
        if forwarded_text:
            st.session_state.vector_script_data = {
                "hook_banner": "THE REAL STORY 🚨",
                "script_text": forwarded_text
            }

    # Step 1: Topic Input & Quick Suggestions
    with st.container():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>1. Enter Topic or Select from Trending Feeds</span><span class='pro-badge badge-blue'>Topic Input</span></div>", unsafe_allow_html=True)

        col_top_in, col_top_btn = st.columns([3, 1])
        with col_top_in:
            cur_topic = st.text_input(
                "Enter Video Topic:",
                value=st.session_state.vector_topic_input,
                placeholder="e.g. GTA 6 leaked map scale, IShowSpeed stream record, xQc ban controversy...",
                key="v_topic_text"
            )
            st.session_state.vector_topic_input = cur_topic

        with col_top_btn:
            st.write("")
            if st.button("Generate Script from Topic", type="secondary", use_container_width=True):
                st.session_state.vector_angle_counter = 0
                st.session_state.vector_script_data = feed_manager.generate_vertical_script(
                    topic=cur_topic,
                    angle_index=0
                )
                st.session_state.last_vector_topic = cur_topic
                st.rerun()

        # Quick Suggestion Chips from Current Live Feeds
        st.markdown("###### Trending Topic Suggestions (Click to autofill):")
        chip_col1, chip_col2, chip_col3, chip_col4 = st.columns(4)
        with chip_col1:
            if st.button("🎮 GTA 6 Vice City Map", use_container_width=True, key="chip_1"):
                st.session_state.vector_topic_input = "GTA 6 Leaked Vice City Map & World Scale"
                st.session_state.vector_angle_counter = 0
                st.session_state.vector_script_data = feed_manager.generate_vertical_script(st.session_state.vector_topic_input, angle_index=0)
                st.session_state.last_vector_topic = st.session_state.vector_topic_input
                st.rerun()
        with chip_col2:
            if st.button("🔴 IShowSpeed 1M Stream", use_container_width=True, key="chip_2"):
                st.session_state.vector_topic_input = "IShowSpeed Live Stream Hits 1 Million Concurrent Viewers"
                st.session_state.vector_angle_counter = 0
                st.session_state.vector_script_data = feed_manager.generate_vertical_script(st.session_state.vector_topic_input, angle_index=0)
                st.session_state.last_vector_topic = st.session_state.vector_topic_input
                st.rerun()
        with chip_col3:
            if st.button("⚡ Top Streamer Twitch Ban", use_container_width=True, key="chip_3"):
                st.session_state.vector_topic_input = "Popular Streamer Permanently Banned on Twitch Over Wild Clip"
                st.session_state.vector_angle_counter = 0
                st.session_state.vector_script_data = feed_manager.generate_vertical_script(st.session_state.vector_topic_input, angle_index=0)
                st.session_state.last_vector_topic = st.session_state.vector_topic_input
                st.rerun()
        with chip_col4:
            if st.button("🏆 Jonathan 1v4 Clutch", use_container_width=True, key="chip_4"):
                st.session_state.vector_topic_input = "Jonathan Gaming & Scout Insane 1v4 BGMI Finals Clutch"
                st.session_state.vector_angle_counter = 0
                st.session_state.vector_script_data = feed_manager.generate_vertical_script(st.session_state.vector_topic_input, angle_index=0)
                st.session_state.last_vector_topic = st.session_state.vector_topic_input
                st.rerun()

        # Auto-generate script if not yet generated or topic changed
        if not st.session_state.vector_script_data or st.session_state.last_vector_topic != cur_topic:
            st.session_state.vector_script_data = feed_manager.generate_vertical_script(
                topic=cur_topic,
                angle_index=st.session_state.vector_angle_counter
            )
            st.session_state.last_vector_topic = cur_topic

        st.markdown("</div>", unsafe_allow_html=True)

    # Step 2: Auto-Generated Script Review & Redo Script Controls
    script_data = st.session_state.vector_script_data
    with st.container():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>2. Auto-Generated Viral Script & Review</span><span class='pro-badge badge-amber'>Script Engine</span></div>", unsafe_allow_html=True)

        col_tone, col_redo = st.columns([2, 1.2])
        with col_tone:
            tone_setting = st.selectbox(
                "Narrative Style & Angle:",
                options=["Dramatic & High Tension", "Shocking Leak & Rumors", "Humorous & Sarcastic", "Fast-Paced Hype"],
                key="v_tone_select"
            )
        with col_redo:
            st.write("")
            if st.button("🔁 Redo Script (Alternative Angle)", type="secondary", use_container_width=True, key="btn_redo_script"):
                st.session_state.vector_angle_counter += 1
                new_s = feed_manager.generate_vertical_script(
                    topic=st.session_state.vector_topic_input,
                    tone=tone_setting,
                    angle_index=st.session_state.vector_angle_counter
                )
                st.session_state.vector_script_data = new_s
                st.success("Regenerated fresh alternative script angle!")
                st.rerun()

        hook_banner_input = st.text_input(
            "Top Motion Hook Banner Title:",
            value=script_data.get("hook_banner", "VIRAL MOMENT"),
            key="v_hook_banner"
        )

        editable_script_text = st.text_area(
            "Script Narrative (35-40s) — Review or Edit freely:",
            value=script_data.get("script_text", ""),
            height=140,
            key="v_script_textarea"
        )

        # Step 3: Voiceover & Kinetic Subtitle Settings
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            voice_options = tts_engine.get_available_voices()
            chosen_voice = st.selectbox(
                "OmniVoice Narration Voice:",
                options=[v["id"] for v in voice_options],
                format_func=lambda vid: next((v["name"] for v in voice_options if v["id"] == vid), vid),
                key="v_voice_select"
            )
        with col_v2:
            sub_style_vec = st.selectbox(
                "Subtitle Kinetic Preset:",
                options=list(SUBTITLE_PRESETS.keys()),
                format_func=lambda k: SUBTITLE_PRESETS[k]["name"],
                key="v_subtitle_preset"
            )

        ref_wav_upload = st.file_uploader("Optional: Upload Reference Voice Sample (.wav) for Zero-Shot Cloning:", type=["wav"], key="v_wav_upload")
        ref_path = None
        if ref_wav_upload:
            ref_save = PROCESSING_DIR / f"ref_voice_{ref_wav_upload.name}"
            with open(ref_save, "wb") as f:
                f.write(ref_wav_upload.getbuffer())
            ref_path = str(ref_save)
            st.caption(f"Loaded voice clone reference: {ref_wav_upload.name}")

        st.write("")
        # Step 4: Generate Video Button
        if st.button("🎬 Generate Complete 1080x1920 Short Video", type="primary", use_container_width=True, key="btn_gen_vector_video"):
            if editable_script_text and editable_script_text.strip():
                with st.spinner("Synthesizing OmniVoice narration, generating vector graphics & compositing 1080x1920 video..."):
                    vec_res = vector_video_engine.build_vector_video(
                        script_text=editable_script_text.strip(),
                        voice_id=chosen_voice,
                        reference_audio=ref_path,
                        custom_hook_title=hook_banner_input,
                        subtitle_preset=sub_style_vec
                    )
                    st.session_state.vector_video_result = vec_res

                    # Auto-publish if enabled
                    if publisher.creds.get("auto_publish_on_render"):
                        pub_res = publisher.auto_publish_if_enabled(vec_res["output_path"], vec_res["social_copy"])
                        st.session_state.publish_status_msg = pub_res

                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Deliverable View for Vector Video
    vec_renders = get_rendered_videos("vector_short_*.mp4") or get_rendered_videos("*.mp4")
    cur_vec_file = None
    cur_vec_meta = None

    if st.session_state.vector_video_result and Path(st.session_state.vector_video_result["output_path"]).exists():
        cur_vec_file = Path(st.session_state.vector_video_result["output_path"])
        cur_vec_meta = st.session_state.vector_video_result.get("social_copy", {})
    elif vec_renders:
        cur_vec_file = vec_renders[0]
        cur_vec_meta = ai_brain.generate_viral_metadata(clip_text=cur_vec_file.stem, niche="EDUCATION")

    if cur_vec_file and cur_vec_file.exists():
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.markdown("<div class='pro-card-header'><span>Rendered Vector Video Short</span><span class='pro-badge badge-green'>1080x1920 @ 60FPS</span></div>", unsafe_allow_html=True)

        if len(vec_renders) > 1:
            vec_pick = st.selectbox(
                "Select Vector Video to Preview:",
                options=vec_renders,
                format_func=lambda p: f"{p.name} ({p.stat().st_size / (1024*1024):.1f} MB)",
                key="vector_studio_file_selector"
            )
            if vec_pick != cur_vec_file:
                cur_vec_file = vec_pick
                cur_vec_meta = ai_brain.generate_viral_metadata(clip_text=cur_vec_file.stem, niche="EDUCATION")

        col_v_play, col_v_dist = st.columns([1, 1.2])
        with col_v_play:
            render_video_player(cur_vec_file, key_prefix="vector_studio")
        with col_v_dist:
            st.markdown("**Viral Title:**")
            st.code(cur_vec_meta.get("title", cur_vec_file.stem), language=None)
            st.markdown("**Instagram / Social Caption:**")
            st.code(f"{cur_vec_meta.get('instagram_caption', '')}\n\n{cur_vec_meta.get('hashtags', '')}", language=None)

            c_p1, c_p2 = st.columns(2)
            with c_p1:
                if st.button("Post to YouTube Shorts", key="pub_yt_vec_btn", use_container_width=True):
                    yt_p = publisher.publish_to_youtube(
                        video_path=str(cur_vec_file),
                        title=cur_vec_meta.get("title", cur_vec_file.stem),
                        description=cur_vec_meta.get("instagram_caption", ""),
                        tags=cur_vec_meta.get("hashtags", "")
                    )
                    if yt_p.get("success"):
                        st.success(f"Uploaded: {yt_p.get('url')}")
                    else:
                        st.error(f"Error: {yt_p.get('error')}")
            with c_p2:
                if st.button("Post to Instagram Reels", key="pub_ig_vec_btn", use_container_width=True):
                    ig_p = publisher.publish_to_instagram(
                        video_url_or_path=str(cur_vec_file),
                        caption=f"{cur_vec_meta.get('instagram_caption', '')}\n\n{cur_vec_meta.get('hashtags', '')}"
                    )
                    if ig_p.get("success"):
                        st.success(f"Uploaded: {ig_p.get('url')}")
                    else:
                        st.error(f"Error: {ig_p.get('error')}")

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No vector videos rendered yet. Enter a script above and click 'Generate Complete Vector Video Short'.")


# -------------------------------------------------------
# TAB 4: EXPORTS & VIDEO LIBRARY (ALL GENERATED VIDEOS)
# -------------------------------------------------------
elif st.session_state.nav_tab == "Exports & Video Library":
    st.markdown("## Studio Exports & Video Library")
    st.caption("Browse, preview, download, and publish all rendered 1080x1920 MP4 Shorts generated across all modules.")

    all_vids = get_rendered_videos("*.mp4")
    
    if not all_vids:
        st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
        st.info("No rendered videos found in workspace/output. Generate a clip in 'Clip Studio', a story video in 'Daily Feeds', or a motion video in 'Script to Vector Video' to populate this library.")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        total_size_mb = sum(p.stat().st_size for p in all_vids) / (1024 * 1024)
        st.markdown(f"**Found {len(all_vids)} Rendered Videos** (`{total_size_mb:.1f} MB` total output storage)")

        # Layout: Video selector dropdown and active player card
        sel_vid = st.selectbox(
            "Select Video to Play & Manage:",
            options=all_vids,
            format_func=lambda p: f"{p.name} — {p.stat().st_size / (1024*1024):.2f} MB"
        )

        if sel_vid and sel_vid.exists():
            st.markdown("<div class='pro-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='pro-card-header'><span>{sel_vid.name}</span><span class='pro-badge badge-green'>1080x1920 MP4</span></div>", unsafe_allow_html=True)

            col_lib_vid, col_lib_info = st.columns([1, 1.2])
            with col_lib_vid:
                render_video_player(sel_vid, key_prefix="library_view")

            with col_lib_info:
                st.markdown(f"**File Size:** `{sel_vid.stat().st_size / (1024*1024):.2f} MB`")
                st.markdown(f"**File Location:** `{sel_vid}`")

                lib_meta = ai_brain.generate_viral_metadata(clip_text=sel_vid.stem, niche="GENERAL")
                st.markdown("**Viral Copy Blueprint:**")
                st.code(f"{lib_meta.get('title', sel_vid.stem)}\n\n{lib_meta.get('instagram_caption', '')}\n\n{lib_meta.get('hashtags', '')}", language=None)

                c_l1, c_l2 = st.columns(2)
                with c_l1:
                    if st.button("Publish to YouTube Shorts", key="lib_pub_yt", use_container_width=True):
                        yt_res = publisher.publish_to_youtube(
                            video_path=str(sel_vid),
                            title=lib_meta.get("title", sel_vid.stem),
                            description=lib_meta.get("instagram_caption", ""),
                            tags=lib_meta.get("hashtags", "")
                        )
                        if yt_res.get("success"):
                            st.success(f"Uploaded: {yt_res.get('url')}")
                        else:
                            st.error(f"Error: {yt_res.get('error')}")

                with c_l2:
                    if st.button("Publish to Instagram Reels", key="lib_pub_ig", use_container_width=True):
                        ig_res = publisher.publish_to_instagram(
                            video_url_or_path=str(sel_vid),
                            caption=f"{lib_meta.get('instagram_caption', '')}\n\n{lib_meta.get('hashtags', '')}"
                        )
                        if ig_res.get("success"):
                            st.success(f"Uploaded: {ig_res.get('url')}")
                        else:
                            st.error(f"Error: {ig_res.get('error')}")

                st.write("")
                if st.button("Delete this Rendered Video", type="secondary", key="del_vid_lib"):
                    try:
                        sel_vid.unlink()
                        st.success(f"Deleted {sel_vid.name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not delete file: {e}")

            st.markdown("</div>", unsafe_allow_html=True)
