"""
NeuroGaze Elite - Advanced Eye-Controlled Assistive Device
Production-grade eye-tracking system with GPU acceleration, strain monitoring, and adaptive intent detection
Part of the NeuroGaze Elite comprehensive rebuild
"""

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import time
import logging
import argparse
import platform
from pathlib import Path
from typing import Optional, Tuple
from collections import deque

# Import all NeuroGaze Elite modules
from cuda_pipeline import CUDAPipeline
from strain_guard import StrainGuard, StrainGuardConfig
from adaptive_calibration import AdaptiveEARCalibrator, UserProfileManager, CalibrationScreenManager
from kalman_gaze import KalmanGaze, KalmanState
from intent_engine import IntentEngine, CommandGatekeeper, IntentLevel
from command_worker import CommandWorkerProcess, CommandType, cross_platform_beep
from hud_renderer import HUDRenderer, HUDMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        hud_mode: str = "standard"
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
        self.enable_gpu = enable_gpu
        self.live_mode = enable_live_mode
        self.simulation_mode = simulation_mode
        self.running = True
        
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
        
        self.cap = cv2.VideoCapture(0)
        time.sleep(0.5)
        
        if not self.cap.isOpened():
            logger.error("Failed to open camera!")
            raise RuntimeError("Camera not available")
        
        self.camera_width = 1280
        self.camera_height = 720
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        logger.info(f"✓ Camera initialized ({self.camera_width}x{self.camera_height})")
    
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
                    logger.warning("Failed to read frame")
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
                        
                        # Calculate EAR (blink detection)
                        ear_value = self._calculate_ear(face_landmarks)
                        
                        # Update strain guard
                        strain_metrics = self.strain_guard.update(ear_value)
                        
                        # Intent analysis
                        dwell_duration_ms = self.intent_engine.update_dwell(gaze_position)
                        intent_score = self.intent_engine.analyze_intent(
                            current_velocity=gaze_velocity,
                            current_position=gaze_position,
                            dwell_duration_ms=dwell_duration_ms
                        )
                        
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
    
    enable_gpu = not args.no_gpu
    live_mode = args.live
    simulation_mode = not args.execute
    hud_mode = args.hud
    
    try:
        app = NeuroGazeElite(
            enable_gpu=enable_gpu,
            enable_live_mode=live_mode,
            simulation_mode=simulation_mode,
            hud_mode=hud_mode
        )
        app.run()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
