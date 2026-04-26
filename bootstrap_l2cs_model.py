"""
Bootstrap L2CS-Net PyTorch weights for NeuroGaze Elite.
Downloads L2CSNet_gaze360.pkl to ~/.neurogaze/models/ and verifies SHA256.

Usage:
    python bootstrap_l2cs_model.py --url <MODEL_URL> --sha256 <HASH>

benchmark: ~20 minutes end-to-end with model download
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        import requests

        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return
    except Exception:
        pass

    # Fallback to urllib
    from urllib import request

    with request.urlopen(url, timeout=30) as resp:
        with dest.open("wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)


def _extract_gdrive_id(url: str) -> str:
    if "drive.google.com" not in url:
        return ""
    if "/file/d/" in url:
        return url.split("/file/d/")[1].split("/")[0]
    if "id=" in url:
        return url.split("id=")[1].split("&")[0]
    return ""


def bootstrap_l2cs_model(url: str, sha256_hash: str, model_name: str) -> Path:
    models_dir = Path.home() / ".neurogaze" / "models"
    model_path = models_dir / "L2CSNet_gaze360.pkl"
    sha_path = model_path.with_suffix(".sha256")

    logger.info(f"Downloading {model_name} from {url}")
    gdrive_id = _extract_gdrive_id(url)
    if gdrive_id:
        try:
            import gdown

            gdown.download(id=gdrive_id, output=str(model_path), quiet=False)
        except Exception:
            _download(url, model_path)
    else:
        _download(url, model_path)

    actual = _sha256(model_path)
    if actual.lower() != sha256_hash.lower():
        model_path.unlink(missing_ok=True)
        raise ValueError(f"SHA256 mismatch: expected {sha256_hash}, got {actual}")

    sha_path.write_text(f"{actual}  {model_path.name}\n", encoding="utf-8")
    logger.info(f"✓ Model downloaded and verified: {model_path}")
    return model_path


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Download L2CS-Net ONNX model")
    parser.add_argument("--url", required=True, help="Direct URL to L2CS-Net ONNX")
    parser.add_argument("--sha256", required=True, help="Expected SHA256 hash")
    parser.add_argument("--model-name", default="l2cs-net-gaze360", help="Model name (unused for pkl, kept for compatibility)")
    args = parser.parse_args(argv)

    try:
        bootstrap_l2cs_model(args.url, args.sha256, args.model_name)
        return 0
    except Exception as exc:
        logger.error(f"Bootstrap failed: {exc}")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
