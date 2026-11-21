"""
Face Detector and Spatial Layout Analyzer using OpenCV YuNet / DNN.
Detects faces, identifies streamer facecam boxes vs talking-head vs podcast vs gameplay,
and computes optimal 9:16 crop coordinates.
"""

import os
import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from config import ASSETS_DIR

logger = logging.getLogger("ViralShortsEngine.FaceDetector")


class FaceDetector:
    def __init__(self):
        self.model_path = ASSETS_DIR / "face_detection_yunet_2023mar.onnx"
        self.detector = None
        self._framing_cache: Dict[Tuple[str, float, float], Dict[str, Any]] = {}

        if self.model_path.exists():
            try:
                # Initialize YuNet with dummy input size; dynamically resized in detect_faces_in_frame
                self.detector = cv2.FaceDetectorYN_create(
                    str(self.model_path),
                    "",
                    (320, 320),
                    score_threshold=0.30,
                    nms_threshold=0.3,
                    top_k=15
                )
                logger.info("Initialized OpenCV YuNet DNN face detector.")
            except Exception as e:
                logger.warning(f"Could not initialize YuNet ({e}). Operating in layout fallback mode.")
                self.detector = None
        else:
            logger.info("YuNet model not found. Operating in layout fallback mode.")

    def sample_video_frames(self, video_path: str, max_samples: int = 24) -> List[Tuple[float, np.ndarray]]:
        """
        Samples evenly spaced frames from video for spatial analysis.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Cannot open video for frame sampling: {video_path}")
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        if total_frames <= 0:
            cap.release()
            return []

        step = max(1, total_frames // max_samples)
        samples = []

        for frame_idx in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                timestamp = frame_idx / fps
                samples.append((timestamp, frame))
            if len(samples) >= max_samples:
                break

        cap.release()
        return samples

    def detect_faces_in_frame(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detects faces in a single frame. Returns list of (x, y, w, h).
        """
        if self.detector is None or frame is None:
            return []

        h, w = frame.shape[:2]
        try:
            self.detector.setInputSize((w, h))
            ret, faces = self.detector.detect(frame)
            if faces is not None and len(faces) > 0:
                results = []
                for f in faces:
                    x, y, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                    # Bound to frame coordinates
                    x = max(0, x)
                    y = max(0, y)
                    fw = min(w - x, fw)
                    fh = min(h - y, fh)
                    if fw > 20 and fh > 20:
                        results.append((x, y, fw, fh))
                return results
        except Exception as e:
            logger.warning(f"Face detection inference error: {e}")

        return []

    def detect_faces_detailed(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects faces and extracts detailed 5-point landmarks (eyes, nose, mouth)
        to assess face size, horizontal center, mouth openness, and gaze direction (looking into camera vs away).
        Uses multi-scale pyramid (1.0x and 0.6x) to catch faces across all distances.
        """
        if self.detector is None or frame is None:
            return []

        h, w = frame.shape[:2]
        try:
            # Multi-scale detection: try native first, then 0.6x if native missed
            faces = None
            detected_scale = 1.0

            for scale in [1.0, 0.6]:
                if scale == 1.0:
                    detect_frame = frame
                    self.detector.setInputSize((w, h))
                else:
                    sw, sh = int(w * scale), int(h * scale)
                    detect_frame = cv2.resize(frame, (sw, sh))
                    self.detector.setInputSize((sw, sw) if sw == sh else (sw, sh))

                ret, detected = self.detector.detect(detect_frame)
                if detected is not None and len(detected) > 0:
                    detected_scale = scale
                    faces = detected
                    break

            if faces is None or len(faces) == 0:
                return []

            results = []
            inv_scale = 1.0 / detected_scale

            for f in faces:
                x = int(f[0] * inv_scale)
                y = int(f[1] * inv_scale)
                fw = int(f[2] * inv_scale)
                fh = int(f[3] * inv_scale)

                x = max(0, x)
                y = max(0, y)
                fw = min(w - x, fw)
                fh = min(h - y, fh)
                if fw < 18 or fh < 18:
                    continue

                # Facial landmarks: right eye, left eye, nose tip, right mouth, left mouth
                x_re, y_re = float(f[4] * inv_scale), float(f[5] * inv_scale)
                x_le, y_le = float(f[6] * inv_scale), float(f[7] * inv_scale)
                x_nt, y_nt = float(f[8] * inv_scale), float(f[9] * inv_scale)
                x_rc, y_rc = float(f[10] * inv_scale), float(f[11] * inv_scale)
                x_lc, y_lc = float(f[12] * inv_scale), float(f[13] * inv_scale)
                score = float(f[14]) if len(f) > 14 else 0.8

                eye_dist = max(1.0, abs(x_le - x_re))
                eye_mid_x = (x_re + x_le) / 2.0
                gaze_dev = abs(x_nt - eye_mid_x) / eye_dist
                is_looking_in_frame = gaze_dev < 0.40
                eye_tilt = abs(y_re - y_le) / eye_dist
                is_upright = eye_tilt < 0.45

                # Mouth opening & speech dynamics calculation
                mouth_w = max(1.0, abs(x_lc - x_rc))
                mouth_mid_y = (y_rc + y_lc) / 2.0
                mouth_h = max(1.0, abs(mouth_mid_y - y_nt))
                mouth_open = mouth_h / mouth_w

                cx = x + fw / 2.0
                cy = y + fh / 2.0
                area_ratio = (fw * fh) / max(1, (w * h))

                results.append({
                    "box": (x, y, fw, fh),
                    "cx": cx,
                    "cy": cy,
                    "width": fw,
                    "height": fh,
                    "area_ratio": area_ratio,
                    "mouth_open": mouth_open,
                    "is_looking_in_frame": bool(is_looking_in_frame and is_upright),
                    "score": score
                })

            results.sort(key=lambda item: item["area_ratio"], reverse=True)
            return results

        except Exception as e:
            logger.warning(f"Detailed face detection error: {e}")
            return []

    def analyze_clip_framing(
        self,
        video_path: str,
        start_time: float,
        duration: float,
        max_samples: int = 12
    ) -> Dict[str, Any]:
        """
        Pinpoint analysis of a specific clip window [start_time, start_time + duration].
        Determines:
        1. Whether a person/speaker is in frame.
        2. Whether the person is looking directly at the camera/viewer.
        3. The optimal horizontal center (cx) to frame them in a Full Vertical Strip (9:16).
        4. Recommends the best vertical layout for this specific clip.
        """
        cache_key = (str(video_path), round(float(start_time), 1), round(float(duration), 1))
        if cache_key in self._framing_cache:
            return self._framing_cache[cache_key]

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning(f"Cannot open video for clip framing analysis: {video_path}")
            res = {
                "person_in_frame": False,
                "person_looking_in_frame": False,
                "tracked_person_cx": 960,
                "recommended_layout": "CINEMATIC_BLUR",
                "reason": "Source video cannot be opened. Using default cinematic blur."
            }
            self._framing_cache[cache_key] = res
            return res

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        # Handle native vertical video (already 9:16)
        if height >= width:
            cap.release()
            res = {
                "person_in_frame": False,
                "person_looking_in_frame": False,
                "source_is_vertical": True,
                "tracked_person_cx": width // 2,
                "crop_x": 0,
                "crop_w": width,
                "crop_h": height,
                "recommended_layout": "FULL_VERTICAL_STRIP",
                "reason": "Source video is already vertical (9:16). Full Vertical Strip fits natively."
            }
            self._framing_cache[cache_key] = res
            return res

        # Sample frames within the clip range
        step_s = max(0.2, duration / max(1, max_samples))
        frame_records = []

        for i in range(max_samples):
            t = start_time + (i * step_s)
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            detailed_faces = self.detect_faces_detailed(frame)
            frame_records.append({"t": t, "faces": detailed_faces})

        cap.release()

        total_sampled = len(frame_records)
        target_ratio = 1080 / 1920
        crop_w = int(height * target_ratio)
        crop_w = crop_w - (crop_w % 2)
        crop_h = height

        if total_sampled == 0:
            res = {
                "person_in_frame": False,
                "person_looking_in_frame": False,
                "tracked_person_cx": width // 2,
                "crop_x": int((width - crop_w) / 2),
                "crop_w": crop_w,
                "crop_h": crop_h,
                "recommended_layout": "CINEMATIC_BLUR",
                "reason": "No frames could be sampled in clip window."
            }
            self._framing_cache[cache_key] = res
            return res

        frames_with_faces = [fr for fr in frame_records if fr["faces"]]
        face_ratio = len(frames_with_faces) / max(1, total_sampled)
        has_person = (len(frames_with_faces) >= 2) or (face_ratio >= 0.15)

        if not has_person:
            crop_x = int((width - crop_w) / 2)
            crop_x = max(0, min(width - crop_w, crop_x))
            crop_x = crop_x - (crop_x % 2)
            res = {
                "person_in_frame": False,
                "person_looking_in_frame": False,
                "face_ratio": round(face_ratio, 2),
                "tracked_person_cx": width // 2,
                "crop_x": crop_x,
                "crop_w": crop_w,
                "crop_h": crop_h,
                "is_corner_facecam": False,
                "recommended_layout": "CINEMATIC_BLUR",
                "reason": "No person in frame (pure gameplay/action). Cinematic blurred backdrop preserves widescreen HUD & action, or use Full Vertical Strip for centered action."
            }
            self._framing_cache[cache_key] = res
            return res

        # Cluster all detected faces into distinct person tracks across the clip
        clusters = []
        for fr in frames_with_faces:
            for face in fr["faces"]:
                matched = False
                for c in clusters:
                    if abs(c["cx_mean"] - face["cx"]) < (width * 0.18):
                        c["items"].append(face)
                        c["cx_mean"] = float(np.mean([item["cx"] for item in c["items"]]))
                        matched = True
                        break
                if not matched:
                    clusters.append({"cx_mean": face["cx"], "items": [face]})

        speaker_candidates = []
        for c in clusters:
            cxs = [item["cx"] for item in c["items"]]
            cys = [item["cy"] for item in c["items"]]
            areas = [item["area_ratio"] for item in c["items"]]
            mouth_opens = [item.get("mouth_open", 0.3) for item in c["items"]]
            looking_count = sum(1 for item in c["items"] if item.get("is_looking_in_frame"))

            mouth_var = float(np.var(mouth_opens)) if len(mouth_opens) > 1 else 0.001
            avg_area = float(np.mean(areas))
            presence = len(c["items"])

            # Speaker score: lip motion cadence + gaze toward viewer + screen presence
            score = presence * (avg_area ** 0.5) * (1.0 + mouth_var * 50.0) * (1.3 if looking_count > 0 else 0.8)

            speaker_candidates.append({
                "median_cx": float(np.median(cxs)),
                "median_cy": float(np.median(cys)),
                "avg_w": float(np.mean([item["width"] for item in c["items"]])),
                "avg_h": float(np.mean([item["height"] for item in c["items"]])),
                "mouth_var": mouth_var,
                "score": score,
                "presence": presence,
                "looking_ratio": looking_count / max(1, presence)
            })

        speaker_candidates.sort(key=lambda x: x["score"], reverse=True)
        active_speaker = speaker_candidates[0]

        active_speaker_cx = active_speaker["median_cx"]
        active_speaker_cy = active_speaker["median_cy"]
        avg_w = active_speaker["avg_w"]
        avg_h = active_speaker["avg_h"]
        person_looking = active_speaker["looking_ratio"] >= 0.35

        # True corner facecam detection:
        # A gaming webcam overlay MUST be in an extreme corner (top-left, top-right, bottom-left, bottom-right)
        # AND occupy a small footprint (< 22% of screen width).
        # Any person framed anywhere else (even off-center in rule-of-thirds) is a primary subject, NOT a webcam!
        is_extreme_x = (active_speaker_cx < width * 0.22) or (active_speaker_cx > width * 0.78)
        is_extreme_y = (active_speaker_cy < height * 0.32) or (active_speaker_cy > height * 0.68)
        is_tiny_box = (avg_w < width * 0.22) and (avg_h < height * 0.25)
        is_corner_facecam = is_extreme_x and is_extreme_y and is_tiny_box

        # PRECISE CENTERING: Center the speaking person exactly in the 9:16 frame!
        crop_x = int(active_speaker_cx - crop_w / 2)
        crop_x = max(0, min(width - crop_w, crop_x))
        crop_x = crop_x - (crop_x % 2)

        # Dynamic multi-speaker tracking: check if two speakers talk in turns
        crop_x_expr = str(crop_x)
        dynamic_cut_info = None

        if len(speaker_candidates) >= 2 and not is_corner_facecam:
            spk1 = speaker_candidates[0]
            spk2 = speaker_candidates[1]
            if abs(spk1["median_cx"] - spk2["median_cx"]) > (width * 0.22):
                spk1_times = []
                spk2_times = []
                for fr in frames_with_faces:
                    t_rel = max(0.0, fr["t"] - start_time)
                    for face in fr["faces"]:
                        if abs(face["cx"] - spk1["median_cx"]) < (width * 0.15):
                            spk1_times.append(t_rel)
                        elif abs(face["cx"] - spk2["median_cx"]) < (width * 0.15):
                            spk2_times.append(t_rel)

                if spk1_times and spk2_times:
                    med1 = float(np.median(spk1_times))
                    med2 = float(np.median(spk2_times))
                    if abs(med1 - med2) > (duration * 0.20):
                        t_cut = round((med1 + med2) / 2.0, 1)
                        crop_x1 = max(0, min(width - crop_w, int(spk1["median_cx"] - crop_w / 2)))
                        crop_x2 = max(0, min(width - crop_w, int(spk2["median_cx"] - crop_w / 2)))
                        crop_x1 = crop_x1 - (crop_x1 % 2)
                        crop_x2 = crop_x2 - (crop_x2 % 2)
                        if med1 < med2:
                            crop_x_expr = f"if(lt(t\\,{t_cut})\\,{crop_x1}\\,{crop_x2})"
                        else:
                            crop_x_expr = f"if(lt(t\\,{t_cut})\\,{crop_x2}\\,{crop_x1})"
                        dynamic_cut_info = f"Auto Speaker Switch at {t_cut}s: Speaker 1 (X={int(spk1['median_cx'])}px) ➡️ Speaker 2 (X={int(spk2['median_cx'])}px)"

        facecam_box = None
        if is_corner_facecam:
            recommended = "STREAMER_SPLIT"
            corner_label = "left" if active_speaker_cx < width * 0.5 else "right"
            reason = f"Streamer webcam detected in {corner_label} corner (X={int(active_speaker_cx)}px). Pro Dual-View preserves 100% of game HUD."

            target_aspect = 1080 / 760  # 1.421:1
            box_h = int(avg_h * 2.3)
            box_w = int(box_h * target_aspect)
            if box_w > width:
                box_w = width
                box_h = int(box_w / target_aspect)
            if box_h > height:
                box_h = height
                box_w = int(box_h * target_aspect)

            box_x = max(0, min(width - box_w, int(active_speaker_cx - box_w / 2)))
            box_y = max(0, min(height - box_h, int(active_speaker_cy - box_h * 0.38)))

            facecam_box = {
                "x": box_x,
                "y": box_y,
                "width": box_w,
                "height": box_h
            }
        elif dynamic_cut_info:
            recommended = "FULL_VERTICAL_STRIP"
            reason = dynamic_cut_info
        elif person_looking:
            recommended = "FULL_VERTICAL_STRIP"
            reason = f"Speaking person detected at X={int(active_speaker_cx)}px (Lip Motion Tracking Active). Centered at 540px in 9:16 Short."
        else:
            recommended = "FULL_VERTICAL_STRIP"
            reason = f"Subject detected at X={int(active_speaker_cx)}px. Centered at 540px in 9:16 Short."

        all_detected_speakers = [
            {"cx": int(sc["median_cx"]), "label": f"Person at X={int(sc['median_cx'])}px"}
            for sc in speaker_candidates
        ]

        res = {
            "person_in_frame": True,
            "person_looking_in_frame": person_looking,
            "face_ratio": round(face_ratio, 2),
            "looking_ratio": round(active_speaker["looking_ratio"], 2),
            "tracked_person_cx": int(active_speaker_cx),
            "tracked_person_cy": int(active_speaker_cy),
            "all_speakers": all_detected_speakers,
            "crop_x": crop_x,
            "crop_x_expr": crop_x_expr,
            "crop_w": crop_w,
            "crop_h": crop_h,
            "is_corner_facecam": is_corner_facecam,
            "facecam_box": facecam_box,
            "recommended_layout": recommended,
            "reason": reason,
            "source_width": width,
            "source_height": height
        }
        self._framing_cache[cache_key] = res
        return res

    @staticmethod
    def get_manual_corner_box(quadrant: str, width: int, height: int) -> Dict[str, int]:
        """Returns standard webcam crop coordinates for a given corner or quadrant."""
        box_w = int(width * 0.32)
        box_h = int(box_w * (760 / 1080))
        q = quadrant.upper()
        if "TOP_LEFT" in q:
            return {"x": 0, "y": 0, "width": box_w, "height": box_h}
        elif "TOP_RIGHT" in q:
            return {"x": width - box_w, "y": 0, "width": box_w, "height": box_h}
        elif "BOTTOM_LEFT" in q:
            return {"x": 0, "y": height - box_h, "width": box_w, "height": box_h}
        elif "BOTTOM_RIGHT" in q:
            return {"x": width - box_w, "y": height - box_h, "width": box_w, "height": box_h}
        elif "BOTTOM_CENTER" in q:
            return {"x": (width - box_w) // 2, "y": height - box_h, "width": box_w, "height": box_h}
        else:
            return {"x": 0, "y": 0, "width": box_w, "height": box_h}

    def classify_source(self, video_path: str) -> Dict[str, Any]:
        """
        Classifies video into layout categories and locates streamer facecam boxes in ANY corner:
        - STREAMER_FACECAM: Persistent facecam in Top-Left, Top-Right, Bottom-Left, or Bottom-Right corner
        - TALKING_HEAD: Prominent centered face across most frames
        - PODCAST: Multiple persistent faces across horizontal axis
        - GAMEPLAY: Fast-moving gameplay with no faces
        - GENERAL: Standard video
        """
        samples = self.sample_video_frames(video_path, max_samples=24)
        if not samples:
            return {
                "classification": "GENERAL",
                "facecam_detected": False,
                "facecam_box": None,
                "facecam_quadrant": None,
                "confidence": 0.5
            }

        height, width = samples[0][1].shape[:2]
        face_records = []

        for ts, frame in samples:
            faces = self.detect_faces_in_frame(frame)
            face_records.append(faces)

        frames_with_faces = sum(1 for faces in face_records if len(faces) > 0)
        face_ratio = frames_with_faces / max(1, len(samples))

        # If very few faces detected (< 15% of frames)
        if face_ratio < 0.15:
            logger.info("Classified source as GAMEPLAY (no persistent faces).")
            return {
                "classification": "GAMEPLAY",
                "facecam_detected": False,
                "facecam_box": None,
                "facecam_quadrant": None,
                "source_width": width,
                "source_height": height,
                "confidence": 0.85
            }

        # Collect all detected face positions
        all_faces = [f for faces in face_records for f in faces]
        if not all_faces:
            return {
                "classification": "GENERAL",
                "facecam_detected": False,
                "facecam_box": None,
                "facecam_quadrant": None,
                "source_width": width,
                "source_height": height,
                "confidence": 0.50
            }

        # Check for multiple faces across horizontal axis (Multi-person Podcast)
        multi_face_count = sum(1 for faces in face_records if len(faces) >= 2)
        left_faces = [f for f in all_faces if (f[0] + f[2] / 2) < width * 0.5]
        right_faces = [f for f in all_faces if (f[0] + f[2] / 2) >= width * 0.5]

        if (multi_face_count / len(samples) > 0.30) or (len(left_faces) >= 3 and len(right_faces) >= 3):
            logger.info("Classified source as PODCAST (multiple speakers detected across horizontal axis).")
            # Calculate speaker centers
            left_cx = sum(x + w / 2 for (x, y, w, h) in left_faces) / len(left_faces) if left_faces else width * 0.25
            left_cy = sum(y + h / 2 for (x, y, w, h) in left_faces) / len(left_faces) if left_faces else height * 0.5

            right_cx = sum(x + w / 2 for (x, y, w, h) in right_faces) / len(right_faces) if right_faces else width * 0.75
            right_cy = sum(y + h / 2 for (x, y, w, h) in right_faces) / len(right_faces) if right_faces else height * 0.5

            # Target 1080x960 box size (matches 9:8 aspect ratio) for split screen
            box_h = int(min(height, max(480, height * 0.85)))
            box_w = int(box_h * (1080 / 960))
            if box_w > width:
                box_w = width
                box_h = int(box_w * (960 / 1080))

            spk1_x = max(0, min(width - box_w, int(left_cx - box_w / 2)))
            spk1_y = max(0, min(height - box_h, int(left_cy - box_h * 0.4)))

            spk2_x = max(0, min(width - box_w, int(right_cx - box_w / 2)))
            spk2_y = max(0, min(height - box_h, int(right_cy - box_h * 0.4)))

            return {
                "classification": "PODCAST",
                "facecam_detected": False,
                "facecam_box": None,
                "facecam_quadrant": None,
                "podcast_speakers": {
                    "has_two_speakers": True,
                    "speaker_left": {"x": spk1_x, "y": spk1_y, "width": box_w, "height": box_h},
                    "speaker_right": {"x": spk2_x, "y": spk2_y, "width": box_w, "height": box_h}
                },
                "source_width": width,
                "source_height": height,
                "confidence": 0.88
            }

        # Calculate average face center and size
        avg_cx = sum(x + w / 2 for (x, y, w, h) in all_faces) / len(all_faces)
        avg_cy = sum(y + h / 2 for (x, y, w, h) in all_faces) / len(all_faces)
        avg_w = sum(w for (x, y, w, h) in all_faces) / len(all_faces)
        avg_h = sum(h for (x, y, w, h) in all_faces) / len(all_faces)

        # Check for genuine corner webcam overlays (Top-Left, Top-Right, Bottom-Left, Bottom-Right)
        # Must be in an extreme corner (X < 22% or > 78%, Y < 32% or > 68%) and small in area
        is_extreme_left = avg_cx < width * 0.22
        is_extreme_right = avg_cx > width * 0.78
        is_extreme_top = avg_cy < height * 0.32
        is_extreme_bottom = avg_cy > height * 0.68
        is_small_box = (avg_w < width * 0.22) and (avg_h < height * 0.25)

        quadrant = "CENTER"
        if is_extreme_top and is_extreme_left:
            quadrant = "TOP_LEFT"
        elif is_extreme_top and is_extreme_right:
            quadrant = "TOP_RIGHT"
        elif is_extreme_bottom and is_extreme_left:
            quadrant = "BOTTOM_LEFT"
        elif is_extreme_bottom and is_extreme_right:
            quadrant = "BOTTOM_RIGHT"

        is_true_corner = (is_extreme_left or is_extreme_right) and (is_extreme_top or is_extreme_bottom)

        if is_true_corner and is_small_box and face_ratio >= 0.35:
            logger.info(f"Classified source as STREAMER_FACECAM in {quadrant} corner.")
            pad_w = int(avg_w * 1.0)
            pad_h = int(avg_h * 1.1)
            crop_w = min(width, int(avg_w + pad_w * 2))
            crop_h = min(height, int(avg_h + pad_h * 2))

            # Maintain 1080:760 aspect ratio for clean top section framing
            target_ratio = 1080 / 760
            if crop_w / max(1, crop_h) < target_ratio:
                crop_w = int(crop_h * target_ratio)
            else:
                crop_h = int(crop_w / target_ratio)

            crop_x = max(0, min(width - crop_w, int(avg_cx - crop_w / 2)))
            crop_y = max(0, min(height - crop_h, int(avg_cy - crop_h * 0.45)))

            return {
                "classification": "STREAMER_FACECAM",
                "facecam_detected": True,
                "facecam_quadrant": quadrant,
                "facecam_box": {
                    "x": crop_x,
                    "y": crop_y,
                    "width": crop_w,
                    "height": crop_h
                },
                "source_width": width,
                "source_height": height,
                "confidence": 0.90
            }

        # Otherwise, large or centered face -> TALKING_HEAD
        logger.info("Classified source as TALKING_HEAD (prominent speaker).")
        return {
            "classification": "TALKING_HEAD",
            "facecam_detected": False,
            "facecam_box": None,
            "facecam_quadrant": None,
            "speaker_center": (int(avg_cx), int(avg_cy)),
            "source_width": width,
            "source_height": height,
            "confidence": 0.85
        }
