"""
Intelligent Viral Moment Detector for Comedy, Advice, Motivation, and High-Energy Highlights.
Analyzes acoustic energy, laughter rhythmic oscillations, speech cadence (WPM),
and semantic pattern recognition across:
1. Laughing / Comedy moments
2. Best Advice & Educational insights
3. Motivational & Mindset thoughts
4. High-energy viral spikes
"""

import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import soundfile as sf

from config import PROCESSING_DIR

logger = logging.getLogger("ViralShortsEngine.MomentDetector")

# 1. COMEDY & LAUGHTER PATTERNS
COMEDY_PATTERNS = [
    # Laugh tokens & onomatopoeia
    r"\b(ha(ha)+|he(he)+|lol|lmao|rofl|lmfao|haha|hehe|ahah|pfft|xd)\b",
    r"\[laughter\]|\(laughter\)|\*laughs\*|\[chuckle\]|\[giggle\]|\[snicker\]",
    # Humorous reactions & slang
    r"\b(i can'?t breathe|dying laughing|deadass|bro is wilding|outta pocket|funniest thing|cracking up|comedy gold)\b",
    r"\b(what is he doing|bro thought|look at him|no shot bro|he got cooked|he actually did that|that'?s foul|bro fell)\b",
    r"\b(literally crying|i am dead|can'?t make this up|joke of the year|roast|clowning|ridiculous|unhinged|goofy)\b",
    r"\b(the dumbest thing|the funniest|are you kidding me|no way in hell|bro really said|wildest thing)\b"
]

# 2. BEST ADVICE & EDUCATIONAL PATTERNS
ADVICE_EDUCATIONAL_PATTERNS = [
    # Direct advice & pro-tips
    r"\b(my advice (is|to you)|best advice|here is the trick|golden rule|number one tip|rule of thumb|protip)\b",
    r"\b(stop doing this|never do this|always remember to|the biggest mistake (people|you|everyone)|do this instead|avoid this)\b",
    r"\b(the secret to|how to actually|if you want to|here is how you|the reason why|the only way to|here'?s the hack)\b",
    r"\b(lesson i learned|key takeaway|the formula is|the framework|step by step|let me give you an example)\b",
    r"\b(the single best thing|what most people get wrong|if i had to start over|listen to this advice)\b",
    # Educational & explanatory insights
    r"\b(what happens when|how does (it|this) work|science shows|studies show|research proves|the psychology of)\b",
    r"\b(in simple terms|broken down|basically what happens|here is what you need to know|concept called)\b",
    r"\b(the truth about|the reality is|most people don'?t realize|here is the data|economists|engineers|scientists)\b",
    r"\b(the difference between|how it affects your brain|mechanism|algorithm|technique|methodology)\b"
]

# 3. MOTIVATIONAL & MINDSET THOUGHTS
MOTIVATIONAL_MINDSET_PATTERNS = [
    # Grit, discipline & perseverance
    r"\b(never give up|keep going|keep pushing|don'?t stop|stay hard|lock in|grind never stops|push through)\b",
    r"\b(discipline|consistency|dedication|sacrifices|put in the work|hard work beats talent|no excuses)\b",
    r"\b(nobody is coming to save you|it starts with you|take full responsibility|control what you can control)\b",
    r"\b(believe in yourself|trust the process|winners and losers|champion mindset|greatness takes time|be obsessed)\b",
    r"\b(pain is temporary|embrace the struggle|turn pain into power|overcome adversity|failure is a lesson)\b",
    r"\b(your dream|your purpose|leave a legacy|chase your goals|get out of your comfort zone|your future self)\b",
    r"\b(wake up early|every single morning|every single day|one day or day one|regret is worse than failure)\b",
    r"\b(they doubted you|prove them wrong|focus on your mission|silent work|you have what it takes)\b"
]

# 4. STREAMER REACTION: ANGRY & RAGE MOMENTS
RAGE_PATTERNS = [
    r"\b(are you (serious|kidding me)|what the (f\*\*\*|fuck|hell)|unbelievable|trash|garbage|this game is (broken|horrible|rigged))\b",
    r"\b(i hate this|stop it|shut up|you suck|are you dumb|stupid|idiot|cheating|hacker|hax|rigged|bullshit|scam)\b",
    r"\b(why would you do that|no way bro|i am done|i quit|uninstall|i cannot with this|smash my|rage)\b",
    r"\b(how did he not die|he is one shot|missed every shot|aim assist|so bad|i'?m so mad|pissed off|absolute nonsense)\b"
]

# 5. STREAMER REACTION: HAPPY & CELEBRATION WINS
HAPPY_PATTERNS = [
    r"\b(let'?s go|we did it|yes yes yes|finally|huge win|massive win|ez|easy|pog|poggers|w in the chat|clutch)\b",
    r"\b(i am so happy|best day ever|thank you so much|we won|champion|victory|unreal|insane play|clean play)\b",
    r"\b(i love you guys|blessed|grateful|dream come true|we hit it|record broken|world record|flawless|let'?s freaking go)\b"
]

# 6. STREAMER REACTION: SHOCKED & DISBELIEF (HYPE)
SHOCK_PATTERNS = [
    r"\b(what (just happened|the hell)|oh my god|holy (shit|moly|crap)|bro what|wait wait wait|hold on a second)\b",
    r"\b(no way|did you see that|are you seeing this|how did that happen|what was that|look at that|did that just happen)\b",
    r"\b(what in the world|i cannot believe|that is impossible|ain'?t no way|is this real|you are lying|jaw dropped)\b"
]

# 7. GEOPOLITICS, GLOBAL CONFLICT & DIPLOMATIC CLASH
GEOPOLITICS_CONFLICT_PATTERNS = [
    r"\b(war|military|invade|missile|tensions|clash|attack|strike|weapon|defense|nato|superpower)\b",
    r"\b(sanctions|embargo|economy|trade war|collapse|dollar|tariffs|oil|semiconductors|chokepoint)\b",
    r"\b(united states|china|russia|taiwan|ukraine|iran|middle east|borders|territory|sovereignty)\b",
    r"\b(the real reason behind|geopolitical strategy|why they did it|secret alliance|crisis|escalation)\b"
]

# 8. SUPERCHAT, VIEWER DONATION & CONTROVERSY CLAPBACKS
SUPERCHAT_CONTROVERSY_PATTERNS = [
    r"\b(someone in chat (said|is saying)|chat is asking|this (superchat|donation) says|\$\d+ from|donation from|reading chat|why did you do|did you really|answering the allegation|addressing the drama)\b",
    r"\b(first of all|let me set the record straight|that is complete bullshit|you don'?t know what happened|let me address this|stop spreading lies|i have the receipts|here is the proof|i never said that|listen to me chat)\b"
]

# 9. STREAMER WATCHING & REACTING TO OTHER CREATOR DRAMA
DRAMA_REACTION_PATTERNS = [
    r"\b(pause (the video|it|it right there)|hold on a second|wait wait wait|did he really just say that|look at what he did|bro is actually lying|he cooked himself|reacting to|drama breakdown|i cannot believe he posted this)\b",
    r"\b(did you hear what he said|unbelievable drama|he responded to me|why is he talking about me|look at this clip)\b"
]

# 10. GAMEPLAY ACTION: MULTI-KILLS, FLICKS & UNEXPECTED CLUTCHES
GAMEPLAY_ACTION_CLUTCH_PATTERNS = [
    r"\b(one down|two down|three down|another one|triple kill|quad kill|ace|1v\d clutch|he'?s one shot|where did he come from|insane flick|how did i hit that|clutch or kick|clean headshot|unexpected kill|sniped him|wiped the whole team)\b",
    r"\b(clutching this|no way i survived|how am i alive|spray transfer|got him through the smoke|flawless round)\b"
]

# 11. GTA 6 & NEW GAME LAUNCH REACTIONS & PHYSICS
GTA6_NEW_GAME_PATTERNS = [
    r"\b(gta\s*6|gta\s*vi|vice city|rockstar games|look at the graphics|look at the physics|water physics|car deformation|they actually added this|first time playing|this game looks unreal|look at this detail|new update is insane|npc reaction)\b",
    r"\b(next gen physics|unreal engine|insane graphics|jaw dropping|best game ever made|worth the wait)\b"
]

# 12. GEOPOLITICAL REFORMS, NEW LAWS & LEGISLATION
GEOPOLITICS_POLICY_PATTERNS = [
    r"\b(new law|signed an executive order|effective immediately|the parliament passed|new regulation|historic legislation|announced a new policy|prime minister announced|president declared|constitutional reform|crackdown on|major reform|new rule in the country)\b",
    r"\b(press conference|answering the press|heated exchange|called out by the journalist|refused to answer|defended the policy|bold move by the government)\b"
]

# 13. GENERAL VIRAL HOOKS & QUESTIONS
HOOK_PATTERNS = [
    r"\b(how to|secret to|the truth about|did you know|guess what|what happens if|can you believe|listen to this)\b",
    r"\b(why|how|what|where|who|when)\b.*\?"
]


def classify_video_niche(
    metadata: Dict[str, Any],
    layout_info: Dict[str, Any],
    transcript_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Intelligently determines the niche of the video:
    - PODCAST: 🎙️ Podcast / Interview / Conversation
    - GAMING: 🎮 Gaming Stream / Let's Play / Esports
    - COMEDY: 😂 Comedy Show / Standup / Roast / Skit
    - EDUCATIONAL: 💡 Educational / Documentary / How-To
    - VLOG: 👤 Vlog / Talking Head / Personal Story
    """
    title = (metadata.get("title", "") + " " + metadata.get("description", "")).lower()
    uploader = metadata.get("uploader", "").lower()
    full_text = ""
    if transcript_data and transcript_data.get("text"):
        full_text = transcript_data["text"][:3000].lower()

    scores = {
        "PODCAST": 0,
        "GAMING": 0,
        "COMEDY": 0,
        "EDUCATIONAL": 0,
        "GEOPOLITICS": 0,
        "VLOG": 0
    }
    reasons = []

    # Visual Layout Cues
    cls_name = layout_info.get("classification", "GENERAL")
    if cls_name == "PODCAST" or layout_info.get("podcast_speakers"):
        scores["PODCAST"] += 45
        reasons.append("Multi-speaker horizontal layout detected")
    elif cls_name == "STREAMER_FACECAM":
        scores["GAMING"] += 45
        reasons.append("Streamer corner facecam detected")
    elif cls_name == "GAMEPLAY":
        scores["GAMING"] += 35
        reasons.append("Fast-motion gameplay footage detected")
    elif cls_name == "TALKING_HEAD":
        scores["VLOG"] += 20
        scores["EDUCATIONAL"] += 15
        scores["GEOPOLITICS"] += 15

    # Title / Metadata Cues
    podcast_kw = ["podcast", "interview", "ft.", "featuring", "ep.", "episode", "with", "show", "talk", "dialogue", "huberman", "raj shamani", "rogan"]
    gaming_kw = ["gameplay", "stream", "live", "twitch", "kick", "fortnite", "valorant", "gta", "minecraft", "cod", "warzone", "ranked", "walkthrough", "speedrun", "clutch", "boss fight"]
    comedy_kw = ["comedy", "standup", "stand-up", "roast", "funny", "jokes", "hilarious", "latent", "parody", "skit", "laughter"]
    edu_kw = ["how to", "tutorial", "guide", "explained", "science", "history", "habits", "lesson", "deep dive", "crash course", "summary", "why do", "breakdown", "quantum", "physics", "biology"]
    geo_kw = ["geopolitics", "war", "military", "sanctions", "china", "russia", "nato", "taiwan", "conflict", "superpower", "crisis", "economy", "border", "tensions", "diplomacy", "treaty", "trade war", "middle east"]

    for kw in podcast_kw:
        if kw in title:
            scores["PODCAST"] += 18
    for kw in gaming_kw:
        if kw in title:
            scores["GAMING"] += 20
    for kw in comedy_kw:
        if kw in title:
            scores["COMEDY"] += 22
    for kw in edu_kw:
        if kw in title:
            scores["EDUCATIONAL"] += 18
    for kw in geo_kw:
        if kw in title:
            scores["GEOPOLITICS"] += 25

    # Transcript Vocabulary Cues
    if full_text:
        if re.search(r"\b(guest|welcome to the show|thank you for coming|in your book|listen|podcast|co-host)\b", full_text):
            scores["PODCAST"] += 20
            reasons.append("Interview / dialogue vocabulary in transcript")
        if re.search(r"\b(gg|clutch|headshot|game|kill|died|revive|bro look|he's low|one shot|ping|stream)\b", full_text):
            scores["GAMING"] += 20
            reasons.append("Gaming callouts in transcript")
        if re.search(r"\b(ha(ha)+|lol|lmao|\[laughter\]|laughing|audience|joke)\b", full_text):
            scores["COMEDY"] += 20
            reasons.append("Laughter reactions in transcript")
        if re.search(r"\b(science|studies show|the reason why|research|first step|technique|method|rule of thumb)\b", full_text):
            scores["EDUCATIONAL"] += 20
            reasons.append("Educational explanations in transcript")
        if re.search(r"\b(geopolitics|war|military|sanctions|nato|superpower|chokepoint|foreign policy|alliance)\b", full_text):
            scores["GEOPOLITICS"] += 25
            reasons.append("Geopolitical and global conflict vocabulary")

    top_niche = max(scores, key=scores.get)
    max_score = scores[top_niche]

    niche_labels = {
        "PODCAST": ("🎙️ Podcast / Interview", "PODCAST_SPLIT", "hormozi"),
        "GAMING": ("🎮 Gaming Stream / Let's Play", "STREAMER_SPLIT", "mrbeast"),
        "COMEDY": ("😂 Comedy & Standup Show", "PODCAST_SPLIT" if cls_name == "PODCAST" else "CINEMATIC_BLUR", "hormozi"),
        "EDUCATIONAL": ("💡 Educational / Video Essay", "TALKING_HEAD" if cls_name == "TALKING_HEAD" else "CINEMATIC_BLUR", "aesthetic"),
        "GEOPOLITICS": ("🌍 Geopolitics & Global Affairs", "TALKING_HEAD" if cls_name == "TALKING_HEAD" else "CINEMATIC_BLUR", "crimson"),
        "VLOG": ("👤 Vlog / Talking Head", "TALKING_HEAD", "hormozi")
    }

    label, template, caption = niche_labels.get(top_niche, ("🎬 General Video", "CINEMATIC_BLUR", "hormozi"))
    confidence = min(0.96, max(0.55, max_score / 75.0))

    return {
        "niche": top_niche,
        "label": label,
        "confidence": round(confidence, 2),
        "reasons": reasons[:3] if reasons else ["Visual & audio dynamics analysis"],
        "recommended_template": template,
        "recommended_caption": caption
    }


class MomentDetector:
    def __init__(self):
        pass

    def extract_audio_energy(
        self,
        video_path: str,
        temp_dir: Path,
        time_range: Optional[Tuple[float, float]] = None
    ) -> Tuple[np.ndarray, float, float]:
        """
        Extracts 16kHz mono audio, computes RMS energy profile across time,
        and measures laughter/oscillation variance. Supports time_range for fast slicing.
        """
        range_suffix = f"_{int(time_range[0])}_{int(time_range[1])}" if time_range else ""
        wav_path = temp_dir / f"{Path(video_path).stem}{range_suffix}_16k.wav"
        
        if not wav_path.exists():
            cmd = ["ffmpeg", "-y"]
            if time_range:
                cmd.extend(["-ss", str(time_range[0]), "-to", str(time_range[1])])
            cmd.extend([
                "-i", str(video_path),
                "-vn", "-ac", "1", "-ar", "16000",
                "-f", "wav", str(wav_path)
            ])
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        data, samplerate = sf.read(str(wav_path))
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        max_val = np.max(np.abs(data)) or 1.0
        data = data / max_val

        # Compute RMS in 0.5s windows (8000 samples) with 0.25s hop
        frame_len = int(samplerate * 0.5)
        hop_len = int(samplerate * 0.25)
        num_frames = max(1, (len(data) - frame_len) // hop_len + 1)
        
        rms_values = []
        for i in range(num_frames):
            frame = data[i * hop_len : i * hop_len + frame_len]
            rms = np.sqrt(np.mean(frame ** 2))
            rms_values.append(rms)

        rms_array = np.array(rms_values)
        if len(rms_array) > 0 and np.max(rms_array) > 0:
            rms_array = rms_array / np.max(rms_array)

        return rms_array, hop_len / samplerate, float(np.std(rms_array) if len(rms_array) > 0 else 0.0)

    def find_stream_reaction_peaks(
        self,
        video_path: str,
        top_n: int = 5,
        window_duration: float = 30.0,
        temp_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """
        Ultra-fast acoustic energy scanner for long live streams/VODs (Kick, Twitch, YouTube).
        Quickly scans 8kHz audio energy to locate the top streamer shouting/rage/hype peaks
        without waiting 45 minutes for full Whisper transcription.
        """
        temp_dir = temp_dir or PROCESSING_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        low_res_wav = temp_dir / f"{Path(video_path).stem}_scan8k.wav"
        if not low_res_wav.exists():
            logger.info("Extracting fast 8kHz audio stream for reaction peak scanning...")
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-ac", "1", "-ar", "8000",
                "-c:a", "pcm_s16le",
                "-f", "wav", str(low_res_wav)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        if not low_res_wav.exists():
            return []

        # Read in streaming blocks of 5 seconds to keep memory minimal
        samplerate = 8000
        block_sec = 5.0
        block_samples = int(samplerate * block_sec)
        
        block_energies = []
        with sf.SoundFile(str(low_res_wav)) as f:
            t = 0.0
            while True:
                data = f.read(block_samples)
                if len(data) == 0:
                    break
                rms = float(np.sqrt(np.mean(data ** 2)))
                block_energies.append((t, rms))
                t += len(data) / samplerate

        if not block_energies:
            return []

        # Find top N local peaks spaced at least 60s apart
        sorted_blocks = sorted(block_energies, key=lambda x: x[1], reverse=True)
        selected_peaks = []
        min_spacing = max(60.0, window_duration * 1.5)

        for t_peak, rms_val in sorted_blocks:
            if any(abs(t_peak - p[0]) < min_spacing for p in selected_peaks):
                continue
            selected_peaks.append((t_peak, rms_val))
            if len(selected_peaks) >= top_n:
                break

        selected_peaks.sort(key=lambda x: x[0])

        candidates = []
        for idx, (t_peak, rms_val) in enumerate(selected_peaks, start=1):
            clip_start = max(0.0, round(t_peak - 5.0, 1))
            clip_end = round(clip_start + window_duration, 1)
            
            cat = "STREAMER_RAGE" if (idx % 2 == 1) else "STREAMER_SHOCK"
            label = "🤬 Streamer Outburst / Peak" if cat == "STREAMER_RAGE" else "😱 Shocked & Hype Reaction"
            
            m = int(t_peak // 60)
            s = int(t_peak % 60)
            candidates.append({
                "start": clip_start,
                "end": clip_end,
                "duration": round(clip_end - clip_start, 1),
                "viral_score": round(92.0 + (top_n - idx), 1),
                "category": cat,
                "category_label": f"{label} #{idx}",
                "hook_text": f"High acoustic reaction peak detected at {m}m {s:02d}s",
                "rage_score": 88.0,
                "happy_score": 75.0,
                "shock_score": 92.0,
                "comedy_score": 80.0,
                "advice_score": 10.0,
                "motivation_score": 15.0,
                "text": f"[High-energy acoustic reaction spike ({rms_val:.4f} RMS) captured at {m}m {s:02d}s]"
            })

        return candidates

    def score_text_categories(self, text: str) -> Dict[str, float]:
        """
        Scores text across:
        - Streamer Reactions: Rage/Anger, Happy/Celebration, Shocked/Hype
        - Content Categories: Comedy/Humor, Advice/Educational, Motivational/Mindset
        """
        text_lower = text.lower()

        # 1. Comedy Score
        comedy_matches = 0
        for pattern in COMEDY_PATTERNS:
            matches = re.findall(pattern, text_lower)
            comedy_matches += len(matches)
        laugh_count = len(re.findall(r"(ha(ha)+|he(he)+|lol|lmao|rofl|\[laughter\])", text_lower))
        comedy_score = min(100.0, (comedy_matches * 22.0) + (laugh_count * 30.0))

        # 2. Streamer Reaction: Rage / Angry Outburst
        rage_matches = 0
        for pattern in RAGE_PATTERNS:
            matches = re.findall(pattern, text_lower)
            rage_matches += len(matches)
        rage_score = min(100.0, rage_matches * 30.0)

        # 3. Streamer Reaction: Happy / Celebration Win
        happy_matches = 0
        for pattern in HAPPY_PATTERNS:
            matches = re.findall(pattern, text_lower)
            happy_matches += len(matches)
        happy_score = min(100.0, happy_matches * 28.0)

        # 4. Streamer Reaction: Shocked / Disbelief (Hype)
        shock_matches = 0
        for pattern in SHOCK_PATTERNS:
            matches = re.findall(pattern, text_lower)
            shock_matches += len(matches)
        shock_score = min(100.0, shock_matches * 28.0)

        # 5. Advice & Educational Score
        advice_matches = 0
        for pattern in ADVICE_EDUCATIONAL_PATTERNS:
            matches = re.findall(pattern, text_lower)
            advice_matches += len(matches)
        advice_score = min(100.0, advice_matches * 25.0)

        # 6. Motivational & Mindset Score
        motivational_matches = 0
        for pattern in MOTIVATIONAL_MINDSET_PATTERNS:
            matches = re.findall(pattern, text_lower)
            motivational_matches += len(matches)
        motivation_score = min(100.0, motivational_matches * 26.0)

        # 7. Curiosity & Hook Score
        hook_matches = 0
        for pattern in HOOK_PATTERNS:
            matches = re.findall(pattern, text_lower)
            hook_matches += len(matches)
        hook_score = min(100.0, hook_matches * 20.0)

        # 8. Geopolitics & Global Conflict Score
        geo_matches = 0
        for pattern in GEOPOLITICS_CONFLICT_PATTERNS:
            matches = re.findall(pattern, text_lower)
            geo_matches += len(matches)
        geo_score = min(100.0, geo_matches * 25.0)

        # 9. Superchat & Controversy Rebuttal Score
        superchat_matches = 0
        for pattern in SUPERCHAT_CONTROVERSY_PATTERNS:
            matches = re.findall(pattern, text_lower)
            superchat_matches += len(matches)
        superchat_score = min(100.0, superchat_matches * 30.0)

        # 10. Drama Reaction to Other Creators
        drama_matches = 0
        for pattern in DRAMA_REACTION_PATTERNS:
            matches = re.findall(pattern, text_lower)
            drama_matches += len(matches)
        drama_score = min(100.0, drama_matches * 30.0)

        # 11. Gameplay Multi-Kills & Clutch Action
        clutch_matches = 0
        for pattern in GAMEPLAY_ACTION_CLUTCH_PATTERNS:
            matches = re.findall(pattern, text_lower)
            clutch_matches += len(matches)
        clutch_score = min(100.0, clutch_matches * 28.0)

        # 12. GTA 6 & New Game Hype Score
        gta6_matches = 0
        for pattern in GTA6_NEW_GAME_PATTERNS:
            matches = re.findall(pattern, text_lower)
            gta6_matches += len(matches)
        gta6_score = min(100.0, gta6_matches * 32.0)

        # 13. Geopolitical Policy & New Laws Score
        policy_matches = 0
        for pattern in GEOPOLITICS_POLICY_PATTERNS:
            matches = re.findall(pattern, text_lower)
            policy_matches += len(matches)
        policy_score = min(100.0, policy_matches * 28.0)

        return {
            "comedy": round(comedy_score, 1),
            "rage": round(rage_score, 1),
            "happy": round(happy_score, 1),
            "shock": round(shock_score, 1),
            "advice": round(advice_score, 1),
            "motivation": round(motivation_score, 1),
            "hook": round(hook_score, 1),
            "geopolitics": round(geo_score, 1),
            "superchat": round(superchat_score, 1),
            "drama": round(drama_score, 1),
            "clutch": round(clutch_score, 1),
            "gta6": round(gta6_score, 1),
            "policy": round(policy_score, 1)
        }

    def analyze_moments(self, video_path: str, transcript_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluates each segment against genre-specific patterns, acoustic energy surges,
        and speech delivery cadence.
        """
        segments = transcript_data.get("segments", [])
        if not segments:
            return []

        temp_dir = PROCESSING_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)

        t_min = min((s["start"] for s in segments), default=0.0)
        t_max = max((s["end"] for s in segments), default=0.0)
        time_offset = transcript_data.get("time_offset", 0.0)
        time_range = None
        if time_offset > 0 or (t_max - t_min > 0 and t_max - t_min < 3600):
            time_range = (t_min, t_max)

        try:
            rms_energy, time_step, global_std = self.extract_audio_energy(video_path, temp_dir, time_range=time_range)
        except Exception as e:
            logger.warning(f"Audio energy extraction failed ({e}). Proceeding with text dynamics.")
            rms_energy = np.array([])
            time_step = 0.25
            global_std = 0.0

        base_t = t_min if time_range else 0.0
        analyzed_segments = []

        for seg in segments:
            start_t = seg["start"]
            end_t = seg["end"]
            duration = max(0.1, end_t - start_t)
            text = seg["text"]
            words = seg.get("words", [])

            # Category Text Scores
            cat_scores = self.score_text_categories(text)

            # Audio Energy & Loudness Dynamics
            audio_score = 50.0
            energy_variance = 0.0
            if len(rms_energy) > 0 and time_step > 0:
                s_idx = max(0, int((start_t - base_t) / time_step))
                e_idx = min(len(rms_energy), int((end_t - base_t) / time_step))
                if e_idx > s_idx:
                    seg_rms = rms_energy[s_idx:e_idx]
                    avg_rms = float(np.mean(seg_rms))
                    peak_rms = float(np.max(seg_rms))
                    energy_variance = float(np.std(seg_rms))
                    audio_score = min(100.0, (peak_rms * 60.0 + avg_rms * 40.0) * 100.0)

            # Acoustic Laughter Boost (Staccato high-energy bursts)
            if energy_variance > 0.18 and audio_score > 60.0:
                cat_scores["comedy"] = min(100.0, cat_scores["comedy"] + 20.0)

            # Speech Rate / Cadence (Words Per Minute)
            num_words = len(words) if words else len(text.split())
            wpm = (num_words / duration) * 60.0
            
            # Pacing adjustment:
            # - Advice/Education prefers clear, deliberate delivery (110 - 160 WPM)
            # - Comedy/Hype prefers energetic delivery (130 - 190 WPM)
            if 115 <= wpm <= 185:
                cadence_score = 90.0
            elif 85 <= wpm < 115 or 185 < wpm <= 220:
                cadence_score = 70.0
            elif wpm < 70:
                cadence_score = 35.0
            else:
                cadence_score = 55.0

            # Acoustic Streamer Reaction Boosts
            if audio_score > 75.0 and cat_scores["rage"] > 0:
                cat_scores["rage"] = min(100.0, cat_scores["rage"] + 25.0)

            if energy_variance > 0.20 and audio_score > 65.0:
                cat_scores["shock"] = min(100.0, cat_scores["shock"] + 20.0)

            if audio_score > 70.0 and cat_scores["happy"] > 0:
                cat_scores["happy"] = min(100.0, cat_scores["happy"] + 20.0)

            # Determine dominant category
            scores_map = {
                "SUPERCHAT_CLAPBACK": cat_scores["superchat"],
                "DRAMA_REACTION": cat_scores["drama"],
                "GAMEPLAY_CLUTCH": cat_scores["clutch"],
                "GTA6_NEW_GAME": cat_scores["gta6"],
                "GEOPOLITICS_POLICY": cat_scores["policy"],
                "GEOPOLITICS_CLASH": cat_scores["geopolitics"],
                "STREAMER_RAGE": cat_scores["rage"],
                "STREAMER_HAPPY": cat_scores["happy"],
                "STREAMER_SHOCK": cat_scores["shock"],
                "COMEDY_HUMOR": cat_scores["comedy"],
                "ADVICE_EDUCATIONAL": cat_scores["advice"],
                "MOTIVATIONAL_MINDSET": cat_scores["motivation"]
            }
            top_category = max(scores_map, key=scores_map.get)
            top_score = scores_map[top_category]

            if top_score < 25.0:
                top_category = "VIRAL_GENERAL"
                category_label = "⚡ Viral Highlight"
            elif top_category == "SUPERCHAT_CLAPBACK":
                category_label = "💬 Superchat Rebuttal / Clapback"
            elif top_category == "DRAMA_REACTION":
                category_label = "🍿 Drama Reaction / Roast"
            elif top_category == "GAMEPLAY_CLUTCH":
                category_label = "🎯 Multi-Kill & Clutch Action"
            elif top_category == "GTA6_NEW_GAME":
                category_label = "🚗 GTA 6 / New Game Hype"
            elif top_category == "GEOPOLITICS_POLICY":
                category_label = "🏛️ New Law & Policy Reform"
            elif top_category == "GEOPOLITICS_CLASH":
                category_label = "⚠️ Geopolitical Showdown"
            elif top_category == "STREAMER_RAGE":
                category_label = "🤬 Streamer Rage & Outburst"
            elif top_category == "STREAMER_HAPPY":
                category_label = "😄 Happy Celebration Win"
            elif top_category == "STREAMER_SHOCK":
                category_label = "😱 Shocked & Disbelief (Hype)"
            elif top_category == "COMEDY_HUMOR":
                category_label = "😂 Laughing & Comedy Moment"
            elif top_category == "ADVICE_EDUCATIONAL":
                category_label = "💡 Best Advice & Educational"
            elif top_category == "MOTIVATIONAL_MINDSET":
                category_label = "🔥 Motivational & Mindset"

            # Composite Segment Score (0 - 100)
            genre_boost = max(top_score, cat_scores["hook"])
            composite_score = (
                genre_boost * 0.45 +
                audio_score * 0.35 +
                cadence_score * 0.20
            )

            analyzed_segments.append({
                "id": seg["id"],
                "start": start_t,
                "end": end_t,
                "duration": round(duration, 2),
                "text": text,
                "words": words,
                "category": top_category,
                "category_label": category_label,
                "comedy_score": cat_scores["comedy"],
                "rage_score": cat_scores["rage"],
                "happy_score": cat_scores["happy"],
                "shock_score": cat_scores["shock"],
                "advice_score": cat_scores["advice"],
                "motivation_score": cat_scores["motivation"],
                "hook_score": cat_scores["hook"],
                "audio_score": round(audio_score, 1),
                "cadence_score": round(cadence_score, 1),
                "wpm": round(wpm, 1),
                "segment_score": round(composite_score, 1)
            })

        return analyzed_segments
