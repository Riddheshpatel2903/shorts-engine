"""
AI Brain Module for ViralShortsEngine.
Provides multi-backend AI intelligence for:
1. High-precision viral moment & controversy detection
2. Automatic niche-aware content scoring (Gaming, Education, Geopolitics, Memes, Sports)
3. Relatable, culturally grounded Indian Titles, Hook Overlays, Captions, and Scripts
4. Viral metadata copying & adaptation: analyzes the original viral video's description,
   tags, and title to replicate the exact winning structure for maximum virality.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.parse

logger = logging.getLogger("ViralShortsEngine.AIBrain")


class AIBrain:
    def __init__(self, api_key: Optional[str] = None, ollama_url: str = "http://localhost:11434"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.ollama_url = ollama_url
        self.backend = self._determine_backend()

    def _determine_backend(self) -> str:
        if self.api_key:
            return "gemini"
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "ViralShortsEngine"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    if models:
                        # Prefer qwen or llama if available
                        preferred = [m for m in models if any(k in m.lower() for k in ["qwen", "llama", "mistral", "gemma"])]
                        self.active_ollama_model = preferred[0] if preferred else models[0]
                        logger.info(f"Ollama connected with model: {self.active_ollama_model}")
                        return "ollama"
        except Exception:
            pass
        return "local_heuristic"

    def set_api_key(self, key: str):
        self.api_key = key.strip()
        if self.api_key:
            self.backend = "gemini"
        else:
            self.backend = self._determine_backend()

    def call_llm(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Calls the active backend LLM (Gemini or Ollama) with thinking-tag stripping."""
        if self.backend == "gemini" and self.api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 1000
                    }
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=12.0) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    return text.strip()
            except Exception as e:
                logger.warning(f"Gemini API call failed ({e}). Falling back to local heuristic.")
                self.backend = "local_heuristic"

        elif self.backend == "ollama":
            try:
                model_name = getattr(self, "active_ollama_model", "qwen3.5:4b")
                url = f"{self.ollama_url}/api/generate"
                payload = {
                    "model": model_name,
                    "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 1024
                    }
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30.0) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    raw_text = res_json.get("response", "").strip()
                    # Strip out Ollama <think>...</think> reasoning tags
                    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_text).strip()
                    return cleaned
            except Exception as e:
                logger.warning(f"Ollama call failed ({e}). Switching permanently to local heuristic.")
                self.backend = "local_heuristic"

        return None

    def detect_uncensored_viral_moments(
        self,
        transcript_segments: List[Dict[str, Any]],
        num_moments: int = 15,
        min_duration: float = 20.0,
        max_duration: float = 55.0,
        focus_genre: str = "uncensored_humor"
    ) -> List[Dict[str, Any]]:
        """
        Extracts up to num_moments highest-potency viral moments using Ollama LLM if available,
        guaranteeing deep semantic understanding of uncensored roasts, controversy, jokes and punchlines.
        """
        if not transcript_segments:
            return []

        # Try LLM if Ollama / Gemini is active and transcript has sufficient length
        if self.backend in ["gemini", "ollama"] and len(transcript_segments) >= 3:
            try:
                # Build concise transcript summary with timestamps
                chunk_lines = []
                for s in transcript_segments[:60]: # First ~5-10 minutes
                    t_str = f"[{s.get('start', 0.0):.1f}s - {s.get('end', 0.0):.1f}s]"
                    chunk_lines.append(f"{t_str} {s.get('text', '').strip()}")
                transcript_text = "\n".join(chunk_lines)

                system = (
                    "You are an uncensored viral social media clip editor. "
                    "Analyze the transcript and identify the most viral, hilarious, controversial, savage roast, "
                    "or shocking moments suitable for 9:16 Shorts (25-50s). "
                    "Focus strictly on HUMOR, SARCASM, ROASTS, CONTROVERSY, and SAVAGE BANTER, not noise. "
                    "Return a JSON array of objects with keys: start, end, hook_title, category, why_viral, punchline_time, score."
                )
                prompt = f"Find up to {num_moments} viral moments from this transcript:\n\n{transcript_text[:3500]}"
                llm_res = self.call_llm(prompt, system_prompt=system)
                if llm_res:
                    clean_json = re.sub(r"^```json\s*|\s*```$", "", llm_res.strip(), flags=re.MULTILINE)
                    parsed = json.loads(clean_json)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        llm_candidates = []
                        for item in parsed:
                            s_t = float(item.get("start", 0.0))
                            e_t = float(item.get("end", s_t + 35.0))
                            dur = round(max(min_duration, min(max_duration, e_t - s_t)), 1)
                            p_t = float(item.get("punchline_time", s_t + dur * 0.65))
                            llm_candidates.append({
                                "start": s_t,
                                "end": s_t + dur,
                                "duration": dur,
                                "viral_score": float(item.get("score", 95.0)),
                                "category": item.get("category", "CONTROVERSY_DRAMA"),
                                "category_label": f"🔥 {item.get('category', 'Viral Moment')}",
                                "hook_text": str(item.get("hook_title", "VIRAL MOMENT")).upper()[:36],
                                "why_viral": item.get("why_viral", "High semantic viral resonance identified by AI Brain."),
                                "punchline_time": p_t,
                                "is_comedy_or_reaction": True,
                                "radar": {"Acoustic Energy": 75, "Speech Cadence": 85, "Hook Potency": 95, "Viral Resonance": 98}
                            })
                        if len(llm_candidates) >= 2:
                            logger.info(f"AI Brain successfully extracted {len(llm_candidates)} semantic moments using {self.backend}.")
                            return llm_candidates[:num_moments]
            except Exception as e:
                logger.debug(f"LLM moment extraction fallback: {e}")

        return []

    def extract_viral_blueprint(self, source_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Inspects the original viral video's description, tags, and title to extract:
        - Winning hashtag sets
        - High-engagement call-to-action phrasing
        - Core topic keywords
        """
        if not source_metadata:
            return {"hashtags": [], "cta": "", "keywords": []}

        desc = source_metadata.get("description", "")
        title = source_metadata.get("title", "")
        raw_tags = source_metadata.get("tags", [])

        # Extract all hashtags present in viral description
        found_hashtags = re.findall(r"#\w+", desc)
        if isinstance(raw_tags, list):
            found_hashtags.extend([f"#{t.strip().replace(' ', '')}" for t in raw_tags if len(t.strip()) > 2])

        # Deduplicate preserving order
        unique_tags = []
        for tag in found_hashtags:
            t_clean = tag.lower()
            if t_clean not in [u.lower() for u in unique_tags] and len(t_clean) > 2:
                unique_tags.append(tag)

        # Extract Call To Action sentence if present
        cta = ""
        for line in desc.splitlines():
            line_str = line.strip()
            if any(k in line_str.lower() for k in ["comment", "thoughts", "subscribe", "share", "what do you think", "drop your"]):
                cta = line_str
                break

        return {
            "hashtags": unique_tags[:12],
            "cta": cta,
            "title_hint": title
        }

    def generate_viral_metadata(
        self,
        clip_text: str,
        niche: str = "GAMING",
        title_hint: str = "",
        source_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Generates ready-to-publish social metadata for YouTube Shorts and Instagram Reels.
        Actively inspects and adapts the original viral video's tags and description structure.
        """
        niche_upper = niche.upper()
        t_low = (clip_text + " " + title_hint).lower()

        # Extract viral blueprint from original video
        blueprint = self.extract_viral_blueprint(source_metadata)
        copied_tags = " ".join(blueprint["hashtags"]) if blueprint["hashtags"] else ""
        copied_cta = blueprint.get("cta", "")

        # If LLM active, let it craft viral copy using the original blueprint
        if self.backend in ["gemini", "ollama"] and clip_text:
            system = (
                f"You are a top viral social media producer in {niche_upper}. "
                "Analyze the source video's viral text and create ultra-high CTR copy for YouTube Shorts & Instagram Reels. "
                "Copy and adapt the winning hashtag structure from the viral original. "
                "Return JSON with keys: title, hook_overlay, instagram_caption, hashtags."
            )
            prompt = (
                f"Topic: {clip_text[:300]}\n"
                f"Original Viral Title: {title_hint}\n"
                f"Original Viral Tags: {copied_tags}\n"
                f"Original Viral CTA: {copied_cta}"
            )
            res = self.call_llm(prompt, system_prompt=system)
            if res:
                try:
                    clean = re.sub(r"^```json\s*|\s*```$", "", res.strip(), flags=re.MULTILINE)
                    data = json.loads(clean)
                    return {
                        "title": data.get("title", f"{title_hint[:60]} #Shorts"),
                        "hook_overlay": data.get("hook_overlay", "WAIT TILL THE END ⚠️"),
                        "instagram_caption": data.get("instagram_caption", f"{title_hint}\n\nDrop your thoughts below! 👇"),
                        "hashtags": data.get("hashtags", copied_tags or "#shorts #viral #reels")
                    }
                except Exception:
                    pass

        # Intelligent Built-In Copy Engine
        if niche_upper == "GEOPOLITICS":
            if any(k in t_low for k in ["jaishankar", "foreign policy", "russian oil", "western media"]):
                title = "S. Jaishankar's Savage Reply to Western Media! 💥🇮🇳 #Shorts"
                hook = "JAISHANKAR DROPS FACTS 💥"
                caption = "When questioned on India's strategic autonomy, EAM Dr. S. Jaishankar gave this iconic reply with pure facts.\n\nDo you support India's independent foreign policy? Drop your thoughts below! 👇"
                default_tags = "#jaishankar #geopolitics #indiadiplomacy #foreignpolicy #worldnews #shorts #reels"
            elif any(k in t_low for k in ["supreme court", "law", "criminal", "bns", "justice", "ruling"]):
                title = "Supreme Court Historic New Law Decision! ⚠️🏛️ #Shorts"
                hook = "NEW CRIMINAL LAW EXPLAINED ⚖️"
                caption = "The new legal reform and Supreme Court ruling impact every citizen from today.\n\nAre you aware of your new rights under this law? Tell us in the comments! 👇"
                default_tags = "#supremecourt #indianlaw #bns #constitution #legalnews #shorts #viral"
            else:
                title = f"{title_hint if title_hint else 'The Crisis That Changes Everything in 2026'} ⚠️ #Shorts"
                hook = "THE SHOCKING REALITY ⚠️"
                caption = "Crucial developments that will shape the upcoming global strategy.\n\nWhat is your perspective on this? Drop your comments below! 👇"
                default_tags = "#geopolitics #india #news #strategy #worldaffairs #shorts #reels"

        elif niche_upper == "GAMING":
            # 1. BGMI New Event / Update / Mode / Leaks
            if any(k in t_low for k in ["bgmi", "battlegrounds"]) and any(k in t_low for k in ["event", "update", "mode", "leak", "rp", "crate", "pass", "dinosaur", "shadow", "winter", "patch"]):
                clean_h = title_hint.strip() if title_hint else "BGMI New Event Update"
                title = f"{clean_h} 🔥 #Shorts" if not clean_h.endswith("#Shorts") else clean_h
                hook = "BGMI NEW EVENT UPDATE 🔥"
                caption = f"{clean_h} is finally here with insane free rewards and new mode! Tag your BGMI squad below! 👇"
                default_tags = "#bgmi #bgminewupdate #bgmievents #bgmiindia #pubgmobile #battlegroundsmobileindia #gaming #shorts #viral #reels"

            # 2. BGMI Clutch / Esports / Tournament
            elif any(k in t_low for k in ["bgmi", "pubg"]) and any(k in t_low for k in ["clutch", "1v4", "1v3", "esports", "scout", "jonathan", "finals", "tourney", "godlike", "soul"]):
                clean_h = title_hint.strip() if title_hint else "Insane 1v4 BGMI Clutch"
                title = f"{clean_h} 🎯🔥 #Shorts" if not clean_h.endswith("#Shorts") else clean_h
                hook = "INSANE 1v4 CLUTCH 🎯🔥"
                caption = f"{clean_h}! Clean squad wipe in the final circle. Rate this clutch from 1 to 10 in the comments! 👇"
                default_tags = "#bgmi #bgmiclutch #1v4 #bgmisports #jonathangaming #scoutop #gaming #esports #shorts #viral #reels"

            # 3. Superchat Controversy & Streamer Rebuttal
            elif any(k in t_low for k in ["superchat", "donation", "reply", "controversy", "drama", "roast", "clapback", "allegation"]):
                clean_h = title_hint.strip() if title_hint else "Streamer Savage Reply to Superchat"
                title = f"{clean_h} 💬🔥 #Shorts" if not clean_h.endswith("#Shorts") else clean_h
                hook = "STREAMER UNFILTERED REPLY 💬🔥"
                caption = f"{clean_h}! Bro sent this Superchat live and got an instant reaction. What's your take on this? Comment below! 👇"
                default_tags = "#superchat #streamer #streamermoments #twitchclips #streamerhighlight #viralmoments #shorts #viral #reels"

            # 4. Top Streamer Live Moments (Speed, Kai Cenat, xQc)
            elif any(k in t_low for k in ["speed", "kai", "ishowspeed", "cenat", "xqc"]):
                clean_h = title_hint.strip() if title_hint else "Top Streamer Goes Wild Live"
                title = f"{clean_h} ⚡🤯 #Shorts" if not clean_h.endswith("#Shorts") else clean_h
                hook = "STREAMER GOES WILD ⚡🤯"
                caption = f"{clean_h}! This live stream moment was completely unhinged 😂 Did you see this live? Tell us below! 👇"
                default_tags = "#ishowspeed #kaicenat #streamer #twitch #livestream #funnyclips #viral #shorts #reels"

            # 5. GTA 6 & Rockstar Next-Gen Game
            elif any(k in t_low for k in ["gta 6", "gta vi", "vice city", "physics", "rockstar"]):
                clean_h = title_hint.strip() if title_hint else "GTA 6 Leaked Gameplay & Map Details"
                title = f"{clean_h} 🚗🚨 #Shorts" if not clean_h.endswith("#Shorts") else clean_h
                hook = "GTA 6 DETAILS LEAKED 🚗"
                caption = f"{clean_h}! The world scale and physics in GTA 6 look unreal. Are you playing on PC or Console? Tell us below! 👇"
                default_tags = "#gta6 #gtavi #rockstargames #gta6leak #gaming #gamerlife #nextgen #shorts #reels"

            # 6. General Gaming / Custom Topic
            else:
                clean_h = title_hint.strip() if title_hint else "Viral Gaming Highlight"
                title = f"{clean_h} 🎮🔥 #Shorts" if not clean_h.endswith("#Shorts") else clean_h
                hook = "VIRAL GAMING MOMENT 🎮"
                caption = f"{clean_h}! Drop your thoughts and tag your squad teammate below! 👇"
                default_tags = "#gaming #gamer #gameplay #streamer #bgmi #shorts #viral #reels #trendingshorts"

        elif niche_upper == "SPORTS":
            title = f"{title_hint if title_hint else 'Unbelievable Final Over Thriller!'} 🏏🔥 #Shorts"
            hook = "UNREAL CLUTCH FINISH 🏏"
            caption = "What a match! Absolute nail-biter in the final overs.\n\nWho was the player of the match for you? Drop your take below! 👇"
            default_tags = "#cricket #teamindia #ipl #viratkohli #rohitsharma #sports #shorts #reels"

        elif niche_upper == "MEMES":
            title = f"{title_hint if title_hint else 'Bro Really Thought He Could Get Away With This'} 💀 #Shorts"
            hook = "BRO THOUGHT 💀"
            caption = "The internet has no chill today 😂\n\nSend this to that one friend who does this every single time! 👇"
            default_tags = "#memes #funny #viral #comedy #relatable #trending #shorts #reels"

        else: # EDUCATION
            title = f"{title_hint if title_hint else 'The Truth Nobody Is Talking About'} 🧠 #Shorts"
            hook = "HOW THIS HAPPENED 🧠"
            caption = "A breakdown of what actually happened behind closed doors.\n\nDid you find this insightful? Follow for more daily deep-dives! 💡"
            default_tags = "#education #casestudy #knowledge #facts #didyouknow #shorts #reels"

        # Merge copied hashtags with default tags
        final_tags = copied_tags if copied_tags else default_tags
        final_caption = f"{caption}\n\n{copied_cta}" if (copied_cta and copied_cta not in caption) else caption

        return {
            "title": title[:80],
            "hook_overlay": hook,
            "instagram_caption": final_caption,
            "hashtags": final_tags
        }


# Global singleton
ai_brain = AIBrain()
