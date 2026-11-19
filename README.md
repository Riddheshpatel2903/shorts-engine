# ⚡ ViralShortsEngine: AI-Powered 9:16 Video Clipper

An automated, locally running AI video clipping and editing engine built natively in Python and FFmpeg. ViralShortsEngine accepts YouTube and Twitch URLs, performs faster-whisper AI transcription, scores viral speech dynamics, and intelligently extracts:
- 😂 **Most Laughing & Comedy Moments**
- 💡 **Best Advice & Educational Insights**
- 🔥 **Motivational & Mindset Thoughts**
- 🌟 **Auto-Discovered High-Engagement Highlights**

All rendered automatically into high-retention 9:16 vertical videos (YouTube Shorts, TikTok, Instagram Reels) with word-by-word animated karaoke subtitles.

---

## 🚀 Key Features

- **Genre-Specific AI Moment Detection**:
  - **Comedy & Laughter**: Detects acoustic laughter oscillations, laugh tokens (`[laughter]`, `haha`, `lmao`), witty banter, and comedy punchlines.
  - **Best Advice & Educational**: Extracts actionable life advice, pro tips, rules of thumb, and explanatory science/business takeaways.
  - **Motivational & Mindset**: Pinpoints powerful inspirational speeches, discipline/grit quotes, and philosophical crescendoes.
- **Native Local Execution**: 100% local, no cloud rendering, no Docker, zero paid API keys.
- **Hardware Acceleration**: Automatic NVIDIA GPU detection with `h264_nvenc` and CUDA, with multi-threaded CPU fallback (`libx264` + int8 Whisper).
- **Zero Audio-Video Drift (RULE A)**: Intermediate synchronized stream downloading, strict timestamp matching, and PTS resetting.
- **Viral Vertical Framing (RULE B)**: Dynamic Gaussian blurred backdrop with smart facecam extraction, talking-head centering, and gameplay composition.
- **Word-by-Word Karaoke Subtitles**: High-contrast, dynamic scale-pop subtitles in ASS format with electric yellow highlighting for the currently spoken word.
- **Interactive Web UI & CLI**: Run seamlessly via Streamlit visual dashboard or direct CLI commands.

---

## 🛠️ Usage

### Option 1: Interactive Streamlit Web UI

Run inside your `ViralShortsEngine` directory:
```powershell
python -m streamlit run ui.py
```
Or via main:
```powershell
python main.py --ui
```

In the UI sidebar:
- Select your **Viral Genre Target**:
  - `🌟 Auto (Best Overall Blend)`
  - `😂 Laughing & Comedy Moments`
  - `💡 Best Advice & Educational`
  - `🔥 Motivational & Mindset`
- Choose the number of Shorts to generate.
- Click **"Transcribe & Identify Viral Hooks"** to see ranked candidates with category badges and score breakdowns.
- Click **"Render 9:16 Viral Shorts"** to produce deliverables.

### Option 2: Command Line (CLI)

**Extract Comedy & Laughing Moments:**
```powershell
python main.py --url "https://www.youtube.com/watch?v=EXAMPLE" --genre comedy --shorts 3
```

**Extract Best Advice & Educational Takeaways:**
```powershell
python main.py --url "https://www.youtube.com/watch?v=EXAMPLE" --genre advice --shorts 3
```

**Extract Motivational & Mindset Speeches:**
```powershell
python main.py --url "https://www.youtube.com/watch?v=EXAMPLE" --genre motivation --shorts 3
```

**Auto Blend (Best Overall Moments across all categories):**
```powershell
python main.py --url "https://www.youtube.com/watch?v=EXAMPLE" --genre auto --shorts 3
```

---

## 📁 Project Architecture

```
ViralShortsEngine/
│
├── main.py                 # Master CLI orchestrator & automation pipeline
├── ui.py                   # Interactive Streamlit Web UI with Genre Selection
├── config.py               # Hardware profile, paths, styling & encoding parameters
├── requirements.txt        # Verified project dependencies
├── README.md               # User & architecture documentation
│
├── core/
│   ├── downloader.py       # yt-dlp downloader with stream merging & metadata
│   ├── transcriber.py      # faster-whisper AI transcription with word timestamps
│   ├── moment_detector.py  # Comedy, advice, motivation & acoustic energy scoring
│   ├── face_detector.py    # OpenCV YuNet neural face & facecam quadrant detector
│   ├── video_analyzer.py   # Deep stream inspection & layout classification
│   ├── clip_selector.py    # Natural sentence boundary alignment & genre ranking
│   ├── editor.py           # FFmpeg filter complex for 9:16 vertical composition
│   ├── subtitles.py        # Animated word-by-word karaoke ASS generator
│   └── exporter.py         # FFmpeg rendering, ffprobe validation & cleanup
│
├── assets/
│   ├── fonts/              # Custom typography
│   └── face_detection_yunet_2023mar.onnx  # OpenCV YuNet Face Detection model
│
├── workspace/
│   ├── downloads/          # Synchronized intermediate source videos
│   ├── processing/         # Temporary audio slices & subtitle files (auto-cleaned)
│   ├── output/             # Final deliverable 9:16 MP4 videos ONLY
│   └── processing_report.json  # Comprehensive run reports
│
└── logs/
    └── engine.log          # Execution diagnostics & runtime logs
```
