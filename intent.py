"""
Intent Detection Engine
Classifies gaze movements as intentional commands vs unintentional glances
Fixes GAP 2: Wire Kalman velocity into intent detection with proper thresholds
Feature F: Intent confidence score for command execution
Part of NeuroGaze Elite
"""

import numpy as np
import logging
import time
from typing import Optional, Tuple
from collections import deque
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntentLevel(Enum):
    """Gaze intent classification"""
    GLANCE = "glance"           # Quick unintentional eye movement
    NORMAL = "normal"           # Regular gaze (ambiguous)
    DELIBERATE = "deliberate"   # Intentional, focused gaze


@dataclass
class IntentScore:
    """Intent analysis result"""
    level: IntentLevel
    confidence: float  # 0-1, higher = more confident
    velocity_score: float
    duration_score: float
    consistency_score: float
    reason: str


class IntentEngine:
    """
    Advanced intent detection engine.
    Uses velocity analysis and dwell characteristics to classify gaze as intentional.
    Fixes GAP 2: Properly wires Kalman velocity into intent detection.
    """
    
    # Velocity thresholds (pixels per frame)
    VELOCITY_THRESHOLD_SLOW = 10.0      # Deliberate movement
    VELOCITY_THRESHOLD_FAST = 80.0      # Rapid glance/saccade
    
    # Dwell thresholds
    MIN_DELIBERATE_DWELL_MS = 300.0     # Minimum time for deliberate gaze
    MIN_COMMAND_CONFIDENCE = 0.70       # 70% confidence needed for command
    
    def __init__(self):
        """Initialize intent engine"""
        # Velocity history for trend analysis
        self.velocity_history = deque(maxlen=30)  # Last 30 frames (1 second at 30fps)
        self.speed_history = deque(maxlen=30)
        
        # Gaze position history
        self.position_history = deque(maxlen=30)
        
        # Dwell tracking
        self.dwell_start_time: Optional[float] = None
        self.dwell_position: Optional[Tuple[float, float]] = None
        self.dwell_radius = 50  # Pixels
        
        # Direction tracking for consistency
        self.direction_history = deque(maxlen=5)
        
        # Session stats
        self.true_positives = 0
        self.false_positives = 0
        
        logger.info("✓ IntentEngine initialized")
    
    def analyze_intent(
        self,
        current_velocity: Tuple[float, float],
        current_position: Tuple[float, float],
        dwell_duration_ms: float,
        previous_positions: Optional[deque] = None
    ) -> IntentScore:
        """
        Comprehensive intent analysis combining velocity, dwell, and history.
        GAP 2 FIX: Properly uses Kalman velocity output for classification.
        
        Args:
            current_velocity: (vx, vy) from Kalman filter
            current_position: (x, y) current gaze position
            dwell_duration_ms: How long user has been looking at current area
            previous_positions: Optional deque of recent positions for consistency
            
        Returns:
            IntentScore with confidence and reasoning
        """
        vx, vy = current_velocity
        speed = np.sqrt(vx**2 + vy**2)
        
        # Update history
        self.velocity_history.append((vx, vy))
        self.speed_history.append(speed)
        self.position_history.append(current_position)
        
        # ========== VELOCITY ANALYSIS (GAP 2 FIX) ==========
        velocity_score, velocity_reason = self._analyze_velocity(speed)
        
        # ========== DWELL DURATION ANALYSIS ==========
        duration_score, duration_reason = self._analyze_dwell(dwell_duration_ms)
        
        # ========== CONSISTENCY ANALYSIS ==========
        consistency_score, consistency_reason = self._analyze_consistency(previous_positions)
        
        # ========== COMBINED INTENT CLASSIFICATION ==========
        # Weighted combination of indicators
        confidence = (velocity_score * 0.4 + duration_score * 0.35 + consistency_score * 0.25)
        
        # Classify intent level
        if speed > self.VELOCITY_THRESHOLD_FAST:
            # Fast movement = glance/saccade
            level = IntentLevel.GLANCE
            reason = f"Fast saccade (speed={speed:.1f}px/frame)"
            
        elif speed > self.VELOCITY_THRESHOLD_SLOW:
            # Moderate movement = normal eye movement
            level = IntentLevel.NORMAL
            reason = f"Normal eye movement (speed={speed:.1f}px/frame)"
            
        elif dwell_duration_ms >= self.MIN_DELIBERATE_DWELL_MS and speed < self.VELOCITY_THRESHOLD_SLOW:
            # Slow + sustained fixation = deliberate
            level = IntentLevel.DELIBERATE
            reason = f"Deliberate fixation ({dwell_duration_ms:.0f}ms dwell)"
            confidence = min(1.0, confidence + 0.2)  # Boost confidence for deliberate fixations
            
        else:
            # Ambiguous
            level = IntentLevel.NORMAL
            reason = "Ambiguous movement pattern"
        
        return IntentScore(
            level=level,
            confidence=min(1.0, confidence),
            velocity_score=velocity_score,
            duration_score=duration_score,
            consistency_score=consistency_score,
            reason=reason
        )
    
    def _analyze_velocity(self, current_speed: float) -> Tuple[float, str]:
        """
        Analyze velocity to determine intentionality.
        GAP 2: Use velocity magnitude threshold classification.
        
        Args:
            current_speed: Current speed in pixels/frame
            
        Returns:
            Tuple of (score 0-1, reason)
        """
        # Calculate trend (is speed increasing/decreasing?)
        if len(self.speed_history) > 2:
            recent_speeds = list(self.speed_history)[-3:]
            speed_trend = recent_speeds[-1] - recent_speeds[0]
            speed_stability = 1.0 - np.std(recent_speeds) if recent_speeds else 0.5
        else:
            speed_trend = 0
            speed_stability = 0.5
        
        # Scoring logic
        if current_speed < self.VELOCITY_THRESHOLD_SLOW:
            # Slow, deliberate movement = high intent score
            velocity_score = 0.9
            reason = f"Slow motion ({current_speed:.1f}px/frame)"
            
        elif current_speed < self.VELOCITY_THRESHOLD_FAST:
            # Moderate speed = medium intent
            normalized_speed = current_speed / self.VELOCITY_THRESHOLD_FAST
            velocity_score = 0.5 + (1.0 - normalized_speed) * 0.3
            reason = f"Moderate motion ({current_speed:.1f}px/frame)"
            
        else:
            # Fast saccade = low intent (glance)
            velocity_score = 0.1
            reason = f"Fast saccade ({current_speed:.1f}px/frame)"
        
        # Adjust by stability
        velocity_score = velocity_score * 0.7 + speed_stability * 0.3
        
        return min(1.0, velocity_score), reason
    
    def _analyze_dwell(self, dwell_duration_ms: float) -> Tuple[float, str]:
        """
        Analyze dwell duration.
        Sustained fixation indicates intentional gaze.
        
        Args:
            dwell_duration_ms: Duration at current location in milliseconds
            
        Returns:
            Tuple of (score 0-1, reason)
        """
        # Thresholds
        min_fixation_ms = 100
        deliberate_fixation_ms = 500
        long_fixation_ms = 1500
        
        if dwell_duration_ms < min_fixation_ms:
            dwell_score = 0.2  # Too short to be intentional
            reason = f"No fixation ({dwell_duration_ms:.0f}ms)"
            
        elif dwell_duration_ms < deliberate_fixation_ms:
            # Intermediate duration
            dwell_score = 0.3 + (dwell_duration_ms - min_fixation_ms) / (deliberate_fixation_ms - min_fixation_ms) * 0.4
            reason = f"Partial fixation ({dwell_duration_ms:.0f}ms)"
            
        elif dwell_duration_ms < long_fixation_ms:
            # Good deliberate fixation
            dwell_score = 0.85
            reason = f"Deliberate fixation ({dwell_duration_ms:.0f}ms)"
            
        else:
            # Very long fixation (possibly fatigue-related)
            dwell_score = 0.9
            reason = f"Extended fixation ({dwell_duration_ms:.0f}ms)"
        
        return min(1.0, dwell_score), reason
    
    def _analyze_consistency(self, previous_positions: Optional[deque] = None) -> Tuple[float, str]:
        """
        Analyze movement consistency.
        Consistent movements indicate intentional gaze control.
        
        Args:
            previous_positions: Optional external position history
            
        Returns:
            Tuple of (score 0-1, reason)
        """
        positions = previous_positions or self.position_history
        
        if len(positions) < 5:
            return 0.5, "Insufficient history"
        
        # Calculate variance in recent positions
        positions_array = np.array(list(positions))
        position_variance = np.var(positions_array, axis=0)
        total_variance = np.sum(position_variance)
        
        # Variance thresholds
        stable_variance = 100  # Pixels^2 - very stable
        normal_variance = 500
        erratic_variance = 2000
        
        if total_variance < stable_variance:
            consistency_score = 0.95
            reason = "Very stable gaze"
            
        elif total_variance < normal_variance:
            consistency_score = 0.8
            reason = "Stable gaze"
            
        elif total_variance < erratic_variance:
            consistency_score = 0.5
            reason = "Normal variability"
            
        else:
            consistency_score = 0.2
            reason = "Erratic movement"
        
        return consistency_score, reason
    
    def should_execute_command(self, intent_score: IntentScore) -> Tuple[bool, str]:
        """
        Determine if command should be executed based on intent analysis.
        Feature F: Uses confidence score to gate command execution.
        
        Args:
            intent_score: IntentScore from analyze_intent
            
        Returns:
            Tuple of (should_execute, reason)
        """
        # Command execution thresholds
        if intent_score.level == IntentLevel.GLANCE:
            should_execute = False
            reason = "Quick glance detected - suppressed"
            
        elif intent_score.level == IntentLevel.DELIBERATE:
            should_execute = intent_score.confidence >= 0.60
            reason = f"Deliberate gaze (confidence {intent_score.confidence:.0%})"
            
        else:  # NORMAL
            should_execute = intent_score.confidence >= self.MIN_COMMAND_CONFIDENCE
            reason = f"Normal movement (confidence {intent_score.confidence:.0%})"
        
        return should_execute, reason
    
    def update_dwell(
        self,
        current_position: Tuple[float, float],
        dwell_radius: int = 50
    ) -> float:
        """
        Update dwell tracking and return dwell duration.
        
        Args:
            current_position: Current gaze position
            dwell_radius: Radius to consider as same fixation point
            
        Returns:
            Dwell duration in milliseconds
        """
        current_time = time.time()
        
        if self.dwell_position is None:
            # Start new fixation
            self.dwell_position = current_position
            self.dwell_start_time = current_time
            return 0.0
        
        # Check distance from dwell start position
        dx = current_position[0] - self.dwell_position[0]
        dy = current_position[1] - self.dwell_position[1]
        distance = np.sqrt(dx**2 + dy**2)
        
        if distance > dwell_radius:
            # Moved to new location - reset dwell
            self.dwell_position = current_position
            self.dwell_start_time = current_time
            return 0.0
        
        # Still in same area - calculate dwell time
        dwell_time_s = current_time - self.dwell_start_time
        dwell_time_ms = dwell_time_s * 1000.0
        
        return dwell_time_ms
    
    def reset_dwell(self) -> None:
        """Reset dwell tracking"""
        self.dwell_position = None
        self.dwell_start_time = None
    
    def get_confidence_for_display(self, intent_score: IntentScore) -> str:
        """
        Format confidence for HUD display (Feature F).
        
        Args:
            intent_score: Intent analysis result
            
        Returns:
            Formatted confidence string with bar
        """
        confidence_pct = int(intent_score.confidence * 100)
        bar_length = int(confidence_pct / 10)
        bar = "█" * bar_length + "░" * (10 - bar_length)
        
        color = "🟢" if intent_score.confidence >= 0.70 else "🟡" if intent_score.confidence >= 0.50 else "🔴"
        
        return f"{color} INTENT: {confidence_pct}% [{bar}]"
    
    def get_stats(self) -> dict:
        """Get session statistics"""
        total_commands = self.true_positives + self.false_positives
        accuracy = (self.true_positives / total_commands * 100) if total_commands > 0 else 0
        
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "total_commands": total_commands,
            "accuracy": accuracy
        }
    
    def reset_stats(self) -> None:
        """Reset statistics"""
        self.true_positives = 0
        self.false_positives = 0


class CommandGatekeeper:
    """
    Smart command queue with deduplication and priority system.
    Feature G: Deduplicates rapid-fire commands and prioritizes critical commands.
    """
    
    def __init__(self, max_queue_depth: int = 5, cooldown_ms: float = 300.0):
        """
        Initialize command gatekeeper.
        
        Args:
            max_queue_depth: Maximum queue length before dropping low-priority
            cooldown_ms: Minimum time between identical commands
        """
        self.queue = deque(maxlen=max_queue_depth)
        self.cooldown_ms = cooldown_ms
        self.last_commands = {}  # Track command timestamps
        
        # Priority levels
        self.priority = {
            "EMERGENCY_ALERT": 1000,
            "CALL_NURSE": 900,
            "CLICK": 500,
            "DOUBLE_CLICK": 490,
            "SCROLL_UP": 300,
            "SCROLL_DOWN": 300,
            "SCROLL_LEFT": 300,
            "SCROLL_RIGHT": 300,
            "LEFT": 250,
            "RIGHT": 250,
            "UP": 250,
            "DOWN": 250,
            "VOLUME_UP": 200,
            "VOLUME_DOWN": 200,
        }
    
    def add_command(self, command_name: str) -> bool:
        """
        Add command to queue if not duplicate.
        
        Args:
            command_name: Name of command to add
            
        Returns:
            True if command was added, False if deduplicated/dropped
        """
        current_time = time.time() * 1000  # milliseconds
        
        # Check for recent duplicate
        if command_name in self.last_commands:
            time_since_last = current_time - self.last_commands[command_name]
            if time_since_last < self.cooldown_ms:
                return False  # Deduplicated
        
        # If queue is full, drop lowest priority command
        if len(self.queue) >= self.queue.maxlen:
            # Remove lowest priority
            if self.queue:
                lowest = min(self.queue, key=lambda cmd: self.priority.get(cmd, 0))
                self.queue.remove(lowest)
        
        self.queue.append(command_name)
        self.last_commands[command_name] = current_time
        
        return True
    
    def get_next_command(self) -> Optional[str]:
        """
        Get next command from queue (highest priority).
        
        Returns:
            Next command name or None if queue is empty
        """
        if not self.queue:
            return None
        
        # Find highest priority command
        next_cmd = max(self.queue, key=lambda cmd: self.priority.get(cmd, 0))
        self.queue.remove(next_cmd)
        
        return next_cmd
    
    def queue_size(self) -> int:
        """Get current queue size"""
        return len(self.queue)
    
    def clear_queue(self) -> None:
        """Clear all queued commands"""
        self.queue.clear()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test intent engine
    logger.info("Testing IntentEngine...")
    
    engine = IntentEngine()
    
    # Simulate slow deliberate movement
    logger.info("\n--- Slow deliberate gaze ---")
    slow_velocity = (2.0, 1.0)
    slow_position = (500, 500)
    slow_dwell = 800.0  # 800ms
    
    score = engine.analyze_intent(slow_velocity, slow_position, slow_dwell)
    should_exec, reason = engine.should_execute_command(score)
    logger.info(f"Intent: {score.level.value}, Confidence: {score.confidence:.1%}")
    logger.info(f"Execute: {should_exec} - {reason}")
    logger.info(engine.get_confidence_for_display(score))
    
    # Simulate fast glance
    logger.info("\n--- Fast glance ---")
    fast_velocity = (100.0, 50.0)
    fast_position = (600, 400)
    fast_dwell = 50.0
    
    score = engine.analyze_intent(fast_velocity, fast_position, fast_dwell)
    should_exec, reason = engine.should_execute_command(score)
    logger.info(f"Intent: {score.level.value}, Confidence: {score.confidence:.1%}")
    logger.info(f"Execute: {should_exec} - {reason}")
    logger.info(engine.get_confidence_for_display(score))
    
    # Test command gatekeeper
    logger.info("\n--- Testing CommandGatekeeper ---")
    gk = CommandGatekeeper()
    
    gk.add_command("CLICK")
    gk.add_command("CLICK")  # Duplicate - should be rejected
    gk.add_command("SCROLL_UP")
    gk.add_command("EMERGENCY_ALERT")
    
    logger.info(f"Queue size: {gk.queue_size()}")
    while True:
        cmd = gk.get_next_command()
        if not cmd:
            break
        logger.info(f"Next command: {cmd}")
    
    logger.info("✓ IntentEngine tests complete")
