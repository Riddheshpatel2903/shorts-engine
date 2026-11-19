"""
Clip Selector module with Genre-Specific Viral Optimization & Multi-Modal Diagnostics.
Ranks and selects candidate clips (20-60s) targeting:
- 💬 Superchat Rebuttal & Streamer Controversy
- 🎯 Multi-Kill & 1v4 Clutch Moments
- 🚗 GTA 6 / New Game Hype & Reactions
- 🏛️ Geopolitical Showdowns & New Laws
- 😂 Comedy & Laughter Moments
- 💡 Best Advice & Educational Takeaways
- 🔥 Motivational & Mindset Insights
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ViralShortsEngine.ClipSelector")


class ClipSelector:
    def __init__(
        self,
        min_duration: float = 20.0,
        max_duration: float = 60.0,
        target_duration: float = 40.0,
        genre_focus: str = "all"
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_duration = target_duration
        self.genre_focus = genre_focus.lower()

    def _ends_sentence(self, text: str) -> bool:
        trimmed = text.strip()
        return bool(trimmed and trimmed[-1] in ".!?\"'")

    def _evaluate_candidate_window(self, segments_subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates category scores, emotional reactions (rage, happy, shock),
        acoustic volume dynamics, speech velocity (WPM), opening hook strength,
        and overall multi-modal viral score.
        """
        if not segments_subset:
            return {
                "viral_score": 0.0,
                "comedy_score": 0.0,
                "rage_score": 0.0,
                "happy_score": 0.0,
                "shock_score": 0.0,
                "advice_score": 0.0,
                "motivation_score": 0.0,
                "audio_score": 50.0,
                "wpm": 130.0,
                "category": "VIRAL_GENERAL",
                "category_label": "⚡ Viral Highlight",
                "why_viral": "General highlight",
                "radar": {"Acoustic Energy": 50, "Speech Cadence": 50, "Hook Potency": 50, "Emotional Spike": 50}
            }

        # Average category & reaction scores across the window
        c_scores = [s.get("comedy_score", 0.0) for s in segments_subset]
        r_scores = [s.get("rage_score", 0.0) for s in segments_subset]
        h_scores = [s.get("happy_score", 0.0) for s in segments_subset]
        s_scores = [s.get("shock_score", 0.0) for s in segments_subset]
        a_scores = [s.get("advice_score", 0.0) for s in segments_subset]
        m_scores = [s.get("motivation_score", 0.0) for s in segments_subset]
        geo_scores = [s.get("geopolitics_score", 0.0) for s in segments_subset]
        gen_scores = [s.get("segment_score", 50.0) for s in segments_subset]
        aud_scores = [s.get("audio_score", 50.0) for s in segments_subset]
        cad_scores = [s.get("cadence_score", 60.0) for s in segments_subset]
        wpm_scores = [s.get("wpm", 130.0) for s in segments_subset]

        avg_comedy = sum(c_scores) / len(c_scores)
        avg_rage = sum(r_scores) / len(r_scores)
        avg_happy = sum(h_scores) / len(h_scores)
        avg_shock = sum(s_scores) / len(s_scores)
        avg_advice = sum(a_scores) / len(a_scores)
        avg_motivation = sum(m_scores) / len(m_scores)
        avg_geo = sum(geo_scores) / len(geo_scores) if geo_scores else 0.0
        avg_general = sum(gen_scores) / len(gen_scores)
        avg_audio = sum(aud_scores) / len(aud_scores)
        avg_cadence = sum(cad_scores) / len(cad_scores)
        avg_wpm = sum(wpm_scores) / len(wpm_scores)

        # Opening Hook (First segment or words)
        hook_seg = segments_subset[0]
        hook_comedy = hook_seg.get("comedy_score", 0.0)
        hook_rage = hook_seg.get("rage_score", 0.0)
        hook_happy = hook_seg.get("happy_score", 0.0)
        hook_shock = hook_seg.get("shock_score", 0.0)
        hook_advice = hook_seg.get("advice_score", 0.0)
        hook_motivation = hook_seg.get("motivation_score", 0.0)
        hook_geo = hook_seg.get("geopolitics_score", 0.0)
        hook_power = hook_seg.get("hook_score", 40.0)

        # Weighted Category & Reaction Virality
        window_comedy = (avg_comedy * 0.55) + (hook_comedy * 0.45)
        window_rage = (avg_rage * 0.55) + (hook_rage * 0.45)
        window_happy = (avg_happy * 0.55) + (hook_happy * 0.45)
        window_shock = (avg_shock * 0.55) + (hook_shock * 0.45)
        window_advice = (avg_advice * 0.55) + (hook_advice * 0.45)
        window_motivation = (avg_motivation * 0.55) + (hook_motivation * 0.45)
        window_geo = (avg_geo * 0.55) + (hook_geo * 0.45)

        # Inspect if window contains specific viral moments from segments
        seg_categories = [s.get("category", "") for s in segments_subset]
        has_superchat = "SUPERCHAT_CLAPBACK" in seg_categories
        has_drama = "DRAMA_REACTION" in seg_categories
        has_clutch = "GAMEPLAY_CLUTCH" in seg_categories
        has_gta6 = "GTA6_NEW_GAME" in seg_categories
        has_policy = "GEOPOLITICS_POLICY" in seg_categories

        # Determine dominant category
        category_map = {
            "SUPERCHAT_CLAPBACK": 88.0 if has_superchat else 0.0,
            "DRAMA_REACTION": 86.0 if has_drama else 0.0,
            "GAMEPLAY_CLUTCH": 84.0 if has_clutch else 0.0,
            "GTA6_NEW_GAME": 85.0 if has_gta6 else 0.0,
            "GEOPOLITICS_POLICY": 84.0 if has_policy else 0.0,
            "GEOPOLITICS_CLASH": window_geo,
            "STREAMER_RAGE": window_rage,
            "STREAMER_HAPPY": window_happy,
            "STREAMER_SHOCK": window_shock,
            "COMEDY_HUMOR": window_comedy,
            "ADVICE_EDUCATIONAL": window_advice,
            "MOTIVATIONAL_MINDSET": window_motivation
        }
        dominant_cat = max(category_map, key=category_map.get)
        dominant_score = category_map[dominant_cat]

        if dominant_score < 25.0:
            dominant_cat = "VIRAL_GENERAL"
            cat_label = "⚡ Viral Highlight"
            why_viral = f"High-momentum viral highlight with strong acoustic delivery ({avg_audio:.0f}% energy, {avg_wpm:.0f} WPM)."
        elif dominant_cat == "SUPERCHAT_CLAPBACK":
            cat_label = "💬 Superchat Rebuttal / Clapback"
            why_viral = f"Streamer directly addresses donor allegation on Superchat ({avg_wpm:.0f} WPM, {avg_audio:.0f}% acoustic energy)."
        elif dominant_cat == "DRAMA_REACTION":
            cat_label = "🍿 Drama Reaction / Roast"
            why_viral = f"High-engagement drama breakdown reacting to other creator controversy."
        elif dominant_cat == "GAMEPLAY_CLUTCH":
            cat_label = "🎯 Multi-Kill & Clutch Action"
            why_viral = f"Intense squad-wipe sequence with acoustic shout spike ({avg_audio:.0f}%) and high-cadence callouts."
        elif dominant_cat == "GTA6_NEW_GAME":
            cat_label = "🚗 GTA 6 / New Game Hype"
            why_viral = f"Next-gen physics & gameplay shock reaction ({avg_shock:.0f}% disbelief, {avg_audio:.0f}% audio surge)."
        elif dominant_cat == "GEOPOLITICS_POLICY":
            cat_label = "🏛️ New Law & Policy Reform"
            why_viral = f"Breaking national legal reform / policy announcement with high retention potential."
        elif dominant_cat == "GEOPOLITICS_CLASH":
            cat_label = "⚠️ Geopolitical Showdown"
            why_viral = f"Sharp diplomatic clash and fact-based rebuttal with deliberate pacing ({avg_wpm:.0f} WPM)."
        elif dominant_cat == "STREAMER_RAGE":
            cat_label = "🤬 Streamer Rage & Outburst"
            why_viral = f"Unfiltered rage outburst (Acoustic peak: {avg_audio:.0f}%, Rage intensity: {window_rage:.0f}%)."
        elif dominant_cat == "STREAMER_HAPPY":
            cat_label = "😄 Happy Celebration Win"
            why_viral = f"Tournament win celebration and clutch victory cheer ({avg_audio:.0f}% loudness surge)."
        elif dominant_cat == "STREAMER_SHOCK":
            cat_label = "😱 Shocked & Disbelief (Hype)"
            why_viral = f"Disbelief reaction with sudden loudness surge ({avg_audio:.0f}% acoustic spike)."
        elif dominant_cat == "COMEDY_HUMOR":
            cat_label = "😂 Laughing & Comedy Moment"
            why_viral = f"Rhythmic laughter oscillations and comedic roast timing ({window_comedy:.0f}% humor index)."
        elif dominant_cat == "ADVICE_EDUCATIONAL":
            cat_label = "💡 Best Advice & Educational"
            why_viral = f"High-value educational takeaway with clear, authoritative delivery ({avg_wpm:.0f} WPM)."
        elif dominant_cat == "MOTIVATIONAL_MINDSET":
            cat_label = "🔥 Motivational & Mindset"
            why_viral = f"Powerful mindset shift with high emotional resonance."

        # Calculate final multi-modal viral score
        boundary_bonus = 5.0 if self._ends_sentence(segments_subset[-1]["text"]) else 0.0

        if self.genre_focus in ["superchat", "drama", "controversy"]:
            score = (max(category_map["SUPERCHAT_CLAPBACK"], category_map["DRAMA_REACTION"], window_rage) * 0.70) + (avg_audio * 0.15) + (avg_general * 0.15) + boundary_bonus
        elif self.genre_focus in ["gaming", "gameplay", "clutch", "gta6"]:
            score = (max(category_map["GAMEPLAY_CLUTCH"], category_map["GTA6_NEW_GAME"], window_happy, window_shock, window_rage) * 0.70) + (avg_audio * 0.15) + (avg_general * 0.15) + boundary_bonus
        elif self.genre_focus in ["geopolitics", "policy", "news"]:
            score = (max(window_geo, category_map["GEOPOLITICS_POLICY"]) * 0.70) + (avg_cadence * 0.15) + (avg_general * 0.15) + boundary_bonus
        elif self.genre_focus in ["rage", "angry", "anger"]:
            score = (window_rage * 0.70) + (avg_audio * 0.20) + (avg_general * 0.10) + boundary_bonus
        elif self.genre_focus in ["happy", "celebration", "win"]:
            score = (window_happy * 0.70) + (avg_audio * 0.20) + (avg_general * 0.10) + boundary_bonus
        elif self.genre_focus in ["shock", "shocked", "hype", "disbelief"]:
            score = (window_shock * 0.70) + (avg_audio * 0.20) + (avg_general * 0.10) + boundary_bonus
        elif self.genre_focus in ["comedy", "humor", "laugh", "laughing"]:
            score = (window_comedy * 0.65) + (avg_audio * 0.15) + (avg_general * 0.20) + boundary_bonus
        elif self.genre_focus in ["advice", "education", "educational"]:
            score = (window_advice * 0.65) + (avg_cadence * 0.15) + (avg_general * 0.20) + boundary_bonus
        elif self.genre_focus in ["motivation", "motivational", "mindset"]:
            score = (window_motivation * 0.65) + (avg_cadence * 0.15) + (avg_general * 0.20) + boundary_bonus
        else:
            # "all" / "auto": Boost highest genre category strength with multi-modal energy!
            genre_power = max(category_map.values())
            score = (avg_general * 0.25) + (genre_power * 0.55) + (avg_audio * 0.20) + boundary_bonus

        radar = {
            "Acoustic Peak": min(100, int(avg_audio)),
            "Speech Velocity": min(100, int(min(100, avg_wpm * 0.6))),
            "Hook Potency": min(100, int(max(40, hook_power))),
            "Viral Resonance": min(100, int(max(dominant_score, 60)))
        }

        return {
            "viral_score": min(round(score, 1), 100.0),
            "comedy_score": round(window_comedy, 1),
            "rage_score": round(window_rage, 1),
            "happy_score": round(window_happy, 1),
            "shock_score": round(window_shock, 1),
            "advice_score": round(window_advice, 1),
            "motivation_score": round(window_motivation, 1),
            "audio_score": round(avg_audio, 1),
            "cadence_score": round(avg_cadence, 1),
            "wpm": round(avg_wpm, 1),
            "category": dominant_cat,
            "category_label": cat_label,
            "why_viral": why_viral,
            "radar": radar
        }

    def select_clips(
        self,
        analyzed_segments: List[Dict[str, Any]],
        num_shorts: int = 3,
        overlap_threshold: float = 0.35,
        genre_focus: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates candidate clips across the video and ranks top non-overlapping clips
        matching the desired viral genre (Comedy, Advice, Motivation, or Auto).
        """
        if genre_focus:
            self.genre_focus = genre_focus.lower()

        if not analyzed_segments:
            logger.warning("No analyzed segments provided to ClipSelector.")
            return []

        candidates = []
        n_segs = len(analyzed_segments)

        for i in range(n_segs):
            start_time = analyzed_segments[i]["start"]
            current_segments = []
            
            for j in range(i, n_segs):
                current_segments.append(analyzed_segments[j])
                end_time = analyzed_segments[j]["end"]
                dur = end_time - start_time

                if dur > self.max_duration:
                    break

                if dur >= self.min_duration:
                    is_clean_end = self._ends_sentence(analyzed_segments[j]["text"])
                    
                    if is_clean_end or dur >= self.target_duration:
                        eval_data = self._evaluate_candidate_window(current_segments)
                        full_text = " ".join(s["text"] for s in current_segments)
                        
                        candidates.append({
                            "start": round(start_time, 2),
                            "end": round(end_time, 2),
                            "duration": round(dur, 2),
                            "viral_score": eval_data["viral_score"],
                            "comedy_score": eval_data["comedy_score"],
                            "rage_score": eval_data.get("rage_score", 0.0),
                            "happy_score": eval_data.get("happy_score", 0.0),
                            "shock_score": eval_data.get("shock_score", 0.0),
                            "advice_score": eval_data["advice_score"],
                            "motivation_score": eval_data["motivation_score"],
                            "audio_score": eval_data.get("audio_score", 50.0),
                            "wpm": eval_data.get("wpm", 130.0),
                            "category": eval_data["category"],
                            "category_label": eval_data["category_label"],
                            "why_viral": eval_data["why_viral"],
                            "radar": eval_data["radar"],
                            "text": full_text,
                            "hook_text": current_segments[0]["text"][:90],
                            "segments": current_segments,
                            "clean_boundary": is_clean_end
                        })

        if not candidates:
            # Fallback if audio/segments were shorter than min_duration
            total_dur = analyzed_segments[-1]["end"] - analyzed_segments[0]["start"]
            full_text = " ".join(s["text"] for s in analyzed_segments)
            eval_data = self._evaluate_candidate_window(analyzed_segments)
            return [{
                "start": round(analyzed_segments[0]["start"], 2),
                "end": round(analyzed_segments[-1]["end"], 2),
                "duration": round(total_dur, 2),
                "viral_score": eval_data["viral_score"] or 75.0,
                "comedy_score": eval_data["comedy_score"],
                "advice_score": eval_data["advice_score"],
                "motivation_score": eval_data["motivation_score"],
                "audio_score": eval_data.get("audio_score", 50.0),
                "wpm": eval_data.get("wpm", 130.0),
                "category": eval_data["category"],
                "category_label": eval_data["category_label"],
                "why_viral": eval_data["why_viral"],
                "radar": eval_data["radar"],
                "text": full_text,
                "hook_text": analyzed_segments[0]["text"][:90],
                "segments": analyzed_segments,
                "clean_boundary": True
            }]

        # Sort candidates by viral score descending
        candidates.sort(key=lambda c: c["viral_score"], reverse=True)

        # Deduplicate using Non-Maximum Suppression (NMS)
        selected_clips = []
        for cand in candidates:
            overlap = False
            for sel in selected_clips:
                overlap_start = max(cand["start"], sel["start"])
                overlap_end = min(cand["end"], sel["end"])
                if overlap_end > overlap_start:
                    overlap_dur = overlap_end - overlap_start
                    shorter_dur = min(cand["duration"], sel["duration"])
                    if (overlap_dur / shorter_dur) > overlap_threshold:
                        overlap = True
                        break
            
            if not overlap:
                selected_clips.append(cand)
                if len(selected_clips) >= num_shorts:
                    break

        logger.info(f"Selected {len(selected_clips)} viral clips for genre '{self.genre_focus}' (requested {num_shorts}).")
        return selected_clips
