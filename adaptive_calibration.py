"""
Adaptive Calibration and User Profile Management
Per-user EAR threshold calibration and gaze zone tracking
Fixes GAP 5: Adaptive EAR calibrator and user profiles
Feature E: Per-user profile system with JSON persistence
Part of NeuroGaze Elite
"""

import json
import logging
import numpy as np
import time
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CalibrationPhase(Enum):
    """Phases of the calibration process"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GazeZones:
    """Screen zones for gaze direction mapping"""
    left_threshold: float = 0.35      # Normalized X coordinate threshold for left
    right_threshold: float = 0.65     # Normalized X coordinate threshold for right
    up_threshold: float = 0.30        # Normalized Y coordinate threshold for up
    down_threshold: float = 0.70      # Normalized Y coordinate threshold for down
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GazeZones':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserProfile:
    """Per-user profile with calibration data and preferences"""
    user_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Calibration results
    ear_threshold: float = 0.21  # Eye Aspect Ratio threshold
    ear_calibration_quality: float = 0.0  # 0-1 quality score
    
    # Gaze zones (user-specific mapping)
    gaze_zones: GazeZones = field(default_factory=GazeZones)
    
    # Baseline metrics
    blink_rate_baseline: float = 12.0  # Blinks per minute
    blink_rate_std: float = 3.0
    
    # Preferences
    dwell_time_ms: int = 1200
    click_radius_pixels: int = 25
    
    # Usage statistics
    total_sessions: int = 0
    total_usage_minutes: float = 0.0
    
    # Metadata
    device_name: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        data = asdict(self)
        data['gaze_zones'] = self.gaze_zones.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UserProfile':
        """Create profile from dict"""
        data_copy = data.copy()
        if 'gaze_zones' in data_copy and isinstance(data_copy['gaze_zones'], dict):
            data_copy['gaze_zones'] = GazeZones.from_dict(data_copy['gaze_zones'])
        return cls(**{k: v for k, v in data_copy.items() if k in cls.__dataclass_fields__})


class AdaptiveEARCalibrator:
    """
    Adaptive Eye Aspect Ratio calibrator.
    Collects EAR samples passively and calculates user-specific threshold.
    """
    
    def __init__(
        self,
        calibration_duration_seconds: float = 30.0,
        percentile: float = 80.0,
        threshold_factor: float = 0.65
    ):
        """
        Initialize EAR calibrator.
        
        Args:
            calibration_duration_seconds: How long to collect samples
            percentile: Percentile of EAR distribution to use (higher = more relaxed threshold)
            threshold_factor: Multiply percentile by this factor to get final threshold
        """
        self.calibration_duration_seconds = calibration_duration_seconds
        self.percentile = percentile
        self.threshold_factor = threshold_factor
        
        self.ear_samples: list = []
        self.calibration_start_time: Optional[float] = None
        self.phase = CalibrationPhase.NOT_STARTED
        
        # Progress tracking
        self.progress: float = 0.0
        self.is_complete: bool = False
        
    def start_calibration(self) -> None:
        """Start EAR calibration"""
        self.calibration_start_time = time.time()
        self.ear_samples = []
        self.phase = CalibrationPhase.IN_PROGRESS
        self.progress = 0.0
        logger.info(f"Starting EAR calibration ({self.calibration_duration_seconds}s)")
    
    def add_ear_sample(self, ear_value: float) -> None:
        """
        Add EAR sample during calibration.
        
        Args:
            ear_value: Eye Aspect Ratio value
        """
        if self.phase != CalibrationPhase.IN_PROGRESS:
            return
        
        if ear_value > 0:  # Only collect valid (positive) values
            self.ear_samples.append(ear_value)
        
        # Update progress
        if self.calibration_start_time:
            elapsed = time.time() - self.calibration_start_time
            self.progress = min(1.0, elapsed / self.calibration_duration_seconds)
    
    def is_calibration_complete(self) -> bool:
        """Check if calibration time has elapsed"""
        if self.phase != CalibrationPhase.IN_PROGRESS:
            return False
        
        if not self.calibration_start_time:
            return False
        
        elapsed = time.time() - self.calibration_start_time
        return elapsed >= self.calibration_duration_seconds
    
    def finalize_calibration(self) -> Tuple[float, float]:
        """
        Finalize calibration and calculate threshold.
        
        Returns:
            Tuple of (ear_threshold, quality_score)
        """
        if len(self.ear_samples) < 10:
            self.phase = CalibrationPhase.FAILED
            logger.warning(f"Calibration failed: insufficient samples ({len(self.ear_samples)})")
            return 0.21, 0.0  # Return default threshold
        
        # Calculate 80th percentile
        ear_array = np.array(self.ear_samples)
        percentile_value = np.percentile(ear_array, self.percentile)
        
        # Apply threshold factor
        ear_threshold = percentile_value * self.threshold_factor
        
        # Quality score based on:
        # - Sample count (more = better)
        # - Sample variance (less = better, more consistent)
        # - Sample range (reasonable range = better)
        
        sample_count_score = min(1.0, len(self.ear_samples) / 1000.0)
        
        mean_ear = np.mean(ear_array)
        std_ear = np.std(ear_array)
        variance_score = max(0.0, 1.0 - std_ear)  # Lower variance = higher score
        
        min_ear = np.min(ear_array)
        max_ear = np.max(ear_array)
        range_acceptable = (max_ear - min_ear) > 0.1  # Should have decent range
        range_score = 1.0 if range_acceptable else 0.5
        
        # Weighted quality score
        quality_score = (sample_count_score * 0.3 + variance_score * 0.4 + range_score * 0.3)
        
        self.phase = CalibrationPhase.COMPLETED
        self.is_complete = True
        
        logger.info(
            f"✓ EAR calibration complete:\n"
            f"  - Threshold: {ear_threshold:.4f}\n"
            f"  - Quality: {quality_score:.1%}\n"
            f"  - Samples: {len(self.ear_samples)}\n"
            f"  - Mean EAR: {mean_ear:.4f}, Std: {std_ear:.4f}"
        )
        
        return ear_threshold, quality_score
    
    def get_calibration_data(self) -> Dict:
        """Get calibration data for display/debugging"""
        if not self.ear_samples:
            return {"samples": 0, "progress": self.progress}
        
        ear_array = np.array(self.ear_samples)
        return {
            "samples": len(self.ear_samples),
            "progress": self.progress,
            "mean": float(np.mean(ear_array)),
            "std": float(np.std(ear_array)),
            "min": float(np.min(ear_array)),
            "max": float(np.max(ear_array)),
            "percentile_80": float(np.percentile(ear_array, 80.0)),
        }


class UserProfileManager:
    """
    Manage user profiles and calibration data.
    Persists profiles to JSON and handles profile loading/saving.
    """
    
    def __init__(self, profile_dir: Optional[Path] = None):
        """
        Initialize profile manager.
        
        Args:
            profile_dir: Directory to store profiles (defaults to ~/.neurogaze)
        """
        if profile_dir is None:
            profile_dir = Path.home() / ".neurogaze" / "profiles"
        
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_profile: Optional[UserProfile] = None
        self.default_profile_name = "default"
        
        logger.info(f"Profile directory: {self.profile_dir}")
    
    def create_new_profile(
        self,
        user_id: str,
        device_name: Optional[str] = None,
        notes: str = ""
    ) -> UserProfile:
        """
        Create a new user profile.
        
        Args:
            user_id: Unique user identifier
            device_name: Device/machine name
            notes: Optional notes
            
        Returns:
            New UserProfile instance
        """
        profile = UserProfile(
            user_id=user_id,
            device_name=device_name or "Unknown",
            notes=notes
        )
        
        logger.info(f"Created new profile for user '{user_id}'")
        return profile
    
    def save_profile(self, profile: UserProfile) -> Path:
        """
        Save profile to JSON file.
        
        Args:
            profile: UserProfile to save
            
        Returns:
            Path to saved file
        """
        profile.last_updated = datetime.now().isoformat()
        
        filename = f"{profile.user_id}_profile.json"
        filepath = self.profile_dir / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
            logger.info(f"Profile saved: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save profile: {e}")
            raise
    
    def load_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Load profile from JSON file.
        
        Args:
            user_id: User identifier
            
        Returns:
            UserProfile if found, None otherwise
        """
        filename = f"{user_id}_profile.json"
        filepath = self.profile_dir / filename
        
        if not filepath.exists():
            logger.warning(f"Profile not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            profile = UserProfile.from_dict(data)
            logger.info(f"Profile loaded: {filepath}")
            return profile
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return None
    
    def list_profiles(self) -> list:
        """
        List all available profiles.
        
        Returns:
            List of user IDs
        """
        profiles = []
        for filepath in self.profile_dir.glob("*_profile.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    profiles.append(data.get('user_id', filepath.stem))
            except Exception as e:
                logger.warning(f"Failed to read {filepath}: {e}")
        
        return profiles
    
    def delete_profile(self, user_id: str) -> bool:
        """
        Delete a profile.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if deleted, False if not found
        """
        filename = f"{user_id}_profile.json"
        filepath = self.profile_dir / filename
        
        if not filepath.exists():
            return False
        
        try:
            filepath.unlink()
            logger.info(f"Profile deleted: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete profile: {e}")
            return False
    
    def set_current_profile(self, profile: UserProfile) -> None:
        """Set the current active profile"""
        self.current_profile = profile
        logger.info(f"Current profile set to: {profile.user_id}")
    
    def get_current_profile(self) -> Optional[UserProfile]:
        """Get the current active profile"""
        return self.current_profile
    
    def update_profile_calibration(
        self,
        profile: UserProfile,
        ear_threshold: float,
        quality_score: float,
        gaze_zones: Optional[GazeZones] = None
    ) -> None:
        """
        Update profile with calibration results.
        
        Args:
            profile: UserProfile to update
            ear_threshold: Calibrated EAR threshold
            quality_score: Calibration quality (0-1)
            gaze_zones: Optional updated gaze zones
        """
        profile.ear_threshold = ear_threshold
        profile.ear_calibration_quality = quality_score
        
        if gaze_zones:
            profile.gaze_zones = gaze_zones
        
        profile.last_updated = datetime.now().isoformat()
        logger.info(f"Profile calibration updated: {profile.user_id}")
    
    def update_profile_session_stats(
        self,
        profile: UserProfile,
        session_duration_minutes: float,
        blink_rate: float
    ) -> None:
        """
        Update profile with session statistics.
        
        Args:
            profile: UserProfile to update
            session_duration_minutes: Duration of session in minutes
            blink_rate: Average blink rate in blinks/minute
        """
        profile.total_sessions += 1
        profile.total_usage_minutes += session_duration_minutes
        
        # Update blink rate baseline (exponential moving average)
        alpha = 0.1  # Smoothing factor
        profile.blink_rate_baseline = (
            alpha * blink_rate + (1 - alpha) * profile.blink_rate_baseline
        )
        
        profile.last_updated = datetime.now().isoformat()


class CalibrationScreenManager:
    """
    Manages calibration UI and 5-point gaze zone calibration.
    """
    
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        """
        Initialize calibration manager.
        
        Args:
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.calibration_points = self._generate_calibration_points()
        self.current_point_index = 0
        self.gaze_samples: Dict[str, list] = {
            'left': [], 'right': [], 'up': [], 'down': [], 'center': []
        }
    
    def _generate_calibration_points(self) -> list:
        """Generate 5-point calibration positions"""
        w, h = self.screen_width, self.screen_height
        return [
            ('center', (w // 2, h // 2)),
            ('left', (int(w * 0.2), h // 2)),
            ('right', (int(w * 0.8), h // 2)),
            ('up', (w // 2, int(h * 0.2))),
            ('down', (w // 2, int(h * 0.8))),
        ]
    
    def get_current_point(self) -> Tuple[str, Tuple[int, int]]:
        """Get current calibration point"""
        if self.current_point_index >= len(self.calibration_points):
            return None, None
        
        return self.calibration_points[self.current_point_index]
    
    def add_gaze_sample(self, norm_x: float, norm_y: float) -> None:
        """
        Add gaze sample for current calibration point.
        
        Args:
            norm_x: Normalized X coordinate (0-1)
            norm_y: Normalized Y coordinate (0-1)
        """
        point_name, _ = self.get_current_point()
        if point_name:
            self.gaze_samples[point_name].append((norm_x, norm_y))
    
    def next_point(self) -> bool:
        """
        Move to next calibration point.
        
        Returns:
            True if there are more points, False if calibration complete
        """
        self.current_point_index += 1
        return self.current_point_index < len(self.calibration_points)
    
    def calculate_gaze_zones(self) -> Optional[GazeZones]:
        """
        Calculate gaze zones from collected samples.
        
        Returns:
            GazeZones instance or None if insufficient data
        """
        if not all(len(samples) > 0 for samples in self.gaze_samples.values()):
            logger.warning("Insufficient calibration data")
            return None
        
        # Calculate average positions for each point
        left_avg = np.mean(self.gaze_samples['left'], axis=0)
        right_avg = np.mean(self.gaze_samples['right'], axis=0)
        up_avg = np.mean(self.gaze_samples['up'], axis=0)
        down_avg = np.mean(self.gaze_samples['down'], axis=0)
        center_avg = np.mean(self.gaze_samples['center'], axis=0)
        
        # Set thresholds as midpoints
        left_threshold = (left_avg[0] + center_avg[0]) / 2
        right_threshold = (right_avg[0] + center_avg[0]) / 2
        up_threshold = (up_avg[1] + center_avg[1]) / 2
        down_threshold = (down_avg[1] + center_avg[1]) / 2
        
        zones = GazeZones(
            left_threshold=float(left_threshold),
            right_threshold=float(right_threshold),
            up_threshold=float(up_threshold),
            down_threshold=float(down_threshold)
        )
        
        logger.info(f"Gaze zones calculated: {zones}")
        return zones


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test calibrator
    logger.info("Testing AdaptiveEARCalibrator...")
    calibrator = AdaptiveEARCalibrator(calibration_duration_seconds=2.0)
    
    calibrator.start_calibration()
    
    # Simulate EAR samples
    ear_values = np.random.normal(0.28, 0.05, 100)
    for ear in ear_values:
        calibrator.add_ear_sample(max(0, ear))
        if calibrator.is_calibration_complete():
            break
        time.sleep(0.02)
    
    if calibrator.is_calibration_complete():
        threshold, quality = calibrator.finalize_calibration()
        logger.info(f"Calibrated threshold: {threshold:.4f}, quality: {quality:.1%}")
    
    # Test profile manager
    logger.info("Testing UserProfileManager...")
    manager = UserProfileManager()
    
    # Create and save profile
    profile = manager.create_new_profile("test_user", "TestDevice")
    manager.update_profile_calibration(profile, 0.21, 0.85)
    manager.save_profile(profile)
    
    # Load profile
    loaded = manager.load_profile("test_user")
    logger.info(f"Loaded profile: {loaded.user_id}, threshold: {loaded.ear_threshold}")
    
    # List profiles
    profiles = manager.list_profiles()
    logger.info(f"Available profiles: {profiles}")
    
    logger.info("✓ Tests complete")
