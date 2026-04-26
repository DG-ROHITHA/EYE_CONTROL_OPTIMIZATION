# NeuroGaze

NeuroGaze is a camera-based assistive control system for hands-free computer interaction. It combines eye tracking, blink intent detection, hand gestures, and eye-hand fusion to improve safety and reduce accidental commands.

The project supports both simulation mode (safe, no system input) and execution mode (real mouse/keyboard actions).

## Core Capabilities

- Eye tracking with MediaPipe Face Landmarker
- Optional GPU-accelerated preprocessing with OpenCV CUDA
- Kalman-based gaze smoothing and velocity tracking
- Intent gating using dwell and movement analysis
- Eye strain monitoring (blink rate, PERCLOS, break reminders)
- Hand gesture recognition and eye-hand fusion modes
- Command worker process for non-blocking system actions
- On-screen HUD with standard, minimal, and debug modes
- User profile persistence and calibration workflows

## Project Entry Point

Primary launcher:

- main.py (recommended)

Equivalent direct launcher:

- main_app.py

## Requirements

- Windows, Linux, or macOS
- Python 3.8+
- Webcam
- MediaPipe face model file: face_landmarker.task in project root

Install dependencies:

	pip install -r requirements_cuda.txt

If you want a CPU-only lightweight install for quick testing:

	pip install opencv-python mediapipe numpy pyautogui sounddevice

## Quick Start

From the project root:

	python main.py

This starts in simulation mode by default when app.simulation_mode is true in config.yaml.

### Useful CLI Flags

- --no-gpu: disable CUDA path and force CPU processing
- --live: start with live mode enabled in UI state
- --execute: enable real command execution (not simulation)
- --simulate: force simulation mode
- --hud minimal|standard|debug: set initial HUD mode

Examples:

	python main.py --no-gpu --hud debug
	python main.py --execute --live

## Keyboard Controls

- C: start 5-point gaze calibration
- M: toggle live/simulation mode
- H: toggle gaze heatmap
- B: toggle blue-light filter overlay
- G: toggle gesture overlay
- F: cycle fusion mode
- R: reset heatmap and strain counters
- Space: cycle HUD mode (minimal, standard, debug)
- Esc: exit

## Configuration

Main runtime configuration is in config.yaml. Key sections:

- camera: webcam index and resolution
- gaze: smoothing and dwell behavior
- intent: confidence and velocity thresholds
- calibration: profile and startup calibration behavior
- strain: eye-health thresholds and break timing
- hand_gestures: enable flag and fusion mode
- caregiver: optional alert routing
- app: simulation mode, HUD mode, logging

Gesture command mappings are in gestures.yaml.

## Safety Notes

- Keep simulation mode enabled while tuning settings.
- Switch to execution mode only after calibration and validation.
- If used for assistive care workflows, test emergency gestures with a caregiver present.
- Recalibrate when camera position, seating position, or lighting changes.

## Training a Personal Gaze Model

Current training flow:

1. Collect data:
	 python gaze_recorder.py
2. Prepare dataset:
	 python prep_data.py
3. Train model:
	 python train_gaze.py
4. Export model:
	 python export_model.py
5. Validate model:
	 python check_model.py

Model artifacts are expected in the models directory and/or user model cache paths used by gaze_inference.py.

## Validation and Tests

Smoke/integration test:

	python test_integration.py

Legacy optimization checks:

	python test_perf.py

## Important Files

- main.py: top-level launcher
- main_app.py: full NeuroGaze runtime
- config.yaml: runtime settings
- gestures.yaml: gesture-to-command mapping
- pipeline.py: CUDA/CPU preprocessing pipeline
- gaze_inference.py: DL-based secondary gaze validation
- hand_engine.py: hand gesture recognition
- fusion.py: eye-hand fusion logic
- eye_health.py: strain and fatigue monitoring
- worker.py: command execution worker process
- HOW_TO_TRAIN.md: model training notes
- CHEATSHEET.txt: quick operator reference

## Troubleshooting

- No camera feed:
	check camera index in config.yaml (camera.index) and close other camera apps.
- Face model not found:
	ensure face_landmarker.task exists in project root.
- Low FPS:
	run with --no-gpu if CUDA setup is unstable, reduce camera resolution in config.yaml.
- Commands not executing:
	verify simulation mode is off (app.simulation_mode false or use --execute).
- Gesture mappings not matching expectations:
	review gestures.yaml and restart app.

## Notes on Legacy Scripts

This repository contains older scripts (for example eye_control_assistive.py and eye_control_optimized.py) kept for experimentation and comparison. The current production path is main.py -> main_app.py.

