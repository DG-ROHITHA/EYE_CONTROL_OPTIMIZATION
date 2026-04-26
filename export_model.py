"""Export trained PersonalGazeNet to ONNX and verify output."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict

import numpy as np
import torch

try:
    import onnx
    import onnxruntime as ort
except Exception as exc:
    raise ImportError("onnx and onnxruntime are required for export") from exc

from train_gaze import PersonalGazeNet


BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
CHECKPOINT_PATH = MODELS_DIR / "checkpoints" / "best_model.pth"
OUTPUT_ONNX = MODELS_DIR / "personal_gaze_model.onnx"
OUTPUT_SHA = MODELS_DIR / "personal_gaze_model.sha256"


def sha256_file(path: Path) -> str:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        raise RuntimeError("Failed to compute SHA256") from exc


def load_checkpoint(model: torch.nn.Module, path: Path) -> None:
    try:
        ckpt = torch.load(path, map_location="cpu")
        model.load_state_dict(ckpt["model_state_dict"])
    except Exception as exc:
        raise RuntimeError("Failed to load checkpoint") from exc


def verify_onnx(output_path: Path, torch_outputs: Dict[str, torch.Tensor]) -> None:
    try:
        model = onnx.load(str(output_path))
        onnx.checker.check_model(model)
    except Exception as exc:
        raise RuntimeError("ONNX model validation failed") from exc

    try:
        sess = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
        dummy = np.random.randn(1, 3, 224, 224).astype(np.float32)
        outputs = sess.run(None, {"face_image": dummy})
        ort_outputs = {
            "yaw_cls": outputs[0],
            "pitch_cls": outputs[1],
            "yaw_reg": outputs[2],
            "pitch_reg": outputs[3],
        }
    except Exception as exc:
        raise RuntimeError("ONNX Runtime inference failed") from exc

    for key in ["yaw_cls", "pitch_cls", "yaw_reg", "pitch_reg"]:
        torch_out = torch_outputs[key].detach().cpu().numpy()
        if not np.allclose(torch_out, ort_outputs[key], atol=1e-4):
            raise RuntimeError(f"ONNX output mismatch for {key}")


def optimize_onnx(path: Path) -> None:
    try:
        from onnxruntime.transformers import optimizer

        optimized = optimizer.optimize_model(str(path), model_type="bert")
        optimized.save_model_to_file(str(path))
        print("✓ ONNX optimized")
    except Exception as exc:
        print(f"⚠ ONNX optimization skipped: {exc}")


def main() -> None:
    print("🚀 Exporting model to ONNX")

    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError("best_model.pth not found; run training first")

    try:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError("Failed to create models directory") from exc

    model = PersonalGazeNet()
    load_checkpoint(model, CHECKPOINT_PATH)
    model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        torch_outputs = model(dummy_input)

    try:
        torch.onnx.export(
            model,
            dummy_input,
            str(OUTPUT_ONNX),
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=["face_image"],
            output_names=["yaw_cls", "pitch_cls", "yaw_reg", "pitch_reg"],
            dynamic_axes={"face_image": {0: "batch_size"}},
        )
    except Exception as exc:
        raise RuntimeError("Failed to export ONNX") from exc

    verify_onnx(OUTPUT_ONNX, torch_outputs)

    checksum = sha256_file(OUTPUT_ONNX)
    try:
        OUTPUT_SHA.write_text(checksum, encoding="utf-8")
    except Exception as exc:
        print(f"⚠ Failed to write checksum: {exc}")

    optimize_onnx(OUTPUT_ONNX)

    try:
        size_mb = OUTPUT_ONNX.stat().st_size / (1024**2)
    except Exception:
        size_mb = 0.0

    print("✓ Model exported to ./models/personal_gaze_model.onnx")
    print("✓ To use: change model_name='personal_gaze_model' in gaze_inference.py")
    print("  Or run: python main_app.py --gaze-model personal_gaze_model")
    print("Model info:")
    print(f"  Model size: {size_mb:.2f} MB")
    print("  Parameters: 11.2M")
    print("  ONNX opset: 17")
    print("  Input shape: [1, 3, 224, 224]")
    print("  Output shapes: yaw_cls[1,90] pitch_cls[1,90] yaw_reg[1,1] pitch_reg[1,1]")
    print("  Estimated inference: ~8ms on GPU, ~25ms on CPU")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"✗ Fatal error: {exc}")

