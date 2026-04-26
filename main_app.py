"""
NeuroGaze Elite - Advanced Eye-Controlled Assistive Device
Production-grade eye-tracking system with GPU acceleration, strain monitoring, and adaptive intent detection
Part of the NeuroGaze Elite comprehensive rebuild
"""

import os
import time
import logging
import argparse
import platform
from pathlib import Path
from typing import Optional, Tuple, Dict
from collections import deque
from dataclasses import dataclass, field

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# Import all NeuroGaze Elite modules
from pipeline import CUDAPipeline
from eye_health import StrainGuard, StrainGuardConfig
from calibration import AdaptiveEARCalibrator, UserProfileManager, CalibrationScreenManager
from smoother import KalmanGaze, KalmanState
from intent import IntentEngine, CommandGatekeeper, IntentLevel
from worker import CommandWorkerProcess, CommandType, cross_platform_beep
from hud import HUDRenderer, HUDMode
from gaze_inference import DLInferenceEngine, CrossValidationResult

# Hand gesture modules
from hand_engine import HandGestureEngine, GestureConfig as HandGestureConfig
from fusion import GazeFusionEngine, FusionConfig, FusionMode, IntentScore as FusionIntentScore
from hand_calibration import HandProfileCalibrator, CalibrationState
from hand_hud import GestureHUDRenderer, GestureDisplayInfo, HUDMode as GestureHUDMode
from cmd_map import GestureCommandMapper

# Read log level from environment or default to INFO
_log_level = os.environ.get("NEUROGAZE_LOG_LEVEL", "INFO").upper()
_handlers = [logging.StreamHandler()]
_file_handler_error = None
try:
    _log_path = Path(__file__).parent / "neurogaze.log"
    _handlers.append(logging.FileHandler(_log_path, mode="a", encoding="utf-8"))
except Exception as exc:
    _file_handler_error = str(exc)

logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=_handlers,
)
logger = logging.getLogger("neurogaze")
if _file_handler_error:
    logger.warning(f"File logging disabled: {_file_handler_error}")

try:
    import yaml
    _YAML_AVAILABLE = True
except Exception:
    _YAML_AVAILABLE = False

try:
    from caregiver_alerts import CaregiverAlertManager
    _CAREGIVER_AVAILABLE = True
    _CAREGIVER_IMPORT_ERROR = ""
except Exception as exc:
    _CAREGIVER_AVAILABLE = False
    _CAREGIVER_IMPORT_ERROR = str(exc)

if not _CAREGIVER_AVAILABLE:
    logger.debug(f"caregiver_alerts.py not found - caregiver alerts disabled ({_CAREGIVER_IMPORT_ERROR})")


@dataclass
class AppConfig:
    """App configuration defaults."""
    CAMERA_INDEX: int = 0
    DWELL_TIME: float = 1.2
    SMOOTHING_FRAMES: int = 3
    SIMULATION_MODE: bool = True


@dataclass
class AppState:
    """Runtime session tracking."""
    session_start_time: float = field(default_factory=time.time)
    commands_fired: int = 0
    commands_by_type: Dict[str, int] = field(default_factory=dict)
    fatigue_events: int = 0
    breaks_taken: int = 0
    last_microsleep: bool = False
    last_break_due: bool = False


def load_config_yaml(config_obj: AppConfig) -> AppConfig:
    """Load config.yaml and override Config dataclass fields."""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return config_obj
    if not _YAML_AVAILABLE:
        logger.warning("PyYAML not available; config.yaml ignored")
        return config_obj
    try:
        with config_path.open("r", encoding="utf-8") as f:
            yaml_cfg = yaml.safe_load(f) or {}

        cam = yaml_cfg.get("camera", {})
        config_obj.CAMERA_INDEX = cam.get("index", config_obj.CAMERA_INDEX)

        gaze = yaml_cfg.get("gaze", {})
        config_obj.DWELL_TIME = gaze.get("dwell_time", config_obj.DWELL_TIME)
        config_obj.SMOOTHING_FRAMES = gaze.get("smoothing_frames", config_obj.SMOOTHING_FRAMES)

        app = yaml_cfg.get("app", {})
        config_obj.SIMULATION_MODE = app.get("simulation_mode", config_obj.SIMULATION_MODE)

        logger.info(f"Config loaded from {config_path}")
    except Exception as exc:
        logger.warning(f"Could not load config.yaml: {exc} - using defaults")
    return config_obj


APP_CONFIG = load_config_yaml(AppConfig())

# Platform-specific flags
CV2_AVAILABLE = True  # OpenCV is required anyway, but check for safety


class NeuroGazeElite:
    """
    Main application class for NeuroGaze Elite.
    Integrates all modules and manages application lifecycle.
    """
    
    def __init__(
        self,
        enable_gpu: bool = True,
        enable_live_mode: bool = False,
        simulation_mode: bool = True,
        hud_mode: str = "standard",
        config: Optional[AppConfig] = None
    ):
        """
        Initialize NeuroGaze Elite.
        
        Args:
            enable_gpu: Try to use GPU/CUDA if available
            enable_live_mode: Start in live mode (vs simulation)
            simulation_mode: Mock mouse/keyboard (don't actually send commands)
            hud_mode: "minimal", "standard", or "debug"
        """
        logger.info("=" * 60)
        logger.info("🚀 NeuroGaze Elite - Initialization")
        logger.info("=" * 60)
        
        # Configuration
        self.config = config or APP_CONFIG
        self.enable_gpu = enable_gpu
        self.live_mode = enable_live_mode
        self.simulation_mode = simulation_mode
        self.running = True

        # Session state
        self.state = AppState()
        
        # Screen info
        try:
            import pyautogui
            self.screen_width, self.screen_height = pyautogui.size()
        except:
            self.screen_width, self.screen_height = 1920, 1080
        
        logger.info(f"Screen resolution: {self.screen_width}x{self.screen_height}")
        
        # Initialize core modules
        logger.info("\n📦 Initializing core modules...")
        
        # CUDA Pipeline (GPU preprocessing)
        self.cuda_pipeline = CUDAPipeline(enable_cuda=enable_gpu)
        
        # Camera
        self._init_camera()
        
        # MediaPipe FaceLandmarker (with GPU delegate if available)
        self._init_mediapipe()
        
        # Deep Learning Inference (secondary gaze validation with ONNX)
        self.dl_engine = DLInferenceEngine(
            model_name="l2cs-net-gaze360",
            agreement_threshold_px=15.0,
            enable_gpu=enable_gpu
        )
        
        # Gaze tracking (Kalman filter with velocity)
        self.gaze_tracker = KalmanGaze(
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            use_adaptive=True,
            use_gpu=enable_gpu
        )
        
        # Intent detection
        self.intent_engine = IntentEngine()
        self.command_gatekeeper = CommandGatekeeper()
        self.intent_engine.MIN_DELIBERATE_DWELL_MS = self.config.DWELL_TIME * 1000.0
        
        # Strain monitoring
        strain_config = StrainGuardConfig()
        self.strain_guard = StrainGuard(strain_config)
        
        # User profile management
        self.profile_manager = UserProfileManager()
        self.current_user_id = "default_user"
        self.current_profile = self.profile_manager.load_profile(self.current_user_id)
        
        if not self.current_profile:
            self.current_profile = self.profile_manager.create_new_profile(
                self.current_user_id,
                device_name=platform.platform()
            )
            self.profile_manager.save_profile(self.current_profile)
        
        # EAR Calibrator
        self.ear_calibrator = AdaptiveEARCalibrator()
        self.ear_threshold = self.current_profile.ear_threshold
        
        # Command execution (multiprocessing worker)
        self.command_worker = CommandWorkerProcess(
            enable_audio=True,
            enable_execution=not simulation_mode
        )
        self.command_worker.start()
        
        # HUD Renderer
        hud_mode_map = {
            "minimal": HUDMode.MINIMAL,
            "standard": HUDMode.STANDARD,
            "debug": HUDMode.DEBUG
        }
        self.hud_renderer = HUDRenderer(
            frame_width=int(self.camera_width),
            frame_height=int(self.camera_height),
            mode=hud_mode_map.get(hud_mode, HUDMode.STANDARD)
        )
        
        # Hand Gesture Modules (NEW: eye-hand fusion for safer control)
        logger.info("\n🖐️  Initializing hand gesture control...")
        
        # Hand gesture detection (MediaPipe Hands with GPU)
        hand_gesture_config = HandGestureConfig()
        self.hand_engine = HandGestureEngine(
            config=hand_gesture_config,
            enable_gpu=enable_gpu
        )
        
        # Gesture command mapper (YAML-driven mapping)
        self.gesture_mapper = GestureCommandMapper()
        
        # Hand-eye fusion engine (combines intent signals)
        fusion_config = FusionConfig(
            fusion_mode=FusionMode.EYE_LEADS_HAND_CONFIRMS  # Safest for paralysis patients
        )
        self.fusion_engine = GazeFusionEngine(fusion_config)
        
        # Hand calibration (per-user normalization)
        self.hand_calibrator = HandProfileCalibrator()
        self.hand_profile = self.hand_calibrator.load_profile(self.current_user_id)
        if not self.hand_profile:
            logger.info("ℹ️  No hand profile found; hand calibration required on first run (press 'H')")
        
        # Gesture HUD overlay renderer
        self.gesture_hud = GestureHUDRenderer(
            frame_width=int(self.camera_width),
            frame_height=int(self.camera_height),
            mode=GestureHUDMode.STANDARD
        )

        # Caregiver alerts (webhook + audio)
        self.caregiver = None
        if _CAREGIVER_AVAILABLE:
            try:
                self.caregiver = CaregiverAlertManager()
                logger.info("Caregiver alert system initialized")
            except Exception as exc:
                logger.warning(f"Caregiver alerts failed to init: {exc}")
        
        # Hand gesture state tracking
        self.hand_calibration_active = False
        self.gesture_overlay_visible = True
        self.current_gesture_result = None
        
        # State tracking
        self.frame_count = 0
        self.fps_history = deque(maxlen=30)
        self.last_frame_time = time.time()
        
        # Calibration state
        self.calibration_active = False
        self.calibration_manager: Optional[CalibrationScreenManager] = None
        
        # Performance monitoring
        self.perf_start_time = time.time()
        
        logger.info("✓ Initialization complete\n")
    
    def _init_camera(self) -> None:
        """Initialize camera"""
        logger.info("Initializing camera...")
        self.cap = self._open_camera(self.config.CAMERA_INDEX)
        self.camera_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.camera_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"✓ Camera initialized ({self.camera_width}x{self.camera_height})")

    def _open_camera(self, index: int, max_retries: int = 5) -> cv2.VideoCapture:
        """Open camera with retry loop. Critical for unattended assistive use."""
        for attempt in range(1, max_retries + 1):
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                logger.info(f"Camera {index} opened on attempt {attempt}")
                return cap
            logger.warning(f"Camera {index} not found (attempt {attempt}/{max_retries})")
            time.sleep(2)
        raise RuntimeError(
            f"Camera index {index} unavailable after {max_retries} attempts.\n"
            "Check: is the webcam plugged in? Try a different index in config.yaml."
        )
    
    def _init_mediapipe(self) -> None:
        """Initialize MediaPipe FaceLandmarker with GPU delegate if available"""
        logger.info("Initializing MediaPipe FaceLandmarker...")
        
        # Try to find face_landmarker.task
        model_candidates = [
            Path("face_landmarker.task"),
            Path(__file__).parent / "face_landmarker.task",
            Path.home() / ".neurogaze" / "face_landmarker.task",
            Path("R:/ROHI/webcame_dectection/face_landmarker.task"),  # Original path
        ]
        
        model_path = None
        for candidate in model_candidates:
            if candidate.exists():
                model_path = str(candidate)
                break
        
        if not model_path:
            logger.error(f"face_landmarker.task not found in common locations")
            logger.error(f"Checked: {[str(p) for p in model_candidates]}")
            raise RuntimeError("MediaPipe model not found")
        
        logger.info(f"Using model: {model_path}")
        
        # Initialize with GPU delegate if possible
        try:
            base_options = mp_python.BaseOptions(
                model_asset_path=model_path,
                delegate=mp_python.Delegate.GPU if self.enable_gpu else mp_python.Delegate.CPU
            )
            logger.info(f"GPU delegate requested (backend: {self.cuda_pipeline.backend.value})")
        except:
            base_options = mp_python.BaseOptions(model_asset_path=model_path)
            logger.info("GPU delegate not available, using CPU")
        
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1,
            running_mode=vision.RunningMode.IMAGE
        )
        
        self.face_landmarker = vision.FaceLandmarker.create_from_options(options)
        logger.info("✓ MediaPipe FaceLandmarker initialized")
    
    def _process_frame(self, frame: np.ndarray) -> Optional[vision.FaceLandmarkerResult]:
        """Process frame with MediaPipe"""
        # Preprocess with CUDA pipeline
        processed_frame = self.cuda_pipeline.process_frame(frame)
        
        # Detect face
        rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = self.face_landmarker.detect(mp_image)
        
        return results
    
    def _extract_gaze_position(self, face_landmarks) -> Optional[Tuple[float, float]]:
        """Extract gaze position from face landmarks"""
        try:
            # Iris center points
            left_iris = face_landmarks[468:469][0]
            right_iris = face_landmarks[473:474][0]
            
            # Average iris position
            iris_x = (left_iris.x + right_iris.x) / 2.0
            iris_y = (left_iris.y + right_iris.y) / 2.0
            
            # Convert to screen coordinates
            screen_x = iris_x * self.screen_width
            screen_y = iris_y * self.screen_height
            
            return screen_x, screen_y
        except:
            return None
    
    def _calculate_ear(self, face_landmarks) -> float:
        """Calculate Eye Aspect Ratio"""
        try:
            # Left eye landmarks
            left_eye = [face_landmarks[i] for i in [33, 160, 158, 133, 153, 144]]
            # Right eye landmarks
            right_eye = [face_landmarks[i] for i in [362, 385, 387, 263, 373, 380]]
            
            def calc_ear(eye_points):
                p1 = eye_points[1]
                p2 = eye_points[2]
                p3 = eye_points[4]
                p4 = eye_points[5]
                p5 = eye_points[0]
                p6 = eye_points[3]
                
                v1 = np.sqrt((p1.x - p5.x)**2 + (p1.y - p5.y)**2)
                v2 = np.sqrt((p2.x - p6.x)**2 + (p2.y - p6.y)**2)
                h = np.sqrt((p3.x - p4.x)**2 + (p3.y - p4.y)**2)
                
                return (v1 + v2) / (2.0 * h) if h > 0 else 0
            
            left_ear = calc_ear(left_eye)
            right_ear = calc_ear(right_eye)
            
            return (left_ear + right_ear) / 2.0
        except:
            return 0.5
    
    def _estimate_head_pose(self, face_landmarks) -> Tuple[float, float, float]:
        """
        Estimate head pose (pitch, yaw, roll) from face landmarks.
        Uses MediaPipe face landmarks for rough estimation.
        
        Returns:
            (pitch, yaw, roll) in radians
        """
        try:
            # Key landmarks for pose estimation
            # Nose tip: 1
            # Chin: 152
            # Left eye outer: 33
            # Right eye outer: 263
            # Left mouth: 61
            # Right mouth: 291
            
            nose = face_landmarks[1]
            chin = face_landmarks[152]
            left_eye = face_landmarks[33]
            right_eye = face_landmarks[263]
            
            # Simple vertical gaze (pitch) from nose to chin
            pitch = np.arctan2(chin.y - nose.y, chin.x - nose.x)
            
            # Horizontal gaze (yaw) from left to right eye
            yaw = np.arctan2(right_eye.x - left_eye.x, right_eye.y - left_eye.y)
            
            # Roll is harder without a full 3D model - estimate from eye level
            left_eye_y = face_landmarks[33].y
            right_eye_y = face_landmarks[263].y
            roll = np.arctan2(right_eye_y - left_eye_y, 1.0)
            
            return (pitch, yaw, roll)
        except:
            # Fallback to neutral pose
            return (0.0, 0.0, 0.0)

    def _enqueue_command(self, command_name: str) -> bool:
        """Enqueue a command using the gatekeeper, supporting older API names."""
        if hasattr(self.command_gatekeeper, "enqueue"):
            return bool(self.command_gatekeeper.enqueue(command_name))
        return bool(self.command_gatekeeper.add_command(command_name))

    def _handle_fusion_command(self, command_name: str) -> None:
        """Handle high-priority commands before queueing."""
        if command_name == "CANCEL_COMMAND":
            try:
                self.command_gatekeeper.queue.clear()
                self.command_gatekeeper.last_commands.clear()
            except Exception:
                pass
            return

        if command_name in {"EMERGENCY_ALERT", "CALL_NURSE"}:
            if command_name == "EMERGENCY_ALERT":
                logger.critical("EMERGENCY ALERT triggered")
            if self.caregiver is not None:
                try:
                    self.caregiver.send_alert(
                        alert_type=command_name,
                        severity="critical",
                        message="Emergency gesture detected",
                        metadata={"source": "hand_gesture"}
                    )
                except Exception as exc:
                    logger.error(f"Caregiver alert failed: {exc}")

        if self._enqueue_command(command_name):
            self.state.commands_fired += 1
            self.state.commands_by_type[command_name] = self.state.commands_by_type.get(command_name, 0) + 1
    
    def _handle_keyboard_input(self, key: int) -> bool:
        """
        Handle keyboard input.
        
        Returns:
            False if ESC pressed (exit signal)
        """
        if key == 27:  # ESC
            return False
        
        elif key == ord('c') or key == ord('C'):
            # Start calibration
            logger.info("Starting 5-point calibration...")
            self._start_calibration()
        
        elif key == ord('m') or key == ord('M'):
            # Toggle live/simulation mode
            self.live_mode = not self.live_mode
            logger.info(f"Mode: {'LIVE' if self.live_mode else 'SIMULATION'}")
        
        elif key == ord('h') or key == ord('H'):
            # Toggle heatmap
            self.hud_renderer.toggle_heatmap()
        
        elif key == ord('b') or key == ord('B'):
            # Toggle blue-light filter
            self.hud_renderer.toggle_blue_light_filter()
        
        elif key == ord('r') or key == ord('R'):
            # Reset session
            logger.info("Resetting session...")
            self.hud_renderer.reset_heatmap()
            self.strain_guard.reset_frame_counters()
        
        elif key == ord('g') or key == ord('G'):
            # Toggle gesture overlay (NEW)
            self.gesture_overlay_visible = not self.gesture_overlay_visible
            self.gesture_hud.toggle_landmarks()
            logger.info(f"Gesture overlay: {'visible' if self.gesture_overlay_visible else 'hidden'}")
        
        elif key == ord('f') or key == ord('F'):
            # Cycle fusion mode (NEW)
            modes = [
                FusionMode.EYE_LEADS_HAND_CONFIRMS,
                FusionMode.HAND_LEADS_EYE_CONFIRMS,
                FusionMode.PARALLEL,
                FusionMode.HAND_OVERRIDE
            ]
            current_idx = modes.index(self.fusion_engine.config.fusion_mode)
            next_mode = modes[(current_idx + 1) % len(modes)]
            self.fusion_engine.set_fusion_mode(next_mode)
            logger.info(f"Fusion mode: {next_mode.value}")
        
        elif key == ord(' '):
            # Toggle HUD mode
            modes = [HUDMode.MINIMAL, HUDMode.STANDARD, HUDMode.DEBUG]
            current_idx = modes.index(self.hud_renderer.mode)
            next_mode = modes[(current_idx + 1) % len(modes)]
            self.hud_renderer.set_mode(next_mode)
            logger.info(f"HUD mode: {next_mode.value}")
        
        return True
    
    def _start_calibration(self) -> None:
        """Start 5-point gaze calibration"""
        self.calibration_active = True
        self.calibration_manager = CalibrationScreenManager(
            self.screen_width, self.screen_height
        )
        logger.info("Calibration started - look at points on screen")
    
    def _process_calibration(
        self,
        raw_gaze_x: float,
        raw_gaze_y: float
    ) -> None:
        """Process calibration point"""
        if not self.calibration_active or not self.calibration_manager:
            return
        
        # Normalize gaze coordinates
        norm_x = raw_gaze_x / self.screen_width
        norm_y = raw_gaze_y / self.screen_height
        
        # Add sample to current point
        self.calibration_manager.add_gaze_sample(norm_x, norm_y)
        
        # Check if we should move to next point
        if self.frame_count % 100 == 0:  # Every ~3 seconds at 30fps
            if not self.calibration_manager.next_point():
                # Calibration complete
                self._finish_calibration()
    
    def _finish_calibration(self) -> None:
        """Finish calibration and update profile"""
        if not self.calibration_manager:
            return
        
        gaze_zones = self.calibration_manager.calculate_gaze_zones()
        
        if gaze_zones:
            self.profile_manager.update_profile_calibration(
                self.current_profile,
                ear_threshold=self.ear_threshold,
                quality_score=0.85,
                gaze_zones=gaze_zones
            )
            self.profile_manager.save_profile(self.current_profile)
            logger.info("✓ Calibration complete - profile updated")
        
        self.calibration_active = False
        self.calibration_manager = None
    
    def run(self) -> None:
        """Main application loop"""
        logger.info("\n" + "=" * 60)
        logger.info("🎯 Starting main loop")
        logger.info("=" * 60)
        logger.info("Controls:")
        logger.info("  C - Calibrate (5-point)")
        logger.info("  M - Toggle Live/Simulation mode")
        logger.info("  H - Toggle gaze heatmap")
        logger.info("  B - Toggle blue-light filter")
        logger.info("  G - Toggle gesture overlay")
        logger.info("  F - Cycle fusion mode (eye/hand/fused)")
        logger.info("  R - Reset session")
        logger.info("  SPACE - Cycle HUD modes")
        logger.info("  ESC - Exit")
        logger.info("=" * 60 + "\n")
        
        # Start strain guard session
        self.strain_guard.start_session()
        session_start = time.time()
        
        try:
            while self.running:
                frame_start = time.time()
                
                # Read frame
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Frame read failed - attempting camera reconnect...")
                    self.cap.release()
                    try:
                        self.cap = self._open_camera(self.config.CAMERA_INDEX)
                        self.camera_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        self.camera_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    except RuntimeError as exc:
                        logger.error(str(exc))
                        break
                    continue
                
                # Resize for processing
                frame = cv2.resize(frame, (int(self.camera_width), int(self.camera_height)))
                
                # Process with MediaPipe
                results = self._process_frame(frame)
                
                gaze_position = None
                gaze_velocity = None
                ear_value = 0.5
                intent_score = None
                
                if results and results.face_landmarks:
                    face_landmarks = results.face_landmarks[0]
                    
                    # Extract gaze
                    gaze_pos = self._extract_gaze_position(face_landmarks)
                    
                    if gaze_pos:
                        # Update Kalman tracker
                        kalman_state = self.gaze_tracker.update_gaze(gaze_pos[0], gaze_pos[1])
                        gaze_position = kalman_state.position
                        gaze_velocity = kalman_state.velocity
                        
                        # Deep Learning cross-validation (secondary gaze model)
                        # Extract head pose from face landmarks if available
                        head_pose_euler = self._estimate_head_pose(face_landmarks)
                        
                        # Run DL inference for secondary validation
                        dl_result = self.dl_engine.infer(
                            face_frame=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if CV2_AVAILABLE else frame,
                            head_pose_euler=head_pose_euler
                        )
                        
                        # Cross-validate DL vs MediaPipe
                        validation_result = self.dl_engine.cross_validate(
                            dl_result=dl_result,
                            mediapipe_point=gaze_pos,
                            screen_width=int(self.camera_width),
                            screen_height=int(self.camera_height)
                        )
                        
                        # Use consensus point if models disagree
                        if not validation_result.is_confident and dl_result is not None:
                            logger.warning(
                                f"⚠ Low DL-MP agreement: {validation_result.agreement_pixels:.1f}px "
                                f"(DL conf: {dl_result.confidence:.2f})"
                            )
                            # Flag for HUD display
                            gaze_position = validation_result.consensus_point
                        
                        # Calculate EAR (blink detection)
                        ear_value = self._calculate_ear(face_landmarks)
                        
                        # Update strain guard
                        strain_metrics = self.strain_guard.update(ear_value)
                        if strain_metrics.microsleep_detected and not self.state.last_microsleep:
                            self.state.fatigue_events += 1
                        self.state.last_microsleep = bool(strain_metrics.microsleep_detected)
                        if strain_metrics.break_due and not self.state.last_break_due:
                            self.state.breaks_taken += 1
                        self.state.last_break_due = bool(strain_metrics.break_due)
                        
                        # Intent analysis
                        dwell_duration_ms = self.intent_engine.update_dwell(gaze_position)
                        intent_score = self.intent_engine.analyze_intent(
                            current_velocity=gaze_velocity,
                            current_position=gaze_position,
                            dwell_duration_ms=dwell_duration_ms
                        )
                        
                        # Hand Gesture Detection & Fusion (NEW)
                        gesture_results = self.hand_engine.process_frame(frame)
                        gesture_result = gesture_results[0] if gesture_results else None
                        self.current_gesture_result = gesture_result
                        
                        # Process hand calibration if active
                        if self.hand_calibration_active and gesture_result:
                            hand_size = (
                                (gesture_result.hand.bounding_box[2] - gesture_result.hand.bounding_box[0])**2 +
                                (gesture_result.hand.bounding_box[3] - gesture_result.hand.bounding_box[1])**2
                            ) ** 0.5
                            self.hand_calibrator.add_sample(gesture_result.hand.landmarks, hand_size)
                        
                        # Fuse eye and hand signals
                        if intent_score:
                            fusion_intent = FusionIntentScore(
                                confidence=intent_score.confidence,
                                level=intent_score.level,
                                position=gaze_position,
                                velocity=gaze_velocity,
                                dwell_duration_ms=dwell_duration_ms
                            )
                        else:
                            fusion_intent = None
                        
                        fusion_result = self.fusion_engine.fuse(
                            intent_score=fusion_intent,
                            gesture_result=gesture_result,
                            screen_width=int(self.camera_width),
                            screen_height=int(self.camera_height)
                        )
                        
                        # Route fused command to gatekeeper
                        if fusion_result.should_execute and fusion_result.command:
                            command_key = fusion_result.command.value
                            command_map = {
                                "mouse_click": "CLICK",
                                "mouse_double_click": "DOUBLE_CLICK",
                                "scroll_up": "SCROLL_UP",
                                "scroll_down": "SCROLL_DOWN",
                                "scroll_mode_toggle": "SCROLL_MODE_TOGGLE",
                                "cancel_command": "CANCEL_COMMAND",
                                "confirm": "CONFIRM",
                                "reject": "REJECT",
                                "emergency_alert": "EMERGENCY_ALERT",
                                "call_nurse": "CALL_NURSE",
                                "cursor_override_start": "CURSOR_OVERRIDE_START",
                                "cursor_override_end": "CURSOR_OVERRIDE_END",
                            }
                            command_name = command_map.get(command_key, command_key.upper())
                            self._handle_fusion_command(command_name)
                            logger.debug(f"Fused command: {command_name} (source: {fusion_result.source})")
                        
                        # Process calibration if active
                        if self.calibration_active:
                            self._process_calibration(gaze_pos[0], gaze_pos[1])
                
                # Calculate FPS
                frame_end = time.time()
                frame_time = frame_end - frame_start
                fps = 1.0 / frame_time if frame_time > 0 else 0
                self.fps_history.append(fps)
                avg_fps = np.mean(self.fps_history) if self.fps_history else 0
                
                # Render HUD
                display_frame = self.hud_renderer.render_frame(
                    frame,
                    gaze_position=gaze_position,
                    gaze_velocity=gaze_velocity,
                    intent_confidence=intent_score.confidence if intent_score else None,
                    strain_metrics={
                        "blink_rate": strain_metrics.blink_rate_per_minute,
                        "perclos": strain_metrics.perclos_score,
                        "fatigue_level": strain_metrics.fatigue_level.value.upper()
                    } if strain_metrics else None,
                    fps=avg_fps,
                    backend_info=self.cuda_pipeline.get_backend_info(),
                    mode_info=f"{'LIVE' if self.live_mode else 'SIM'} - {self.cuda_pipeline.backend.value}"
                )
                
                # Add Hand Gesture Overlay (NEW)
                if self.gesture_overlay_visible and self.current_gesture_result:
                    gesture_display_info = GestureDisplayInfo(
                        gesture_name=self.current_gesture_result.gesture_type.value,
                        confidence=self.current_gesture_result.confidence,
                        hand_position=self.current_gesture_result.hand_position,
                        handedness=self.current_gesture_result.hand.handedness
                    )
                    
                    hand_landmarks = [
                        (lm.x, lm.y) for lm in self.current_gesture_result.hand.landmarks
                    ]
                    
                    display_frame = self.gesture_hud.render_hand_overlay(
                        frame=display_frame,
                        hand_landmarks=hand_landmarks,
                        gesture_info=gesture_display_info,
                        fusion_mode=self.fusion_engine.config.fusion_mode.value,
                        diagnostics={
                            "hands_detected": 1,
                            "fps": avg_fps,
                            "inference_ms": self.hand_engine._get_avg_inference_time(),
                            "confidence": self.current_gesture_result.confidence
                        }
                    )
                
                # Display
                cv2.imshow("NeuroGaze Elite", display_frame)
                
                # Keyboard handling
                key = cv2.waitKey(1) & 0xFF
                if key != 255:
                    if not self._handle_keyboard_input(key):
                        break
                
                self.frame_count += 1
                
                # Periodic logging
                if self.frame_count % 300 == 0:
                    elapsed = (time.time() - session_start) / 60.0
                    logger.info(f"[{self.frame_count} frames, {elapsed:.1f}min] FPS: {avg_fps:.1f} | "
                              f"EAR: {ear_value:.3f} | "
                              f"Intent: {intent_score.level.value if intent_score else 'N/A'}")
        
        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        
        finally:
            self._cleanup()

    def _print_session_summary(self, session_stats: Dict[str, float]) -> None:
        """Log and save session summary on exit."""
        duration = time.time() - self.state.session_start_time
        mins = int(duration // 60)
        secs = int(duration % 60)

        summary = {
            "duration_seconds": int(duration),
            "commands_fired": self.state.commands_fired,
            "commands_by_type": self.state.commands_by_type,
            "avg_blink_rate": round(float(session_stats.get("avg_blink_rate", 0.0)), 1),
            "fatigue_events": self.state.fatigue_events,
            "breaks_taken": self.state.breaks_taken,
            "session_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        logger.info("-" * 45)
        logger.info(f"Session ended - {mins}m {secs}s")
        logger.info(f"Commands fired : {summary['commands_fired']}")
        logger.info(f"Avg blink rate : {summary['avg_blink_rate']}/min")
        logger.info(f"Fatigue events : {summary['fatigue_events']}")
        logger.info(f"Breaks taken   : {summary['breaks_taken']}")
        logger.info("-" * 45)

        log_path = Path(__file__).parent / "session_log.json"
        try:
            import json
            with log_path.open("w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Saved -> {log_path.name}")
        except Exception as exc:
            logger.warning(f"Could not save session log: {exc}")
    
    def _cleanup(self) -> None:
        """Clean up resources"""
        logger.info("\n" + "=" * 60)
        logger.info("🛑 Shutting down...")
        logger.info("=" * 60)
        
        # Stop strain guard session
        session_stats = self.strain_guard.end_session()
        
        # Save session stats
        if self.current_profile:
            session_duration = session_stats.get('session_duration_seconds', 0) / 60.0
            blink_rate = session_stats.get('avg_blink_rate', 0)
            
            self.profile_manager.update_profile_session_stats(
                self.current_profile,
                session_duration,
                blink_rate
            )
            self.profile_manager.save_profile(self.current_profile)
        
        self._print_session_summary(session_stats)

        # Stop command worker
        if self.command_worker:
            worker_stats = self.command_worker.get_stats()
            logger.info(f"Commands: {worker_stats['commands_executed']} executed, "
                       f"{worker_stats['commands_failed']} failed")
            self.command_worker.stop()
        
        # Clean up GPU
        if self.cuda_pipeline:
            self.cuda_pipeline.cleanup()
        
        # Close camera
        if self.cap:
            self.cap.release()
        
        # Close windows
        cv2.destroyAllWindows()
        
        logger.info(f"Session stats: {session_stats}")
        logger.info("✓ Shutdown complete\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="NeuroGaze Elite - Eye-Controlled Assistive Device")
    parser.add_argument("--gpu", action="store_true", default=True, help="Enable GPU acceleration")
    parser.add_argument("--no-gpu", action="store_true", help="Disable GPU acceleration")
    parser.add_argument("--live", action="store_true", help="Start in live mode")
    parser.add_argument("--simulate", action="store_true", default=True, help="Simulation mode (no actual commands)")
    parser.add_argument("--execute", action="store_true", help="Execute actual commands (live mode)")
    parser.add_argument("--hud", choices=["minimal", "standard", "debug"], default="standard", help="HUD display mode")
    
    args = parser.parse_args()
    
    config = load_config_yaml(AppConfig())
    enable_gpu = not args.no_gpu
    live_mode = args.live
    simulation_mode = config.SIMULATION_MODE
    if args.execute:
        simulation_mode = False
    elif args.simulate:
        simulation_mode = True
    hud_mode = args.hud
    
    try:
        app = NeuroGazeElite(
            enable_gpu=enable_gpu,
            enable_live_mode=live_mode,
            simulation_mode=simulation_mode,
            hud_mode=hud_mode,
            config=config,
        )
        app.run()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
