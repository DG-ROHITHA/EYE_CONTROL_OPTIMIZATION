"""Prepare training and validation datasets for personal gaze model."""

from __future__ import annotations

import csv
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import torch

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception as exc:
    raise ImportError("mediapipe is required for dataset preparation") from exc


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "training_data"
FRAMES_DIR = DATA_DIR / "frames"
LABELS_PATH = DATA_DIR / "labels.csv"
PROCESSED_DIR = DATA_DIR / "processed"
TRAIN_PKL = PROCESSED_DIR / "train_dataset.pkl"
VAL_PKL = PROCESSED_DIR / "val_dataset.pkl"
STATS_JSON = PROCESSED_DIR / "dataset_stats.json"
FACE_TASK_PATH = BASE_DIR / "face_landmarker.task"

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class Sample:
    image: np.ndarray
    yaw: float
    pitch: float
    yaw_bin: int
    pitch_bin: int
    dot_index: int
    frame_path: str


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

    def detect(self, bgr_image: np.ndarray) -> vision.FaceLandmarkerResult | None:
        try:
            rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._detector.detect(mp_image)
            return result
        except Exception:
            return None


def angle_to_bin(angle: float, offset: float, span: float) -> int:
    bin_val = int(((angle + offset) / span) * 90)
    return int(np.clip(bin_val, 0, 89))


def compute_bbox(landmarks: List[vision.NormalizedLandmark], width: int, height: int) -> Tuple[int, int, int, int]:
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    x1 = int(min(xs) * width)
    y1 = int(min(ys) * height)
    x2 = int(max(xs) * width)
    y2 = int(max(ys) * height)
    return x1, y1, x2, y2


def crop_face(image: np.ndarray, bbox: Tuple[int, int, int, int], margin: float = 0.15) -> np.ndarray:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox
    box_w = x2 - x1
    box_h = y2 - y1
    dx = int(box_w * margin)
    dy = int(box_h * margin)
    x1 = max(0, x1 - dx)
    y1 = max(0, y1 - dy)
    x2 = min(w, x2 + dx)
    y2 = min(h, y2 + dy)
    return image[y1:y2, x1:x2]


def random_augment(image: np.ndarray) -> np.ndarray:
    """Apply mild augmentations for training."""
    img = image.copy()

    if np.random.rand() < 0.3:
        img = cv2.flip(img, 1)

    brightness = 1.0 + (np.random.rand() * 0.4 - 0.2)
    contrast = 1.0 + (np.random.rand() * 0.4 - 0.2)
    img = np.clip(img * contrast + (brightness - 1.0) * 128.0, 0, 255).astype(np.uint8)

    noise = np.random.normal(0, 2.55, img.shape).astype(np.float32)
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    h, w = img.shape[:2]
    margin = int(min(h, w) * 0.05)
    x1 = np.random.randint(0, margin + 1)
    y1 = np.random.randint(0, margin + 1)
    x2 = w - np.random.randint(0, margin + 1)
    y2 = h - np.random.randint(0, margin + 1)
    img = cv2.resize(img[y1:y2, x1:x2], (224, 224))

    return img


def normalize_image(image: np.ndarray) -> np.ndarray:
    img = image.astype(np.float32) / 255.0
    img = (img - IMAGENET_MEAN) / IMAGENET_STD
    return img


def split_by_dot(samples: List[Sample]) -> Tuple[List[Sample], List[Sample]]:
    train: List[Sample] = []
    val: List[Sample] = []
    samples_by_dot: Dict[int, List[Sample]] = {}
    for s in samples:
        samples_by_dot.setdefault(s.dot_index, []).append(s)

    for dot_index, dot_samples in samples_by_dot.items():
        np.random.shuffle(dot_samples)
        split_idx = int(len(dot_samples) * 0.8)
        train.extend(dot_samples[:split_idx])
        val.extend(dot_samples[split_idx:])
    return train, val


def compute_stats(images: List[np.ndarray]) -> Dict[str, object]:
    if not images:
        return {"mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0]}
    stacked = np.stack([img.astype(np.float32) / 255.0 for img in images], axis=0)
    mean = stacked.mean(axis=(0, 1, 2)).tolist()
    std = stacked.std(axis=(0, 1, 2)).tolist()
    return {"mean": mean, "std": std}


def load_labels() -> List[Dict[str, str]]:
    if not LABELS_PATH.exists():
        raise FileNotFoundError("labels.csv not found; run gaze_recorder.py first")
    rows: List[Dict[str, str]] = []
    try:
        with LABELS_PATH.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as exc:
        raise RuntimeError("Failed to read labels.csv") from exc
    return rows


def main() -> None:
    print("🚀 Preparing dataset")
    if not FACE_TASK_PATH.exists():
        raise FileNotFoundError("face_landmarker.task not found in project folder")

    try:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError("Failed to create processed directory") from exc

    detector = FaceDetector(FACE_TASK_PATH)
    rows = load_labels()

    processed_samples: List[Sample] = []
    removed = 0
    raw_images_for_stats: List[np.ndarray] = []

    for row in rows:
        frame_path = FRAMES_DIR / row["filename"]
        if not frame_path.exists():
            removed += 1
            continue

        try:
            frame = cv2.imread(str(frame_path))
        except Exception:
            removed += 1
            continue

        if frame is None:
            removed += 1
            continue

        result = detector.detect(frame)
        if result is None or not result.face_landmarks:
            removed += 1
            continue

        landmarks = result.face_landmarks[0]
        h, w = frame.shape[:2]
        bbox = compute_bbox(landmarks, w, h)
        face_crop = crop_face(frame, bbox)
        if face_crop.size == 0:
            removed += 1
            continue

        face_crop = cv2.resize(face_crop, (224, 224))
        face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)

        yaw = float(row["yaw_angle"])
        pitch = float(row["pitch_angle"])
        yaw_bin = angle_to_bin(yaw, 0.5, 1.0)
        pitch_bin = angle_to_bin(pitch, 0.3, 0.6)

        raw_images_for_stats.append(face_rgb)

        processed_samples.append(
            Sample(
                image=face_rgb,
                yaw=yaw,
                pitch=pitch,
                yaw_bin=yaw_bin,
                pitch_bin=pitch_bin,
                dot_index=int(row["dot_index"]),
                frame_path=str(frame_path),
            )
        )

    train_samples, val_samples = split_by_dot(processed_samples)

    # Apply augmentations to training samples only
    augmented_train: List[Sample] = []
    for sample in train_samples:
        img = sample.image.copy()
        flipped = False
        if np.random.rand() < 0.3:
            img = cv2.flip(img, 1)
            flipped = True
        img = random_augment(img)
        yaw = -sample.yaw if flipped else sample.yaw
        yaw_bin = angle_to_bin(yaw, 0.5, 1.0)
        augmented_train.append(
            Sample(
                image=img,
                yaw=yaw,
                pitch=sample.pitch,
                yaw_bin=yaw_bin,
                pitch_bin=sample.pitch_bin,
                dot_index=sample.dot_index,
                frame_path=sample.frame_path,
            )
        )

    def serialize_samples(samples: List[Sample]) -> List[Dict[str, object]]:
        serialized: List[Dict[str, object]] = []
        for sample in samples:
            img_norm = normalize_image(sample.image)
            serialized.append(
                {
                    "image": img_norm.astype(np.float32),
                    "yaw": sample.yaw,
                    "pitch": sample.pitch,
                    "yaw_bin": sample.yaw_bin,
                    "pitch_bin": sample.pitch_bin,
                    "dot_index": sample.dot_index,
                    "frame_path": sample.frame_path,
                }
            )
        return serialized

    train_serialized = serialize_samples(augmented_train)
    val_serialized = serialize_samples(val_samples)

    try:
        with TRAIN_PKL.open("wb") as f:
            pickle.dump(train_serialized, f)
        with VAL_PKL.open("wb") as f:
            pickle.dump(val_serialized, f)
    except Exception as exc:
        raise RuntimeError("Failed to write dataset pickle files") from exc

    stats = compute_stats(raw_images_for_stats)
    dot_counts = [0] * 9
    for sample in processed_samples:
        dot_counts[sample.dot_index] += 1

    stats.update(
        {
            "total_samples": len(processed_samples),
            "train_samples": len(train_serialized),
            "val_samples": len(val_serialized),
            "removed": removed,
            "samples_per_dot": dot_counts,
            "yaw_range": [-0.30, 0.30],
            "pitch_range": [-0.20, 0.20],
        }
    )

    try:
        with STATS_JSON.open("w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception as exc:
        print(f"⚠ Failed to write stats: {exc}")

    print("✓ Dataset prepared")
    print(
        f"Total samples: {len(processed_samples)} | Train: {len(train_serialized)} | Val: {len(val_serialized)} | Removed: {removed}"
    )
    print(f"Samples per dot: {dot_counts}")
    print("Angle ranges — Yaw: [-0.30, +0.30] rad | Pitch: [-0.20, +0.20] rad")


class PersonalGazeDataset(torch.utils.data.Dataset):
    """Dataset for loading preprocessed gaze samples from pickle files."""

    def __init__(self, pkl_path: Path) -> None:
        self.pkl_path = pkl_path
        self.samples = self._load_samples()

    def _load_samples(self) -> List[Dict[str, object]]:
        try:
            with self.pkl_path.open("rb") as f:
                return pickle.load(f)
        except Exception as exc:
            raise RuntimeError("Failed to load dataset pickle") from exc

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, object]:
        sample = self.samples[idx]
        image = torch.tensor(sample["image"], dtype=torch.float32).permute(2, 0, 1)
        return {
            "image": image,
            "yaw": float(sample["yaw"]),
            "pitch": float(sample["pitch"]),
            "yaw_bin": int(sample["yaw_bin"]),
            "pitch_bin": int(sample["pitch_bin"]),
            "dot_index": int(sample["dot_index"]),
            "frame_path": str(sample["frame_path"]),
        }


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"✗ Fatal error: {exc}")

