"""
Sound Effects (SFX) and Meme Audio Engine.
Synthesizes, manages, and seamlessly mixes viral sound effects into video clips:
- Vine Boom (dramatic punchline / plot twist / shock)
- Whoosh (intro hook / scene transition)
- Ding / Bell (highlight / fact reveal / superchat)
- Record Scratch (funny stop / awkward pause / confusion)
- Bruh (fail / disbelief / facepalm)
- Pop (bubble text reveal)
- Punch / Action Hit (clutch kill / headshot)
- Tension Riser (build up to climax)
"""

import os
import wave
import struct
import math
import random
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config import BASE_DIR, PROCESSING_DIR

logger = logging.getLogger("ViralShortsEngine.SFX")

SFX_DIR = Path(BASE_DIR) / "assets" / "sfx"


class SFXEngine:
    def __init__(self):
        self.sfx_dir = SFX_DIR
        self.sfx_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = 44100
        self._ensure_all_sfx_exist()

    def _ensure_all_sfx_exist(self):
        """Generates all standard SFX audio files if not already present."""
        generators = {
            "whoosh.wav": self._generate_whoosh,
            "vine_boom.wav": self._generate_vine_boom,
            "ding.wav": self._generate_ding,
            "record_scratch.wav": self._generate_record_scratch,
            "bruh.wav": self._generate_bruh,
            "pop.wav": self._generate_pop,
            "punch.wav": self._generate_punch,
            "riser.wav": self._generate_riser,
            "laugh.wav": self._generate_laugh
        }
        for fname, gen_func in generators.items():
            fpath = self.sfx_dir / fname
            if not fpath.exists() or fpath.stat().st_size < 100:
                try:
                    gen_func(fpath)
                    logger.info(f"Synthesized broadcast SFX asset: {fname}")
                except Exception as e:
                    logger.warning(f"Failed to generate {fname}: {e}")

    def _write_wav(self, file_path: Path, samples: List[float]):
        """Writes floating point audio samples (-1.0 to 1.0) to 16-bit PCM mono WAV."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(file_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            packed = bytearray()
            for s in samples:
                val = max(-1.0, min(1.0, s))
                int_s = int(val * 32767.0)
                packed.extend(struct.pack("<h", int_s))
            wf.writeframes(packed)

    def _generate_vine_boom(self, file_path: Path):
        """
        Synthesizes the iconic Vine Boom meme sound effect:
        Heavy sub-bass impact (65Hz down to 32Hz) with transient punch,
        soft saturation distortion, and resonant room tail decay.
        """
        duration = 1.6
        total_samples = int(self.sample_rate * duration)
        samples = []

        phase = 0.0
        for i in range(total_samples):
            t = i / self.sample_rate
            # Pitch drop from 68Hz down to 34Hz
            freq = 68.0 * math.exp(-2.5 * t) + 32.0
            phase += 2.0 * math.pi * freq / self.sample_rate

            # Sub-bass fundamental + 2nd harmonic
            sub = math.sin(phase) + 0.35 * math.sin(phase * 2.0)

            # Punch transient at the very attack (first 30ms)
            if t < 0.035:
                transient = math.sin(2.0 * math.pi * 180.0 * (t / 0.035)) * (1.0 - (t / 0.035))
            else:
                transient = 0.0

            # Envelope decay
            env = math.exp(-2.2 * t)
            raw = (sub * 0.85 + transient * 0.75) * env

            # Soft saturation curve (tanh-like distortion for thickness)
            saturated = raw / (1.0 + 0.4 * abs(raw))
            samples.append(saturated)

        self._write_wav(file_path, samples)

    def _generate_whoosh(self, file_path: Path):
        """
        Synthesizes a clean cinematic air whoosh:
        Bandpass-filtered white noise with frequency sweep and exponential volume swell.
        """
        duration = 0.65
        total_samples = int(self.sample_rate * duration)
        samples = []

        # Filter state
        y1, y2 = 0.0, 0.0
        random.seed(42)

        for i in range(total_samples):
            t = i / self.sample_rate
            progress = t / duration

            # Bell curve amplitude envelope
            amp = math.sin(math.pi * progress) ** 2.2

            # White noise input
            noise = (random.random() * 2.0 - 1.0)

            # Center frequency sweeps up then down (300Hz -> 1800Hz -> 400Hz)
            center_f = 300.0 + 1500.0 * math.sin(math.pi * progress)
            w0 = 2.0 * math.pi * center_f / self.sample_rate
            q = 3.5
            alpha = math.sin(w0) / (2.0 * q)
            b0 = alpha
            b1 = 0.0
            b2 = -alpha
            a0 = 1.0 + alpha
            a1 = -2.0 * math.cos(w0)
            a2 = 1.0 - alpha

            filtered = (b0 / a0) * noise + (b2 / a0) * y2 - (a1 / a0) * y1 - (a2 / a0) * y2
            y2 = y1
            y1 = filtered

            samples.append(filtered * amp * 1.8)

        self._write_wav(file_path, samples)

    def _generate_ding(self, file_path: Path):
        """Synthesizes a sparkling bell ding / chime for key revelations and superchats."""
        duration = 1.1
        total_samples = int(self.sample_rate * duration)
        samples = []
        f0 = 987.77  # B5 note
        harmonics = [(f0, 0.7, 3.2), (f0 * 2.0, 0.35, 4.5), (f0 * 3.01, 0.15, 6.0), (f0 * 4.16, 0.08, 8.0)]

        for i in range(total_samples):
            t = i / self.sample_rate
            val = 0.0
            for freq, weight, decay in harmonics:
                val += weight * math.sin(2.0 * math.pi * freq * t) * math.exp(-decay * t)
            samples.append(val * 0.9)

        self._write_wav(file_path, samples)

    def _generate_record_scratch(self, file_path: Path):
        """Synthesizes a classic DJ record scratch / vinyl stop for comedic timing."""
        duration = 0.50
        total_samples = int(self.sample_rate * duration)
        samples = []
        phase = 0.0

        for i in range(total_samples):
            t = i / self.sample_rate
            p = t / duration
            # Modulation frequency back and forth
            mod_freq = 600.0 + 1200.0 * math.sin(p * math.pi * 5.0) * math.exp(-1.5 * p)
            phase += 2.0 * math.pi * mod_freq / self.sample_rate

            noise = (random.random() * 2.0 - 1.0) * 0.25
            sig = (math.sin(phase) + noise) * (1.0 - p) ** 1.5
            samples.append(sig * 0.75)

        self._write_wav(file_path, samples)

    def _generate_bruh(self, file_path: Path):
        """Synthesizes a low-pitch dual-formant vocal sound mimicking the 'bruh' meme inflection."""
        duration = 0.75
        total_samples = int(self.sample_rate * duration)
        samples = []
        phase1, phase2 = 0.0, 0.0

        for i in range(total_samples):
            t = i / self.sample_rate
            p = t / duration
            # Pitch drops from 145Hz down to 98Hz
            f0 = 145.0 - 50.0 * p
            phase1 += 2.0 * math.pi * f0 / self.sample_rate
            # Vocal resonance at Formant 1 (550Hz) and Formant 2 (1150Hz)
            res1 = math.sin(2.0 * math.pi * 550.0 * t) * 0.4
            res2 = math.sin(2.0 * math.pi * 1150.0 * t) * 0.25

            sig = (math.sin(phase1) + res1 + res2) * math.sin(math.pi * p) ** 1.2
            samples.append(sig * 0.7)

        self._write_wav(file_path, samples)

    def _generate_pop(self, file_path: Path):
        """Synthesizes a bubbly popping sound for caption pop-ins and emojis."""
        duration = 0.12
        total_samples = int(self.sample_rate * duration)
        samples = []
        phase = 0.0

        for i in range(total_samples):
            t = i / self.sample_rate
            p = t / duration
            # Rapid pitch drop 1400Hz -> 320Hz
            f = 1400.0 * math.exp(-12.0 * p) + 320.0
            phase += 2.0 * math.pi * f / self.sample_rate
            env = math.exp(-18.0 * p)
            samples.append(math.sin(phase) * env * 0.9)

        self._write_wav(file_path, samples)

    def _generate_punch(self, file_path: Path):
        """Synthesizes a punchy action impact for kills, clutches, and headshots."""
        duration = 0.55
        total_samples = int(self.sample_rate * duration)
        samples = []
        phase = 0.0

        for i in range(total_samples):
            t = i / self.sample_rate
            p = t / duration
            f = 120.0 * math.exp(-8.0 * p) + 45.0
            phase += 2.0 * math.pi * f / self.sample_rate
            click = (1.0 - t / 0.02) if t < 0.02 else 0.0
            raw = (math.sin(phase) * 0.8 + click * 0.5) * math.exp(-4.5 * p)
            samples.append(raw)

        self._write_wav(file_path, samples)

    def _generate_riser(self, file_path: Path):
        """Synthesizes a tension build-up riser sweeping upwards."""
        duration = 2.0
        total_samples = int(self.sample_rate * duration)
        samples = []
        phase = 0.0

        for i in range(total_samples):
            t = i / self.sample_rate
            p = t / duration
            freq = 90.0 * math.exp(2.8 * p)
            phase += 2.0 * math.pi * freq / self.sample_rate
            env = p ** 1.8
            sig = math.sin(phase) * env * 0.7
            samples.append(sig)

        self._write_wav(file_path, samples)

    def _generate_laugh(self, file_path: Path):
        """Synthesizes comedic chuckle / laughing burst."""
        duration = 1.4
        total_samples = int(self.sample_rate * duration)
        samples = []

        for i in range(total_samples):
            t = i / self.sample_rate
            p = t / duration
            # 5.5 Hz laughing pulse modulation
            pulse = math.sin(2.0 * math.pi * 5.5 * t) ** 4
            vowel = math.sin(2.0 * math.pi * 380.0 * t) + 0.4 * math.sin(2.0 * math.pi * 750.0 * t)
            env = (1.0 - p) ** 1.2
            samples.append(pulse * vowel * env * 0.6)

        self._write_wav(file_path, samples)

    def detect_sfx_cues(
        self,
        transcript: Dict[str, Any],
        clip_start: float,
        clip_end: float,
        is_comedy: bool = False,
        is_action: bool = False,
        style: str = "balanced"
    ) -> List[Dict[str, Any]]:
        """
        Analyzes the transcript and boundary timing of the clip to intelligently place
        relevant meme sounds and sound effects:
        - t = 0.2s: 'whoosh' (hook banner entrance)
        - Climax / punchlines: 'vine_boom' or 'record_scratch'
        - Laughing / fail moments: 'bruh' or 'laugh'
        - Action clutches: 'punch'
        - Superchats / key highlights: 'ding'
        """
        events = []
        clip_dur = clip_end - clip_start
        if clip_dur < 5.0:
            return events

        # Always add whoosh near intro hook
        events.append({
            "rel_time": 0.20,
            "sfx": "whoosh.wav",
            "volume": 0.60,
            "name": "Intro Hook Whoosh"
        })

        if not transcript or not isinstance(transcript, dict):
            # Fallback if no transcript: add dramatic boom near 65% duration
            if is_action or is_comedy:
                events.append({
                    "rel_time": round(clip_dur * 0.65, 2),
                    "sfx": "vine_boom.wav",
                    "volume": 0.75,
                    "name": "Climax Boom"
                })
            return events

        # Scan transcript words within this window
        words_in_window = []
        for seg in transcript.get("segments", []):
            if seg.get("end", 0) < clip_start or seg.get("start", 0) > clip_end:
                continue
            for w in seg.get("words", []):
                w_start = float(w.get("start", 0.0))
                if clip_start <= w_start <= clip_end:
                    words_in_window.append({
                        "word": str(w.get("word", "")).strip().lower(),
                        "start": w_start,
                        "rel_time": round(w_start - clip_start, 2)
                    })

        last_sfx_time = 0.5
        # Look for punchlines / shock / memes
        for w_item in words_in_window:
            rel_t = w_item["rel_time"]
            word = w_item["word"]

            # Prevent placing sounds too close together (min 3.5s spacing)
            if (rel_t - last_sfx_time) < 3.2:
                continue

            # Shock / Plot Twist / Vine Boom cues
            if any(cue in word for cue in ["what", "no way", "impossible", "dead", "omg", "shocked", "bhai ye", "kya"]):
                events.append({
                    "rel_time": rel_t,
                    "sfx": "vine_boom.wav",
                    "volume": 0.75,
                    "name": f"Vine Boom ({word})"
                })
                last_sfx_time = rel_t

            # Confusion / Sudden stop / Record scratch
            elif any(cue in word for cue in ["wait", "pause", "hold on", "stop"]):
                events.append({
                    "rel_time": rel_t,
                    "sfx": "record_scratch.wav",
                    "volume": 0.65,
                    "name": f"Record Scratch ({word})"
                })
                last_sfx_time = rel_t

            # Funny fail / Facepalm / Bruh cues
            elif any(cue in word for cue in ["bruh", "fail", "stupid", "dumb", "lose", "lost"]):
                events.append({
                    "rel_time": rel_t,
                    "sfx": "bruh.wav",
                    "volume": 0.70,
                    "name": f"Bruh ({word})"
                })
                last_sfx_time = rel_t

            # Action / Clutch / Kill hit
            elif any(cue in word for cue in ["knock", "kill", "headshot", "clutch", "spray", "wiped", "down"]):
                events.append({
                    "rel_time": rel_t,
                    "sfx": "punch.wav",
                    "volume": 0.70,
                    "name": f"Action Hit ({word})"
                })
                last_sfx_time = rel_t

        # If clip is tagged comedy and no punchline SFX placed near the end, place a vine boom or chuckle at 80% mark
        if is_comedy and (last_sfx_time < clip_dur * 0.5):
            t_punch = round(clip_dur * 0.75, 2)
            events.append({
                "rel_time": t_punch,
                "sfx": "vine_boom.wav",
                "volume": 0.75,
                "name": "Comedy Climax Boom"
            })

        return events

    def create_sfx_mix_track(
        self,
        sfx_events: List[Dict[str, Any]],
        duration: float,
        output_path: Path
    ) -> Optional[Path]:
        """
        Creates a single, sample-accurate, mixed 44.1kHz audio track containing all
        scheduled SFX and meme sounds positioned at their exact timestamps.
        Zero drift, zero FFmpeg filter graph crashes!
        """
        if not sfx_events or duration <= 0:
            return None

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_samples = int(self.sample_rate * (duration + 1.0))
        master_buffer = [0.0] * total_samples

        for ev in sfx_events:
            rel_t = max(0.0, float(ev.get("rel_time", 0.0)))
            sfx_fname = ev.get("sfx")
            vol = float(ev.get("volume", 0.70))
            sfx_p = self.get_sfx_path(sfx_fname)

            if not sfx_p.exists():
                continue

            try:
                with wave.open(str(sfx_p), "rb") as wf:
                    n_frames = wf.getnframes()
                    raw_bytes = wf.readframes(n_frames)
                    sfx_samples = struct.unpack(f"<{n_frames}h", raw_bytes)

                start_idx = int(rel_t * self.sample_rate)
                for i, sample_val in enumerate(sfx_samples):
                    target_idx = start_idx + i
                    if target_idx < total_samples:
                        norm_val = (sample_val / 32767.0) * vol
                        master_buffer[target_idx] += norm_val
            except Exception as e:
                logger.warning(f"Error mixing SFX {sfx_fname}: {e}")

        # Check if anything was mixed
        has_sound = any(abs(s) > 0.001 for s in master_buffer[:min(len(master_buffer), 50000)]) or len(sfx_events) > 0
        if not has_sound:
            return None

        # Write mixed track
        self._write_wav(output_path, master_buffer[:int(self.sample_rate * duration)])
        logger.info(f"Generated precision SFX composite track ({len(sfx_events)} sound events) at {output_path.name}")
        return output_path

    def get_sfx_path(self, sfx_name: str) -> Path:
        """Returns the absolute path to a given SFX file."""
        return self.sfx_dir / sfx_name


# Singleton instance
sfx_engine = SFXEngine()
