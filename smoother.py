"""
Kalman Filter for Gaze Tracking with GPU Support
2D Kalman filter with optional CuPy GPU acceleration and velocity tracking
Fixes GAP 2: Wires Kalman velocity output for intent detection
Feature B: CuPy GPU tensors for accelerated state matrix operations
Part of NeuroGaze Elite
"""

import numpy as np
import logging
from typing import Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import CuPy for GPU acceleration
try:
    import cupy as cp
    CUPY_AVAILABLE = True
    logger.info("✓ CuPy available - GPU Kalman filter enabled")
except ImportError:
    CUPY_AVAILABLE = False
    logger.info("CuPy not available - using NumPy Kalman filter (CPU)")


@dataclass
class KalmanState:
    """Current Kalman filter state"""
    position: Tuple[float, float]      # (x, y) screen position
    velocity: Tuple[float, float]      # (vx, vy) pixels per frame
    position_covariance: float         # Uncertainty in position
    velocity_covariance: float         # Uncertainty in velocity
    confidence: float                  # 0-1 confidence score


class KalmanFilter2D:
    """
    2D Kalman filter for smooth gaze position tracking.
    Supports both CPU (NumPy) and GPU (CuPy) backends.
    
    State vector: [x, y, vx, vy]
    - x, y: screen position
    - vx, vy: velocity (pixels per frame)
    """
    
    def __init__(
        self,
        process_variance: float = 1e-5,
        measurement_variance: float = 1e-1,
        use_gpu: bool = True
    ):
        """
        Initialize Kalman filter.
        
        Args:
            process_variance: Process noise covariance (lower = smoother)
            measurement_variance: Measurement noise covariance (sensor accuracy)
            use_gpu: Try to use GPU (CuPy) if available
        """
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.use_gpu = use_gpu and CUPY_AVAILABLE
        self.backend = "GPU" if self.use_gpu else "CPU"
        
        # Choose numpy/cupy backend
        self.xp = cp if self.use_gpu else np
        
        # Initialize state vector [x, y, vx, vy]
        self.state = self.xp.zeros((4, 1))
        
        # State transition matrix (constant velocity model)
        # Next state = F @ current_state
        self.F = self.xp.array([
            [1, 0, 1, 0],  # x' = x + vx
            [0, 1, 0, 1],  # y' = y + vy
            [0, 0, 1, 0],  # vx' = vx
            [0, 0, 0, 1]   # vy' = vy
        ], dtype=self.xp.float32)
        
        # Measurement matrix (we only measure position, not velocity)
        self.H = self.xp.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=self.xp.float32)
        
        # Process covariance (how much we trust our motion model)
        self.Q = self.xp.eye(4, dtype=self.xp.float32) * process_variance
        
        # Measurement covariance (how much we trust the sensor)
        self.R = self.xp.eye(2, dtype=self.xp.float32) * measurement_variance
        
        # State estimation covariance
        self.P = self.xp.eye(4, dtype=self.xp.float32)
        
        # Flags
        self.initialized = False
        self.frame_count = 0
        
        if self.use_gpu:
            logger.info(f"✓ Kalman filter using GPU backend (CuPy)")
        else:
            logger.info(f"Kalman filter using CPU backend (NumPy)")
    
    def predict(self) -> Tuple[float, float]:
        """
        Predict next state based on motion model.
        Called before receiving new measurement.
        
        Returns:
            Predicted (x, y) position
        """
        # Predict state: x_pred = F @ x
        self.state = self.F @ self.state
        
        # Predict covariance: P_pred = F @ P @ F^T + Q
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        # Extract position from state
        x = float(self.state[0, 0])
        y = float(self.state[1, 0])
        
        return x, y
    
    def update(self, measurement: Tuple[float, float]) -> Tuple[float, float]:
        """
        Update filter with new measurement.
        
        Args:
            measurement: (x, y) measured gaze position
            
        Returns:
            Updated (x, y) filtered position
        """
        z = self.xp.array([[measurement[0]], [measurement[1]]], dtype=self.xp.float32)
        
        if not self.initialized:
            # First measurement - initialize state with measurement
            self.state[0, 0] = measurement[0]
            self.state[1, 0] = measurement[1]
            self.state[2, 0] = 0.0  # Initial velocity = 0
            self.state[3, 0] = 0.0
            self.initialized = True
            self.frame_count = 1
            return measurement
        
        self.frame_count += 1
        
        # Innovation (measurement residual)
        y = z - self.H @ self.state
        
        # Innovation covariance
        S = self.H @ self.P @ self.H.T + self.R
        
        # Kalman gain
        try:
            if self.use_gpu:
                K = self.P @ self.H.T @ cp.linalg.inv(S)
            else:
                K = self.P @ self.H.T @ np.linalg.inv(S)
        except:
            # Fallback if matrix inversion fails
            K = self.P @ self.H.T / (self.xp.trace(S) + 1e-6)
        
        # Update state
        self.state = self.state + K @ y
        
        # Update covariance
        I_KH = self.xp.eye(4) - K @ self.H
        self.P = I_KH @ self.P
        
        # Extract filtered position
        x = float(self.state[0, 0])
        y = float(self.state[1, 0])
        
        return x, y
    
    def get_state(self) -> KalmanState:
        """
        Get complete filter state including velocity.
        CRITICAL FOR GAP 2: Returns velocity for intent detection.
        
        Returns:
            KalmanState dataclass with position, velocity, and confidence
        """
        x = float(self.state[0, 0])
        y = float(self.state[1, 0])
        vx = float(self.state[2, 0])
        vy = float(self.state[3, 0])
        
        # Position covariance (diagonal element)
        pos_cov = float(self.P[0, 0] + self.P[1, 1])
        
        # Velocity covariance
        vel_cov = float(self.P[2, 2] + self.P[3, 3])
        
        # Confidence based on covariance (lower = higher confidence)
        confidence = max(0.0, 1.0 - (pos_cov + vel_cov) / 10.0)
        
        return KalmanState(
            position=(x, y),
            velocity=(vx, vy),
            position_covariance=pos_cov,
            velocity_covariance=vel_cov,
            confidence=confidence
        )
    
    def get_velocity(self) -> Tuple[float, float]:
        """
        Get current velocity estimate.
        Used by intent detection to classify deliberate vs glance movements.
        
        Returns:
            (vx, vy) velocity in pixels per frame
        """
        vx = float(self.state[2, 0])
        vy = float(self.state[3, 0])
        return vx, vy
    
    def get_velocity_magnitude(self) -> float:
        """
        Get speed (magnitude of velocity vector).
        Used by IntentEngine for velocity-based filtering.
        
        Returns:
            Speed in pixels per frame
        """
        vx, vy = self.get_velocity()
        return np.sqrt(vx**2 + vy**2)
    
    def get_position(self) -> Tuple[float, float]:
        """Get current position estimate"""
        return float(self.state[0, 0]), float(self.state[1, 0])
    
    def reset(self) -> None:
        """Reset filter state"""
        self.state = self.xp.zeros((4, 1))
        self.P = self.xp.eye(4, dtype=self.xp.float32)
        self.initialized = False
        self.frame_count = 0


class AdaptiveKalmanFilter:
    """
    Adaptive Kalman filter that adjusts noise parameters based on movement patterns.
    Reduces lag during fast movements, increases smoothing during fixation.
    """
    
    def __init__(
        self,
        base_process_variance: float = 1e-5,
        base_measurement_variance: float = 1e-1,
        use_gpu: bool = True
    ):
        """
        Initialize adaptive Kalman filter.
        
        Args:
            base_process_variance: Base process noise
            base_measurement_variance: Base measurement noise
            use_gpu: Use GPU if available
        """
        self.base_pv = base_process_variance
        self.base_mv = base_measurement_variance
        
        self.filter = KalmanFilter2D(
            process_variance=base_process_variance,
            measurement_variance=base_measurement_variance,
            use_gpu=use_gpu
        )
        
        self.velocity_history = []
        self.max_history = 10
        self.last_adjustment_time = 0
    
    def predict(self) -> Tuple[float, float]:
        """Predict next state"""
        return self.filter.predict()
    
    def update(self, measurement: Tuple[float, float]) -> Tuple[float, float]:
        """Update with measurement and adapt parameters"""
        result = self.filter.update(measurement)
        
        # Track velocity for adaptation
        vx, vy = self.filter.get_velocity()
        speed = np.sqrt(vx**2 + vy**2)
        
        self.velocity_history.append(speed)
        if len(self.velocity_history) > self.max_history:
            self.velocity_history.pop(0)
        
        # Adapt filter parameters based on motion pattern
        self._adapt_parameters()
        
        return result
    
    def _adapt_parameters(self) -> None:
        """Adaptively adjust Kalman parameters based on motion"""
        if len(self.velocity_history) < 5:
            return
        
        avg_speed = np.mean(self.velocity_history)
        
        # During fixation (low speed): increase smoothing
        if avg_speed < 5.0:
            process_variance = self.base_pv * 0.5  # More trust in motion model
            measurement_variance = self.base_mv * 2.0  # Less trust in noisy measurement
        
        # During saccade (high speed): reduce lag
        elif avg_speed > 20.0:
            process_variance = self.base_pv * 2.0  # Less trust in motion model
            measurement_variance = self.base_mv * 0.5  # More trust in measurement
        
        # Normal motion
        else:
            process_variance = self.base_pv
            measurement_variance = self.base_mv
        
        # Update filter parameters
        xp = self.filter.xp
        self.filter.Q = xp.eye(4, dtype=xp.float32) * process_variance
        self.filter.R = xp.eye(2, dtype=xp.float32) * measurement_variance
    
    def get_state(self) -> KalmanState:
        """Get complete state"""
        return self.filter.get_state()
    
    def get_velocity(self) -> Tuple[float, float]:
        """Get velocity"""
        return self.filter.get_velocity()
    
    def get_velocity_magnitude(self) -> float:
        """Get speed"""
        return self.filter.get_velocity_magnitude()
    
    def get_position(self) -> Tuple[float, float]:
        """Get position"""
        return self.filter.get_position()
    
    def reset(self) -> None:
        """Reset filter"""
        self.filter.reset()
        self.velocity_history.clear()


class KalmanGaze:
    """
    Comprehensive gaze tracking with Kalman filtering.
    Main interface for gaze position and velocity tracking.
    """
    
    def __init__(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
        use_adaptive: bool = True,
        use_gpu: bool = True
    ):
        """
        Initialize gaze tracker.
        
        Args:
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
            use_adaptive: Use adaptive Kalman filter
            use_gpu: Use GPU if available
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        if use_adaptive:
            self.filter = AdaptiveKalmanFilter(use_gpu=use_gpu)
            logger.info("Using adaptive Kalman filter")
        else:
            self.filter = KalmanFilter2D(use_gpu=use_gpu)
            logger.info("Using standard Kalman filter")
        
        self.is_initialized = False
    
    def initialize_with_position(self, x: float, y: float) -> None:
        """Initialize filter with first detected position"""
        if not self.is_initialized:
            self.filter.update((x, y))
            self.is_initialized = True
    
    def update_gaze(self, raw_x: float, raw_y: float) -> KalmanState:
        """
        Update gaze position with raw measurement and return filtered state.
        
        Args:
            raw_x: Raw gaze X coordinate (pixels)
            raw_y: Raw gaze Y coordinate (pixels)
            
        Returns:
            Filtered KalmanState with position and velocity
        """
        if not self.is_initialized:
            self.initialize_with_position(raw_x, raw_y)
        
        # Clamp to screen bounds
        clamped_x = max(0, min(self.screen_width, raw_x))
        clamped_y = max(0, min(self.screen_height, raw_y))
        
        # Update filter
        self.filter.predict()
        self.filter.update((clamped_x, clamped_y))
        
        return self.filter.get_state()
    
    def get_gaze_position(self) -> Tuple[float, float]:
        """Get current filtered gaze position"""
        return self.filter.get_position()
    
    def get_gaze_velocity(self) -> Tuple[float, float]:
        """
        Get gaze velocity (pixels per frame).
        Critical for IntentEngine to classify deliberate vs glance movements.
        
        Returns:
            (vx, vy) velocity
        """
        return self.filter.get_velocity()
    
    def get_gaze_speed(self) -> float:
        """Get gaze speed (magnitude of velocity)"""
        return self.filter.get_velocity_magnitude()
    
    def get_full_state(self) -> KalmanState:
        """Get complete state including position, velocity, and confidence"""
        return self.filter.get_state()
    
    def reset(self) -> None:
        """Reset filter"""
        self.filter.reset()
        self.is_initialized = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test Kalman filter
    logger.info("Testing KalmanGaze...")
    
    tracker = KalmanGaze(screen_width=1920, screen_height=1080, use_adaptive=True)
    
    # Simulate gaze movement
    for frame in range(100):
        # Simulate smooth horizontal movement
        true_x = 500 + frame * 5
        true_y = 500 + np.sin(frame * 0.1) * 50
        
        # Add measurement noise
        measured_x = true_x + np.random.normal(0, 10)
        measured_y = true_y + np.random.normal(0, 10)
        
        # Update tracker
        state = tracker.update_gaze(measured_x, measured_y)
        
        if frame % 20 == 0:
            vx, vy = tracker.get_gaze_velocity()
            speed = tracker.get_gaze_speed()
            logger.info(f"Frame {frame}: pos={state.position}, vel=({vx:.1f}, {vy:.1f}), speed={speed:.1f}")
    
    logger.info("✓ KalmanGaze test complete")
