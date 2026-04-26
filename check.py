#!/usr/bin/env python3
"""
check.py - NeuroGaze Elite startup health check
Run this first to verify your system is ready.
Usage: python check.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent
PASS = "OK"
FAIL = "FAIL"
WARN = "WARN"

results = []


def check(label: str, ok: bool, detail: str = "", warn: bool = False) -> None:
    symbol = PASS if ok else (WARN if warn else FAIL)
    color = "\033[92m" if ok else ("\033[93m" if warn else "\033[91m")
    reset = "\033[0m"
    line = f"  {color}{symbol}{reset} {label}"
    if detail:
        line += f" - {detail}"
    print(line)
    results.append(ok or warn)


print("\nNeuroGaze Elite - System Check")
print("-" * 40)

# 1. Python version
py_ok = sys.version_info >= (3, 9)
check("Python version", py_ok, f"{sys.version.split()[0]}" + ("" if py_ok else " (need 3.9+)"))

# 2. OpenCV
try:
    import cv2
    cuda_count = 0
    try:
        cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
    except Exception:
        pass
    cv_detail = f"v{cv2.__version__} | CUDA devices: {cuda_count}"
    check("OpenCV", True, cv_detail)
except ImportError:
    check("OpenCV", False, "pip install opencv-contrib-python")

# 3. MediaPipe
try:
    import mediapipe
    check("MediaPipe", True, f"v{mediapipe.__version__}")
except ImportError:
    check("MediaPipe", False, "pip install mediapipe")

# 4. PyTorch + CUDA
try:
    import torch
    cuda_ok = torch.cuda.is_available()
    if cuda_ok:
        gpu = torch.cuda.get_device_name(0)
        mem = torch.cuda.get_device_properties(0).total_memory // (1024**3)
        detail = f"v{torch.__version__} | GPU: {gpu} ({mem}GB)"
    else:
        detail = f"v{torch.__version__} | No CUDA GPU - CPU mode only"
    check("PyTorch", True, detail, warn=not cuda_ok)
except ImportError:
    check("PyTorch", False, "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121", warn=True)

# 5. CuPy (optional but recommended)
try:
    import cupy
    check("CuPy (GPU Kalman)", True, f"v{cupy.__version__}")
except ImportError:
    check("CuPy (GPU Kalman)", True, "not installed - CPU Kalman will be used (acceptable)", warn=True)

# 6. face_landmarker.task
task_path = BASE / "face_landmarker.task"
check(
    "face_landmarker.task",
    task_path.exists(),
    str(task_path) if task_path.exists() else
    "MISSING - download from: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

# 7. hand_landmarker.task (optional)
hand_path = BASE / "hand_landmarker.task"
check(
    "hand_landmarker.task (hand gestures)",
    hand_path.exists(),
    "found" if hand_path.exists() else
    "not found - hand gestures disabled. curl -L [URL] -o hand_landmarker.task",
    warn=not hand_path.exists()
)

# 8. Personal gaze model
model_path = BASE / "models" / "personal_gaze_model.onnx"
check(
    "personal_gaze_model.onnx",
    model_path.exists(),
    "found" if model_path.exists() else
    "not trained yet - run: python gaze_recorder.py",
    warn=not model_path.exists()
)

# 9. Camera
try:
    import cv2
    cap = cv2.VideoCapture(0)
    cam_ok = cap.isOpened()
    if cam_ok:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        check("Camera (index 0)", True, f"{w}x{h}")
    else:
        cap.release()
        check("Camera (index 0)", False, "not found - check USB connection or set camera.index in config.yaml")
except Exception as e:
    check("Camera", False, str(e))

# 10. config.yaml
cfg_path = BASE / "config.yaml"
check(
    "config.yaml",
    cfg_path.exists(),
    "found" if cfg_path.exists() else
    "not found - defaults will be used (acceptable)",
    warn=not cfg_path.exists()
)

# 11. PyAutoGUI
try:
    import pyautogui
    check("PyAutoGUI (live commands)", True, f"v{pyautogui.__version__}")
except ImportError:
    check("PyAutoGUI", False, "pip install pyautogui", warn=True)

# 12. ONNX Runtime
try:
    import onnxruntime as ort
    providers = ort.get_available_providers()
    gpu = "CUDAExecutionProvider" in providers
    check("ONNX Runtime", True, f"v{ort.__version__} | {'GPU OK' if gpu else 'CPU only'}", warn=not gpu)
except ImportError:
    check("ONNX Runtime", True, "not installed - neural gaze validation disabled (acceptable)", warn=True)

# Summary
print("-" * 40)
passed = sum(1 for r in results if r)
total = len(results)
print(f"\n  {passed}/{total} checks passed")
if passed == total:
    print("  All good! Run: python main.py --simulate")
elif passed >= total - 3:
    print("  Minor warnings only. Run: python main.py --simulate")
else:
    print("  Fix the FAIL errors above before running.")
print()
