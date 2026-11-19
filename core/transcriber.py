"""
AI Transcriber module using faster-whisper.
Extracts word-level and sentence-level timestamps, detects language,
and structures segments for viral moment analysis and karaoke subtitles.
"""

import os
import sys

# Prevent PyAV 19 metadata_errors incompatibility with faster-whisper
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from faster_whisper import WhisperModel

from config import HW_PROFILE, PROCESSING_DIR

logger = logging.getLogger("ViralShortsEngine.Transcriber")


class AudioTranscriber:
    def __init__(self, model_size: Optional[str] = None):
        self.profile = HW_PROFILE
        self.model_size = model_size or self.profile["whisper_model"]
        self.device = self.profile["device"]
        self.compute_type = self.profile["compute_type"]
        self.threads = self.profile["threads"]
        self._model = None

    def _load_model(self):
        if self._model is None:
            logger.info(f"Loading faster-whisper model '{self.model_size}' on {self.device} (compute_type={self.compute_type})...")
            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.threads,
                    download_root=str(Path.home() / ".cache" / "whisper")
                )
            except Exception as e:
                logger.warning(f"Failed to load Whisper on {self.device} ({e}). Falling back to CPU int8.")
                self.device = "cpu"
                self.compute_type = "int8"
                self._model = WhisperModel(
                    "small",
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=self.threads,
                    download_root=str(Path.home() / ".cache" / "whisper")
                )
        return self._model

    def transcribe(
        self,
        audio_or_video_path: str,
        start_time: Optional[float] = None,
        duration: Optional[float] = None,
        cache_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Transcribes media file, returning segments with word-level timestamps.
        Supports fast slice transcription (start_time, duration) for long streams/VODs.
        Checks cache first if available.
        """
        import subprocess
        input_path = Path(audio_or_video_path)
        
        # Build cache key
        cache_suffix = f"_s{int(start_time)}_d{int(duration)}" if (start_time is not None and duration is not None) else ""
        cache_path = (cache_dir or PROCESSING_DIR) / f"{input_path.stem}{cache_suffix}_transcript.json"

        if cache_path.exists():
            try:
                logger.info(f"Loading cached transcript from {cache_path}")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed reading cache: {e}. Re-transcribing.")

        target_audio = input_path
        time_offset = 0.0

        # Fast audio slice extraction if a specific range is requested
        if start_time is not None and duration is not None:
            time_offset = max(0.0, float(start_time))
            slice_path = (cache_dir or PROCESSING_DIR) / f"{input_path.stem}_slice_{int(start_time)}_{int(duration)}.wav"
            if not slice_path.exists():
                logger.info(f"Extracting fast audio slice: {start_time:.1f}s to {start_time+duration:.1f}s...")
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_time),
                    "-t", str(duration),
                    "-i", str(input_path),
                    "-vn", "-ac", "1", "-ar", "16000",
                    "-f", "wav", str(slice_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            target_audio = slice_path

        model = self._load_model()
        logger.info(f"Transcribing {target_audio} with word-level timestamps (offset={time_offset:.1f}s)...")

        segments_raw, info = model.transcribe(
            str(target_audio),
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        segments = []
        full_text_parts = []

        for seg_idx, segment in enumerate(segments_raw):
            words_list = []
            if segment.words:
                for w in segment.words:
                    words_list.append({
                        "word": w.word.strip(),
                        "start": round(w.start + time_offset, 3),
                        "end": round(w.end + time_offset, 3),
                        "probability": round(w.probability, 3)
                    })

            seg_dict = {
                "id": seg_idx,
                "start": round(segment.start + time_offset, 3),
                "end": round(segment.end + time_offset, 3),
                "text": segment.text.strip(),
                "words": words_list
            }
            segments.append(seg_dict)
            full_text_parts.append(segment.text.strip())

        result = {
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 3),
            "time_offset": time_offset,
            "full_transcript": " ".join(full_text_parts),
            "segments": segments
        }

        # Save cache
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved transcript cache to {cache_path}")
        except Exception as e:
            logger.warning(f"Could not write transcript cache: {e}")

        return result
