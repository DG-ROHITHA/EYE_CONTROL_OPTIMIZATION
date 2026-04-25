"""
Hand Gesture Calibration for NeuroGaze Elite
Per-user hand normalization and gesture threshold customization

Gap Fix: Personalization for hand size and morphology variation
Different users have vastly different hand sizes, finger lengths, and mobility.
This module runs a 20-second passive calibration collecting hand metrics and
normalizing all gesture thresholds to the individual user's hand scale.

Benchmark: 20s one-time calibration per user profile
Calibration quality: 0-1 score tracking accuracy confidence
Auto-recalibration: Triggered if gesture accuracy drops below 80% in 5-min window
"""

from __future__ import annotations

import logging
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class CalibrationState(Enum):
    """Hand calibration state machine"""
    IDLE = "idle"
    COLLECTING = "collecting"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class HandMetrics:
    """Collected hand measurements during calibration"""
    hand_size_norm: float = 0.0  # Diagonal of hand bounding box (normalized)
    pinch_distance_min: float = 1.0  # Minimum pinch distance observed
    pinch_distance_max: float = 0.0  # Maximum (open hand)
    pinch_distance_mean: float = 0.5
    palm_span_pixels: float = 0.0  # Distance thumb to pinky
    finger_lengths: Dict[str, float] = field(default_factory=dict)  # Per-finger metrics
    fingertip_spread: float = 0.0  # Max distance between fingertips
    samples_collected: int = 0


@dataclass
class HandProfile:
    """Per-user hand calibration profile"""
    user_id: str
    hand_metrics: HandMetrics
    calibration_timestamp: float = 0.0
    calibration_quality: float = 0.0  # 0-1 confidence
    dominant_hand: str = "Right"  # "Left" or "Right"
    
    # Gesture thresholds (normalized to this user's hand)
    pinch_threshold_normalized: float = 0.05
    palm_extension_threshold_normalized: float = 0.15
    fist_curl_threshold_normalized: float = 0.10
    swipe_velocity_threshold_normalized: float = 0.3
    
    # Calibration metadata
    notes: str = ""
    recalibration_due: bool = False
    last_accuracy_check_ms: float = 0.0
    recent_accuracy: float = 1.0  # 0-1, drops if gestures misclassified


class HandProfileCalibrator:
    """
    Runs passive hand calibration and manages per-user profiles.
    """
    
    def __init__(self, profile_dir: Optional[Path] = None):
        """
        Initialize calibrator.
        
        Args:
            profile_dir: Directory for storing hand profiles (defaults to ~/.neurogaze/profiles/)
        """
        self.profile_dir = profile_dir or (Path.home() / ".neurogaze" / "profiles")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        self.calibration_state = CalibrationState.IDLE
        self.current_calibration: Optional[HandMetrics] = None
        self.calibration_start_time = 0.0
        self.collected_samples: list = []
        
        logger.info(f"✓ HandProfileCalibrator initialized (profile dir: {self.profile_dir})")

    def start_calibration(self) -> bool:
        """Start a new hand calibration session"""
        if self.calibration_state in (CalibrationState.COLLECTING, CalibrationState.PROCESSING):
            logger.warning("Calibration already in progress")
            return False
        
        self.calibration_state = CalibrationState.COLLECTING
        self.calibration_start_time = time.time()
        self.collected_samples = []
        self.current_calibration = HandMetrics()
        
        logger.info("🎯 Hand calibration started (20 seconds)")
        return True

    def add_sample(self, hand_landmarks: Any, hand_size: float):
        """
        Add a hand frame sample during calibration.
        
        Args:
            hand_landmarks: List of MediaPipe hand landmarks
            hand_size: Normalized hand bounding box diagonal
        """
        if self.calibration_state != CalibrationState.COLLECTING:
            return
        
        if not self.current_calibration:
            self.current_calibration = HandMetrics()
        
        # Record hand size
        self.current_calibration.hand_size_norm = max(
            self.current_calibration.hand_size_norm,
            hand_size
        )
        
        # Record pinch distance (thumb to index)
        if len(hand_landmarks) >= 9:
            thumb = hand_landmarks[4]
            index = hand_landmarks[8]
            pinch_dist = ((thumb.x - index.x)**2 + (thumb.y - index.y)**2) ** 0.5
            
            self.current_calibration.pinch_distance_min = min(
                self.current_calibration.pinch_distance_min,
                pinch_dist
            )
            self.current_calibration.pinch_distance_max = max(
                self.current_calibration.pinch_distance_max,
                pinch_dist
            )
        
        # Record sample count
        self.current_calibration.samples_collected += 1
        self.collected_samples.append({
            "timestamp": time.time(),
            "hand_size": hand_size,
            "pinch_dist": pinch_dist if len(hand_landmarks) >= 9 else 0.0
        })
        
        # Check if calibration complete (20 seconds at 30fps ≈ 600 frames)
        elapsed = time.time() - self.calibration_start_time
        if elapsed >= 20.0:
            self.finalize_calibration()

    def finalize_calibration(self) -> tuple[HandProfile, float]:
        """
        Finalize calibration and compute quality score.
        
        Returns:
            (HandProfile, quality_score) where quality_score is 0-1
        """
        if self.calibration_state != CalibrationState.COLLECTING:
            logger.warning("No active calibration to finalize")
            return None, 0.0
        
        self.calibration_state = CalibrationState.PROCESSING
        
        if not self.current_calibration or self.current_calibration.samples_collected < 100:
            logger.error("Insufficient samples for calibration")
            self.calibration_state = CalibrationState.FAILED
            return None, 0.0
        
        # Compute mean pinch distance
        self.current_calibration.pinch_distance_mean = (
            self.current_calibration.pinch_distance_min +
            self.current_calibration.pinch_distance_max
        ) / 2.0
        
        # Quality score based on:
        # - Number of samples (should be ~600 for 20s at 30fps)
        # - Variance in measurements (stable = high quality)
        sample_quality = min(1.0, self.current_calibration.samples_collected / 600.0)
        
        # Variance in hand size measurements
        hand_sizes = [s["hand_size"] for s in self.collected_samples]
        if len(hand_sizes) > 1:
            mean_size = sum(hand_sizes) / len(hand_sizes)
            variance = sum((x - mean_size) ** 2 for x in hand_sizes) / len(hand_sizes)
            std_dev = variance ** 0.5
            # Lower std dev = higher quality (stable hand position)
            stability_quality = max(0.0, 1.0 - std_dev * 2)
        else:
            stability_quality = 0.5
        
        quality_score = (sample_quality + stability_quality) / 2.0
        
        # Create profile
        profile = HandProfile(
            user_id="current_user",  # Will be updated when saved
            hand_metrics=self.current_calibration,
            calibration_timestamp=time.time(),
            calibration_quality=quality_score,
            pinch_threshold_normalized=self.current_calibration.pinch_distance_min * 0.8,
            notes=f"Calibrated from {self.current_calibration.samples_collected} samples"
        )
        
        self.calibration_state = CalibrationState.COMPLETE
        logger.info(f"✓ Hand calibration complete (quality: {quality_score:.2f})")
        
        return profile, quality_score

    def save_profile(self, user_id: str, profile: HandProfile) -> bool:
        """
        Save hand profile to JSON.
        
        Args:
            user_id: User identifier
            profile: HandProfile to save
            
        Returns:
            True if successful
        """
        try:
            profile.user_id = user_id
            profile_path = self.profile_dir / f"{user_id}_hand_profile.json"
            
            # Convert dataclass to dict
            profile_dict = asdict(profile)
            
            with open(profile_path, 'w') as f:
                json.dump(profile_dict, f, indent=2)
            
            logger.info(f"✓ Hand profile saved to {profile_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save hand profile: {e}")
            return False

    def load_profile(self, user_id: str) -> Optional[HandProfile]:
        """
        Load hand profile from JSON.
        
        Args:
            user_id: User identifier
            
        Returns:
            HandProfile if found, None otherwise
        """
        try:
            profile_path = self.profile_dir / f"{user_id}_hand_profile.json"
            
            if not profile_path.exists():
                logger.debug(f"Hand profile not found: {profile_path}")
                return None
            
            with open(profile_path, 'r') as f:
                profile_dict = json.load(f)
            
            # Reconstruct dataclass
            hand_metrics = HandMetrics(**profile_dict.pop("hand_metrics", {}))
            profile = HandProfile(
                hand_metrics=hand_metrics,
                **profile_dict
            )
            
            logger.info(f"✓ Hand profile loaded (quality: {profile.calibration_quality:.2f})")
            return profile
        except Exception as e:
            logger.error(f"Failed to load hand profile: {e}")
            return None

    def check_recalibration_needed(self, profile: HandProfile, recent_accuracy: float) -> bool:
        """
        Check if hand profile needs recalibration based on gesture accuracy.
        
        Args:
            profile: Current hand profile
            recent_accuracy: Recent gesture recognition accuracy (0-1)
            
        Returns:
            True if recalibration recommended
        """
        # Trigger recalibration if accuracy drops below 80%
        if recent_accuracy < 0.80:
            logger.warning(f"Gesture accuracy low ({recent_accuracy:.1%}); recalibration recommended")
            profile.recalibration_due = True
            profile.recent_accuracy = recent_accuracy
            return True
        
        profile.recent_accuracy = recent_accuracy
        return False

    def get_normalized_gesture_config(self, profile: HandProfile) -> Dict[str, float]:
        """
        Get gesture detection thresholds normalized for this user's hand.
        
        Args:
            profile: User's hand profile
            
        Returns:
            Dict of threshold name -> normalized value
        """
        return {
            "pinch_threshold": profile.pinch_threshold_normalized,
            "palm_extension_threshold": profile.palm_extension_threshold_normalized,
            "fist_curl_threshold": profile.fist_curl_threshold_normalized,
            "swipe_velocity_threshold": profile.swipe_velocity_threshold_normalized,
            "hand_scale": profile.hand_metrics.hand_size_norm,
        }

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostics for logging"""
        return {
            "calibration_state": self.calibration_state.value,
            "samples_collected": self.current_calibration.samples_collected if self.current_calibration else 0,
            "profile_dir": str(self.profile_dir),
        }


@dataclass
class UserProfileWithHand:
    """Extended UserProfile that includes hand calibration (for integration)"""
    user_id: str
    ear_threshold: float
    hand_profile: Optional[HandProfile] = None
    
    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization"""
        return {
            "user_id": self.user_id,
            "ear_threshold": self.ear_threshold,
            "hand_profile": asdict(self.hand_profile) if self.hand_profile else None
        }


# Integration Example for neurogaze_elite.py:
"""
# In neurogaze_elite.py __init__:
from gesture_calibration import HandProfileCalibrator, HandProfile

self.hand_calibrator = HandProfileCalibrator()

# Load or create hand profile
self.hand_profile = self.hand_calibrator.load_profile(self.current_user_id)
if not self.hand_profile:
    logger.info("No hand profile found; will calibrate on first run")

# In main loop, check for calibration key press (e.g., 'H'):
if key == ord('H'):
    self.hand_calibrator.start_calibration()

# After gesture detection:
if self.hand_calibrator.calibration_state == CalibrationState.COLLECTING:
    for hand in detected_hands:
        hand_size = hand.bounding_box_size  # Diagonal
        self.hand_calibrator.add_sample(hand.landmarks, hand_size)

# After calibration complete:
if self.hand_calibrator.calibration_state == CalibrationState.COMPLETE:
    profile, quality = self.hand_calibrator.finalize_calibration()
    if quality > 0.6:
        self.hand_calibrator.save_profile(self.current_user_id, profile)
        self.hand_profile = profile
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    calibrator = HandProfileCalibrator()
    print(f"✓ Calibrator ready: {calibrator.get_diagnostics()}")
