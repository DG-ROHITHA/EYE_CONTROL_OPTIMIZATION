"""
HUD Renderer Module
Comprehensive heads-up display with strain monitoring, gaze heatmap, and real-time feedback
Features C & D: Gaze heatmap, blue-light filter
Features: Strain guard panel, intent confidence display, break countdown
Part of NeuroGaze Elite
"""

import cv2
import numpy as np
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class HUDMode(Enum):
    """HUD display modes"""
    MINIMAL = "minimal"       # Show only essential info
    STANDARD = "standard"     # Full HUD display
    DEBUG = "debug"          # Debug with extra diagnostics


@dataclass
class HUDColors:
    """HUD color palette (BGR format for OpenCV)"""
    # Status colors
    normal = (0, 255, 0)      # Green
    warning = (0, 165, 255)   # Orange
    alert = (0, 0, 255)       # Red
    info = (255, 255, 0)      # Cyan
    
    # UI colors
    text_primary = (255, 255, 255)     # White
    text_secondary = (200, 200, 200)   # Light gray
    background_dark = (30, 30, 30)     # Dark gray
    background_semi = (50, 50, 50)     # Semi-transparent base
    
    # Heatmap colors
    heatmap_cool = (255, 0, 0)         # Blue
    heatmap_warm = (0, 0, 255)         # Red


class HUDRenderer:
    """
    Comprehensive HUD rendering engine.
    Handles all on-screen display elements for NeuroGaze Elite.
    """
    
    def __init__(
        self,
        frame_width: int = 1280,
        frame_height: int = 720,
        mode: HUDMode = HUDMode.STANDARD
    ):
        """
        Initialize HUD renderer.
        
        Args:
            frame_width: Video frame width
            frame_height: Video frame height
            mode: HUD display mode
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.mode = mode
        self.colors = HUDColors()
        
        # Heatmap buffer (Feature C: Gaze heatmap)
        self.heatmap = np.zeros((frame_height, frame_width, 1), dtype=np.float32)
        self.heatmap_enabled = False
        
        # Blue-light filter (Feature D)
        self.blue_light_filter_enabled = False
        
        # Font settings
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_size_small = 0.4
        self.font_size_normal = 0.6
        self.font_size_large = 1.0
        self.font_thickness_normal = 1
        self.font_thickness_bold = 2
        
        logger.info(f"✓ HUDRenderer initialized ({frame_width}x{frame_height}, mode: {mode.value})")
    
    def render_frame(
        self,
        frame: np.ndarray,
        gaze_position: Optional[Tuple[float, float]] = None,
        gaze_velocity: Optional[Tuple[float, float]] = None,
        intent_confidence: Optional[float] = None,
        strain_metrics: Optional[dict] = None,
        fps: Optional[float] = None,
        backend_info: Optional[dict] = None,
        mode_info: Optional[str] = None
    ) -> np.ndarray:
        """
        Render complete HUD on frame.
        
        Args:
            frame: Input BGR frame
            gaze_position: (x, y) gaze coordinates
            gaze_velocity: (vx, vy) velocity
            intent_confidence: Confidence 0-1
            strain_metrics: Dict with strain data
            fps: Frames per second
            backend_info: GPU/CUDA info
            mode_info: Current mode string
            
        Returns:
            Frame with HUD overlaid
        """
        output = frame.copy()
        
        # Apply blue-light filter if enabled (Feature D)
        if self.blue_light_filter_enabled:
            output = self._apply_blue_light_filter(output)
        
        # Render gaze heatmap if enabled (Feature C)
        if self.heatmap_enabled and gaze_position is not None:
            output = self._render_heatmap(output, gaze_position)
        
        # Render gaze cursor
        if gaze_position is not None:
            output = self._render_gaze_cursor(output, gaze_position, gaze_velocity)
        
        # Render HUD panels based on mode
        if self.mode == HUDMode.MINIMAL:
            output = self._render_minimal_hud(output, fps, intent_confidence)
        
        elif self.mode == HUDMode.STANDARD:
            output = self._render_standard_hud(
                output, gaze_position, intent_confidence,
                strain_metrics, fps, backend_info, mode_info
            )
        
        elif self.mode == HUDMode.DEBUG:
            output = self._render_debug_hud(
                output, gaze_position, gaze_velocity,
                intent_confidence, strain_metrics, fps,
                backend_info, mode_info
            )
        
        return output
    
    def _apply_blue_light_filter(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply blue-light filter to reduce eye strain.
        Feature D: Toggle-able blue-light filter.
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            Filtered frame
        """
        if frame.shape[2] < 3:
            return frame
        
        # Reduce blue channel (index 0 in BGR), boost red (index 2)
        filtered = frame.copy().astype(np.float32)
        filtered[:, :, 0] = filtered[:, :, 0] * 0.70  # Reduce blue by 30%
        filtered[:, :, 2] = np.minimum(filtered[:, :, 2] * 1.15, 255)  # Boost red by 15%
        
        return np.clip(filtered, 0, 255).astype(np.uint8)
    
    def _render_heatmap(
        self,
        frame: np.ndarray,
        gaze_position: Tuple[float, float]
    ) -> np.ndarray:
        """
        Render gaze heatmap overlay.
        Feature C: Shows which screen zones user fixates most.
        
        Args:
            frame: Input frame
            gaze_position: Current gaze (x, y)
            
        Returns:
            Frame with heatmap overlay
        """
        x, y = int(gaze_position[0]), int(gaze_position[1])
        
        # Clamp to bounds
        x = max(0, min(self.frame_width - 1, x))
        y = max(0, min(self.frame_height - 1, y))
        
        # Draw gaussian blob at gaze position
        radius = 30
        y_start = max(0, y - radius)
        y_end = min(self.frame_height, y + radius)
        x_start = max(0, x - radius)
        x_end = min(self.frame_width, x + radius)
        
        # Create gaussian kernel
        kernel_h = y_end - y_start
        kernel_w = x_end - x_start
        
        if kernel_h > 0 and kernel_w > 0:
            yy, xx = np.ogrid[-radius:radius+1, -radius:radius+1]
            gaussian = np.exp(-(xx**2 + yy**2) / (2.0 * 15.0**2))
            
            gaussian_region = gaussian[
                max(0, -y_start):max(0, -y_start) + kernel_h,
                max(0, -x_start):max(0, -x_start) + kernel_w
            ]
            
            self.heatmap[y_start:y_end, x_start:x_end, 0] += gaussian_region * 10.0
        
        # Normalize and colorize heatmap
        heatmap_norm = np.clip(self.heatmap / np.max(self.heatmap + 1e-6) * 255, 0, 255).astype(np.uint8)
        heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
        
        # Blend with frame (40% heatmap, 60% frame)
        output = cv2.addWeighted(frame, 0.6, heatmap_color, 0.4, 0)
        
        return output
    
    def _render_gaze_cursor(
        self,
        frame: np.ndarray,
        gaze_position: Tuple[float, float],
        gaze_velocity: Optional[Tuple[float, float]] = None
    ) -> np.ndarray:
        """
        Render gaze cursor on frame.
        
        Args:
            frame: Input frame
            gaze_position: (x, y) gaze coordinates
            gaze_velocity: Optional velocity for visualization
            
        Returns:
            Frame with cursor
        """
        x, y = int(gaze_position[0]), int(gaze_position[1])
        
        # Clamp to bounds
        x = max(0, min(self.frame_width - 1, x))
        y = max(0, min(self.frame_height - 1, y))
        
        # Draw crosshair cursor
        size = 25
        thickness = 2
        
        # Horizontal and vertical lines
        cv2.line(frame, (x - size, y), (x + size, y), self.colors.info, thickness)
        cv2.line(frame, (x, y - size), (x, y + size), self.colors.info, thickness)
        
        # Center dot
        cv2.circle(frame, (x, y), 4, self.colors.normal, -1)
        
        # Draw velocity vector if available
        if gaze_velocity is not None:
            vx, vy = gaze_velocity
            if abs(vx) > 0.1 or abs(vy) > 0.1:
                # Scale velocity for visualization
                end_x = int(x + vx * 5)
                end_y = int(y + vy * 5)
                cv2.arrowedLine(frame, (x, y), (end_x, end_y), self.colors.warning, 2)
        
        return frame
    
    def _render_minimal_hud(
        self,
        frame: np.ndarray,
        fps: Optional[float] = None,
        intent_confidence: Optional[float] = None
    ) -> np.ndarray:
        """Minimal HUD - just FPS and intent"""
        y_offset = 30
        
        # FPS
        if fps is not None:
            fps_text = f"FPS: {fps:.0f}"
            cv2.putText(frame, fps_text, (10, y_offset), self.font,
                       self.font_size_normal, self.colors.normal, self.font_thickness_normal)
        
        # Intent confidence
        if intent_confidence is not None:
            y_offset += 30
            confidence_pct = int(intent_confidence * 100)
            conf_text = f"INTENT: {confidence_pct}%"
            color = self.colors.normal if intent_confidence >= 0.7 else self.colors.warning
            cv2.putText(frame, conf_text, (10, y_offset), self.font,
                       self.font_size_normal, color, self.font_thickness_normal)
        
        return frame
    
    def _render_standard_hud(
        self,
        frame: np.ndarray,
        gaze_position: Optional[Tuple[float, float]] = None,
        intent_confidence: Optional[float] = None,
        strain_metrics: Optional[dict] = None,
        fps: Optional[float] = None,
        backend_info: Optional[dict] = None,
        mode_info: Optional[str] = None
    ) -> np.ndarray:
        """Standard HUD with strain panel and status"""
        
        # Top-left: Mode and backend info
        y = 25
        x = 10
        
        if mode_info:
            cv2.putText(frame, mode_info, (x, y), self.font,
                       self.font_size_normal, self.colors.text_primary, self.font_thickness_normal)
            y += 25
        
        if backend_info:
            backend_str = f"GPU: {backend_info.get('backend', 'CPU')}"
            cv2.putText(frame, backend_str, (x, y), self.font,
                       self.font_size_small, self.colors.text_secondary, self.font_thickness_normal)
            y += 20
        
        if fps is not None:
            fps_text = f"FPS: {fps:.0f}"
            cv2.putText(frame, fps_text, (x, y), self.font,
                       self.font_size_small, self.colors.text_secondary, self.font_thickness_normal)
        
        # Bottom-right: Strain panel
        if strain_metrics:
            self._render_strain_panel(frame, strain_metrics)
        
        # Bottom-left: Gaze position and intent
        y = self.frame_height - 60
        
        if gaze_position is not None:
            pos_text = f"Gaze: ({int(gaze_position[0])}, {int(gaze_position[1])})"
            cv2.putText(frame, pos_text, (10, y), self.font,
                       self.font_size_small, self.colors.text_secondary, self.font_thickness_normal)
            y += 20
        
        if intent_confidence is not None:
            confidence_pct = int(intent_confidence * 100)
            conf_text = f"INTENT: {confidence_pct}%"
            color = self.colors.normal if intent_confidence >= 0.7 else self.colors.warning
            cv2.putText(frame, conf_text, (10, y), self.font,
                       self.font_size_normal, color, self.font_thickness_normal)
        
        return frame
    
    def _render_strain_panel(self, frame: np.ndarray, strain_metrics: dict) -> None:
        """Render strain monitoring panel (bottom-right)"""
        panel_width = 280
        panel_height = 150
        x = self.frame_width - panel_width - 10
        y = self.frame_height - panel_height - 10
        
        # Background
        cv2.rectangle(frame, (x, y), (x + panel_width, y + panel_height),
                     self.colors.background_dark, -1)
        cv2.rectangle(frame, (x, y), (x + panel_width, y + panel_height),
                     self.colors.text_secondary, 2)
        
        # Title
        cv2.putText(frame, "STRAIN GUARD", (x + 10, y + 20), self.font,
                   self.font_size_normal, self.colors.info, self.font_thickness_bold)
        
        y_offset = y + 50
        
        # Blink rate
        if "blink_rate" in strain_metrics:
            br = strain_metrics["blink_rate"]
            br_text = f"Blink: {br:.1f}/min"
            color = self.colors.normal if 8 <= br <= 20 else self.colors.warning
            cv2.putText(frame, br_text, (x + 10, y_offset), self.font,
                       self.font_size_small, color, self.font_thickness_normal)
            y_offset += 25
        
        # PERCLOS
        if "perclos" in strain_metrics:
            perclos = strain_metrics["perclos"]
            perclos_text = f"PERCLOS: {perclos:.1f}%"
            color = self.colors.normal if perclos < 10 else self.colors.warning
            cv2.putText(frame, perclos_text, (x + 10, y_offset), self.font,
                       self.font_size_small, color, self.font_thickness_normal)
            y_offset += 25
        
        # Fatigue level
        if "fatigue_level" in strain_metrics:
            fatigue = strain_metrics["fatigue_level"]
            fatigue_text = f"Fatigue: {fatigue}"
            color_map = {
                "EXCELLENT": self.colors.normal,
                "NORMAL": self.colors.normal,
                "WARNING": self.colors.warning,
                "ALERT": self.colors.alert
            }
            color = color_map.get(fatigue, self.colors.text_secondary)
            cv2.putText(frame, fatigue_text, (x + 10, y_offset), self.font,
                       self.font_size_small, color, self.font_thickness_normal)
    
    def _render_debug_hud(
        self,
        frame: np.ndarray,
        gaze_position: Optional[Tuple[float, float]] = None,
        gaze_velocity: Optional[Tuple[float, float]] = None,
        intent_confidence: Optional[float] = None,
        strain_metrics: Optional[dict] = None,
        fps: Optional[float] = None,
        backend_info: Optional[dict] = None,
        mode_info: Optional[str] = None
    ) -> np.ndarray:
        """Debug HUD with comprehensive diagnostics"""
        
        # Render standard first
        frame = self._render_standard_hud(
            frame, gaze_position, intent_confidence,
            strain_metrics, fps, backend_info, mode_info
        )
        
        # Add debug info in top-right
        y = 25
        x = self.frame_width - 300
        
        cv2.rectangle(frame, (x - 10, 15), (self.frame_width - 5, 300),
                     self.colors.background_semi, -1)
        
        # Debug title
        cv2.putText(frame, "DEBUG", (x, y), self.font,
                   self.font_size_small, self.colors.info, self.font_thickness_bold)
        y += 25
        
        # Velocity
        if gaze_velocity:
            vx, vy = gaze_velocity
            vel_text = f"Vel: ({vx:.1f}, {vy:.1f}) px/fr"
            speed = np.sqrt(vx**2 + vy**2)
            cv2.putText(frame, vel_text, (x, y), self.font,
                       self.font_size_small, self.colors.text_secondary, 1)
            y += 18
            speed_text = f"Speed: {speed:.1f} px/fr"
            cv2.putText(frame, speed_text, (x, y), self.font,
                       self.font_size_small, self.colors.text_secondary, 1)
        
        y += 25
        
        # Backend info
        if backend_info:
            backend_text = f"Backend: {backend_info.get('backend', 'CPU')}"
            cuda_status = "✓ CUDA" if backend_info.get('cuda_enabled') else "✗ CPU"
            cv2.putText(frame, backend_text, (x, y), self.font,
                       self.font_size_small, self.colors.text_secondary, 1)
            y += 18
            cv2.putText(frame, cuda_status, (x, y), self.font,
                       self.font_size_small, self.colors.normal if backend_info.get('cuda_enabled') else self.colors.warning, 1)
        
        return frame
    
    def toggle_heatmap(self) -> None:
        """Toggle gaze heatmap display"""
        self.heatmap_enabled = not self.heatmap_enabled
        status = "ON" if self.heatmap_enabled else "OFF"
        logger.info(f"Heatmap toggled: {status}")
    
    def toggle_blue_light_filter(self) -> None:
        """Toggle blue-light filter"""
        self.blue_light_filter_enabled = not self.blue_light_filter_enabled
        status = "ON" if self.blue_light_filter_enabled else "OFF"
        logger.info(f"Blue-light filter toggled: {status}")
    
    def reset_heatmap(self) -> None:
        """Clear heatmap data"""
        self.heatmap.fill(0)
        logger.info("Heatmap reset")
    
    def set_mode(self, mode: HUDMode) -> None:
        """Set HUD display mode"""
        self.mode = mode
        logger.info(f"HUD mode: {mode.value}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test HUD renderer
    logger.info("Testing HUDRenderer...")
    
    renderer = HUDRenderer(1280, 720, HUDMode.STANDARD)
    
    # Create test frame
    test_frame = np.ones((720, 1280, 3), dtype=np.uint8) * 50
    
    # Render with test data
    output = renderer.render_frame(
        test_frame,
        gaze_position=(640, 360),
        gaze_velocity=(5.0, 2.0),
        intent_confidence=0.85,
        strain_metrics={
            "blink_rate": 15.5,
            "perclos": 8.2,
            "fatigue_level": "NORMAL"
        },
        fps=30.0,
        backend_info={"backend": "CUDA", "cuda_enabled": True},
        mode_info="LIVE - 5pt calibration active"
    )
    
    logger.info(f"✓ Frame rendered: {output.shape}")
    
    # Test toggles
    renderer.toggle_heatmap()
    logger.info(f"Heatmap enabled: {renderer.heatmap_enabled}")
    
    renderer.toggle_blue_light_filter()
    logger.info(f"Blue-light filter enabled: {renderer.blue_light_filter_enabled}")
    
    # Test modes
    renderer.set_mode(HUDMode.DEBUG)
    logger.info(f"Current mode: {renderer.mode.value}")
    
    logger.info("✓ HUDRenderer tests complete")
