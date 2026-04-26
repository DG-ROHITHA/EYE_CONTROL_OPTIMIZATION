"""Append training dependencies to requirements_cuda.txt."""

from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).parent
REQ_PATH = BASE_DIR / "requirements_cuda.txt"

BLOCK = """
# ==========================================
# PERSONAL GAZE MODEL TRAINING DEPENDENCIES
# (appended by setup_deps.py)
# ==========================================
torch>=2.0.0               # PyTorch deep learning
torchvision>=0.15.0        # ResNet-18 pre-trained weights
onnx>=1.15.0               # ONNX model format
onnxruntime-gpu>=1.16.0    # ONNX Runtime with CUDA
Pillow>=10.0.0             # Image loading/saving
""".lstrip()


def main() -> None:
    if not REQ_PATH.exists():
        raise FileNotFoundError("requirements_cuda.txt not found")

    try:
        current = REQ_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        raise RuntimeError("Failed to read requirements_cuda.txt") from exc

    if "PERSONAL GAZE MODEL TRAINING DEPENDENCIES" in current:
        print("⚠ Dependencies already appended")
        return

    try:
        with REQ_PATH.open("a", encoding="utf-8") as f:
            f.write("\n" + BLOCK)
    except Exception as exc:
        raise RuntimeError("Failed to append dependencies") from exc

    print("✓ Appended training dependencies to requirements_cuda.txt")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"✗ Fatal error: {exc}")

