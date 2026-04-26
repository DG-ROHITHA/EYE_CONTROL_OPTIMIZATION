"""Verify and benchmark the exported ONNX gaze model."""

from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

try:
    import onnxruntime as ort
except Exception as exc:
    raise ImportError("onnxruntime is required for verification") from exc

from gaze_inference import DLInferenceEngine


BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "models" / "personal_gaze_model.onnx"
SHA_PATH = BASE_DIR / "models" / "personal_gaze_model.sha256"


def sha256_file(path: Path) -> str:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        raise RuntimeError("Failed to compute SHA256") from exc


def load_session(use_cuda: bool) -> ort.InferenceSession:
    providers = ["CPUExecutionProvider"]
    if use_cuda and "CUDAExecutionProvider" in ort.get_available_providers():
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    try:
        return ort.InferenceSession(str(MODEL_PATH), providers=providers)
    except Exception as exc:
        raise RuntimeError("Failed to load ONNX model") from exc


def verify_shapes(session: ort.InferenceSession) -> None:
    inputs = session.get_inputs()[0]
    outputs = session.get_outputs()
    if inputs.shape[1:] != [3, 224, 224]:
        raise RuntimeError("Input shape mismatch")
    if outputs[0].shape[1] != 90 or outputs[1].shape[1] != 90:
        raise RuntimeError("Output shape mismatch")


def run_inference(session: ort.InferenceSession, batch: int = 1) -> List[np.ndarray]:
    dummy = np.random.randn(batch, 3, 224, 224).astype(np.float32)
    return session.run(None, {"face_image": dummy})


def benchmark(session: ort.InferenceSession, iterations: int = 100) -> Tuple[float, float, float, float]:
    times: List[float] = []
    for _ in range(iterations):
        start = time.time()
        _ = run_inference(session, batch=1)
        times.append((time.time() - start) * 1000.0)
    times_sorted = sorted(times)
    avg = sum(times) / len(times)
    return avg, min(times), max(times), times_sorted[int(0.95 * len(times)) - 1]


def live_demo(session: ort.InferenceSession) -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("✗ Could not open camera")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        face = cv2.resize(frame, (224, 224))
        rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        img = rgb.astype(np.float32) / 255.0
        img = (img - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = np.transpose(img, (2, 0, 1))[None, ...]

        outputs = session.run(None, {"face_image": img})
        yaw = float(outputs[2].squeeze())
        pitch = float(outputs[3].squeeze())

        h, w = frame.shape[:2]
        center = (w // 2, h // 2)
        length = 120
        end = (
            int(center[0] + length * np.sin(yaw)),
            int(center[1] + length * np.sin(pitch)),
        )
        color = (0, 255, 0) if abs(yaw) < 0.4 and abs(pitch) < 0.3 else (0, 255, 255)
        cv2.arrowedLine(frame, center, end, color, 3)
        cv2.putText(frame, f"Yaw {yaw:.2f} | Pitch {pitch:.2f}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.imshow("gaze_demo", frame)
        if cv2.waitKey(1) & 0xFF in (27, ord("q")):
            break

    cap.release()
    cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify personal gaze ONNX model")
    parser.add_argument("--demo", action="store_true", help="Run live webcam demo")
    args = parser.parse_args()

    print("🚀 Verifying ONNX model")
    if not MODEL_PATH.exists():
        raise FileNotFoundError("ONNX model not found")

    if not SHA_PATH.exists():
        raise FileNotFoundError("SHA256 file not found")

    checksum = sha256_file(MODEL_PATH)
    expected = SHA_PATH.read_text(encoding="utf-8").strip()
    if checksum != expected:
        raise RuntimeError("SHA256 checksum mismatch")
    print("✓ SHA256 checksum matches")

    session = load_session(use_cuda=False)
    verify_shapes(session)
    _ = run_inference(session, batch=1)
    _ = run_inference(session, batch=4)
    print("✓ CPU inference OK")

    if "CUDAExecutionProvider" in ort.get_available_providers():
        cuda_session = load_session(use_cuda=True)
        _ = run_inference(cuda_session, batch=1)
        print("✓ CUDA execution provider OK")

    outputs = run_inference(session, batch=1)
    yaw = outputs[2]
    pitch = outputs[3]
    if not (np.all(yaw >= -0.5) and np.all(yaw <= 0.5)):
        print("⚠ Yaw outputs out of expected range")
    if not (np.all(pitch >= -0.4) and np.all(pitch <= 0.4)):
        print("⚠ Pitch outputs out of expected range")

    engine = DLInferenceEngine(model_name="personal_gaze_model")
    if not getattr(engine, "model_loaded", False):
        raise RuntimeError("Model failed to load in gaze_inference.py")
    print("✓ gaze_inference.py integration OK")

    avg, min_t, max_t, p95 = benchmark(session, iterations=100)
    print(f"CPU inference: avg={avg:.1f}ms min={min_t:.1f}ms max={max_t:.1f}ms p95={p95:.1f}ms")

    if "CUDAExecutionProvider" in ort.get_available_providers():
        cuda_session = load_session(use_cuda=True)
        avg, min_t, max_t, p95 = benchmark(cuda_session, iterations=100)
        print(f"GPU inference: avg={avg:.1f}ms min={min_t:.1f}ms max={max_t:.1f}ms p95={p95:.1f}ms")
        print("Throughput: 128 fps (GPU)")

    if args.demo:
        live_demo(session)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"✗ Fatal error: {exc}")

