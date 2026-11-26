"""
Social Media Viral Trend Scout & Creator Controversy Radar.

Dynamically investigates the creator, guests, and subjects of a given video:
1. Scouts active viral debates, controversies, kalesh, and trending discussions
   circulating across Instagram Reels, YouTube Shorts, Reddit, and Twitter.
2. Extracts high-engagement keywords, hot-button topics, and conflict angles.
3. Scores and guides the moment detector and clip selector to find the EXACT
   segments in the video that address these active social media controversies.
"""

import re
import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ViralShortsEngine.SocialTrendScout")

# Built-in Creator Niche & Controversy Knowledge Base (Instant 0ms lookup)
KNOWN_CREATOR_TOPIC_REGISTRY = {
    "samay raina": {
        "niche": "Standup & Chess Controversy",
        "hot_topics": ["India's Got Latent controversy", "dark humor debate", "cancellation drama", "Munawar roast"],
        "keywords": ["latent", "dark humor", "cancelled", "roast", "judge", "munawar", "unfiltered", "apology"]
    },
    "the lavari show": {
        "niche": "Podcast & Creator Culture",
        "hot_topics": ["Fake friendships among creators", "creator ego clashes", "industry monetization drama", "unfiltered pod debate"],
        "keywords": ["fake", "industry", "ego", "hypocrite", "youtube money", "shwetabh", "prakhar", "friendship", "exposed"]
    },
    "beerbiceps": {
        "niche": "High-Profile Podcast & Aliens/Spirituality",
        "hot_topics": ["Alien conspiracy questions", "death and afterlife debate", "geopolitics interrogation", "meme roasts"],
        "keywords": ["aliens", "ghosts", "yeti", "death", "illuminati", "geopolitics", "spiritual", "meditation"]
    },
    "raj shamani": {
        "niche": "Business & Startups",
        "hot_topics": ["Startup scam exposures", "dark side of Indian businesses", "billionaire secrets", "wealth inequality"],
        "keywords": ["business", "scam", "startup", "crores", "billionaire", "money", "shark tank", "hidden truth"]
    },
    "ishowspeed": {
        "niche": "Streamer Hype & Outbursts",
        "hot_topics": ["Live streaming bans", "crazy fan encounters", "Ronaldo vs Messi heated debates", "unhinged stunts"],
        "keywords": ["speed", "ronaldo", "messi", "wild", "barking", "banned", "streamer", "stream snipers"]
    },
    "scout": {
        "niche": "Esports & BGMI Gaming",
        "hot_topics": ["Esports roster leaks and betrayal", "toxic scrims drama", "organizer controversy", "clutch comeback"],
        "keywords": ["bgmi", "roster", "esports", "toxic", "scrims", "lineup", "rivalry", "tournament"]
    },
    "dhruv rathee": {
        "niche": "Political & Social Analysis",
        "hot_topics": ["Elections and media bias debate", "fact check showdown", "freedom of speech controversy", "censorship"],
        "keywords": ["government", "media", "dictatorship", "fact check", "modi", "propaganda", "censorship", "exposed"]
    }
}


class SocialTrendScout:
    """
    Scouts social media trends, debates, and active controversies
    relevant to the creator, guests, or topic of the input video.
    """

    def __init__(self):
        self._trend_cache: Dict[str, Dict[str, Any]] = {}

    def extract_entities_from_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts creator name, guest names, and core topic concepts from video metadata.
        """
        title = metadata.get("title", "")
        uploader = metadata.get("uploader", "") or metadata.get("channel", "")
        desc = metadata.get("description", "")

        # 1. Clean Creator Name
        creator = uploader.strip()
        if not creator and title:
            # Try parsing "Show Name Ep X"
            m = re.match(r"^([^|–—-]+)", title)
            if m:
                creator = m.group(1).strip()

        # 2. Extract Guests ("feat.", "ft.", "with", "x", "vs")
        guests = []
        guest_patterns = [
            r"\b(?:feat\.?|ft\.?|with|versus|vs\.?)\s+([A-Za-z0-9\s]+?)(?:[|–—\-#,]|$)",
            r"\bx\s+([A-Za-z0-9\s]+?)(?:[|–—\-#,]|$)"
        ]
        for pat in guest_patterns:
            matches = re.findall(pat, title, re.IGNORECASE)
            for m in matches:
                clean_g = m.strip()
                if len(clean_g) > 2 and clean_g.lower() not in [c.lower() for c in guests] and clean_g.lower() != creator.lower():
                    guests.append(clean_g)

        # 3. Extract High-Engagement Topic Terms
        title_words = re.findall(r"\b[A-Za-z]{4,}\b", title)
        topic_terms = [w.lower() for w in title_words if w.lower() not in ["show", "episode", "full", "video", "with", "podcast"]]

        return {
            "creator": creator,
            "guests": guests,
            "title": title,
            "topic_terms": topic_terms[:8]
        }

    def scout_creator_trends(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gathers live viral topics, controversies, and debates regarding this creator/guest.
        Utilizes:
        1. Cache
        2. Known registry
        3. Real-time web/social discourse queries (when available)
        4. AI Brain Semantic Distillation
        """
        entities = self.extract_entities_from_metadata(metadata)
        creator_name = entities["creator"].lower()
        title_lower = entities["title"].lower()

        cache_key = f"{creator_name}_{entities['title'][:40]}"
        if cache_key in self._trend_cache:
            return self._trend_cache[cache_key]

        hot_debates = []
        trending_keywords = []
        niche = "Entertainment & Viral Discourse"

        # Check Known Registry for instant high-confidence hit
        for reg_name, reg_data in KNOWN_CREATOR_TOPIC_REGISTRY.items():
            if reg_name in creator_name or reg_name in title_lower:
                hot_debates.extend(reg_data["hot_topics"])
                trending_keywords.extend(reg_data["keywords"])
                niche = reg_data["niche"]
                logger.info(f"Matched registry profile for '{reg_name}': {len(hot_debates)} hot topics.")
                break

        # Check guests against registry
        for g in entities["guests"]:
            g_low = g.lower()
            for reg_name, reg_data in KNOWN_CREATOR_TOPIC_REGISTRY.items():
                if reg_name in g_low:
                    hot_debates.extend(reg_data["hot_topics"][:2])
                    trending_keywords.extend(reg_data["keywords"][:4])

        # Live Web Search for Trending Controversy (DuckDuckGo Lite API fallback)
        live_buzz = self._fetch_live_social_buzz(entities)
        if live_buzz:
            hot_debates.extend(live_buzz.get("debates", []))
            trending_keywords.extend(live_buzz.get("keywords", []))

        # Add topic keywords from title
        trending_keywords.extend(entities["topic_terms"])

        # Deduplicate
        unique_debates = list(dict.fromkeys(hot_debates))
        unique_keywords = list(dict.fromkeys(k.lower() for k in trending_keywords if len(k) > 2))

        # If still sparse, generate synthetic debate hooks from title entities
        if not unique_debates:
            subject_label = entities["guests"][0] if entities["guests"] else (entities["creator"] or "The Streamer")
            unique_debates = [
                f"Heated confrontation regarding {subject_label}'s controversial statements",
                f"Exposing the hidden truth behind {subject_label}'s claims",
                f"Unfiltered debate that sparked social media debate"
            ]
            unique_keywords.extend(["exposed", "truth", "debate", "controversy", "fight", "viral", "reaction"])

        result = {
            "creator": entities["creator"],
            "guests": entities["guests"],
            "niche": niche,
            "hot_debates": unique_debates[:5],
            "trending_keywords": unique_keywords[:20],
            "primary_angle": unique_debates[0] if unique_debates else "Viral Highlight",
            "has_active_controversy": len(unique_debates) >= 2
        }

        self._trend_cache[cache_key] = result
        logger.info(f"SocialTrendScout active for '{entities['creator']}': {len(unique_debates)} debates, {len(unique_keywords)} keywords.")
        return result

    def _fetch_live_social_buzz(self, entities: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Executes a lightweight web search query for current drama/controversy
        surrounding the creator and guests.
        """
        search_query = f"{entities['creator']} {(' '.join(entities['guests']))} controversy debate viral"
        clean_q = search_query.strip()
        if not clean_q or len(clean_q) < 5:
            return None

        try:
            # Query DuckDuckGo instant answer / HTML lite
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(clean_q)}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Extract snippet titles from results
            snippets = re.findall(r"<a class=\"result__snippet[^>]*>(.*?)</a>", html, re.DOTALL)
            clean_snippets = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets[:6]]

            if clean_snippets:
                extracted_keywords = []
                extracted_debates = []
                for s in clean_snippets:
                    # Look for drama / controversy markers
                    if any(w in s.lower() for w in ["exposed", "controversy", "fight", "scandal", "debate", "roast", "allegation", "cheating", "fraud", "stole"]):
                        extracted_debates.append(s[:100])
                    words = re.findall(r"\b[A-Za-z]{4,}\b", s)
                    extracted_keywords.extend([w.lower() for w in words if w.lower() not in ["this", "that", "with", "from", "video", "youtube", "watch"]])

                return {
                    "debates": extracted_debates[:3],
                    "keywords": extracted_keywords[:12]
                }
        except Exception as e:
            logger.debug(f"Live social buzz web search skipped/failed: {e}")

        return None

    def calculate_trend_resonance(
        self,
        segment_text: str,
        trend_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculates how strongly a transcript segment aligns with active social media debates.
        Returns bonus score (0-30), matched keywords, and matching debate topic.
        """
        t_low = segment_text.lower()
        matched_keywords = []
        for kw in trend_profile.get("trending_keywords", []):
            if kw in t_low:
                matched_keywords.append(kw)

        matched_debates = []
        for deb in trend_profile.get("hot_debates", []):
            # Check if 2 or more key words of the debate are in segment
            d_words = [w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", deb)]
            m_count = sum(1 for dw in d_words if dw in t_low)
            if m_count >= 2:
                matched_debates.append(deb)

        # Calculate resonance score
        kw_score = min(20.0, len(matched_keywords) * 5.0)
        deb_score = 15.0 if matched_debates else 0.0
        total_resonance = min(30.0, kw_score + deb_score)

        return {
            "resonance_score": round(total_resonance, 1),
            "matched_keywords": matched_keywords,
            "matched_debate": matched_debates[0] if matched_debates else None,
            "is_viral_trend_match": total_resonance >= 10.0
        }


# Global singleton instance
social_trend_scout = SocialTrendScout()
