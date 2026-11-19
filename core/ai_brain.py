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
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    if models:
                        self.active_ollama_model = models[0]
                        logger.info(f"Ollama connected with model: {self.active_ollama_model}")
                        return "ollama"
                    else:
                        logger.info("Ollama is running but has no installed models. Using local heuristic.")
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
        """Calls the active backend LLM."""
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
                        "maxOutputTokens": 800
                    }
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    return text.strip()
            except Exception as e:
                logger.warning(f"Gemini API call failed ({e}). Falling back to local heuristic.")
                self.backend = "local_heuristic"

        elif self.backend == "ollama":
            try:
                model_name = getattr(self, "active_ollama_model", "llama3")
                url = f"{self.ollama_url}/api/generate"
                payload = {
                    "model": model_name,
                    "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
                    "stream": False
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    return res_json.get("response", "").strip()
            except Exception as e:
                logger.warning(f"Ollama call failed ({e}). Switching permanently to local heuristic.")
                self.backend = "local_heuristic"

        return None

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
            if any(k in t_low for k in ["jonathan", "godlike", "superchat", "soul", "reply"]):
                title = "Jonathan Bhai Live Reply on Superchat Controversy! 🤯 #Shorts"
                hook = "JONATHAN UNFILTERED REPLY 💬🔥"
                caption = "Bhai ne stream pe seedha bina filter reply de diya! Roster controversy ka pura sach.\n\nWhose side are you on: GodLike or Soul? Comment below! 👇"
                default_tags = "#jonathan #jonathangaming #godlike #teamsoul #bgmi #bgmisports #shorts"
            elif any(k in t_low for k in ["scout", "clutch", "1v4", "m416", "bgis"]):
                title = "Scout OP Insane 1v4 M416 Clutch in Tournament Lobby! 🎯🔥 #Shorts"
                hook = "SCOUT 1v4 SQUAD WIPE 🎯💥"
                caption = "Full squad wipe in the last circle! Scout screaming 'Lobby khali kar di!' on mic.\n\nRate this clutch out of 10 in the comments! 👇"
                default_tags = "#scoutop #teamxspark #bgmi #bgmiclutch #1v4clutch #esports #shorts"
            elif any(k in t_low for k in ["gta 6", "gta vi", "vice city", "physics", "rockstar"]):
                title = "GTA 6 Next-Gen Gameplay: Streamers Shocked Reaction! 🚗🤯 #Shorts"
                hook = "GTA 6 PHYSICS ARE UNREAL 🚗"
                caption = "The car deformation, water physics, and AI reactions in GTA 6 are blowing everyone's mind.\n\nAre you playing on PC or Console? Tell us below! 👇"
                default_tags = "#gta6 #gtavi #rockstargames #gaming #gamerlife #nextgen #shorts #reels"
            else:
                title = f"{title_hint if title_hint else 'This Player Broke The Lobby in Ranked!'} 💀 #Shorts"
                hook = "NO WAY HE SURVIVED THIS 💀"
                caption = "Bro was fighting for his life in this final zone 😂\n\nCould you have clutched this? Tag your squad teammate! 👇"
                default_tags = "#bgmi #pubgmobile #gaming #gamer #clutch #streamer #shorts #reels"

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
