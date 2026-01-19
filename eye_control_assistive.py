"""
Eye-Controlled Assistive Device for Paralysis Patients
Uses iris tracking + dwell-time clicks + directional gestures
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

# Disable pyautogui failsafe for smooth operation
pyautogui.FAILSAFE = False

# -------------------- CONFIGURATION --------------------
class Config:
    # Camera settings
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    
    # Calibration points (will be updated during calibration)
    calibrated = False
    screen_width, screen_height = pyautogui.size()
    
    # Gaze smoothing
    SMOOTHING_FRAMES = 5  # Average over last N frames
    
    # Dwell-time click settings
    DWELL_TIME = 1.5  # seconds to trigger click
    CLICK_RADIUS = 30  # pixels - how close gaze must stay
    
    # Gesture thresholds
    LOOK_LEFT_THRESHOLD = 0.35   # Left 35% of screen
    LOOK_RIGHT_THRESHOLD = 0.65  # Right 65% of screen
    LOOK_UP_THRESHOLD = 0.30    # Top 30% of screen
    LOOK_DOWN_THRESHOLD = 0.70  # Bottom 70% of screen
    
    # Diagonal thresholds
    DIAGONAL_TOLERANCE = 0.15  # Range for detecting diagonals
    
    # Blink detection
    EAR_THRESHOLD = 0.21  # Eye Aspect Ratio threshold for blink
    BLINK_FRAMES = 2  # Consecutive frames to confirm blink
    DOUBLE_BLINK_WINDOW = 0.6  # seconds between blinks for double-blink
    LONG_BLINK_TIME = 3.0  # seconds for long blink (emergency)
    EYES_CLOSED_SLEEP = 5.0  # seconds for sleep mode
    
    # Sequence detection
    SEQUENCE_TIMEOUT = 3.0  # seconds to complete sequence
    DIRECTION_HOLD_TIME = 0.4  # seconds to hold direction for sequence
    
    # Safety
    GESTURE_COOLDOWN = 0.5  # seconds between gesture commands
    COMMAND_COOLDOWN = 0.8  # seconds between command executions
    MAX_CURSOR_SPEED = 50   # max pixels per frame
    
    # Command system
    SIMULATION_MODE = False  # If True, print commands instead of executing
    ENABLE_BASIC_CONTROLS = True
    ENABLE_ADVANCED_CONTROLS = True
    ENABLE_ASSISTIVE_CONTROLS = True
    ENABLE_AUDIO_FEEDBACK = True

# -------------------- INITIALIZATION --------------------
config = Config()

# Webcam
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

# MediaPipe Face Landmarker
model_path = r"R:\ROHI\webcame_dectection\face_landmarker.task"
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    num_faces=1
)
face_mesh = vision.FaceLandmarker.create_from_options(options)

# -------------------- STATE TRACKING --------------------
class GazeState:
    def __init__(self):
        self.gaze_history = deque(maxlen=config.SMOOTHING_FRAMES)
        self.dwell_start_time = None
        self.dwell_position = None
        self.last_gesture_time = 0
        self.last_command_time = 0
        self.calibration_data = {
            'left': None, 'right': None, 
            'top': None, 'bottom': None, 
            'center': None
        }
        
        # Blink tracking
        self.blink_counter = 0
        self.last_blink_time = 0
        self.blink_start_time = None
        self.eyes_closed_start = None
        self.consecutive_blink_frames = 0
        
        # Direction tracking
        self.current_direction = None
        self.direction_start_time = None
        self.direction_history = deque(maxlen=5)
        
        # Sequence tracking
        self.sequence_buffer = []
        self.sequence_start_time = None
        
        # Feedback
        self.last_command = None
        self.command_display_time = None
        
    def add_gaze(self, x, y):
        """Add gaze point and return smoothed position"""
        self.gaze_history.append((x, y))
        if len(self.gaze_history) > 0:
            avg_x = np.mean([p[0] for p in self.gaze_history])
            avg_y = np.mean([p[1] for p in self.gaze_history])
            return avg_x, avg_y
        return x, y
    
    def check_dwell(self, current_pos):
        """Check if user has dwelled on a position long enough"""
        if self.dwell_position is None:
            self.dwell_position = current_pos
            self.dwell_start_time = time.time()
            return False
        
        # Check if still looking at same spot
        distance = np.sqrt(
            (current_pos[0] - self.dwell_position[0])**2 + 
            (current_pos[1] - self.dwell_position[1])**2
        )
        
        if distance > config.CLICK_RADIUS:
            # Moved away, reset
            self.dwell_position = current_pos
            self.dwell_start_time = time.time()
            return False
        
        # Check if enough time has passed
        elapsed = time.time() - self.dwell_start_time
        if elapsed >= config.DWELL_TIME:
            self.dwell_position = None
            self.dwell_start_time = None
            return True
        
        return False
    
    def get_dwell_progress(self):
        """Get dwell progress (0-1) for visual feedback"""
        if self.dwell_start_time is None:
            return 0
        elapsed = time.time() - self.dwell_start_time
        return min(elapsed / config.DWELL_TIME, 1.0)

state = GazeState()

# -------------------- BLINK DETECTION --------------------
class BlinkDetector:
    @staticmethod
    def calculate_ear(eye_landmarks, face_landmarks):
        """Calculate Eye Aspect Ratio for blink detection"""
        # Get eye points
        points = [face_landmarks[i] for i in eye_landmarks]
        
        # Vertical distances
        v1 = np.linalg.norm(np.array([points[1].x, points[1].y]) - np.array([points[5].x, points[5].y]))
        v2 = np.linalg.norm(np.array([points[2].x, points[2].y]) - np.array([points[4].x, points[4].y]))
        
        # Horizontal distance
        h = np.linalg.norm(np.array([points[0].x, points[0].y]) - np.array([points[3].x, points[3].y]))
        
        # EAR formula
        ear = (v1 + v2) / (2.0 * h) if h > 0 else 0
        return ear
    
    @staticmethod
    def detect_blink(face_landmarks):
        """Detect if eyes are blinking"""
        # Left eye landmarks: [33, 160, 158, 133, 153, 144]
        # Right eye landmarks: [362, 385, 387, 263, 373, 380]
        left_eye = [33, 160, 158, 133, 153, 144]
        right_eye = [362, 385, 387, 263, 373, 380]
        
        left_ear = BlinkDetector.calculate_ear(left_eye, face_landmarks)
        right_ear = BlinkDetector.calculate_ear(right_eye, face_landmarks)
        
        avg_ear = (left_ear + right_ear) / 2.0
        
        return avg_ear < config.EAR_THRESHOLD, avg_ear

blink_detector = BlinkDetector()

# -------------------- DIRECTION DETECTION --------------------
class DirectionDetector:
    @staticmethod
    def detect_direction(screen_x, screen_y):
        """Detect gaze direction with support for diagonals"""
        norm_x = screen_x / config.screen_width
        norm_y = screen_y / config.screen_height
        
        # Check for primary directions first
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
        
        # Cardinals
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

# -------------------- SEQUENCE DETECTOR --------------------
class SequenceDetector:
    def __init__(self):
        self.patterns = {
            'CALL_NURSE': ['LEFT', 'RIGHT', 'LEFT'],
            'ADJUST_BED': ['UP', 'DOWN', 'UP'],
        }
    
    def check_sequence(self, sequence_buffer):
        """Check if buffer matches any pattern"""
        if len(sequence_buffer) < 3:
            return None
        
        # Check last 3 directions
        recent = sequence_buffer[-3:]
        
        for command, pattern in self.patterns.items():
            if recent == pattern:
                return command
        
        return None

sequence_detector = SequenceDetector()

# -------------------- COMMAND EXECUTOR --------------------
class CommandExecutor:
    def __init__(self):
        self.command_log = []
    
    def execute(self, command):
        """Execute command or simulate it"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.command_log.append((timestamp, command))
        
        if config.SIMULATION_MODE:
            print(f"🎮 [{timestamp}] COMMAND: {command}")
            if config.ENABLE_AUDIO_FEEDBACK:
                self.play_beep()
        else:
            self._execute_real(command)
    
    def _execute_real(self, command):
        """Execute actual keyboard/mouse commands"""
        try:
            # Basic direction controls
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
            
            # Advanced controls
            elif command == "CLICK":
                pyautogui.click()
            elif command == "DOUBLE_CLICK":
                pyautogui.doubleClick()
            elif command == "DRAG_START":
                pyautogui.mouseDown()
            elif command == "DRAG_END":
                pyautogui.mouseUp()
            
            # Volume and brightness
            elif command == "VOLUME_UP":
                pyautogui.press('volumeup')
            elif command == "BRIGHTNESS_UP":
                pyautogui.press('brightnessup')
            
            # Navigation
            elif command == "BACK":
                pyautogui.hotkey('alt', 'left')
            elif command == "HOME":
                pyautogui.press('home')
            
            # Assistive commands
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
            print(f"❌ Error executing {command}: {e}")
    
    def trigger_emergency(self):
        """Emergency alert system"""
        print("\n" + "="*50)
        print("🚨 EMERGENCY ALERT TRIGGERED 🚨")
        print("="*50 + "\n")
        # Play alarm sound
        for _ in range(3):
            winsound.Beep(1000, 200)
            time.sleep(0.1)
    
    def call_nurse(self):
        """Nurse call system"""
        print("\n📞 CALLING NURSE...")
        winsound.Beep(800, 300)
    
    def adjust_bed(self):
        """Bed adjustment request"""
        print("\n🛏️ BED ADJUSTMENT REQUEST")
        winsound.Beep(600, 200)
    
    def enter_sleep_mode(self):
        """Enter sleep/rest mode"""
        print("\n😴 ENTERING SLEEP MODE")
        winsound.Beep(500, 400)
    
    def play_beep(self):
        """Play confirmation beep"""
        try:
            winsound.Beep(750, 100)
        except:
            pass

command_executor = CommandExecutor()

# -------------------- CALIBRATION --------------------
def calibrate_gaze():
    """5-point calibration: center, left, right, top, bottom"""
    calibration_points = [
        ('center', config.screen_width // 2, config.screen_height // 2),
        ('left', config.screen_width // 4, config.screen_height // 2),
        ('right', 3 * config.screen_width // 4, config.screen_height // 2),
        ('top', config.screen_width // 2, config.screen_height // 4),
        ('bottom', config.screen_width // 2, 3 * config.screen_height // 4)
    ]
    
    print("\n=== CALIBRATION MODE ===")
    print("Look at each point for 2 seconds")
    print("Press SPACE to start, ESC to skip\n")
    
    for name, screen_x, screen_y in calibration_points:
        # Show calibration point
        cal_screen = np.zeros((config.screen_height, config.screen_width, 3), dtype=np.uint8)
        cv2.circle(cal_screen, (screen_x, screen_y), 20, (0, 255, 0), -1)
        cv2.putText(cal_screen, f"Look at {name.upper()}", 
                    (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(cal_screen, "Hold gaze for 2 seconds", 
                    (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        
        cv2.imshow("Calibration", cal_screen)
        key = cv2.waitKey(0)
        
        if key == 27:  # ESC
            print("Calibration skipped")
            cv2.destroyWindow("Calibration")
            return False
        
        # Collect gaze data for 2 seconds
        gaze_samples = []
        start_time = time.time()
        
        while time.time() - start_time < 2.0:
            ret, frame = cap.read()
            if not ret:
                continue
            
            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = face_mesh.detect(mp_image)
            
            if results.face_landmarks:
                iris_x, iris_y = get_iris_center(results.face_landmarks[0], w, h)
                gaze_samples.append((iris_x, iris_y))
            
            # Show progress
            progress = (time.time() - start_time) / 2.0
            cv2.rectangle(cal_screen, (50, 150), (50 + int(500 * progress), 180), (0, 255, 0), -1)
            cv2.imshow("Calibration", cal_screen)
            cv2.waitKey(1)
        
        if gaze_samples:
            avg_iris_x = np.mean([p[0] for p in gaze_samples])
            avg_iris_y = np.mean([p[1] for p in gaze_samples])
            state.calibration_data[name] = (avg_iris_x, avg_iris_y, screen_x, screen_y)
            print(f"✓ {name.capitalize()} calibrated: iris({avg_iris_x:.1f}, {avg_iris_y:.1f}) → screen({screen_x}, {screen_y})")
    
    cv2.destroyWindow("Calibration")
    config.calibrated = True
    print("\n✓ Calibration complete!\n")
    return True

def iris_to_screen(iris_x, iris_y, frame_w, frame_h):
    """Map iris position to screen coordinates"""
    if not config.calibrated or state.calibration_data['center'] is None:
        # Simple proportional mapping (fallback)
        screen_x = int((iris_x / frame_w) * config.screen_width)
        screen_y = int((iris_y / frame_h) * config.screen_height)
        return screen_x, screen_y
    
    # Use calibration data for better mapping
    center_data = state.calibration_data['center']
    left_data = state.calibration_data['left']
    right_data = state.calibration_data['right']
    
    # Interpolate based on calibration
    if left_data and right_data and center_data:
        # Horizontal mapping
        iris_range = right_data[0] - left_data[0]
        iris_offset = iris_x - left_data[0]
        if iris_range != 0:
            screen_x = int(left_data[2] + (iris_offset / iris_range) * (right_data[2] - left_data[2]))
        else:
            screen_x = config.screen_width // 2
        
        # Vertical mapping (simplified)
        screen_y = int((iris_y / frame_h) * config.screen_height)
        
        # Clamp to screen bounds
        screen_x = max(0, min(config.screen_width - 1, screen_x))
        screen_y = max(0, min(config.screen_height - 1, screen_y))
        
        return screen_x, screen_y
    
    # Fallback
    screen_x = int((iris_x / frame_w) * config.screen_width)
    screen_y = int((iris_y / frame_h) * config.screen_height)
    return screen_x, screen_y

# -------------------- EYE TRACKING --------------------
def process_blink_commands(face_landmarks):
    """Process blink-based commands"""
    if not config.ENABLE_ADVANCED_CONTROLS:
        return None
    
    current_time = time.time()
    is_blinking, ear = blink_detector.detect_blink(face_landmarks)
    
    # Track consecutive blink frames
    if is_blinking:
        state.consecutive_blink_frames += 1
        
        if state.blink_start_time is None:
            state.blink_start_time = current_time
        
        # Check for long blink (emergency)
        blink_duration = current_time - state.blink_start_time
        if blink_duration >= config.LONG_BLINK_TIME and config.ENABLE_ASSISTIVE_CONTROLS:
            if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                state.blink_start_time = None
                state.consecutive_blink_frames = 0
                state.last_command_time = current_time
                return "EMERGENCY_ALERT"
    else:
        # Blink ended
        if state.consecutive_blink_frames >= config.BLINK_FRAMES:
            # Valid blink detected
            state.blink_counter += 1
            state.last_blink_time = current_time
            
            # Check for double blink
            if state.blink_counter == 2:
                time_since_first = current_time - state.last_blink_time
                if time_since_first <= config.DOUBLE_BLINK_WINDOW:
                    state.blink_counter = 0
                    if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                        state.last_command_time = current_time
                        return "DOUBLE_CLICK"
            
            # Single blink (click)
            if state.blink_counter == 1:
                if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                    state.last_command_time = current_time
                    return "CLICK"
        
        state.consecutive_blink_frames = 0
        state.blink_start_time = None
        
        # Reset blink counter if too much time passed
        if current_time - state.last_blink_time > config.DOUBLE_BLINK_WINDOW:
            state.blink_counter = 0
    
    # Check for eyes closed (sleep mode)
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
    """Process direction-based commands and sequences"""
    current_time = time.time()
    direction = direction_detector.detect_direction(screen_x, screen_y)
    
    # Track direction for sequences
    if direction != "CENTER":
        if state.current_direction != direction:
            state.current_direction = direction
            state.direction_start_time = current_time
        elif current_time - state.direction_start_time >= config.DIRECTION_HOLD_TIME:
            # Direction held long enough, add to sequence
            if not state.sequence_buffer or state.sequence_buffer[-1] != direction:
                state.sequence_buffer.append(direction)
                
                if state.sequence_start_time is None:
                    state.sequence_start_time = current_time
                
                # Check for sequence patterns
                if config.ENABLE_ASSISTIVE_CONTROLS:
                    sequence_command = sequence_detector.check_sequence(state.sequence_buffer)
                    if sequence_command:
                        state.sequence_buffer = []
                        state.sequence_start_time = None
                        if current_time - state.last_command_time > config.COMMAND_COOLDOWN:
                            state.last_command_time = current_time
                            return sequence_command
    else:
        state.current_direction = None
        state.direction_start_time = None
    
    # Timeout sequence if too slow
    if state.sequence_start_time and current_time - state.sequence_start_time > config.SEQUENCE_TIMEOUT:
        state.sequence_buffer = []
        state.sequence_start_time = None
    
    # Execute basic direction commands
    if current_time - state.last_gesture_time < config.GESTURE_COOLDOWN:
        return None
    
    if not config.ENABLE_BASIC_CONTROLS:
        return None
    
    command = None
    
    # Diagonal controls (advanced)
    if direction == "UP_LEFT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "VOLUME_UP"
    elif direction == "UP_RIGHT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "BRIGHTNESS_UP"
    elif direction == "DOWN_LEFT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "BACK"
    elif direction == "DOWN_RIGHT" and config.ENABLE_ADVANCED_CONTROLS:
        command = "HOME"
    
    # Cardinal directions (basic)
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
    
    return command

# -------------------- EYE TRACKING --------------------
def get_iris_center(face_landmarks, frame_w, frame_h):
    """Get average iris center from both eyes"""
    left_iris_ids = [474, 475, 476, 477]
    right_iris_ids = [469, 470, 471, 472]
    
    all_xs, all_ys = [], []
    
    for eye_ids in [left_iris_ids, right_iris_ids]:
        for i in eye_ids:
            lm = face_landmarks[i]
            all_xs.append(lm.x * frame_w)
            all_ys.append(lm.y * frame_h)
    
    center_x = np.mean(all_xs)
    center_y = np.mean(all_ys)
    
    return center_x, center_y

# -------------------- VISUALIZATION --------------------
def draw_feedback(frame, iris_x, iris_y, screen_x, screen_y, face_landmarks=None):
    """Draw visual feedback on frame"""
    h, w = frame.shape[:2]
    
    # Draw iris tracking
    cv2.circle(frame, (int(iris_x), int(iris_y)), 8, (0, 0, 255), 2)
    
    # Draw screen position indicator (minimap)
    mini_w, mini_h = 200, 150
    mini_x, mini_y = w - mini_w - 10, 10
    
    # Minimap background
    cv2.rectangle(frame, (mini_x, mini_y), (mini_x + mini_w, mini_y + mini_h), (50, 50, 50), -1)
    cv2.rectangle(frame, (mini_x, mini_y), (mini_x + mini_w, mini_y + mini_h), (255, 255, 255), 2)
    
    # Draw direction zones on minimap
    # Vertical lines
    left_line = mini_x + int(config.LOOK_LEFT_THRESHOLD * mini_w)
    right_line = mini_x + int(config.LOOK_RIGHT_THRESHOLD * mini_w)
    cv2.line(frame, (left_line, mini_y), (left_line, mini_y + mini_h), (100, 100, 100), 1)
    cv2.line(frame, (right_line, mini_y), (right_line, mini_y + mini_h), (100, 100, 100), 1)
    
    # Horizontal lines
    up_line = mini_y + int(config.LOOK_UP_THRESHOLD * mini_h)
    down_line = mini_y + int(config.LOOK_DOWN_THRESHOLD * mini_h)
    cv2.line(frame, (mini_x, up_line), (mini_x + mini_w, up_line), (100, 100, 100), 1)
    cv2.line(frame, (mini_x, down_line), (mini_x + mini_w, down_line), (100, 100, 100), 1)
    
    # Gaze point on minimap
    mini_gaze_x = mini_x + int((screen_x / config.screen_width) * mini_w)
    mini_gaze_y = mini_y + int((screen_y / config.screen_height) * mini_h)
    cv2.circle(frame, (mini_gaze_x, mini_gaze_y), 5, (0, 255, 0), -1)
    
    # Current direction
    current_dir = direction_detector.detect_direction(screen_x, screen_y)
    if current_dir != "CENTER":
        cv2.putText(frame, current_dir, (mini_x, mini_y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    
    # Dwell progress indicator
    progress = state.get_dwell_progress()
    if progress > 0:
        radius = int(20 + progress * 10)
        color = (0, int(255 * progress), int(255 * (1 - progress)))
        cv2.circle(frame, (int(iris_x), int(iris_y)), radius, color, 2)
        
        bar_w = 200
        bar_h = 20
        bar_x = (w - bar_w) // 2
        bar_y = h - 100
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (100, 100, 100), -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(bar_w * progress), bar_y + bar_h), (0, 255, 0), -1)
        cv2.putText(frame, "DWELL CLICK", (bar_x, bar_y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # Blink detection feedback
    if face_landmarks:
        is_blinking, ear = blink_detector.detect_blink(face_landmarks)
        
        # EAR indicator
        ear_text = f"EAR: {ear:.3f}"
        ear_color = (0, 0, 255) if is_blinking else (0, 255, 0)
        cv2.putText(frame, ear_text, (w - 150, h - 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, ear_color, 2)
        
        # Long blink progress
        if state.blink_start_time:
            elapsed = time.time() - state.blink_start_time
            if elapsed > 0.5:  # Show after 0.5s
                blink_progress = min(elapsed / config.LONG_BLINK_TIME, 1.0)
                bar_x = (w - 200) // 2
                bar_y = h - 60
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 200, bar_y + 15), (100, 100, 100), -1)
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(200 * blink_progress), bar_y + 15), (0, 0, 255), -1)
                cv2.putText(frame, "LONG BLINK", (bar_x, bar_y - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Eyes closed progress
        if state.eyes_closed_start:
            elapsed = time.time() - state.eyes_closed_start
            if elapsed > 1.0:  # Show after 1s
                sleep_progress = min(elapsed / config.EYES_CLOSED_SLEEP, 1.0)
                bar_x = (w - 200) // 2
                bar_y = h - 35
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 200, bar_y + 15), (100, 100, 100), -1)
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(200 * sleep_progress), bar_y + 15), (255, 0, 255), -1)
                cv2.putText(frame, "SLEEP MODE", (bar_x, bar_y - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Sequence buffer display
    if state.sequence_buffer:
        seq_text = " > ".join(state.sequence_buffer)
        cv2.putText(frame, f"Sequence: {seq_text}", (10, h - 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
    
    # Last command feedback
    if state.last_command and state.command_display_time:
        elapsed = time.time() - state.command_display_time
        if elapsed < 2.0:  # Show for 2 seconds
            alpha = max(0, 1.0 - elapsed / 2.0)
            cmd_color = (0, int(255 * alpha), int(255 * alpha))
            cv2.putText(frame, f"✓ {state.last_command}", (w // 2 - 100, h - 150), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, cmd_color, 2)
    
    # Status text
    status_y = 30
    cv2.putText(frame, f"Screen: ({screen_x}, {screen_y})", 
                (10, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    status_y += 30
    
    mode = "CALIBRATED" if config.calibrated else "UNCALIBRATED"
    color = (0, 255, 0) if config.calibrated else (0, 165, 255)
    cv2.putText(frame, f"Mode: {mode}", 
                (10, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    status_y += 30
    
    sim_text = "SIMULATION" if config.SIMULATION_MODE else "LIVE"
    sim_color = (0, 255, 255) if config.SIMULATION_MODE else (0, 255, 0)
    cv2.putText(frame, f"Control: {sim_text}", 
                (10, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, sim_color, 2)
    status_y += 30
    
    cv2.putText(frame, "C: Calibrate | M: Toggle Mode | ESC: Quit", 
                (10, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

# -------------------- MAIN CONTROL LOOP --------------------
print("=== EYE-CONTROLLED ASSISTIVE DEVICE ===")
print("\n📋 CONTROLS:")
print("  C - Start calibration")
print("  M - Toggle Simulation/Live mode")
print("  SPACE - Pause/Resume cursor control")
print("  ESC - Exit")
print("\n✨ FEATURES:")
print("  • Dwell-time click (stare 1.5s)")
print("  • Blink detection for clicks")
print("  • Direction-based commands")
print("  • Sequence gestures")
print("  • Assistive patient controls")
print("\n🎮 COMMAND MAPPING:")
print("  Basic: UP/DOWN/LEFT/RIGHT → Arrow keys/Scroll")
print("  Blink once → CLICK")
print("  Blink twice → DOUBLE CLICK")
print("  Long blink (3s) → EMERGENCY ALERT")
print("  Diagonals: UP-LEFT→Volume, UP-RIGHT→Brightness")
print("  Sequences: LEFT-RIGHT-LEFT→Call Nurse, UP-DOWN-UP→Adjust Bed")
print("  Eyes closed 5s → SLEEP MODE")
print(f"\n⚙️  Mode: {'SIMULATION (Safe Testing)' if config.SIMULATION_MODE else 'LIVE (Real Commands)'}")
print("\nStarting...\n")

cursor_control_enabled = False

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        h, w, _ = frame.shape
        
        # Detect face and iris
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = face_mesh.detect(mp_image)
        
        if results.face_landmarks:
            face = results.face_landmarks[0]
            
            # Get iris position
            iris_x, iris_y = get_iris_center(face, w, h)
            
            # Map to screen coordinates
            screen_x, screen_y = iris_to_screen(iris_x, iris_y, w, h)
            
            # Smooth gaze
            smooth_x, smooth_y = state.add_gaze(screen_x, screen_y)
            
            # Move cursor (if enabled)
            if cursor_control_enabled and config.calibrated:
                current_x, current_y = pyautogui.position()
                
                # Limit cursor speed for safety
                dx = smooth_x - current_x
                dy = smooth_y - current_y
                distance = np.sqrt(dx**2 + dy**2)
                
                if distance > config.MAX_CURSOR_SPEED:
                    scale = config.MAX_CURSOR_SPEED / distance
                    dx *= scale
                    dy *= scale
                
                new_x = int(current_x + dx)
                new_y = int(current_y + dy)
                pyautogui.moveTo(new_x, new_y, duration=0.1)
                
                # Check for dwell click
                if state.check_dwell((smooth_x, smooth_y)):
                    pyautogui.click()
                    print("✓ DWELL CLICK!")
            
            # Process commands (even without cursor control)
            # Blink-based commands
            blink_command = process_blink_commands(face)
            if blink_command:
                command_executor.execute(blink_command)
                state.last_command = blink_command
                state.command_display_time = time.time()
            
            # Direction-based commands
            direction_command = process_direction_commands(int(smooth_x), int(smooth_y))
            if direction_command:
                command_executor.execute(direction_command)
                state.last_command = direction_command
                state.command_display_time = time.time()
            
            # Visual feedback
            draw_feedback(frame, iris_x, iris_y, int(smooth_x), int(smooth_y), face)
        else:
            cv2.putText(frame, "NO FACE DETECTED", (w//2 - 100, h//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Display
        cv2.imshow("Eye Control System", frame)
        
        # Handle keyboard
        key = cv2.waitKey(1) & 0xFF
        
        if key == 27:  # ESC
            break
        elif key == ord('c') or key == ord('C'):
            calibrate_gaze()
        elif key == ord(' '):  # SPACE
            cursor_control_enabled = not cursor_control_enabled
            status = "ENABLED" if cursor_control_enabled else "DISABLED"
            print(f"\n{'='*40}")
            print(f"Cursor control: {status}")
            print(f"{'='*40}\n")
        elif key == ord('m') or key == ord('M'):  # M for mode toggle
            config.SIMULATION_MODE = not config.SIMULATION_MODE
            mode = "SIMULATION" if config.SIMULATION_MODE else "LIVE"
            print(f"\n{'='*40}")
            print(f"⚠️  Control mode: {mode}")
            if not config.SIMULATION_MODE:
                print("⚠️  WARNING: Real commands will be executed!")
            print(f"{'='*40}\n")

except KeyboardInterrupt:
    print("\nStopped by user")
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("\n=== System Shutdown ===")
