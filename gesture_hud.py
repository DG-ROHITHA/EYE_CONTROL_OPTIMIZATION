"""
Gesture HUD Renderer for NeuroGaze Elite
Visual overlay for hand landmarks, gestures, and fusion mode indication

This module renders on top of the existing HUD:
- 21 hand landmarks as dots + skeleton connections
- Current gesture name with confidence bar
- Fusion mode indicator (EYE / HAND / FUSED)
- Hand tracking diagnostics in debug mode

Benchmark: ≤2ms overlay rendering on main 30fps loop
Non-blocking: All draw calls complete before frame display
Color scheme: Landmarks in BGR (OpenCV), fingertips=coral, knuckles=teal, wrist=gray
"""

from __future__ import annotations

import cv2
import numpy as np
import logging
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class HUDMode(Enum):
    """HUD display modes"""
    MINIMAL = "minimal"  # Only fps + gesture
    STANDARD = "standard"  # Landmarks + gesture name + mode
    DEBUG = "debug"  # All above + diagnostics


@dataclass
class GestureDisplayInfo:
    """Info to display about current gesture"""
    gesture_name: str = "none"
    confidence: float = 0.0
    hand_position: Tuple[int, int] = (0, 0)
    handedness: str = "Right"
    notes: str = ""


class GestureHUDRenderer:
    """
    Renders gesture information on video frame.
    Extends the existing HUDRenderer with hand-specific overlays.
    """
    
    # Colors in BGR (OpenCV format)
    COLOR_WRIST = (200, 200, 200)  # Light gray
    COLOR_PALM = (150, 150, 200)   # Light purple/gray
    COLOR_THUMB = (50, 100, 255)   # Red
    COLOR_INDEX = (0, 165, 255)    # Orange
    COLOR_MIDDLE = (0, 200, 255)   # Yellow-orange
    COLOR_RING = (0, 255, 255)     # Yellow
    COLOR_PINKY = (255, 165, 0)    # Cyan
    COLOR_FINGERTIP = (0, 100, 255)  # Coral/Orange
    COLOR_KNUCKLE = (255, 100, 0)    # Teal
    
    # MediaPipe hand landmark connections (21 landmarks)
    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
        (0, 5), (5, 6), (6, 7), (7, 8),      # Index
        (0, 9), (9, 10), (10, 11), (11, 12), # Middle
        (0, 13), (13, 14), (14, 15), (15, 16), # Ring
        (0, 17), (17, 18), (18, 19), (19, 20) # Pinky
    ]
    
    def __init__(self, frame_width: int, frame_height: int, mode: HUDMode = HUDMode.STANDARD):
        """
        Initialize gesture HUD renderer.
        
        Args:
            frame_width: Video frame width
            frame_height: Video frame height
            mode: Display mode
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.mode = mode
        
        # State tracking
        self.landmarks_visible = True
        self.gesture_display_info: Optional[GestureDisplayInfo] = None
        self.last_hand_landmarks: Optional[List] = None
        self.fps_counter = 0
        
        logger.info(f"✓ GestureHUDRenderer initialized ({mode.value} mode)")

    def render_hand_overlay(
        self,
        frame: np.ndarray,
        hand_landmarks: Optional[List[Tuple[float, float]]] = None,
        gesture_info: Optional[GestureDisplayInfo] = None,
        fusion_mode: str = "eye_leads_hand_confirms",
        diagnostics: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Render hand gesture overlay on frame.
        
        Args:
            frame: Input video frame (BGR)
            hand_landmarks: List of (x, y) normalized hand landmarks (0-1 range)
            gesture_info: Current gesture information
            fusion_mode: Current fusion mode string
            diagnostics: Diagnostic info dict (for debug mode)
            
        Returns:
            Frame with hand overlay rendered
        """
        display_frame = frame.copy()
        
        # Store for continuity
        if hand_landmarks:
            self.last_hand_landmarks = hand_landmarks
        if gesture_info:
            self.gesture_display_info = gesture_info
        
        # Render based on mode
        if self.mode == HUDMode.MINIMAL:
            display_frame = self._render_minimal(display_frame, fusion_mode)
        elif self.mode == HUDMode.STANDARD:
            display_frame = self._render_standard(display_frame, fusion_mode)
        elif self.mode == HUDMode.DEBUG:
            display_frame = self._render_debug(display_frame, fusion_mode, diagnostics)
        
        # Always render landmarks and gesture if available
        if self.landmarks_visible and hand_landmarks:
            display_frame = self._render_landmarks(display_frame, hand_landmarks)
        
        return display_frame

    def _render_landmarks(self, frame: np.ndarray, landmarks: List[Tuple[float, float]]) -> np.ndarray:
        """Render 21 hand landmarks and skeleton"""
        display_frame = frame.copy()
        
        if not landmarks or len(landmarks) < 21:
            return display_frame
        
        # Convert normalized coordinates to pixels
        landmarks_px = [
            (int(lm[0] * self.frame_width), int(lm[1] * self.frame_height))
            for lm in landmarks
        ]
        
        # Draw connections (skeleton)
        for conn_start, conn_end in self.HAND_CONNECTIONS:
            if conn_start < len(landmarks_px) and conn_end < len(landmarks_px):
                pt1 = landmarks_px[conn_start]
                pt2 = landmarks_px[conn_end]
                
                # Color based on finger
                if conn_start == 0:  # Wrist
                    color = self.COLOR_WRIST
                elif conn_start <= 4:  # Thumb
                    color = self.COLOR_THUMB
                elif conn_start <= 8:  # Index
                    color = self.COLOR_INDEX
                elif conn_start <= 12:  # Middle
                    color = self.COLOR_MIDDLE
                elif conn_start <= 16:  # Ring
                    color = self.COLOR_RING
                else:  # Pinky
                    color = self.COLOR_PINKY
                
                cv2.line(display_frame, pt1, pt2, color, 2)
        
        # Draw landmarks (circles at joints)
        for i, pt in enumerate(landmarks_px):
            if i == 0:  # Wrist
                cv2.circle(display_frame, pt, 6, self.COLOR_WRIST, -1)
            elif i % 4 == 0:  # Fingertip
                cv2.circle(display_frame, pt, 5, self.COLOR_FINGERTIP, -1)
            else:  # Knuckle
                cv2.circle(display_frame, pt, 4, self.COLOR_KNUCKLE, -1)
        
        return display_frame

    def _render_minimal(self, frame: np.ndarray, fusion_mode: str) -> np.ndarray:
        """Minimal HUD: gesture name + confidence only"""
        display_frame = frame.copy()
        
        # Gesture name in top-right corner
        if self.gesture_display_info:
            text = f"{self.gesture_display_info.gesture_name} ({self.gesture_display_info.confidence:.0%})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            
            # Text background
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x, y = self.frame_width - text_size[0] - 15, 30
            cv2.rectangle(display_frame, (x - 5, y - text_size[1] - 5), 
                         (x + text_size[0] + 5, y + 5), (50, 50, 50), -1)
            cv2.putText(display_frame, text, (x, y), font, font_scale, (0, 255, 0), thickness)
        
        # Fusion mode pill (top-right corner, below gesture)
        fusion_text = fusion_mode.replace("_", " ").upper()
        self._draw_mode_pill(display_frame, fusion_text, x=self.frame_width - 180, y=65)
        
        return display_frame

    def _render_standard(self, frame: np.ndarray, fusion_mode: str) -> np.ndarray:
        """Standard HUD: landmarks + gesture name + confidence bar + mode"""
        display_frame = frame.copy()
        
        # Full gesture info panel (top-right)
        if self.gesture_display_info:
            self._draw_gesture_panel(display_frame)
        
        # Fusion mode indicator
        fusion_text = fusion_mode.replace("_", " ").upper()
        self._draw_mode_pill(display_frame, fusion_text, x=self.frame_width - 200, y=150)
        
        return display_frame

    def _render_debug(self, frame: np.ndarray, fusion_mode: str, diagnostics: Optional[Dict]) -> np.ndarray:
        """Debug HUD: all above + diagnostics"""
        display_frame = self._render_standard(frame, fusion_mode)
        
        # Diagnostics panel (bottom-left)
        if diagnostics:
            self._draw_diagnostics_panel(display_frame, diagnostics)
        
        return display_frame

    def _draw_gesture_panel(self, frame: np.ndarray):
        """Draw gesture info panel"""
        if not self.gesture_display_info:
            return
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        
        # Panel position
        x, y = self.frame_width - 200, 30
        panel_height = 80
        panel_width = 180
        
        # Background
        cv2.rectangle(frame, (x - 5, y - 5), (x + panel_width + 5, y + panel_height + 5),
                     (40, 40, 40), -1)
        cv2.rectangle(frame, (x - 5, y - 5), (x + panel_width + 5, y + panel_height + 5),
                     (100, 100, 100), 2)
        
        # Gesture name
        gesture_text = self.gesture_display_info.gesture_name.replace("_", " ").upper()
        cv2.putText(frame, gesture_text, (x + 5, y + 20), font, font_scale, (0, 255, 0), thickness)
        
        # Confidence bar
        confidence = self.gesture_display_info.confidence
        bar_width = panel_width - 10
        bar_height = 10
        bar_x = x + 5
        bar_y = y + 35
        
        # Background bar
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height),
                     (50, 50, 50), -1)
        
        # Filled portion
        filled_width = int(bar_width * confidence)
        fill_color = (0, 200, 0) if confidence > 0.7 else (0, 165, 255) if confidence > 0.4 else (0, 0, 255)
        if filled_width > 0:
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled_width, bar_y + bar_height),
                         fill_color, -1)
        
        # Confidence percentage
        conf_text = f"{confidence:.0%}"
        cv2.putText(frame, conf_text, (bar_x + bar_width - 30, bar_y + 20), 
                   font, font_scale * 0.8, (200, 200, 200), 1)
        
        # Handedness
        hand_text = self.gesture_display_info.handedness
        cv2.putText(frame, hand_text, (x + 5, y + 65), font, font_scale * 0.7,
                   (150, 150, 150), 1)

    def _draw_mode_pill(self, frame: np.ndarray, text: str, x: int, y: int):
        """Draw a rounded rectangle "pill" for fusion mode"""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        width = text_size[0] + 16
        height = text_size[1] + 8
        
        # Rounded rectangle background
        cv2.rectangle(frame, (x - 2, y - 2), (x + width + 2, y + height + 2),
                     (100, 100, 200), -1)
        cv2.rectangle(frame, (x - 2, y - 2), (x + width + 2, y + height + 2),
                     (200, 200, 255), 1)
        
        # Text
        cv2.putText(frame, text, (x + 8, y + text_size[1] + 4), font, font_scale,
                   (255, 255, 0), thickness)

    def _draw_diagnostics_panel(self, frame: np.ndarray, diagnostics: Dict):
        """Draw diagnostics info in bottom-left"""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4
        thickness = 1
        
        x, y = 15, frame.shape[0] - 120
        line_height = 20
        
        # Background
        cv2.rectangle(frame, (x - 5, y - 5), (x + 300, y + 120), (20, 20, 20), -1)
        cv2.rectangle(frame, (x - 5, y - 5), (x + 300, y + 120), (100, 100, 100), 1)
        
        # Title
        cv2.putText(frame, "GESTURE DIAGNOSTICS", (x + 5, y + 15), font, font_scale * 1.2,
                   (0, 255, 255), 1)
        
        # Info lines
        lines = [
            f"Hands: {diagnostics.get('hands_detected', 0)}",
            f"FPS: {diagnostics.get('fps', 0):.1f}",
            f"Inference: {diagnostics.get('inference_ms', 0):.1f}ms",
            f"Landmarks: {diagnostics.get('landmarks_detected', 0)}",
            f"Confidence: {diagnostics.get('confidence', 0):.2f}",
        ]
        
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (x + 10, y + 35 + i * line_height), font, font_scale,
                       (200, 200, 200), 1)

    def toggle_landmarks(self):
        """Toggle landmark visibility"""
        self.landmarks_visible = not self.landmarks_visible
        logger.info(f"Landmarks {'enabled' if self.landmarks_visible else 'disabled'}")

    def set_mode(self, mode: HUDMode):
        """Change HUD display mode"""
        self.mode = mode
        logger.info(f"HUD mode changed to: {mode.value}")

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return rendering diagnostics"""
        return {
            "mode": self.mode.value,
            "landmarks_visible": self.landmarks_visible,
            "gesture_displayed": self.gesture_display_info is not None if self.gesture_display_info else False,
        }


# Integration Example for neurogaze_elite.py:
"""
# In neurogaze_elite.py __init__:
from gesture_hud import GestureHUDRenderer, GestureDisplayInfo, HUDMode

self.gesture_hud = GestureHUDRenderer(
    frame_width=int(self.camera_width),
    frame_height=int(self.camera_height),
    mode=HUDMode.STANDARD
)

# In main loop after gesture detection:
gesture_display_info = GestureDisplayInfo(
    gesture_name=gesture_result.gesture_type.value,
    confidence=gesture_result.confidence,
    hand_position=gesture_result.hand_position,
    handedness=gesture_result.hand.handedness
)

display_frame = self.gesture_hud.render_hand_overlay(
    frame=display_frame,
    hand_landmarks=[(lm.x, lm.y) for lm in gesture_result.hand.landmarks],
    gesture_info=gesture_display_info,
    fusion_mode=self.fusion_engine.config.fusion_mode.value
)

# In keyboard handler for 'G' key:
if key == ord('G'):
    self.gesture_hud.toggle_landmarks()
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    renderer = GestureHUDRenderer(1280, 720, HUDMode.STANDARD)
    print(f"✓ Gesture HUD renderer ready")
    print(f"  Diagnostics: {renderer.get_diagnostics()}")
