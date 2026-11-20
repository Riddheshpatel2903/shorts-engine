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

        if self.model_path.exists():
            try:
                # Initialize YuNet with dummy input size; dynamically resized in detect_faces_in_frame
                self.detector = cv2.FaceDetectorYN_create(
                    str(self.model_path),
                    "",
                    (320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=10
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
        to assess face size, horizontal center, and gaze direction (looking into camera vs away).
        """
        if self.detector is None or frame is None:
            return []

        h, w = frame.shape[:2]
        try:
            self.detector.setInputSize((w, h))
            ret, faces = self.detector.detect(frame)
            if faces is None or len(faces) == 0:
                return []

            results = []
            for f in faces:
                x, y, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                x = max(0, x)
                y = max(0, y)
                fw = min(w - x, fw)
                fh = min(h - y, fh)
                if fw < 20 or fh < 20:
                    continue

                # Facial landmarks: right eye, left eye, nose tip, right mouth, left mouth
                x_re, y_re = float(f[4]), float(f[5])
                x_le, y_le = float(f[6]), float(f[7])
                x_nt, y_nt = float(f[8]), float(f[9])
                score = float(f[14]) if len(f) > 14 else 0.8

                eye_dist = abs(x_le - x_re)
                if eye_dist > 6:
                    eye_mid_x = (x_re + x_le) / 2.0
                    gaze_dev = abs(x_nt - eye_mid_x) / eye_dist
                    is_looking_in_frame = gaze_dev < 0.38
                    eye_tilt = abs(y_re - y_le) / eye_dist
                    is_upright = eye_tilt < 0.45
                else:
                    is_looking_in_frame = True
                    is_upright = True

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
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning(f"Cannot open video for clip framing analysis: {video_path}")
            return {
                "person_in_frame": False,
                "person_looking_in_frame": False,
                "tracked_person_cx": 960,
                "recommended_layout": "CINEMATIC_BLUR",
                "reason": "Source video cannot be opened. Using default cinematic blur."
            }

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        # Handle native vertical video (already 9:16)
        if height >= width:
            cap.release()
            return {
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
            return {
                "person_in_frame": False,
                "person_looking_in_frame": False,
                "tracked_person_cx": width // 2,
                "crop_x": int((width - crop_w) / 2),
                "crop_w": crop_w,
                "crop_h": crop_h,
                "recommended_layout": "CINEMATIC_BLUR",
                "reason": "No frames could be sampled in clip window."
            }

        frames_with_faces = [fr for fr in frame_records if fr["faces"]]
        face_ratio = len(frames_with_faces) / max(1, total_sampled)
        has_person = face_ratio >= 0.20

        if not has_person:
            crop_x = int((width - crop_w) / 2)
            crop_x = max(0, min(width - crop_w, crop_x))
            crop_x = crop_x - (crop_x % 2)
            return {
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

        primary_faces = [fr["faces"][0] for fr in frames_with_faces]
        looking_faces = [f for f in primary_faces if f["is_looking_in_frame"]]
        looking_ratio = len(looking_faces) / max(1, len(primary_faces))
        person_looking = looking_ratio >= 0.35

        cxs = [f["cx"] for f in primary_faces]
        cys = [f["cy"] for f in primary_faces]
        avg_w = sum(f["width"] for f in primary_faces) / len(primary_faces)
        median_cx = float(np.median(cxs))
        median_cy = float(np.median(cys))

        is_corner_x = (median_cx < width * 0.35) or (median_cx > width * 0.65)
        is_small = avg_w < (width * 0.35)
        is_corner_facecam = is_corner_x and is_small

        crop_x = int(median_cx - crop_w / 2)
        crop_x = max(0, min(width - crop_w, crop_x))
        crop_x = crop_x - (crop_x % 2)

        facecam_box = None
        if is_corner_facecam:
            recommended = "STREAMER_SPLIT"
            corner_label = "left" if median_cx < width * 0.5 else "right"
            reason = f"Streamer webcam detected in {corner_label} corner. Pro Dual-View (Facecam Top + Full Game View Bottom) preserves 100% of game HUD and killfeed."

            # Compute optimal padded facecam box with headroom and shoulder framing
            avg_h = sum(f["height"] for f in primary_faces) / len(primary_faces)
            target_aspect = 1080 / 760  # 1.421:1
            box_h = int(avg_h * 2.3)
            box_w = int(box_h * target_aspect)
            if box_w > width:
                box_w = width
                box_h = int(box_w / target_aspect)
            if box_h > height:
                box_h = height
                box_w = int(box_h * target_aspect)

            box_x = max(0, min(width - box_w, int(median_cx - box_w / 2)))
            box_y = max(0, min(height - box_h, int(median_cy - box_h * 0.38)))

            facecam_box = {
                "x": box_x,
                "y": box_y,
                "width": box_w,
                "height": box_h
            }
        elif person_looking:
            recommended = "FULL_VERTICAL_STRIP"
            reason = f"Person looking directly at camera detected (centered at X={int(median_cx)}px). Full Vertical Strip tracks them seamlessly in 9:16."
        else:
            recommended = "FULL_VERTICAL_STRIP"
            reason = f"Subject in frame (centered at X={int(median_cx)}px). Full Vertical Strip tracks the subject in 9:16."

        return {
            "person_in_frame": True,
            "person_looking_in_frame": person_looking,
            "face_ratio": round(face_ratio, 2),
            "looking_ratio": round(looking_ratio, 2),
            "tracked_person_cx": int(median_cx),
            "tracked_person_cy": int(median_cy),
            "crop_x": crop_x,
            "crop_w": crop_w,
            "crop_h": crop_h,
            "is_corner_facecam": is_corner_facecam,
            "facecam_box": facecam_box,
            "recommended_layout": recommended,
            "reason": reason,
            "source_width": width,
            "source_height": height
        }

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

        # Check ANY Corner: Top-Left, Top-Right, Bottom-Left, Bottom-Right, Bottom-Center
        is_left = avg_cx < width * 0.38
        is_right = avg_cx > width * 0.62
        is_top = avg_cy < height * 0.48
        is_bottom = avg_cy > height * 0.52
        is_small_box = (avg_w < width * 0.38) and (avg_h < height * 0.45)

        quadrant = "CENTER"
        if is_top and is_left:
            quadrant = "TOP_LEFT"
        elif is_top and is_right:
            quadrant = "TOP_RIGHT"
        elif is_bottom and is_left:
            quadrant = "BOTTOM_LEFT"
        elif is_bottom and is_right:
            quadrant = "BOTTOM_RIGHT"
        elif is_bottom:
            quadrant = "BOTTOM_CENTER"
        elif is_left:
            quadrant = "LEFT_SIDE"
        elif is_right:
            quadrant = "RIGHT_SIDE"
        elif is_top:
            quadrant = "TOP_CENTER"

        is_corner = (is_left or is_right or (is_bottom and is_small_box))

        if is_corner and is_small_box and face_ratio >= 0.35:
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
