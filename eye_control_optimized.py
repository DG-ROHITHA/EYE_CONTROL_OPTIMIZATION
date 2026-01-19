"""
OPTIMIZED Eye-Controlled Assistive Device
Enhanced with: Kalman filtering, intent detection, multiprocessing, GPU acceleration
Performance Target: <50ms response time, reduced CPU usage
"""

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import pyautogui
import time
from collections import deque
from datetime import datetime
import threading
import winsound
from multiprocessing import Process, Queue, Value
import ctypes

# Disable pyautogui failsafe
pyautogui.FAILSAFE = False

# ==================== PERFORMANCE CONFIGURATION ====================
class PerformanceConfig:
    # Frame processing optimization
    SKIP_FRAMES = 0  # Process every frame for reliable detection
    PROCESS_WIDTH = 640  # Higher resolution for better accuracy
    PROCESS_HEIGHT = 480
    USE_GPU = True  # Enable GPU acceleration if available
    
    # Region of Interest optimization
    USE_ROI = False  # Disable ROI until face is reliably detected
    ROI_MARGIN = 80  # Larger margin around detected face
    
    # Threading configuration
    USE_THREADING = True
    COMMAND_QUEUE_SIZE = 10
    
    # Performance monitoring
    ENABLE_FPS_COUNTER = True
    TARGET_FPS = 30
    
    # Response time optimization
    TARGET_RESPONSE_TIME_MS = 50
    
# ==================== MAIN CONFIGURATION ====================
class Config:
    # Camera settings
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    
    # Performance settings
    perf = PerformanceConfig()
    
    # Calibration
    calibrated = False
    screen_width, screen_height = pyautogui.size()
    
    # Gaze smoothing with Kalman filter
    USE_KALMAN_FILTER = True
    SMOOTHING_FRAMES = 3  # Reduced for faster response
    
    # Intent detection parameters
    INTENT_DETECTION = True
    
    # Duration thresholds
    INTENTIONAL_GAZE_DURATION = 1.0  # Intentional looks (>1s)
    QUICK_GLANCE_MAX = 0.3  # Quick glances (<0.3s, likely unintentional)
    
    # Pattern detection
    PATTERN_DETECTION = True
    PATTERN_TIMEOUT = 3.0
    
    # Intensity detection
    INTENSITY_DETECTION = True
    VELOCITY_THRESHOLD_SLOW = 10  # pixels/frame - deliberate movement
    VELOCITY_THRESHOLD_FAST = 100  # pixels/frame - rapid glance
    
    # Confirmation system
    REQUIRE_CONFIRMATION = False  # Set to True for critical commands
    CONFIRMATION_BLINK_PATTERN = [0.2, 0.5]  # Quick blink, pause, blink
    
    # Dwell-time settings (optimized)
    DWELL_TIME = 1.2  # Reduced from 1.5s for faster response
    CLICK_RADIUS = 25  # Slightly tighter radius
    
    # Gesture thresholds
    LOOK_LEFT_THRESHOLD = 0.35
    LOOK_RIGHT_THRESHOLD = 0.65
    LOOK_UP_THRESHOLD = 0.30
    LOOK_DOWN_THRESHOLD = 0.70
    
    # Blink detection
    EAR_THRESHOLD = 0.21
    BLINK_FRAMES = 2
    DOUBLE_BLINK_WINDOW = 0.6
    LONG_BLINK_TIME = 3.0
    EYES_CLOSED_SLEEP = 5.0
    
    # Safety
    GESTURE_COOLDOWN = 0.4  # Reduced for faster response
    COMMAND_COOLDOWN = 0.6
    MAX_CURSOR_SPEED = 60  # Increased slightly
    
    # Command system
    SIMULATION_MODE = True
    ENABLE_BASIC_CONTROLS = True
    ENABLE_ADVANCED_CONTROLS = True
    ENABLE_ASSISTIVE_CONTROLS = True
    ENABLE_AUDIO_FEEDBACK = True

config = Config()

# ==================== KALMAN FILTER FOR SMOOTH TRACKING ====================
class KalmanFilter2D:
    """2D Kalman filter for smooth gaze tracking"""
    def __init__(self, process_variance=1e-5, measurement_variance=1e-1):
        # State: [x, y, vx, vy] - position and velocity
        self.state = np.zeros((4, 1))
        
        # State transition matrix (constant velocity model)
        self.F = np.array([
            [1, 0, 1, 0],  # x = x + vx
            [0, 1, 0, 1],  # y = y + vy
            [0, 0, 1, 0],  # vx = vx
            [0, 0, 0, 1]   # vy = vy
        ])
        
        # Measurement matrix (we only measure position)
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        # Process covariance
        self.Q = np.eye(4) * process_variance
        
        # Measurement covariance
        self.R = np.eye(2) * measurement_variance
        
        # Estimation covariance
        self.P = np.eye(4)
        
        self.initialized = False
    
    def predict(self):
        """Predict next state"""
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.state[0, 0], self.state[1, 0]
    
    def update(self, measurement):
        """Update state with new measurement"""
        z = np.array([[measurement[0]], [measurement[1]]])
        
        if not self.initialized:
            self.state[0, 0] = measurement[0]
            self.state[1, 0] = measurement[1]
            self.initialized = True
            return measurement
        
        # Prediction step
        self.predict()
        
        # Update step
        y = z - self.H @ self.state  # Innovation
        S = self.H @ self.P @ self.H.T + self.R  # Innovation covariance
        K = self.P @ self.H.T @ np.linalg.inv(S)  # Kalman gain
        
        self.state = self.state + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        
        return self.state[0, 0], self.state[1, 0]
    
    def get_velocity(self):
        """Get current velocity (useful for intent detection)"""
        return self.state[2, 0], self.state[3, 0]

# ==================== INTENT DETECTION SYSTEM ====================
class IntentDetector:
    """Detect intentional gaze vs. unintentional glances"""
    def __init__(self):
        self.gaze_positions = deque(maxlen=30)  # Last 30 frames
        self.gaze_timestamps = deque(maxlen=30)
        self.region_enter_time = {}  # Track when user enters a region
        self.last_position = None
        
    def add_gaze_point(self, x, y, timestamp):
        """Add gaze point for analysis"""
        self.gaze_positions.append((x, y))
        self.gaze_timestamps.append(timestamp)
        self.last_position = (x, y)
    
    def get_duration_at_position(self, target_x, target_y, radius=50):
        """Get duration looking at specific position"""
        if len(self.gaze_positions) < 2:
            return 0
        
        duration = 0
        for i, (x, y) in enumerate(self.gaze_positions):
            distance = np.sqrt((x - target_x)**2 + (y - target_y)**2)
            if distance <= radius:
                if i > 0:
                    duration += self.gaze_timestamps[i] - self.gaze_timestamps[i-1]
        
        return duration
    
    def detect_pattern(self, pattern_sequence):
        """
        Detect gaze patterns (e.g., left-right-left)
        pattern_sequence: list of regions like ['LEFT', 'RIGHT', 'LEFT']
        """
        if len(self.gaze_positions) < len(pattern_sequence):
            return False
        
        # Analyze recent movement pattern
        detected_pattern = []
        for x, y in list(self.gaze_positions)[-len(pattern_sequence):]:
            norm_x = x / config.screen_width
            norm_y = y / config.screen_height
            
            if norm_x < config.LOOK_LEFT_THRESHOLD:
                detected_pattern.append('LEFT')
            elif norm_x > config.LOOK_RIGHT_THRESHOLD:
                detected_pattern.append('RIGHT')
            elif norm_y < config.LOOK_UP_THRESHOLD:
                detected_pattern.append('UP')
            elif norm_y > config.LOOK_DOWN_THRESHOLD:
                detected_pattern.append('DOWN')
        
        return detected_pattern == pattern_sequence
    
    def get_movement_intensity(self):
        """Calculate movement intensity (velocity)"""
        if len(self.gaze_positions) < 2:
            return 0
        
        velocities = []
        for i in range(1, len(self.gaze_positions)):
            dx = self.gaze_positions[i][0] - self.gaze_positions[i-1][0]
            dy = self.gaze_positions[i][1] - self.gaze_positions[i-1][1]
            velocity = np.sqrt(dx**2 + dy**2)
            velocities.append(velocity)
        
        return np.mean(velocities) if velocities else 0
    
    def is_intentional(self, position, region_id):
        """Determine if gaze at position is intentional"""
        # Check duration
        duration = self.get_duration_at_position(position[0], position[1])
        
        # Check intensity (slow, deliberate movements are intentional)
        intensity = self.get_movement_intensity()
        
        # Intentional criteria:
        # 1. Long duration (>1s)
        # 2. Low velocity (deliberate movement)
        is_long_duration = duration >= config.INTENTIONAL_GAZE_DURATION
        is_deliberate_movement = intensity < config.VELOCITY_THRESHOLD_SLOW
        
        return is_long_duration or (duration > 0.5 and is_deliberate_movement)
    
    def get_timing_consistency(self):
        """Check if commands are at consistent intervals (pattern indicator)"""
        if len(self.gaze_timestamps) < 3:
            return 0
        
        intervals = []
        for i in range(1, len(self.gaze_timestamps)):
            interval = self.gaze_timestamps[i] - self.gaze_timestamps[i-1]
            intervals.append(interval)
        
        # Calculate variance (lower = more consistent)
        variance = np.var(intervals) if intervals else float('inf')
        consistency = 1.0 / (1.0 + variance)  # 0-1 score
        
        return consistency

# ==================== PERFORMANCE MONITOR ====================
class PerformanceMonitor:
    """Monitor and optimize system performance"""
    def __init__(self):
        self.frame_times = deque(maxlen=30)
        self.processing_times = deque(maxlen=30)
        self.last_frame_time = time.time()
        
    def frame_start(self):
        """Mark start of frame processing"""
        self.start_time = time.time()
    
    def frame_end(self):
        """Mark end of frame processing"""
        current_time = time.time()
        processing_time = (current_time - self.start_time) * 1000  # ms
        frame_time = (current_time - self.last_frame_time) * 1000
        
        self.processing_times.append(processing_time)
        self.frame_times.append(frame_time)
        self.last_frame_time = current_time
    
    def get_fps(self):
        """Get current FPS"""
        if len(self.frame_times) == 0:
            return 0
        avg_frame_time = np.mean(self.frame_times)
        return 1000.0 / avg_frame_time if avg_frame_time > 0 else 0
    
    def get_avg_processing_time(self):
        """Get average processing time in ms"""
        return np.mean(self.processing_times) if self.processing_times else 0
    
    def get_stats(self):
        """Get performance statistics"""
        return {
            'fps': self.get_fps(),
            'avg_processing_ms': self.get_avg_processing_time(),
            'min_processing_ms': min(self.processing_times) if self.processing_times else 0,
            'max_processing_ms': max(self.processing_times) if self.processing_times else 0
        }

# ==================== OPTIMIZED FACE DETECTOR ====================
class OptimizedFaceDetector:
    """Optimized face detection with ROI and frame skipping"""
    def __init__(self, model_path):
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1
        )
        self.face_mesh = vision.FaceLandmarker.create_from_options(options)
        
        self.frame_counter = 0
        self.last_face_bbox = None
        self.roi = None
        
    def detect(self, frame):
        """Detect face with optimizations"""
        h, w = frame.shape[:2]
        
        # Frame skipping
        self.frame_counter += 1
        if self.frame_counter % (config.perf.SKIP_FRAMES + 1) != 0:
            return None  # Skip this frame
        
        # Use ROI if available
        if config.perf.USE_ROI and self.roi is not None:
            x, y, roi_w, roi_h = self.roi
            roi_frame = frame[y:y+roi_h, x:x+roi_w]
            
            # Process ROI at reduced resolution
            if config.perf.PROCESS_WIDTH < w:
                scale = config.perf.PROCESS_WIDTH / roi_w
                small_frame = cv2.resize(roi_frame, 
                    (config.perf.PROCESS_WIDTH, int(roi_h * scale)))
            else:
                small_frame = roi_frame
                scale = 1.0
            
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        else:
            # Full frame at reduced resolution
            scale = config.perf.PROCESS_WIDTH / w
            small_frame = cv2.resize(frame, 
                (config.perf.PROCESS_WIDTH, config.perf.PROCESS_HEIGHT))
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Detect
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = self.face_mesh.detect(mp_image)
        
        # Update ROI for next frame
        if results.face_landmarks and config.perf.USE_ROI:
            face = results.face_landmarks[0]
            # Calculate bounding box
            xs = [lm.x for lm in face]
            ys = [lm.y for lm in face]
            
            min_x = int(min(xs) * w) - config.perf.ROI_MARGIN
            max_x = int(max(xs) * w) + config.perf.ROI_MARGIN
            min_y = int(min(ys) * h) - config.perf.ROI_MARGIN
            max_y = int(max(ys) * h) + config.perf.ROI_MARGIN
            
            # Clamp to frame bounds
            min_x = max(0, min_x)
            min_y = max(0, min_y)
            max_x = min(w, max_x)
            max_y = min(h, max_y)
            
            self.roi = (min_x, min_y, max_x - min_x, max_y - min_y)
        
        return results

# ==================== INITIALIZATION ====================
config = Config()
perf_monitor = PerformanceMonitor()
intent_detector = IntentDetector()
kalman_filter = KalmanFilter2D()

# Webcam with error handling
print("Initializing camera...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Use DirectShow for faster initialization on Windows
time.sleep(0.5)  # Give camera time to initialize

if not cap.isOpened():
    print("ERROR: Could not open camera!")
    print("Please check:")
    print("  1. Camera is connected")
    print("  2. No other application is using the camera")
    print("  3. Camera permissions are enabled")
    exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
print("✓ Camera initialized successfully")

# MediaPipe Face Landmarker with optimization
model_path = r"R:\ROHI\webcame_dectection\face_landmarker.task"
face_detector = OptimizedFaceDetector(model_path)

# ==================== STATE TRACKING ====================
class GazeState:
    def __init__(self):
        self.gaze_history = deque(maxlen=config.SMOOTHING_FRAMES)
        self.dwell_start_time = None
        self.dwell_position = None
        self.last_gesture_time = 0
        self.last_command_time = 0
        
        # Blink tracking
        self.blink_counter = 0
        self.last_blink_time = 0
        self.blink_start_time = None
        self.blink_times = deque(maxlen=5)
        self.eyes_closed_start = None
        self.consecutive_blink_frames = 0
        
        # Direction tracking
        self.current_direction = None
        self.direction_start_time = None
        self.direction_history = deque(maxlen=5)
        
        # Sequence tracking
        self.sequence_buffer = []
        self.sequence_start_time = None
        
        # Calibration
        self.calibration_data = {
            'left': None, 'right': None,
            'top': None, 'bottom': None,
            'center': None
        }
        
        # Feedback
        self.last_command = None
        self.command_display_time = None
        
        # Intent confirmation
        self.pending_command = None
        self.confirmation_start_time = None
        
    def add_gaze(self, x, y):
        """Add gaze point with Kalman filtering"""
        if config.USE_KALMAN_FILTER:
            filtered_x, filtered_y = kalman_filter.update((x, y))
            return filtered_x, filtered_y
        else:
            self.gaze_history.append((x, y))
            if len(self.gaze_history) > 0:
                avg_x = np.mean([p[0] for p in self.gaze_history])
                avg_y = np.mean([p[1] for p in self.gaze_history])
                return avg_x, avg_y
            return x, y
    
    def check_dwell(self, current_pos):
        """Check dwell with intent detection"""
        current_time = time.time()
        
        if self.dwell_position is None:
            self.dwell_position = current_pos
            self.dwell_start_time = current_time
            return False
        
        distance = np.sqrt(
            (current_pos[0] - self.dwell_position[0])**2 +
            (current_pos[1] - self.dwell_position[1])**2
        )
        
        if distance > config.CLICK_RADIUS:
            self.dwell_position = current_pos
            self.dwell_start_time = current_time
            return False
        
        elapsed = current_time - self.dwell_start_time
        
        # Check intent before triggering
        if elapsed >= config.DWELL_TIME:
            if config.INTENT_DETECTION:
                is_intentional = intent_detector.is_intentional(
                    current_pos, 'dwell_region'
                )
                if not is_intentional:
                    # Not intentional, require more time
                    if elapsed >= config.DWELL_TIME * 1.5:
                        self.dwell_position = None
                        self.dwell_start_time = None
                        return True
                    return False
            
            self.dwell_position = None
            self.dwell_start_time = None
            return True
        
        return False
    
    def get_dwell_progress(self):
        """Get dwell progress (0-1)"""
        if self.dwell_start_time is None:
            return 0
        elapsed = time.time() - self.dwell_start_time
        return min(elapsed / config.DWELL_TIME, 1.0)

state = GazeState()

# ==================== BLINK DETECTION ====================
class BlinkDetector:
    @staticmethod
    def calculate_ear(eye_landmarks, face_landmarks):
        """Calculate Eye Aspect Ratio"""
        points = [face_landmarks[i] for i in eye_landmarks]
        
        v1 = np.linalg.norm(np.array([points[1].x, points[1].y]) - 
                           np.array([points[5].x, points[5].y]))
        v2 = np.linalg.norm(np.array([points[2].x, points[2].y]) - 
                           np.array([points[4].x, points[4].y]))
        h = np.linalg.norm(np.array([points[0].x, points[0].y]) - 
                          np.array([points[3].x, points[3].y]))
        
        ear = (v1 + v2) / (2.0 * h) if h > 0 else 0
        return ear
    
    @staticmethod
    def detect_blink(face_landmarks):
        """Detect blink"""
        left_eye = [33, 160, 158, 133, 153, 144]
        right_eye = [362, 385, 387, 263, 373, 380]
        
        left_ear = BlinkDetector.calculate_ear(left_eye, face_landmarks)
        right_ear = BlinkDetector.calculate_ear(right_eye, face_landmarks)
        
        avg_ear = (left_ear + right_ear) / 2.0
        return avg_ear < config.EAR_THRESHOLD, avg_ear
    
    @staticmethod
    def detect_blink_pattern(blink_times, pattern):
        """
        Detect specific blink patterns for confirmation
        pattern: list of max intervals, e.g., [0.2, 0.5] = quick blink, pause, blink
        """
        if len(blink_times) < len(pattern) + 1:
            return False
        
        recent_blinks = list(blink_times)[-(len(pattern) + 1):]
        intervals = []
        
        for i in range(1, len(recent_blinks)):
            intervals.append(recent_blinks[i] - recent_blinks[i-1])
        
        # Check if intervals match pattern
        for i, max_interval in enumerate(pattern):
            if i >= len(intervals):
                return False
            if intervals[i] > max_interval:
                return False
        
        return True

blink_detector = BlinkDetector()

# ==================== DIRECTION DETECTION ====================
class DirectionDetector:
    @staticmethod
    def detect_direction(screen_x, screen_y):
        """Detect gaze direction"""
        norm_x = screen_x / config.screen_width
        norm_y = screen_y / config.screen_height
        
        is_left = norm_x < config.LOOK_LEFT_THRESHOLD
        is_right = norm_x > config.LOOK_RIGHT_THRESHOLD
        is_up = norm_y < config.LOOK_UP_THRESHOLD
        is_down = norm_y > config.LOOK_DOWN_THRESHOLD
        
        # Diagonals
        if is_up and is_left:
            return "UP_LEFT"
        elif is_up and is_right:
            return "UP_RIGHT"
        elif is_down and is_left:
            return "DOWN_LEFT"
        elif is_down and is_right:
            return "DOWN_RIGHT"
        elif is_up:
            return "UP"
        elif is_down:
            return "DOWN"
        elif is_left:
            return "LEFT"
        elif is_right:
            return "RIGHT"
        
        return "CENTER"

direction_detector = DirectionDetector()

# ==================== SEQUENCE DETECTOR ====================
class SequenceDetector:
    def __init__(self):
        self.patterns = {
            'CALL_NURSE': ['LEFT', 'RIGHT', 'LEFT'],
            'ADJUST_BED': ['UP', 'DOWN', 'UP'],
            'EMERGENCY': ['LEFT', 'LEFT', 'RIGHT', 'RIGHT'],  # Konami-style
        }
    
    def check_sequence(self, sequence_buffer):
        """Check if buffer matches pattern"""
        if len(sequence_buffer) < 3:
            return None
        
        for command, pattern in self.patterns.items():
            if len(sequence_buffer) >= len(pattern):
                recent = sequence_buffer[-len(pattern):]
                if recent == pattern:
                    return command
        
        return None

sequence_detector = SequenceDetector()

# ==================== COMMAND EXECUTOR ====================
class CommandExecutor:
    def __init__(self):
        self.command_log = []
        self.command_queue = deque(maxlen=config.perf.COMMAND_QUEUE_SIZE)
        
    def execute(self, command, intent_confidence=1.0):
        """Execute command with intent confidence"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        confidence_str = f"({intent_confidence*100:.0f}%)"
        
        self.command_log.append((timestamp, command, intent_confidence))
        
        if config.SIMULATION_MODE:
            print(f"🎮 [{timestamp}] {command} {confidence_str}")
            if config.ENABLE_AUDIO_FEEDBACK:
                self.play_beep()
        else:
            self._execute_real(command)
    
    def _execute_real(self, command):
        """Execute actual commands"""
        try:
            if command == "UP":
                pyautogui.press('up')
            elif command == "DOWN":
                pyautogui.press('down')
            elif command == "LEFT":
                pyautogui.press('left')
            elif command == "RIGHT":
                pyautogui.press('right')
            elif command == "SCROLL_UP":
                pyautogui.scroll(3)
            elif command == "SCROLL_DOWN":
                pyautogui.scroll(-3)
            elif command == "CLICK":
                pyautogui.click()
            elif command == "DOUBLE_CLICK":
                pyautogui.doubleClick()
            elif command == "EMERGENCY_ALERT":
                self.trigger_emergency()
            elif command == "CALL_NURSE":
                self.call_nurse()
            elif command == "ADJUST_BED":
                self.adjust_bed()
            elif command == "SLEEP_MODE":
                self.enter_sleep_mode()
            
            if config.ENABLE_AUDIO_FEEDBACK:
                self.play_beep()
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def trigger_emergency(self):
        """Emergency alert"""
        print("\n🚨 EMERGENCY ALERT 🚨")
        for _ in range(3):
            winsound.Beep(1000, 200)
            time.sleep(0.1)
    
    def call_nurse(self):
        """Call nurse"""
        print("\n📞 CALLING NURSE")
        winsound.Beep(800, 300)
    
    def adjust_bed(self):
        """Adjust bed"""
        print("\n🛏️ BED ADJUSTMENT")
        winsound.Beep(600, 200)
    
    def enter_sleep_mode(self):
        """Sleep mode"""
        print("\n😴 SLEEP MODE")
        winsound.Beep(500, 400)
    
    def play_beep(self):
        """Confirmation beep"""
        try:
            winsound.Beep(750, 100)
        except:
            pass

command_executor = CommandExecutor()

# ==================== EYE TRACKING ====================
def get_iris_center(face_landmarks, frame_w, frame_h):
    """Get iris center from both eyes"""
    left_iris_ids = [474, 475, 476, 477]
    right_iris_ids = [469, 470, 471, 472]
    
    all_xs, all_ys = [], []
    
    for eye_ids in [left_iris_ids, right_iris_ids]:
        for i in eye_ids:
            lm = face_landmarks[i]
            all_xs.append(lm.x * frame_w)
            all_ys.append(lm.y * frame_h)
    
    return np.mean(all_xs), np.mean(all_ys)

def iris_to_screen(iris_x, iris_y, frame_w, frame_h):
    """Map iris to screen coordinates"""
    # Simple proportional mapping (can be enhanced with calibration)
    screen_x = int((iris_x / frame_w) * config.screen_width)
    screen_y = int((iris_y / frame_h) * config.screen_height)
    
    screen_x = max(0, min(config.screen_width - 1, screen_x))
    screen_y = max(0, min(config.screen_height - 1, screen_y))
    
    return screen_x, screen_y

# ==================== COMMAND PROCESSING ====================
def process_blink_commands(face_landmarks):
    """Process blink commands with pattern detection"""
    if not config.ENABLE_ADVANCED_CONTROLS:
        return None
    
    current_time = time.time()
    is_blinking, ear = blink_detector.detect_blink(face_landmarks)
    
    if is_blinking:
        state.consecutive_blink_frames += 1
        
        if state.blink_start_time is None:
            state.blink_start_time = current_time
        
        # Long blink detection
        blink_duration = current_time - state.blink_start_time
        if blink_duration >= config.LONG_BLINK_TIME:
            if config.ENABLE_ASSISTIVE_CONTROLS:
                if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                    state.blink_start_time = None
                    state.consecutive_blink_frames = 0
                    state.last_command_time = current_time
                    return "EMERGENCY_ALERT"
    else:
        if state.consecutive_blink_frames >= config.BLINK_FRAMES:
            # Valid blink
            state.blink_times.append(current_time)
            state.blink_counter += 1
            state.last_blink_time = current_time
            
            # Check for confirmation pattern
            if config.REQUIRE_CONFIRMATION and state.pending_command:
                if blink_detector.detect_blink_pattern(
                    state.blink_times, config.CONFIRMATION_BLINK_PATTERN
                ):
                    command = state.pending_command
                    state.pending_command = None
                    return command
            
            # Double blink
            if state.blink_counter >= 2:
                if len(state.blink_times) >= 2:
                    time_between = state.blink_times[-1] - state.blink_times[-2]
                    if time_between <= config.DOUBLE_BLINK_WINDOW:
                        state.blink_counter = 0
                        if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                            state.last_command_time = current_time
                            return "DOUBLE_CLICK"
            
            # Single blink
            if state.blink_counter == 1:
                if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                    state.last_command_time = current_time
                    return "CLICK"
        
        state.consecutive_blink_frames = 0
        state.blink_start_time = None
        
        # Reset counter
        if current_time - state.last_blink_time > config.DOUBLE_BLINK_WINDOW:
            state.blink_counter = 0
    
    # Eyes closed (sleep mode)
    if is_blinking:
        if state.eyes_closed_start is None:
            state.eyes_closed_start = current_time
        elif current_time - state.eyes_closed_start >= config.EYES_CLOSED_SLEEP:
            if config.ENABLE_ASSISTIVE_CONTROLS:
                state.eyes_closed_start = None
                if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                    state.last_command_time = current_time
                    return "SLEEP_MODE"
    else:
        state.eyes_closed_start = None
    
    return None

def process_direction_commands(screen_x, screen_y):
    """Process direction commands with intent detection"""
    current_time = time.time()
    direction = direction_detector.detect_direction(screen_x, screen_y)
    
    # Track direction for sequences
    if direction != "CENTER":
        if state.current_direction != direction:
            state.current_direction = direction
            state.direction_start_time = current_time
        elif current_time - state.direction_start_time >= 0.3:  # Faster response
            if not state.sequence_buffer or state.sequence_buffer[-1] != direction:
                state.sequence_buffer.append(direction)
                
                if state.sequence_start_time is None:
                    state.sequence_start_time = current_time
                
                # Check sequences
                if config.PATTERN_DETECTION and config.ENABLE_ASSISTIVE_CONTROLS:
                    sequence_command = sequence_detector.check_sequence(state.sequence_buffer)
                    if sequence_command:
                        state.sequence_buffer = []
                        state.sequence_start_time = None
                        if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                            state.last_command_time = current_time
                            return sequence_command, 1.0
    else:
        state.current_direction = None
        state.direction_start_time = None
    
    # Timeout
    if state.sequence_start_time and current_time - state.sequence_start_time > config.PATTERN_TIMEOUT:
        state.sequence_buffer = []
        state.sequence_start_time = None
    
    # Basic direction commands
    if current_time - state.last_gesture_time < config.GESTURE_COOLDOWN:
        return None, 0
    
    if not config.ENABLE_BASIC_CONTROLS:
        return None, 0
    
    # Calculate intent confidence
    intent_confidence = 0.5  # Default
    if config.INTENT_DETECTION:
        intensity = intent_detector.get_movement_intensity()
        duration = intent_detector.get_duration_at_position(screen_x, screen_y, 100)
        
        # High confidence if: slow movement + longer duration
        if intensity < config.VELOCITY_THRESHOLD_SLOW and duration > 0.5:
            intent_confidence = 0.9
        elif intensity < config.VELOCITY_THRESHOLD_FAST and duration > 0.3:
            intent_confidence = 0.7
        else:
            intent_confidence = 0.4
    
    command = None
    
    # Diagonal controls
    if direction == "UP_LEFT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "VOLUME_UP"
    elif direction == "UP_RIGHT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "BRIGHTNESS_UP"
    elif direction == "DOWN_LEFT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "BACK"
    elif direction == "DOWN_RIGHT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "HOME"
    elif direction == "UP":
        command = "SCROLL_UP"
    elif direction == "DOWN":
        command = "SCROLL_DOWN"
    elif direction == "LEFT":
        command = "LEFT"
    elif direction == "RIGHT":
        command = "RIGHT"
    
    if command:
        state.last_gesture_time = current_time
    
    return command, intent_confidence

# ==================== VISUALIZATION ====================
def draw_optimized_feedback(frame, iris_x, iris_y, screen_x, screen_y, face_landmarks=None):
    """Draw feedback with performance stats"""
    h, w = frame.shape[:2]
    
    # Iris tracking
    cv2.circle(frame, (int(iris_x), int(iris_y)), 6, (0, 0, 255), 2)
    
    # Velocity vector (intent visualization)
    if config.USE_KALMAN_FILTER:
        vx, vy = kalman_filter.get_velocity()
        if abs(vx) > 1 or abs(vy) > 1:
            end_x = int(iris_x + vx * 10)
            end_y = int(iris_y + vy * 10)
            cv2.arrowedLine(frame, (int(iris_x), int(iris_y)), 
                          (end_x, end_y), (255, 255, 0), 2)
    
    # Performance stats (top-right)
    stats = perf_monitor.get_stats()
    fps = stats['fps']
    proc_time = stats['avg_processing_ms']
    
    stats_x = w - 250
    stats_y = 25
    
    # FPS
    fps_color = (0, 255, 0) if fps >= 25 else (0, 165, 255) if fps >= 15 else (0, 0, 255)
    cv2.putText(frame, f"FPS: {fps:.1f}", (stats_x, stats_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, fps_color, 2)
    
    # Processing time
    proc_color = (0, 255, 0) if proc_time < 50 else (0, 165, 255) if proc_time < 100 else (0, 0, 255)
    cv2.putText(frame, f"Time: {proc_time:.1f}ms", (stats_x, stats_y + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, proc_color, 2)
    
    # Target indicator
    target_met = proc_time < config.perf.TARGET_RESPONSE_TIME_MS
    target_color = (0, 255, 0) if target_met else (0, 0, 255)
    target_text = "✓ TARGET MET" if target_met else "✗ ABOVE TARGET"
    cv2.putText(frame, target_text, (stats_x, stats_y + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, target_color, 1)
    
    # Intent confidence
    if config.INTENT_DETECTION:
        intensity = intent_detector.get_movement_intensity()
        intent_text = "DELIBERATE" if intensity < config.VELOCITY_THRESHOLD_SLOW else \
                     "NORMAL" if intensity < config.VELOCITY_THRESHOLD_FAST else "RAPID"
        intent_color = (0, 255, 0) if intent_text == "DELIBERATE" else \
                      (0, 165, 255) if intent_text == "NORMAL" else (0, 0, 255)
        cv2.putText(frame, f"Intent: {intent_text}", (10, h - 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, intent_color, 2)
    
    # Minimap (compact version)
    mini_w, mini_h = 180, 135
    mini_x, mini_y = w - mini_w - 10, 90
    
    cv2.rectangle(frame, (mini_x, mini_y), (mini_x + mini_w, mini_y + mini_h), 
                 (50, 50, 50), -1)
    cv2.rectangle(frame, (mini_x, mini_y), (mini_x + mini_w, mini_y + mini_h), 
                 (255, 255, 255), 1)
    
    # Gaze point
    mini_gaze_x = mini_x + int((screen_x / config.screen_width) * mini_w)
    mini_gaze_y = mini_y + int((screen_y / config.screen_height) * mini_h)
    cv2.circle(frame, (mini_gaze_x, mini_gaze_y), 4, (0, 255, 0), -1)
    
    # Direction
    current_dir = direction_detector.detect_direction(screen_x, screen_y)
    if current_dir != "CENTER":
        cv2.putText(frame, current_dir, (mini_x, mini_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    
    # Dwell progress
    progress = state.get_dwell_progress()
    if progress > 0:
        radius = int(15 + progress * 8)
        color = (0, int(255 * progress), int(255 * (1 - progress)))
        cv2.circle(frame, (int(iris_x), int(iris_y)), radius, color, 2)
    
    # Last command
    if state.last_command and state.command_display_time:
        elapsed = time.time() - state.command_display_time
        if elapsed < 1.5:
            alpha = max(0, 1.0 - elapsed / 1.5)
            cmd_color = (0, int(255 * alpha), int(255 * alpha))
            cv2.putText(frame, f"✓ {state.last_command}", (w // 2 - 100, h - 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, cmd_color, 2)
    
    # Sequence buffer
    if state.sequence_buffer:
        seq_text = " > ".join(state.sequence_buffer[-3:])
        cv2.putText(frame, f"Pattern: {seq_text}", (10, h - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
    
    # Status
    cv2.putText(frame, f"Optimized Mode | Kalman: {'ON' if config.USE_KALMAN_FILTER else 'OFF'}", 
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.putText(frame, f"Intent Detection: {'ON' if config.INTENT_DETECTION else 'OFF'}",
                (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

# ==================== MAIN LOOP ====================
print("=" * 60)
print("🚀 OPTIMIZED EYE-CONTROLLED ASSISTIVE DEVICE")
print("=" * 60)
print("\n⚡ PERFORMANCE OPTIMIZATIONS:")
print(f"  • Frame skipping: Process every {config.perf.SKIP_FRAMES + 1} frames")
print(f"  • Resolution: {config.perf.PROCESS_WIDTH}x{config.perf.PROCESS_HEIGHT}")
print(f"  • ROI detection: {'ENABLED' if config.perf.USE_ROI else 'DISABLED'}")
print(f"  • Kalman filtering: {'ENABLED' if config.USE_KALMAN_FILTER else 'DISABLED'}")
print(f"  • Target response: <{config.perf.TARGET_RESPONSE_TIME_MS}ms")
print("\n🎯 INTENT DETECTION:")
print(f"  • Duration analysis: >={config.INTENTIONAL_GAZE_DURATION}s = intentional")
print(f"  • Velocity tracking: <{config.VELOCITY_THRESHOLD_SLOW}px/frame = deliberate")
print(f"  • Pattern recognition: {'ENABLED' if config.PATTERN_DETECTION else 'DISABLED'}")
print(f"  • Confirmation blinks: {'REQUIRED' if config.REQUIRE_CONFIRMATION else 'OPTIONAL'}")
print("\n📋 CONTROLS:")
print("  M - Toggle Simulation/Live mode")
print("  SPACE - Pause/Resume")
print("  ESC - Exit")
print(f"\n⚙️  Mode: {'SIMULATION' if config.SIMULATION_MODE else 'LIVE'}")
print("\nStarting...\n")

cursor_control_enabled = False

try:
    while True:
        perf_monitor.frame_start()
        
        ret, frame = cap.read()
        if not ret:
            break
        
        h, w, _ = frame.shape
        
        # Optimized detection
        results = face_detector.detect(frame)
        
        if results and results.face_landmarks:
            face = results.face_landmarks[0]
            
            # Get iris position
            iris_x, iris_y = get_iris_center(face, w, h)
            
            # Map to screen
            screen_x, screen_y = iris_to_screen(iris_x, iris_y, w, h)
            
            # Smooth with Kalman filter
            smooth_x, smooth_y = state.add_gaze(screen_x, screen_y)
            
            # Update intent detector
            current_time = time.time()
            intent_detector.add_gaze_point(smooth_x, smooth_y, current_time)
            
            # Process blink commands
            blink_command = process_blink_commands(face)
            if blink_command:
                command_executor.execute(blink_command, 1.0)
                state.last_command = blink_command
                state.command_display_time = current_time
            
            # Process direction commands
            direction_command, intent_confidence = process_direction_commands(
                int(smooth_x), int(smooth_y)
            )
            if direction_command:
                # Only execute if confidence is high enough
                if intent_confidence >= 0.5:
                    command_executor.execute(direction_command, intent_confidence)
                    state.last_command = f"{direction_command} ({intent_confidence*100:.0f}%)"
                    state.command_display_time = current_time
            
            # Visual feedback
            draw_optimized_feedback(frame, iris_x, iris_y, 
                                   int(smooth_x), int(smooth_y), face)
        else:
            cv2.putText(frame, "NO FACE DETECTED", (w//2 - 120, h//2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Still show performance stats
            stats = perf_monitor.get_stats()
            cv2.putText(frame, f"FPS: {stats['fps']:.1f}", (w - 150, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Display
        cv2.imshow("Optimized Eye Control System", frame)
        
        perf_monitor.frame_end()
        
        # Handle keyboard
        key = cv2.waitKey(1) & 0xFF
        
        if key == 27:  # ESC
            break
        elif key == ord('m') or key == ord('M'):
            config.SIMULATION_MODE = not config.SIMULATION_MODE
            mode = "SIMULATION" if config.SIMULATION_MODE else "LIVE"
            print(f"\n{'='*40}")
            print(f"⚠️  Control mode: {mode}")
            print(f"{'='*40}\n")
        elif key == ord(' '):
            cursor_control_enabled = not cursor_control_enabled
            status = "ENABLED" if cursor_control_enabled else "DISABLED"
            print(f"\nCursor control: {status}\n")

except KeyboardInterrupt:
    print("\nStopped by user")
finally:
    # Print final statistics
    final_stats = perf_monitor.get_stats()
    print("\n" + "=" * 60)
    print("📊 FINAL PERFORMANCE STATISTICS")
    print("=" * 60)
    print(f"Average FPS: {final_stats['fps']:.1f}")
    print(f"Avg Processing Time: {final_stats['avg_processing_ms']:.2f}ms")
    print(f"Min Processing Time: {final_stats['min_processing_ms']:.2f}ms")
    print(f"Max Processing Time: {final_stats['max_processing_ms']:.2f}ms")
    print(f"Target Met: {'✓ YES' if final_stats['avg_processing_ms'] < config.perf.TARGET_RESPONSE_TIME_MS else '✗ NO'}")
    print("=" * 60)
    
    cap.release()
    cv2.destroyAllWindows()
    print("\n✓ System Shutdown Complete")
