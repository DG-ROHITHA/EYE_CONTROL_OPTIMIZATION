"""
NeuroGaze Elite Integration Smoke Test (Standalone)
Runs a 60-second synthetic pipeline to validate imports, shapes, and latency.

Usage:
  python test_integration.py

benchmark: ~60s runtime, prints average latency and FPS
"""

from __future__ import annotations

import time
import numpy as np
import logging

from pipeline import CUDAPipeline
from smoother import KalmanGaze
from intent import IntentEngine, CommandGatekeeper
from eye_health import StrainGuard, StrainGuardConfig
from hand_engine import HandGestureEngine
from gaze_inference import DLInferenceEngine


def run_integration_test(duration_s: int = 60) -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("integration_test")

    logger.info("Initializing modules...")
    cuda = CUDAPipeline(enable_cuda=True)
    kalman = KalmanGaze(screen_width=1280, screen_height=720, use_adaptive=True, use_gpu=True)
    intent = IntentEngine()
    gatekeeper = CommandGatekeeper()
    strain = StrainGuard(StrainGuardConfig())
    hand_engine = HandGestureEngine(enable_gpu=True)
    dl_engine = DLInferenceEngine(model_name="l2cs-net-gaze360", enable_gpu=True)

    logger.info("Starting 60s synthetic loop...")
    start = time.time()
    frame_count = 0
    latencies = []

    while time.time() - start < duration_s:
        frame_start = time.time()

        # Synthetic frame (720p)
        frame = (np.random.rand(720, 1280, 3) * 255).astype(np.uint8)

        # CUDA preprocessing
        processed = cuda.process_frame(frame)

        # Simulated gaze (center + noise)
        gaze_x = 640 + np.random.randn() * 5
        gaze_y = 360 + np.random.randn() * 5
        kalman_state = kalman.update_gaze(gaze_x, gaze_y)

        # Intent analysis
        dwell_ms = intent.update_dwell(kalman_state.position)
        intent.analyze_intent(kalman_state.velocity, kalman_state.position, dwell_ms)

        # Strain update (simulate EAR)
        strain.update(0.25 + np.random.randn() * 0.01)

        # Hand engine (likely returns no hands, but should not crash)
        hand_engine.process_frame(frame)

        # DL inference (only if model loaded)
        if dl_engine.model_loaded:
            dl_engine.infer(frame, head_pose_euler=(0.0, 0.0, 0.0))

        frame_end = time.time()
        frame_time = frame_end - frame_start
        latencies.append(frame_time * 1000)
        frame_count += 1

    avg_latency = float(np.mean(latencies)) if latencies else 0.0
    fps = frame_count / duration_s

    logger.info("Integration test complete")
    logger.info(f"Frames: {frame_count}")
    logger.info(f"Avg latency: {avg_latency:.2f}ms")
    logger.info(f"Avg FPS: {fps:.1f}")


if __name__ == "__main__":
    run_integration_test(60)

