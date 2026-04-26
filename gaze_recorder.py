"""Collect personal gaze data using a 3x3 dot grid."""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception as exc:
    raise ImportError("mediapipe is required for data collection") from exc


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "training_data"
FRAMES_DIR = DATA_DIR / "frames"
LABELS_PATH = DATA_DIR / "labels.csv"
SESSION_INFO_PATH = DATA_DIR / "session_info.json"
FACE_TASK_PATH = BASE_DIR / "face_landmarker.task"


LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]


@dataclass
class DotTarget:
    index: int
    x_norm: float
    y_norm: float

    @property
    def yaw_angle(self) -> float:
        return (self.x_norm - 0.5) * 0.6

    @property
    def pitch_angle(self) -> float:
        return (self.y_norm - 0.5) * 0.4


class FaceDetector:
    """Thin wrapper around MediaPipe FaceLandmarker."""

    def __init__(self, model_path: Path) -> None:
        try:
            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
                num_faces=1,
            )
            self._detector = vision.FaceLandmarker.create_from_options(options)
        except Exception as exc:
            raise RuntimeError("Failed to initialize FaceLandmarker") from exc

    def detect(self, bgr_image: np.ndarray) -> Optional[vision.FaceLandmarkerResult]:
        try:
            rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._detector.detect(mp_image)
            return result
        except Exception:
            return None


def compute_ear(landmarks: List[vision.NormalizedLandmark], width: int, height: int) -> float:
    """Compute eye aspect ratio (EAR) using 6-point landmarks for each eye."""

    def _eye_ear(indices: List[int]) -> float:
        pts = np.array(
            [(landmarks[i].x * width, landmarks[i].y * height) for i in indices],
            dtype=np.float32,
        )
        p1, p2, p3, p4, p5, p6 = pts
        vertical1 = np.linalg.norm(p2 - p6)
        vertical2 = np.linalg.norm(p3 - p5)
        horizontal = np.linalg.norm(p1 - p4)
        if horizontal <= 1e-6:
            return 0.0
        return (vertical1 + vertical2) / (2.0 * horizontal)

    left = _eye_ear(LEFT_EYE_IDX)
    right = _eye_ear(RIGHT_EYE_IDX)
    return float((left + right) / 2.0)


def face_quality_ok(
    landmarks: List[vision.NormalizedLandmark],
    width: int,
    height: int,
    min_size: int = 80,
) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
    """Validate face bounding box size and position; return bbox if ok."""
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    box_w = int((x_max - x_min) * width)
    box_h = int((y_max - y_min) * height)
    x1 = int(x_min * width)
    y1 = int(y_min * height)
    x2 = int(x_max * width)
    y2 = int(y_max * height)

    if box_w < min_size or box_h < min_size:
        return False, None

    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    if center_x < width * 0.2 or center_x > width * 0.8:
        return False, None
    if center_y < height * 0.2 or center_y > height * 0.8:
        return False, None

    return True, (x1, y1, x2, y2)


def build_targets() -> List[DotTarget]:
    coords = [0.2, 0.5, 0.8]
    targets: List[DotTarget] = []
    idx = 0
    for y in coords:
        for x in coords:
            targets.append(DotTarget(index=idx, x_norm=x, y_norm=y))
            idx += 1
    return targets


def ensure_dirs() -> None:
    try:
        FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError("Failed to create training_data directories") from exc


def open_camera() -> cv2.VideoCapture:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if cap.get(cv2.CAP_PROP_FRAME_WIDTH) < 1000:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
    cap.set(cv2.CAP_PROP_EXPOSURE, -5)
    return cap


def draw_preview(canvas: np.ndarray, frame: np.ndarray) -> None:
    preview = cv2.resize(frame, (160, 120))
    h, w = preview.shape[:2]
    canvas[20 : 20 + h, -20 - w : -20] = preview
    cv2.rectangle(canvas, (canvas.shape[1] - 20 - w, 20), (canvas.shape[1] - 20, 20 + h), (255, 255, 255), 1)


def draw_progress(
    canvas: np.ndarray,
    pass_idx: int,
    dot_idx: int,
    total_frames: int,
    target_frames: int,
) -> None:
    text = f"Pass {pass_idx + 1}/3 | Dot {dot_idx + 1}/9 | Frames: {total_frames}/{target_frames}"
    cv2.putText(canvas, text, (40, canvas.shape[0] - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def draw_instructions(canvas: np.ndarray, paused: bool) -> None:
    msg = "Look directly at the dot. Keep head still."
    if paused:
        msg = "PAUSED - Press P to resume"
    cv2.putText(canvas, msg, (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)


def save_session_info(info: Dict[str, object]) -> None:
    try:
        with SESSION_INFO_PATH.open("w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as exc:
        print(f"⚠ Failed to write session info: {exc}")


def append_label_row(row: Dict[str, object]) -> None:
    new_file = not LABELS_PATH.exists()
    try:
        with LABELS_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "filename",
                    "dot_index",
                    "dot_x_norm",
                    "dot_y_norm",
                    "screen_width",
                    "screen_height",
                    "timestamp",
                    "yaw_angle",
                    "pitch_angle",
                ],
            )
            if new_file:
                writer.writeheader()
            writer.writerow(row)
    except Exception as exc:
        print(f"⚠ Failed to write label row: {exc}")


def get_screen_size() -> Tuple[int, int]:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:
        return 1920, 1080


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect personal gaze data")
    parser.add_argument("--windowed", action="store_true", help="Use a window instead of fullscreen")
    args = parser.parse_args()

    print("🚀 Starting gaze data collection")
    ensure_dirs()

    if not FACE_TASK_PATH.exists():
        raise FileNotFoundError("face_landmarker.task not found in project folder")

    detector = FaceDetector(FACE_TASK_PATH)
    targets = build_targets()

    try:
        cap = open_camera()
    except Exception as exc:
        raise RuntimeError("Failed to open camera") from exc

    screen_width, screen_height = get_screen_size()
    fps = 30.0
    total_expected = 9 * 45 * 3

    session_info = {
        "screen_width": screen_width,
        "screen_height": screen_height,
        "fps": fps,
        "camera_index": 0,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_frames_target": total_expected,
    }

    cv2.namedWindow("gaze_collect", cv2.WINDOW_NORMAL)
    if not args.windowed:
        cv2.setWindowProperty("gaze_collect", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    else:
        cv2.resizeWindow("gaze_collect", min(1280, screen_width), min(720, screen_height))

    total_frames = 0
    paused = False
    skipped_per_dot: Dict[int, int] = {i: 0 for i in range(9)}

    for pass_idx in range(3):
        for dot in targets:
            if not cap.isOpened():
                print("✗ Camera closed unexpectedly")
                break

            start_show = time.time()
            while time.time() - start_show < 1.0:
                ret, frame = cap.read()
                if not ret:
                    continue
                canvas = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)
                dot_pos = (int(dot.x_norm * screen_width), int(dot.y_norm * screen_height))
                cv2.circle(canvas, dot_pos, 32, (0, 0, 255), -1)
                draw_preview(canvas, frame)
                draw_progress(canvas, pass_idx, dot.index, total_frames, total_expected)
                draw_instructions(canvas, paused)
                cv2.imshow("gaze_collect", canvas)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    print("⚠ Quit requested")
                    save_session_info(session_info)
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                if key == ord("p"):
                    paused = not paused

            if paused:
                while paused:
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    canvas = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)
                    dot_pos = (int(dot.x_norm * screen_width), int(dot.y_norm * screen_height))
                    cv2.circle(canvas, dot_pos, 32, (0, 0, 255), -1)
                    draw_preview(canvas, frame)
                    draw_progress(canvas, pass_idx, dot.index, total_frames, total_expected)
                    draw_instructions(canvas, paused)
                    cv2.imshow("gaze_collect", canvas)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("p"):
                        paused = False
                    if key in (27, ord("q")):
                        print("⚠ Quit requested")
                        save_session_info(session_info)
                        cap.release()
                        cv2.destroyAllWindows()
                        return

            # Recording phase
            record_start = time.time()
            frame_count = 0
            while frame_count < 45:
                ret, frame = cap.read()
                if not ret:
                    continue

                result = detector.detect(frame)
                if result is None or not result.face_landmarks:
                    skipped_per_dot[dot.index] += 1
                    continue

                landmarks = result.face_landmarks[0]
                h, w = frame.shape[:2]
                ok, _bbox = face_quality_ok(landmarks, w, h)
                if not ok:
                    skipped_per_dot[dot.index] += 1
                    continue

                ear = compute_ear(landmarks, w, h)
                if ear < 0.15:
                    skipped_per_dot[dot.index] += 1
                    continue

                filename = f"dot_{dot.index}_pass_{pass_idx}_frame_{frame_count}.jpg"
                file_path = FRAMES_DIR / filename
                try:
                    cv2.imwrite(str(file_path), frame)
                except Exception as exc:
                    print(f"⚠ Failed to save frame: {exc}")
                    continue

                append_label_row(
                    {
                        "filename": filename,
                        "dot_index": dot.index,
                        "dot_x_norm": f"{dot.x_norm:.4f}",
                        "dot_y_norm": f"{dot.y_norm:.4f}",
                        "screen_width": screen_width,
                        "screen_height": screen_height,
                        "timestamp": f"{time.time():.4f}",
                        "yaw_angle": f"{dot.yaw_angle:.6f}",
                        "pitch_angle": f"{dot.pitch_angle:.6f}",
                    }
                )
                frame_count += 1
                total_frames += 1

                canvas = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)
                dot_pos = (int(dot.x_norm * screen_width), int(dot.y_norm * screen_height))
                cv2.circle(canvas, dot_pos, 32, (0, 255, 0), -1)
                cv2.putText(canvas, "RECORDING", (40, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                draw_preview(canvas, frame)
                draw_progress(canvas, pass_idx, dot.index, total_frames, total_expected)
                draw_instructions(canvas, paused)
                cv2.imshow("gaze_collect", canvas)
                key = cv2.waitKey(1) & 0xFF
                if key == ord(" "):
                    print("⚠ Dot skipped by user")
                    skipped_per_dot[dot.index] += (45 - frame_count)
                    break
                if key in (27, ord("q")):
                    print("⚠ Quit requested")
                    save_session_info(session_info)
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                if key == ord("r"):
                    print("⚠ Restart requested")
                    cap.release()
                    cv2.destroyAllWindows()
                    main()
                    return
                time.sleep(max(0.0, (1.0 / fps) - (time.time() - record_start)))

            canvas = np.zeros((screen_height, screen_width, 3), dtype=np.uint8)
            dot_pos = (int(dot.x_norm * screen_width), int(dot.y_norm * screen_height))
            cv2.circle(canvas, dot_pos, 32, (0, 255, 0), -1)
            cv2.putText(canvas, "✓", (dot_pos[0] - 10, dot_pos[1] + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
            draw_progress(canvas, pass_idx, dot.index, total_frames, total_expected)
            cv2.imshow("gaze_collect", canvas)
            cv2.waitKey(500)

    save_session_info(session_info)
    cap.release()
    cv2.destroyAllWindows()
    print("✓ Data collection complete")
    print(f"Skipped frames per dot: {skipped_per_dot}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"✗ Fatal error: {exc}")
