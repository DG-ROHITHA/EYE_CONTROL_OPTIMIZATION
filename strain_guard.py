"""
StrainGuard: Eye Strain and Fatigue Detection Module
Comprehensive system for blink rate tracking, PERCLOS scoring, 20-20-20 breaks, and fatigue management.
Fixes GAP 6: Critical anti-eye-strain system for assistive device users.
Part of NeuroGaze Elite
"""

import time
import logging
import numpy as np
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

logger = logging.getLogger(__name__)


class FatigueLevel(Enum):
    """Fatigue severity levels"""
    ALERT = "ALERT"          # User is very drowsy/fatigued
    WARNING = "WARNING"      # User showing signs of fatigue
    NORMAL = "NORMAL"        # User is alert
    EXCELLENT = "EXCELLENT" # User is very alert


@dataclass
class StrainMetrics:
    """Current strain metrics snapshot"""
    blink_rate_per_minute: float
    perclos_score: float  # 0-100, percentage of frames with closed eyes
    fatigue_level: FatigueLevel
    is_drowsy: bool
    microsleep_detected: bool
    break_due: bool
    session_minutes_elapsed: float


@dataclass
class StrainGuardConfig:
    """Configuration for StrainGuard"""
    # Blink rate thresholds (blinks/minute)
    BLINK_RATE_NORMAL_MIN: float = 8.0
    BLINK_RATE_NORMAL_MAX: float = 20.0
    BLINK_RATE_LOW_THRESHOLD: float = 6.0  # Alert if below this
    
    # PERCLOS thresholds (percentage)
    PERCLOS_NORMAL_MAX: float = 10.0    # Normal: <10% eyes closed
    PERCLOS_DROWSY_THRESHOLD: float = 15.0  # Drowsy: >15% eyes closed
    PERCLOS_CRITICAL_THRESHOLD: float = 25.0  # Critical: >25% eyes closed
    
    # Time windows (seconds)
    BLINK_WINDOW_SECONDS: float = 60.0   # Rolling window for blink counting
    PERCLOS_WINDOW_SECONDS: float = 60.0  # Rolling window for PERCLOS
    
    # Microsleep detection
    MICROSLEEP_THRESHOLD_SECONDS: float = 2.0  # Alert if eyes closed for >2s
    
    # 20-20-20 break scheduling
    BREAK_INTERVAL_MINUTES: float = 20.0  # Every 20 minutes
    BREAK_DURATION_SECONDS: float = 20.0  # 20 seconds per break
    
    # Session limits
    SESSION_HARD_LIMIT_MINUTES: float = 45.0  # Force break after 45 min
    SESSION_SOFT_WARNING_MINUTES: float = 30.0  # Warn at 30 min
    
    # EAR threshold (blink detection)
    EAR_THRESHOLD: float = 0.21
    
    # Logging
    ENABLE_LOGGING: bool = True


class StrainGuard:
    """
    Comprehensive eye strain and fatigue monitoring system.
    Tracks blink rates, PERCLOS, microsleep, and enforces break schedules.
    """
    
    def __init__(self, config: StrainGuardConfig = None):
        """
        Initialize StrainGuard.
        
        Args:
            config: StrainGuardConfig instance (uses defaults if None)
        """
        self.config = config or StrainGuardConfig()
        
        # Blink tracking
        self.blink_times: deque = deque(maxlen=100)  # Timestamps of recent blinks
        self.current_blink_frame_count: int = 0
        self.last_ear_below_threshold: bool = False
        
        # PERCLOS tracking (Percentage of Eyelid Closure)
        self.perclos_closed_frames: int = 0
        self.perclos_total_frames: int = 0
        self.eyes_closed_start_time: Optional[float] = None
        
        # Session tracking
        self.session_start_time: Optional[float] = None
        self.session_paused_time: Optional[float] = None
        self.total_paused_duration: float = 0.0
        
        # Break scheduling
        self.last_break_time: Optional[float] = None
        self.break_in_progress: bool = False
        self.break_start_time: Optional[float] = None
        
        # Fatigue accumulation
        self.fatigue_score: float = 0.0  # 0-100
        
        # Current metrics
        self.current_metrics: StrainMetrics = self._create_default_metrics()
        
        # State flags
        self.is_active: bool = False
        
        if self.config.ENABLE_LOGGING:
            logger.info("✓ StrainGuard initialized")

    def _create_default_metrics(self) -> StrainMetrics:
        """Create default metrics"""
        return StrainMetrics(
            blink_rate_per_minute=0.0,
            perclos_score=0.0,
            fatigue_level=FatigueLevel.NORMAL,
            is_drowsy=False,
            microsleep_detected=False,
            break_due=False,
            session_minutes_elapsed=0.0
        )

    def start_session(self) -> None:
        """Start a new monitoring session"""
        self.session_start_time = time.time()
        self.last_break_time = self.session_start_time
        self.total_paused_duration = 0.0
        self.is_active = True
        self.fatigue_score = 0.0
        
        if self.config.ENABLE_LOGGING:
            logger.info("StrainGuard session started")

    def pause_session(self) -> None:
        """Pause session (user moved to background)"""
        if self.is_active and self.session_paused_time is None:
            self.session_paused_time = time.time()
            self.is_active = False
            if self.config.ENABLE_LOGGING:
                logger.info("StrainGuard session paused")

    def resume_session(self) -> None:
        """Resume paused session"""
        if self.session_paused_time is not None:
            pause_duration = time.time() - self.session_paused_time
            self.total_paused_duration += pause_duration
            self.session_paused_time = None
            self.is_active = True
            if self.config.ENABLE_LOGGING:
                logger.info(f"StrainGuard session resumed (paused for {pause_duration:.1f}s)")

    def end_session(self) -> dict:
        """
        End current session and return statistics.
        
        Returns:
            Dictionary with session statistics
        """
        if not self.session_start_time:
            return {}

        elapsed = (time.time() - self.session_start_time) - self.total_paused_duration
        
        stats = {
            "session_duration_seconds": elapsed,
            "total_blinks": len(self.blink_times),
            "avg_blink_rate": (len(self.blink_times) / elapsed * 60) if elapsed > 0 else 0,
            "final_fatigue_score": self.fatigue_score,
            "final_perclos": self.current_metrics.perclos_score,
            "breaks_taken": self.last_break_time != self.session_start_time,
        }
        
        # Reset
        self.session_start_time = None
        self.is_active = False
        self.blink_times.clear()
        self.fatigue_score = 0.0
        self.perclos_closed_frames = 0
        self.perclos_total_frames = 0
        
        if self.config.ENABLE_LOGGING:
            logger.info(f"StrainGuard session ended: {elapsed:.1f}s, {stats['total_blinks']} blinks")
        
        return stats

    def update(self, ear_value: float) -> StrainMetrics:
        """
        Update strain detection with current eye aspect ratio.
        Call this every frame with EAR (Eye Aspect Ratio).
        
        Args:
            ear_value: Current Eye Aspect Ratio value
            
        Returns:
            Current StrainMetrics
        """
        if not self.is_active or not self.session_start_time:
            return self.current_metrics

        current_time = time.time()
        
        # ========== BLINK DETECTION ==========
        is_blinking = ear_value < self.config.EAR_THRESHOLD
        
        if is_blinking and not self.last_ear_below_threshold:
            # Blink started
            self.current_blink_frame_count = 0
            self.eyes_closed_start_time = current_time
            
        elif is_blinking:
            # Blink continues
            self.current_blink_frame_count += 1
            
        elif not is_blinking and self.last_ear_below_threshold:
            # Blink ended - record it
            blink_duration = current_time - self.eyes_closed_start_time
            if 0.05 < blink_duration < 0.5:  # Valid blink (50ms - 500ms)
                self.blink_times.append(current_time)
            self.eyes_closed_start_time = None
        
        self.last_ear_below_threshold = is_blinking
        
        # ========== PERCLOS CALCULATION ==========
        self.perclos_total_frames += 1
        if is_blinking:
            self.perclos_closed_frames += 1
        
        # Calculate PERCLOS over rolling window
        perclos_score = self._calculate_perclos()
        
        # ========== BLINK RATE CALCULATION ==========
        blink_rate = self._calculate_blink_rate()
        
        # ========== MICROSLEEP DETECTION ==========
        microsleep_detected = False
        if self.eyes_closed_start_time is not None:
            eyes_closed_duration = current_time - self.eyes_closed_start_time
            if eyes_closed_duration > self.config.MICROSLEEP_THRESHOLD_SECONDS:
                microsleep_detected = True
        
        # ========== BREAK SCHEDULING ==========
        break_due = self._check_break_due(current_time)
        
        # ========== FATIGUE LEVEL CALCULATION ==========
        is_drowsy = perclos_score > self.config.PERCLOS_DROWSY_THRESHOLD
        fatigue_level = self._calculate_fatigue_level(
            blink_rate, perclos_score, is_drowsy
        )
        
        # ========== UPDATE FATIGUE SCORE ==========
        self.fatigue_score = self._update_fatigue_score(
            blink_rate, perclos_score, is_drowsy
        )
        
        # ========== UPDATE METRICS ==========
        session_elapsed = (current_time - self.session_start_time) - self.total_paused_duration
        
        self.current_metrics = StrainMetrics(
            blink_rate_per_minute=blink_rate,
            perclos_score=perclos_score,
            fatigue_level=fatigue_level,
            is_drowsy=is_drowsy,
            microsleep_detected=microsleep_detected,
            break_due=break_due,
            session_minutes_elapsed=session_elapsed / 60.0
        )
        
        return self.current_metrics

    def _calculate_blink_rate(self) -> float:
        """
        Calculate blinks per minute from rolling window.
        
        Returns:
            Blinks per minute
        """
        if not self.blink_times or len(self.blink_times) < 1:
            return 0.0
        
        current_time = time.time()
        window_start = current_time - self.config.BLINK_WINDOW_SECONDS
        
        # Count blinks in window
        blinks_in_window = sum(
            1 for t in self.blink_times if t > window_start
        )
        
        # Convert to per-minute rate
        window_duration_minutes = self.config.BLINK_WINDOW_SECONDS / 60.0
        blink_rate = blinks_in_window / window_duration_minutes if window_duration_minutes > 0 else 0.0
        
        return blink_rate

    def _calculate_perclos(self) -> float:
        """
        Calculate PERCLOS (Percentage of Eyelid Closure).
        
        Returns:
            PERCLOS score 0-100
        """
        if self.perclos_total_frames == 0:
            return 0.0
        
        perclos = (self.perclos_closed_frames / self.perclos_total_frames) * 100.0
        
        # Reset counters periodically to maintain rolling window
        if self.perclos_total_frames > 10000:
            # Keep last 30fps * 60s = 1800 frames worth
            scale_factor = 1800 / self.perclos_total_frames
            self.perclos_closed_frames = int(self.perclos_closed_frames * scale_factor)
            self.perclos_total_frames = 1800
        
        return perclos

    def _calculate_fatigue_level(
        self,
        blink_rate: float,
        perclos_score: float,
        is_drowsy: bool
    ) -> FatigueLevel:
        """
        Calculate fatigue level from multiple indicators.
        
        Args:
            blink_rate: Blinks per minute
            perclos_score: PERCLOS percentage (0-100)
            is_drowsy: Drowsiness flag
            
        Returns:
            FatigueLevel enum
        """
        # Critical alert conditions
        if perclos_score > self.config.PERCLOS_CRITICAL_THRESHOLD:
            return FatigueLevel.ALERT
        
        if is_drowsy or perclos_score > self.config.PERCLOS_DROWSY_THRESHOLD:
            return FatigueLevel.WARNING
        
        # Low blink rate indicates fixation strain
        if blink_rate < self.config.BLINK_RATE_LOW_THRESHOLD:
            return FatigueLevel.WARNING
        
        # High blink rate indicates strain/discomfort
        if blink_rate > self.config.BLINK_RATE_NORMAL_MAX * 1.5:
            return FatigueLevel.WARNING
        
        # Excellent state
        if (self.config.BLINK_RATE_NORMAL_MIN <= blink_rate <= self.config.BLINK_RATE_NORMAL_MAX
            and perclos_score < self.config.PERCLOS_NORMAL_MAX):
            return FatigueLevel.EXCELLENT
        
        # Normal state (default)
        return FatigueLevel.NORMAL

    def _update_fatigue_score(
        self,
        blink_rate: float,
        perclos_score: float,
        is_drowsy: bool
    ) -> float:
        """
        Update cumulative fatigue score (0-100).
        Score increases with strain indicators.
        
        Args:
            blink_rate: Blinks per minute
            perclos_score: PERCLOS percentage
            is_drowsy: Drowsiness flag
            
        Returns:
            Updated fatigue score (0-100)
        """
        # Base score from PERCLOS (primary indicator)
        perclos_factor = max(0, (perclos_score - self.config.PERCLOS_NORMAL_MAX) / 10.0)
        
        # Blink rate factor
        blink_deviation = abs(blink_rate - (self.config.BLINK_RATE_NORMAL_MIN + self.config.BLINK_RATE_NORMAL_MAX) / 2)
        blink_factor = min(1.0, blink_deviation / 10.0)
        
        # Drowsiness factor
        drowsy_factor = 1.0 if is_drowsy else 0.0
        
        # Weighted fatigue increase
        fatigue_increase = (perclos_factor * 0.5 + blink_factor * 0.3 + drowsy_factor * 0.2)
        
        # Apply exponential decay to fatigue score when conditions improve
        self.fatigue_score = self.fatigue_score * 0.95 + fatigue_increase * 5
        
        # Cap between 0-100
        return max(0.0, min(100.0, self.fatigue_score))

    def _check_break_due(self, current_time: float) -> bool:
        """
        Check if break is due based on 20-20-20 schedule or hard session limit.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            True if break is due
        """
        if not self.session_start_time:
            return False
        
        session_elapsed = (current_time - self.session_start_time) - self.total_paused_duration
        session_minutes = session_elapsed / 60.0
        
        # Hard session limit - enforce break after 45 minutes
        if session_minutes > self.config.SESSION_HARD_LIMIT_MINUTES:
            return True
        
        # 20-20-20 schedule
        if self.last_break_time:
            time_since_break = current_time - self.last_break_time
            if time_since_break > self.config.BREAK_INTERVAL_MINUTES * 60:
                return True
        
        return False

    def take_break(self) -> None:
        """Record that user took a break"""
        self.last_break_time = time.time()
        self.break_in_progress = False
        if self.config.ENABLE_LOGGING:
            logger.info("Break taken - fatigue reset")

    def get_break_countdown(self) -> float:
        """
        Get time until next scheduled break in seconds.
        
        Returns:
            Seconds until next break (0 if break is overdue)
        """
        if not self.session_start_time or not self.last_break_time:
            return self.config.BREAK_INTERVAL_MINUTES * 60
        
        time_since_break = time.time() - self.last_break_time
        time_until_break = (self.config.BREAK_INTERVAL_MINUTES * 60) - time_since_break
        
        return max(0.0, time_until_break)

    def get_metrics(self) -> StrainMetrics:
        """Get current strain metrics without updating"""
        return self.current_metrics

    def get_hud_status(self) -> str:
        """
        Get HUD status line for display.
        
        Returns:
            Formatted status string
        """
        m = self.current_metrics
        
        status_parts = []
        
        # Fatigue indicator
        fatigue_emoji = {
            FatigueLevel.EXCELLENT: "🟢",
            FatigueLevel.NORMAL: "🟡",
            FatigueLevel.WARNING: "🟠",
            FatigueLevel.ALERT: "🔴",
        }.get(m.fatigue_level, "⚪")
        
        status_parts.append(f"{fatigue_emoji} BR:{m.blink_rate_per_minute:.1f}/min")
        status_parts.append(f"PERCLOS:{m.perclos_score:.1f}%")
        
        if m.is_drowsy:
            status_parts.append("⚠️ DROWSY")
        
        if m.microsleep_detected:
            status_parts.append("🚨 MICROSLEEP")
        
        if m.break_due:
            status_parts.append("⏰ BREAK DUE")
        
        return " | ".join(status_parts)

    def reset_frame_counters(self) -> None:
        """Reset per-frame counters (call each session start)"""
        self.perclos_closed_frames = 0
        self.perclos_total_frames = 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test StrainGuard
    logger.info("Testing StrainGuard...")
    
    config = StrainGuardConfig()
    guard = StrainGuard(config)
    
    # Start session
    guard.start_session()
    
    # Simulate frames with varying EAR values
    for i in range(300):  # 10 seconds at 30fps
        # Simulate normal eye
        if i % 100 < 5:  # Blink every ~3 seconds
            ear = 0.1
        else:
            ear = 0.3
        
        metrics = guard.update(ear)
    
    logger.info(f"Metrics: {metrics}")
    
    # End session
    stats = guard.end_session()
    logger.info(f"Session stats: {stats}")
    
    logger.info("✓ StrainGuard test complete")
