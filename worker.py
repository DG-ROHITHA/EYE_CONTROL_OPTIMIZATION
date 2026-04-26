"""
Command Worker Process
Async command execution via multiprocessing queue and cross-platform audio
Fixes GAP 3: Move pyautogui calls to dedicated worker process with queue
Fixes Windows platform lock: Cross-platform audio and path handling
Part of NeuroGaze Elite
"""

import multiprocessing as mp
from multiprocessing import Process, Queue, Value
import time
import logging
import platform
import numpy as np
from typing import Optional, Callable
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands"""
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DOUBLE_CLICK = "mouse_double_click"
    MOUSE_SCROLL = "mouse_scroll"
    KEYBOARD = "keyboard"
    AUDIO_BEEP = "audio_beep"
    SYSTEM = "system"
    SLEEP = "sleep"


def cross_platform_beep(frequency: int = 1000, duration_ms: int = 100) -> None:
    """
    Cross-platform beep without winsound dependency.
    
    Args:
        frequency: Frequency in Hz
        duration_ms: Duration in milliseconds
    """
    try:
        if platform.system() == "Windows":
            try:
                import winsound
                winsound.Beep(frequency, duration_ms)
                return
            except:
                pass
        
        # Fallback: use sounddevice if available
        try:
            import sounddevice as sd
            import numpy as np
            
            sample_rate = 44100
            samples = int(duration_ms / 1000.0 * sample_rate)
            t = np.linspace(0, duration_ms / 1000.0, samples)
            wave = (np.sin(2 * np.pi * frequency * t) * 0.3).astype(np.float32)
            
            sd.play(wave, sample_rate)
            sd.wait()
            return
        except:
            pass
        
        # Final fallback: print (silent visual indicator)
        logger.debug(f"Beep: {frequency}Hz x {duration_ms}ms")
        
    except Exception as e:
        logger.warning(f"Cross-platform beep failed: {e}")


class CommandWorkerProcess:
    """
    Dedicated worker process for command execution.
    Runs on separate process to prevent blocking main camera loop.
    Fixes GAP 3: Multiprocessing-based command execution.
    """
    
    def __init__(self, enable_audio: bool = True, enable_execution: bool = True):
        """
        Initialize command worker.
        
        Args:
            enable_audio: Enable audio feedback
            enable_execution: Enable actual command execution (False = simulation)
        """
        self.enable_audio = enable_audio
        self.enable_execution = enable_execution
        
        # Multiprocessing queue and control
        self.command_queue: mp.Queue = mp.Queue(maxsize=50)
        self.running = mp.Value('i', 0)
        self.worker_process: Optional[Process] = None
        
        # Stats
        self.commands_executed = mp.Value('i', 0)
        self.commands_failed = mp.Value('i', 0)
        
        # Configuration
        self.screen_width, self.screen_height = self._get_screen_size()
        
        logger.info(f"✓ CommandWorkerProcess initialized (screen: {self.screen_width}x{self.screen_height})")
    
    def _get_screen_size(self) -> tuple:
        """Get screen size cross-platform"""
        try:
            import pyautogui
            return pyautogui.size()
        except:
            # Fallback defaults
            return 1920, 1080
    
    def start(self) -> None:
        """Start the worker process"""
        if self.worker_process is None or not self.worker_process.is_alive():
            self.running.value = 1
            self.worker_process = Process(
                target=self._worker_loop,
                args=(
                    self.command_queue,
                    self.running,
                    self.commands_executed,
                    self.commands_failed,
                    self.enable_audio,
                    self.enable_execution,
                    self.screen_width,
                    self.screen_height
                )
            )
            self.worker_process.daemon = True
            self.worker_process.start()
            logger.info("✓ Command worker process started")
    
    def stop(self) -> None:
        """Stop the worker process"""
        self.running.value = 0
        if self.worker_process and self.worker_process.is_alive():
            self.worker_process.join(timeout=2.0)
            if self.worker_process.is_alive():
                self.worker_process.terminate()
            logger.info("✓ Command worker process stopped")
    
    @staticmethod
    def _worker_loop(
        cmd_queue: mp.Queue,
        running: mp.Value,
        cmd_executed: mp.Value,
        cmd_failed: mp.Value,
        enable_audio: bool,
        enable_execution: bool,
        screen_width: int,
        screen_height: int
    ) -> None:
        """
        Worker process main loop.
        Runs on separate process - handles all blocking operations here.
        """
        try:
            import pyautogui
            # Disable failsafe for controlled execution
            pyautogui.FAILSAFE = False
        except:
            logger.warning("pyautogui not available in worker process")
            pyautogui = None
        
        logger.info(f"Command worker loop started (pid: {mp.current_process().pid})")
        
        while running.value:
            try:
                # Get command from queue with timeout
                try:
                    command_data = cmd_queue.get(timeout=0.5)
                except:
                    continue
                
                # Execute command
                success = CommandWorkerProcess._execute_command(
                    command_data,
                    pyautogui,
                    enable_audio,
                    enable_execution,
                    screen_width,
                    screen_height
                )
                
                if success:
                    cmd_executed.value += 1
                else:
                    cmd_failed.value += 1
                    
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                cmd_failed.value += 1
        
        logger.info("Command worker loop stopped")
    
    @staticmethod
    def _execute_command(
        command_data: dict,
        pyautogui,
        enable_audio: bool,
        enable_execution: bool,
        screen_width: int,
        screen_height: int
    ) -> bool:
        """
        Execute individual command.
        
        Args:
            command_data: Command dictionary
            pyautogui: PyAutoGUI module
            enable_audio: Enable audio feedback
            enable_execution: Enable actual execution
            screen_width: Screen width
            screen_height: Screen height
            
        Returns:
            True if successful
        """
        try:
            cmd_type = CommandType(command_data.get("type", ""))
            
            if cmd_type == CommandType.MOUSE_MOVE:
                x = int(command_data.get("x", 0))
                y = int(command_data.get("y", 0))
                
                if enable_execution and pyautogui:
                    # Clamp to screen bounds
                    x = max(0, min(screen_width - 1, x))
                    y = max(0, min(screen_height - 1, y))
                    pyautogui.moveTo(x, y, duration=0)  # No animation
                
                if enable_audio:
                    cross_platform_beep(2000, 20)
                
                return True
            
            elif cmd_type == CommandType.MOUSE_CLICK:
                x = command_data.get("x")
                y = command_data.get("y")
                button = command_data.get("button", "left")
                
                if enable_execution and pyautogui:
                    if x is not None and y is not None:
                        x = max(0, min(screen_width - 1, x))
                        y = max(0, min(screen_height - 1, y))
                        pyautogui.click(x, y, button=button)
                    else:
                        pyautogui.click(button=button)
                
                if enable_audio:
                    cross_platform_beep(800, 50)
                
                return True
            
            elif cmd_type == CommandType.MOUSE_DOUBLE_CLICK:
                x = command_data.get("x")
                y = command_data.get("y")
                
                if enable_execution and pyautogui:
                    if x is not None and y is not None:
                        x = max(0, min(screen_width - 1, x))
                        y = max(0, min(screen_height - 1, y))
                        pyautogui.click(x, y, clicks=2, interval=0.1)
                    else:
                        pyautogui.click(clicks=2, interval=0.1)
                
                if enable_audio:
                    cross_platform_beep(1000, 30)
                    time.sleep(0.05)
                    cross_platform_beep(1000, 30)
                
                return True
            
            elif cmd_type == CommandType.MOUSE_SCROLL:
                direction = command_data.get("direction", "up")
                amount = command_data.get("amount", 3)
                
                if enable_execution and pyautogui:
                    scroll_amount = amount if direction in ["up", "right"] else -amount
                    if direction in ["up", "down"]:
                        pyautogui.scroll(scroll_amount)
                    else:
                        # Horizontal scroll (if supported)
                        pyautogui.press("right" if direction == "right" else "left")
                        time.sleep(0.05)
                
                if enable_audio:
                    cross_platform_beep(1500, 25)
                
                return True
            
            elif cmd_type == CommandType.KEYBOARD:
                key = command_data.get("key", "")
                keys = command_data.get("keys", [])
                
                if enable_execution and pyautogui:
                    if key:
                        pyautogui.press(key)
                    elif keys:
                        for k in keys:
                            pyautogui.press(k)
                            time.sleep(0.05)
                
                if enable_audio:
                    cross_platform_beep(1200, 40)
                
                return True
            
            elif cmd_type == CommandType.AUDIO_BEEP:
                freq = command_data.get("frequency", 1000)
                duration = command_data.get("duration_ms", 100)
                
                if enable_audio:
                    cross_platform_beep(freq, duration)
                
                return True
            
            elif cmd_type == CommandType.SLEEP:
                duration = command_data.get("duration_ms", 100)
                time.sleep(duration / 1000.0)
                return True
            
            else:
                logger.warning(f"Unknown command type: {cmd_type}")
                return False
                
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return False
    
    def queue_command(
        self,
        command_type: CommandType,
        **kwargs
    ) -> bool:
        """
        Queue a command for execution.
        Non-blocking - returns immediately.
        
        Args:
            command_type: Type of command
            **kwargs: Command-specific parameters
            
        Returns:
            True if queued successfully
        """
        try:
            command_data = {
                "type": command_type.value,
                **kwargs
            }
            self.command_queue.put_nowait(command_data)
            return True
        except Exception as e:
            logger.error(f"Failed to queue command: {e}")
            return False
    
    # Convenience methods for common commands
    
    def move_mouse(self, x: int, y: int) -> bool:
        """Queue mouse movement"""
        return self.queue_command(CommandType.MOUSE_MOVE, x=x, y=y)
    
    def click(self, x: int = None, y: int = None, button: str = "left") -> bool:
        """Queue mouse click"""
        return self.queue_command(CommandType.MOUSE_CLICK, x=x, y=y, button=button)
    
    def double_click(self, x: int = None, y: int = None) -> bool:
        """Queue double click"""
        return self.queue_command(CommandType.MOUSE_DOUBLE_CLICK, x=x, y=y)
    
    def scroll(self, direction: str = "up", amount: int = 3) -> bool:
        """Queue scroll"""
        return self.queue_command(CommandType.MOUSE_SCROLL, direction=direction, amount=amount)
    
    def press_key(self, key: str) -> bool:
        """Queue single key press"""
        return self.queue_command(CommandType.KEYBOARD, key=key)
    
    def press_keys(self, keys: list) -> bool:
        """Queue multiple key presses"""
        return self.queue_command(CommandType.KEYBOARD, keys=keys)
    
    def beep(self, frequency: int = 1000, duration_ms: int = 100) -> bool:
        """Queue beep"""
        return self.queue_command(CommandType.AUDIO_BEEP, frequency=frequency, duration_ms=duration_ms)
    
    def get_stats(self) -> dict:
        """Get worker statistics"""
        return {
            "commands_executed": self.commands_executed.value,
            "commands_failed": self.commands_failed.value,
            "queue_size": self.command_queue.qsize() if hasattr(self.command_queue, 'qsize') else -1,
            "is_running": bool(self.worker_process and self.worker_process.is_alive())
        }
    
    def reset_stats(self) -> None:
        """Reset statistics"""
        self.commands_executed.value = 0
        self.commands_failed.value = 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test command worker
    logger.info("Testing CommandWorkerProcess...")
    
    worker = CommandWorkerProcess(enable_audio=True, enable_execution=False)  # Simulation mode
    worker.start()
    
    # Queue some test commands
    logger.info("Queueing test commands...")
    worker.beep(1000, 100)
    worker.move_mouse(500, 500)
    worker.click(500, 500)
    worker.double_click(600, 600)
    worker.scroll("down", 3)
    worker.press_key("a")
    
    # Let worker process them
    time.sleep(2.0)
    
    # Get stats
    stats = worker.get_stats()
    logger.info(f"Stats: {stats}")
    
    # Stop worker
    worker.stop()
    
    logger.info("✓ CommandWorkerProcess test complete")
