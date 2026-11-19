"""
Daily Viral Feed Manager & Script Generator.
Focused 100% on Gaming Culture, Top Streamers, Game Launches & Internet Creator Drama:
1. GTA 6 & Major Game Launches (Rockstar Games, leaks, trailers, PC releases, updates)
2. Top Streamers & Live Moments (IShowSpeed, Kai Cenat, xQc, Asmongold, Jynxzi, Tarik, Scout, Mortal)
3. Streamer Drama & Twitch/Kick Bans (Controversies, ban waves, callouts, creator beefs)
4. Esports & BGMI / Valorant Clutches (Tournaments, insane plays, LAN championship drama)
5. Viral Gaming Memes & Rage Quits (Funny glitches, speedruns, viral stream clips)
"""

import os
import re
import json
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.ai_brain import ai_brain

logger = logging.getLogger("ViralShortsEngine.FeedManager")

FEED_QUERIES = {
    "GTA6_GAMES": "https://news.google.com/rss/search?q=%22GTA+6%22+OR+%22Grand+Theft+Auto+VI%22+OR+%22Rockstar+Games%22+OR+%22gameplay+leak%22+when:7d&hl=en-US&gl=US&ceid=US:en",
    "STREAMERS": "https://news.google.com/rss/search?q=(%22IShowSpeed%22+OR+%22Kai+Cenat%22+OR+xQc+OR+Asmongold+OR+Jynxzi+OR+%22live+stream%22+OR+%22Twitch+stream%22)+when:5d&hl=en-US&gl=US&ceid=US:en",
    "DRAMA_BANS": "https://news.google.com/rss/search?q=(streamer+banned+OR+%22Twitch+ban%22+OR+%22Kick+drama%22+OR+%22cheater+banned%22+OR+streamer+controversy)+when:7d&hl=en-US&gl=US&ceid=US:en",
    "ESPORTS": "https://news.google.com/rss/search?q=(BGMI+OR+%22PUBG+Mobile%22+OR+%22Valorant+Champions%22+OR+%22CS2+Major%22+OR+%22Jonathan+Gaming%22+OR+%22Scout+OP%22)+when:7d&hl=en-IN&gl=IN&ceid=IN:en",
    "MEMES": "https://news.google.com/rss/search?q=(%22gaming+meme%22+OR+%22viral+gaming+clip%22+OR+%22speedrun+record%22+OR+%22rage+quit%22)+when:7d&hl=en-US&gl=US&ceid=US:en"
}

CATEGORY_METADATA = {
    "GTA6_GAMES": {"label": "GTA 6 & Game Launches", "badge": "🎮 GTA 6 & RELEASES"},
    "STREAMERS": {"label": "Top Streamers & Live Moments", "badge": "🔴 LIVE STREAM MOMENT"},
    "DRAMA_BANS": {"label": "Streamer Drama & Bans", "badge": "⚡ TWITCH & KICK DRAMA"},
    "ESPORTS": {"label": "Esports & BGMI Clutches", "badge": "🏆 TOURNAMENT CLUTCH"},
    "MEMES": {"label": "Viral Gaming Memes", "badge": "😂 GAMING CULTURE"}
}

CURATED_GAMING_STORIES = [
    {
        "id": "cur_gta_01",
        "title": "GTA 6 Release Window & Leaked Vice City Map Mechanics Confirmed by Industry Insiders",
        "category": "GTA6_GAMES",
        "category_label": "GTA 6 & Game Launches",
        "source": "Rockstar Insider",
        "freshness": "Today",
        "search_url": "ytsearch1:GTA 6 leaked map mechanics analysis"
    },
    {
        "id": "cur_speed_02",
        "title": "IShowSpeed Shuts Down Entire Street Stream After Reaching 1 Million Concurrent Live Viewers",
        "category": "STREAMERS",
        "category_label": "Top Streamers & Live Moments",
        "source": "Stream Highlights",
        "freshness": "2h ago",
        "search_url": "ytsearch1:IShowSpeed stream 1 million viewers record"
    },
    {
        "id": "cur_kai_03",
        "title": "Kai Cenat Pulls Off Wildest Marathon Stream Stunt with Surprise A-List Celebrity Guest",
        "category": "STREAMERS",
        "category_label": "Top Streamers & Live Moments",
        "source": "AMP Live Hub",
        "freshness": "4h ago",
        "search_url": "ytsearch1:Kai Cenat marathon stream crazy moment"
    },
    {
        "id": "cur_drama_04",
        "title": "Top Ranked Creator Caught with Wallhack on Live Stream: Instant Permanent Twitch Ban",
        "category": "DRAMA_BANS",
        "category_label": "Streamer Drama & Bans",
        "source": "Esports News Network",
        "freshness": "Today",
        "search_url": "ytsearch1:streamer caught cheating live twitch ban"
    },
    {
        "id": "cur_esports_05",
        "title": "Jonathan Gaming & Scout Pull Off Unbelievable 1v4 Clutch in BGMI Pro Championship",
        "category": "ESPORTS",
        "category_label": "Esports & BGMI Clutches",
        "source": "BGMI Esports Central",
        "freshness": "Today",
        "search_url": "ytsearch1:Jonathan Gaming 1v4 clutch BGMI finals"
    },
    {
        "id": "cur_gta_06",
        "title": "Rockstar Games Teases Next GTA 6 Trailer Reveal Date with Hidden Code in New Update",
        "category": "GTA6_GAMES",
        "category_label": "GTA 6 & Game Launches",
        "source": "Gaming Intel",
        "freshness": "5h ago",
        "search_url": "ytsearch1:GTA 6 trailer 2 release date breakdown"
    },
    {
        "id": "cur_xqc_07",
        "title": "xQc Nearly Destroys His Multi-Monitor Setup After Massive High-Stakes Wager Loss on Stream",
        "category": "STREAMERS",
        "category_label": "Top Streamers & Live Moments",
        "source": "Twitch Vault",
        "freshness": "6h ago",
        "search_url": "ytsearch1:xQc rage stream reaction"
    },
    {
        "id": "cur_memes_08",
        "title": "Speedrunner Breaks 10-Year Impossible Minecraft World Record by 0.4 Seconds Live",
        "category": "MEMES",
        "category_label": "Viral Gaming Memes",
        "source": "Speedrun Central",
        "freshness": "Today",
        "search_url": "ytsearch1:speedrunner breaks minecraft world record live"
    }
]


class FeedManager:
    """Fetches high-energy gaming & streamer feeds and crafts viral vertical scripts."""

    def __init__(self):
        pass

    def fetch_category_feed(self, category: str = "ALL", limit: int = 8) -> List[Dict[str, Any]]:
        """
        Fetches live stories filtered exclusively to Gaming, Streamers, GTA 6, and Creator Drama.
        """
        cat_key = category.upper()
        targets = [cat_key] if cat_key in FEED_QUERIES else list(FEED_QUERIES.keys())
        stories = []

        for target in targets:
            url = FEED_QUERIES[target]
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    xml_data = resp.read()

                root = ET.fromstring(xml_data)
                channel = root.find("channel")
                if channel is not None:
                    count = 0
                    for item in channel.findall("item"):
                        raw_title = item.findtext("title", "")
                        source = item.findtext("source", "Gaming Media")
                        pub_date = item.findtext("pubDate", "")

                        if not raw_title:
                            continue

                        clean_title = re.sub(r"\s*-\s*[^-]+$", "", raw_title).strip()
                        
                        # Filter out mainstream politics, law, finance that accidentally slips in
                        lower_t = clean_title.lower()
                        bad_keywords = ["supreme court", "parliament", "bjp", "congress", "gdp", "stock market", "budget", "election"]
                        if any(b in lower_t for b in bad_keywords):
                            continue

                        # Freshness calculation
                        freshness = "Today"
                        if pub_date:
                            try:
                                clean_dt_str = re.sub(r"\s+GMT.*$", " +0000", pub_date)
                                dt = datetime.strptime(clean_dt_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                                diff_hours = (datetime.now() - dt).total_seconds() / 3600.0
                                if diff_hours < 24:
                                    freshness = f"{int(max(1, diff_hours))}h ago"
                                else:
                                    freshness = f"{int(diff_hours // 24)}d ago"
                            except Exception:
                                freshness = "Recent"

                        clean_words = re.sub(r"[^\w\s]", "", clean_title).split()[:6]
                        yt_query = f"ytsearch1:{' '.join(clean_words)} gameplay highlight"

                        cat_info = CATEGORY_METADATA.get(target, {"label": target, "badge": "GAMING"})

                        stories.append({
                            "id": f"feed_{abs(hash(clean_title)) % 100000}",
                            "title": clean_title,
                            "category": target,
                            "category_label": cat_info["label"],
                            "source": source,
                            "freshness": freshness,
                            "search_url": yt_query
                        })
                        count += 1
                        if count >= 3 and len(targets) > 1:
                            break
                        if count >= limit and len(targets) == 1:
                            break
            except Exception as e:
                logger.debug(f"Feed query error for {target}: {e}")

        # Mix in curated viral gaming stories if network empty or limited
        if not stories:
            if cat_key in FEED_QUERIES:
                matching_curated = [s for s in CURATED_GAMING_STORIES if s["category"] == cat_key]
                stories.extend(matching_curated if matching_curated else CURATED_GAMING_STORIES)
            else:
                stories.extend(CURATED_GAMING_STORIES)
        elif len(stories) < 4:
            # Supplement with curated stories to keep feed rich
            for s in CURATED_GAMING_STORIES:
                if not any(existing["title"] == s["title"] for existing in stories):
                    stories.append(s)

        return stories[:limit]

    def generate_vertical_script(self, topic: str, category: str = "GTA6_GAMES", tone: str = "Dramatic & High Tension", angle_index: int = 0) -> Dict[str, Any]:
        """
        Generates a 35-40 second viral vertical script specifically tailored
        to Gaming, Streamer Moments, and Game Launches, supporting multiple alternative angles.
        """
        # If AI Brain LLM is active, generate ultra-dynamic script
        if ai_brain.backend in ["gemini", "ollama"]:
            system = (
                f"You are a top viral gaming content creator and scriptwriter for YouTube Shorts and TikTok. "
                f"Topic: {topic}. Category: {category}. Tone: {tone}. Variation Angle: #{angle_index + 1}. "
                "Write an electrifying 35-40 second vertical script with 4 scenes: "
                "Scene 1: 0-4s Insane Hook (Ask a shocking question or drop a crazy fact to hook gaming fans). "
                "Scene 2: 4-18s What Happened (Break down the gameplay, stream moment, leak, or drama with high energy). "
                "Scene 3: 18-30s Community Reaction & Chat Explosion (How streamers, chat, and gamers reacted). "
                "Scene 4: 30-38s Call to Action (Ask for comments and predictions). "
                "Return JSON with keys: hook_banner, script_text, scenes (list of strings), visual_prompts (list of strings)."
            )
            prompt = f"Write viral short script angle #{angle_index + 1} for: {topic}"
            res = ai_brain.call_llm(prompt, system_prompt=system)
            if res:
                try:
                    clean = re.sub(r"^```json\s*|\s*```$", "", res.strip(), flags=re.MULTILINE)
                    data = json.loads(clean)
                    return data
                except Exception:
                    pass

        # High-Voltage Gaming & Streamer Multi-Angle Script Engine
        t_clean = topic.replace('"', '').strip()
        is_gta = "gta" in t_clean.lower() or "rockstar" in t_clean.lower()
        is_stream = any(w in t_clean.lower() for w in ["speed", "kai", "stream", "xqc", "live", "twitch"])
        is_ban = "ban" in t_clean.lower() or "cheat" in t_clean.lower()

        angle = angle_index % 3

        if is_gta:
            gta_angles = [
                (
                    "GTA 6 BIGGEST UPDATE 🚨",
                    [
                        f"Did Rockstar Games just secretly reveal the biggest detail yet about {t_clean[:35]}?!",
                        "Gamers digging into the latest files found mind-blowing details about the Vice City map and realistic gameplay physics that changes everything we knew.",
                        "The entire gaming community is going crazy right now, and insider reports confirm this is releasing way sooner than everyone thought.",
                        "Are you buying GTA 6 on day one, or waiting for PC? Drop your honest predictions in the comments right now!"
                    ]
                ),
                (
                    "MAP SCALE EXPOSED 🗺️",
                    [
                        f"Hold up, the actual leaked scale of Vice City in {t_clean[:35]} was just uncovered and it completely dwarfs GTA 5!",
                        "Every single building has enterable interiors, interactive AI pedestrians, and dynamic hurricane weather systems that look like real-life footage.",
                        "The hype across Twitter and YouTube is at an all-time peak with millions watching every leaked second.",
                        "Is this going to be the greatest open-world game in human history? Type YES or NO down below!"
                    ]
                ),
                (
                    "ROCKSTAR DROPS BOMBSHELL 💥",
                    [
                        f"Nobody saw this coming, but Rockstar just broke their silence on {t_clean[:35]}!",
                        "New insider reports reveal groundbreaking graphical upgrades running at a smooth 60 frames per second on next-gen hardware.",
                        "Content creators and streamers everywhere are reacting to the news, and the pre-order hype is already breaking records.",
                        "What vehicle or weapon are you trying first in Vice City? Let me know in the comments!"
                    ]
                )
            ]
            hook_banner, lines = gta_angles[angle]

        elif is_stream:
            stream_angles = [
                (
                    "STREAM EXPLODED LIVE 🔴",
                    [
                        f"The moment this live stream started, nobody had any idea this was about to happen.",
                        f"Look at what happened with {t_clean[:35]} — the chat was moving so fast that servers literally started buffering for over 500,000 live viewers.",
                        "From the streamer's raw reaction to the insane chaos that followed, this is easily going down as the wildest live stream clip of the year.",
                        "Did you catch this live on stream? Type your reaction in the comments and subscribe for more viral stream moments!"
                    ]
                ),
                (
                    "UNREAL LIVE MOMENT ⚡",
                    [
                        f"They actually pulled this off live in front of hundreds of thousands of viewers and broke internet records!",
                        f"When {t_clean[:35]} went down, nobody believed what they were seeing on camera until the clip started trending everywhere.",
                        "Even rival streamers and creators couldn't believe it, spamming chat with disbelief as the clip hit 10 million views.",
                        "Was this totally scripted or 100% genuine? Drop your honest verdict in the comments!"
                    ]
                ),
                (
                    "STREAMER WENT CRAZY 🤯",
                    [
                        f"You will not believe the chaos that just unfolded during this live stream!",
                        f"The streamer completely lost it after {t_clean[:35]}, resulting in one of the most hilarious and shocking moments ever captured on camera.",
                        "Clip channels across TikTok and YouTube Shorts are re-uploading this nonstop as the community loses its mind.",
                        "Who is your favorite streamer to watch live right now? Drop their name in the comments!"
                    ]
                )
            ]
            hook_banner, lines = stream_angles[angle]

        elif is_ban:
            ban_angles = [
                (
                    "BANNED ON STREAM ⛔",
                    [
                        f"They thought they could get away with it live on camera, but they just got caught in 4K.",
                        f"During the match, footage clearly showed suspicious gameplay in {t_clean[:35]} that triggered an instant permanent ban right in front of thousands of viewers.",
                        "The clip immediately went viral across Twitter and Reddit, sparking huge controversy across the entire competitive scene.",
                        "Do you think this ban was 100% deserved or was it a glitch? Let me know what you think below!"
                    ]
                ),
                (
                    "TWITCH BAN DRAMA 🔥",
                    [
                        f"The biggest controversy on Twitch just hit a breaking point after what happened with {t_clean[:35]}!",
                        "After the clip leaked online, moderators stepped in within minutes and completely suspended the account with zero warning.",
                        "The streamer just posted an emergency response video claiming they are completely innocent and appealing the decision.",
                        "Do you stand with the streamer or the ban? Let me know your honest thoughts right now!"
                    ]
                ),
                (
                    "CAUGHT IN 4K LIVE 📸",
                    [
                        f"Look closely at this screen — they never expected their stream setup to reveal this live to the public!",
                        f"The moment {t_clean[:35]} happened, chat started clipping and archiving the evidence before the VOD could even be deleted.",
                        "Now every major creator is reacting to the fallout, calling it the most embarrassing slip-up in streaming history.",
                        "Could you ever recover from a slip-up like this? Tell me what you would do in the comments!"
                    ]
                )
            ]
            hook_banner, lines = ban_angles[angle]

        else:
            general_angles = [
                (
                    "GAMING ALERT 🎮",
                    [
                        f"Wait, you need to see what just happened with {t_clean[:35]}!",
                        "In a stunning turn of events, new gameplay footage and community reactions are completely flipping the entire narrative.",
                        "Look closely at these numbers and the community feedback — everyone is agreeing that this changes the whole game.",
                        "What is your honest take on this? Are you hyped or disappointed? Drop your thoughts down below!"
                    ]
                ),
                (
                    "GAME CHANGING UPDATE 🚀",
                    [
                        f"This single announcement about {t_clean[:35]} just broke the entire gaming community!",
                        "Players who tested the early build are calling it a complete masterpiece that redefines next-generation gaming standards.",
                        "The hype train is moving full speed ahead with millions of pre-orders and wishlists piling up overnight.",
                        "Will you be playing this on launch day? Let me know what platform you play on!"
                    ]
                ),
                (
                    "THE UNTOLD TRUTH ⚠️",
                    [
                        f"Behind the scenes of {t_clean[:35]}, something massive was happening in complete secrecy.",
                        "Now that the official details have finally dropped, gamers are realizing how much effort went into this revolutionary project.",
                        "From unbelievable mechanics to jaw-dropping visual fidelity, this is setting the bar impossibly high for competitors.",
                        "Drop a like if you are hyped, and tell me your thoughts in the comments!"
                    ]
                )
            ]
            hook_banner, lines = general_angles[angle]

        return {
            "hook_banner": hook_banner,
            "script_text": "\n\n".join(lines),
            "scenes": lines,
            "angle_index": angle,
            "visual_prompts": [
                f"High-impact gaming splash visual of {t_clean[:30]}",
                "Dynamic gameplay highlight with neon cyber accents",
                "Split screen streamer reaction and exploding live chat",
                "Call to action graphic with pulsing engagement buttons"
            ]
        }

    def regenerate_script(self, topic: str, category: str = "GTA6_GAMES", tone: str = "Dramatic & High Tension", angle_index: int = 1) -> Dict[str, Any]:
        """Regenerates an alternative viral script angle."""
        return self.generate_vertical_script(topic=topic, category=category, tone=tone, angle_index=angle_index)


# Singleton instance
feed_manager = FeedManager()
