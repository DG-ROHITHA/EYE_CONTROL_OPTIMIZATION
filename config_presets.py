"""
Configuration Presets for Eye-Tracking System
Easy-to-use profiles for different scenarios
"""

class ConfigPreset:
    """Base configuration preset"""
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.settings = {}
    
    def apply_to_config(self, config_obj):
        """Apply preset settings to config object"""
        for key, value in self.settings.items():
            if hasattr(config_obj, key):
                setattr(config_obj, key, value)
            elif hasattr(config_obj, 'perf') and hasattr(config_obj.perf, key):
                setattr(config_obj.perf, key, value)
        
        print(f"✓ Applied preset: {self.name}")
        print(f"  {self.description}")


# ==================== PERFORMANCE PRESETS ====================

class HighPerformancePreset(ConfigPreset):
    """Maximum speed, lower accuracy (for powerful computers)"""
    def __init__(self):
        super().__init__(
            "High Performance",
            "Best for powerful systems - Maximum speed with good accuracy"
        )
        self.settings = {
            # Performance
            'SKIP_FRAMES': 0,
            'PROCESS_WIDTH': 640,
            'PROCESS_HEIGHT': 480,
            'USE_ROI': True,
            
            # Smoothing
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 3,
            
            # Response time
            'DWELL_TIME': 1.0,
            'GESTURE_COOLDOWN': 0.3,
            'COMMAND_COOLDOWN': 0.5,
            
            # Intent detection
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 0.8,
            'VELOCITY_THRESHOLD_SLOW': 12,
            'VELOCITY_THRESHOLD_FAST': 100,
        }


class BalancedPreset(ConfigPreset):
    """Balanced performance and accuracy (recommended)"""
    def __init__(self):
        super().__init__(
            "Balanced (Recommended)",
            "Optimal balance of speed and accuracy for most systems"
        )
        self.settings = {
            # Performance
            'SKIP_FRAMES': 2,
            'PROCESS_WIDTH': 320,
            'PROCESS_HEIGHT': 240,
            'USE_ROI': True,
            
            # Smoothing
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 3,
            
            # Response time
            'DWELL_TIME': 1.2,
            'GESTURE_COOLDOWN': 0.4,
            'COMMAND_COOLDOWN': 0.6,
            
            # Intent detection
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 1.0,
            'VELOCITY_THRESHOLD_SLOW': 10,
            'VELOCITY_THRESHOLD_FAST': 100,
        }


class PowerSaverPreset(ConfigPreset):
    """Minimum CPU usage (for low-end computers/laptops)"""
    def __init__(self):
        super().__init__(
            "Power Saver",
            "Optimized for low-end systems and battery life"
        )
        self.settings = {
            # Performance
            'SKIP_FRAMES': 4,
            'PROCESS_WIDTH': 240,
            'PROCESS_HEIGHT': 180,
            'USE_ROI': True,
            
            # Smoothing
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 2,
            
            # Response time
            'DWELL_TIME': 1.5,
            'GESTURE_COOLDOWN': 0.5,
            'COMMAND_COOLDOWN': 0.8,
            
            # Intent detection
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 1.2,
            'VELOCITY_THRESHOLD_SLOW': 10,
            'VELOCITY_THRESHOLD_FAST': 80,
        }


# ==================== USE CASE PRESETS ====================

class GamingPreset(ConfigPreset):
    """Fast, responsive controls for gaming"""
    def __init__(self):
        super().__init__(
            "Gaming",
            "Fast response times for gaming - Lower safety margins"
        )
        self.settings = {
            # Performance
            'SKIP_FRAMES': 1,
            'PROCESS_WIDTH': 320,
            'PROCESS_HEIGHT': 240,
            'USE_ROI': True,
            
            # Smoothing (less for faster response)
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 2,
            
            # Response time (faster)
            'DWELL_TIME': 0.8,
            'GESTURE_COOLDOWN': 0.2,
            'COMMAND_COOLDOWN': 0.3,
            
            # Intent detection (more lenient)
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 0.6,
            'VELOCITY_THRESHOLD_SLOW': 15,
            'VELOCITY_THRESHOLD_FAST': 120,
            
            # Features
            'ENABLE_BASIC_CONTROLS': True,
            'ENABLE_ADVANCED_CONTROLS': True,
            'ENABLE_ASSISTIVE_CONTROLS': False,
            'REQUIRE_CONFIRMATION': False,
        }


class AssistiveDevicePreset(ConfigPreset):
    """Medical/assistive use - High accuracy and safety"""
    def __init__(self):
        super().__init__(
            "Assistive Device (Medical)",
            "Maximum accuracy and safety for medical/assistive use"
        )
        self.settings = {
            # Performance (accuracy over speed)
            'SKIP_FRAMES': 0,
            'PROCESS_WIDTH': 480,
            'PROCESS_HEIGHT': 360,
            'USE_ROI': True,
            
            # Smoothing (maximum)
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 5,
            
            # Response time (slower, safer)
            'DWELL_TIME': 1.5,
            'GESTURE_COOLDOWN': 0.6,
            'COMMAND_COOLDOWN': 1.0,
            
            # Intent detection (strict)
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 1.2,
            'VELOCITY_THRESHOLD_SLOW': 8,
            'VELOCITY_THRESHOLD_FAST': 80,
            
            # Features
            'ENABLE_BASIC_CONTROLS': True,
            'ENABLE_ADVANCED_CONTROLS': True,
            'ENABLE_ASSISTIVE_CONTROLS': True,
            'REQUIRE_CONFIRMATION': True,
            'ENABLE_AUDIO_FEEDBACK': True,
            
            # Safety
            'MAX_CURSOR_SPEED': 40,
        }


class ProductivityPreset(ConfigPreset):
    """General computing and productivity"""
    def __init__(self):
        super().__init__(
            "Productivity",
            "Optimized for general computing, web browsing, documents"
        )
        self.settings = {
            # Performance
            'SKIP_FRAMES': 2,
            'PROCESS_WIDTH': 320,
            'PROCESS_HEIGHT': 240,
            'USE_ROI': True,
            
            # Smoothing
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 4,
            
            # Response time
            'DWELL_TIME': 1.2,
            'GESTURE_COOLDOWN': 0.5,
            'COMMAND_COOLDOWN': 0.7,
            
            # Intent detection
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 1.0,
            'VELOCITY_THRESHOLD_SLOW': 10,
            'VELOCITY_THRESHOLD_FAST': 100,
            
            # Features
            'ENABLE_BASIC_CONTROLS': True,
            'ENABLE_ADVANCED_CONTROLS': True,
            'ENABLE_ASSISTIVE_CONTROLS': False,
            'REQUIRE_CONFIRMATION': False,
        }


class AccessibilityPreset(ConfigPreset):
    """For users with motor difficulties"""
    def __init__(self):
        super().__init__(
            "Accessibility",
            "For users with limited motor control - Very forgiving settings"
        )
        self.settings = {
            # Performance
            'SKIP_FRAMES': 1,
            'PROCESS_WIDTH': 400,
            'PROCESS_HEIGHT': 300,
            'USE_ROI': True,
            
            # Smoothing (high to help with tremors)
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 7,
            
            # Response time (longer to account for slower movements)
            'DWELL_TIME': 2.0,
            'GESTURE_COOLDOWN': 0.8,
            'COMMAND_COOLDOWN': 1.2,
            'CLICK_RADIUS': 40,
            
            # Intent detection (very strict)
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 1.5,
            'VELOCITY_THRESHOLD_SLOW': 5,
            'VELOCITY_THRESHOLD_FAST': 60,
            
            # Features
            'ENABLE_BASIC_CONTROLS': True,
            'ENABLE_ADVANCED_CONTROLS': False,
            'ENABLE_ASSISTIVE_CONTROLS': True,
            'REQUIRE_CONFIRMATION': True,
            'ENABLE_AUDIO_FEEDBACK': True,
            
            # Safety
            'MAX_CURSOR_SPEED': 30,
        }


class DemoPreset(ConfigPreset):
    """For demonstrations and testing"""
    def __init__(self):
        super().__init__(
            "Demo/Testing",
            "Safe settings for demonstrations and testing"
        )
        self.settings = {
            # Performance
            'SKIP_FRAMES': 1,
            'PROCESS_WIDTH': 320,
            'PROCESS_HEIGHT': 240,
            'USE_ROI': True,
            
            # Smoothing
            'USE_KALMAN_FILTER': True,
            'SMOOTHING_FRAMES': 3,
            
            # Response time
            'DWELL_TIME': 1.5,
            'GESTURE_COOLDOWN': 0.5,
            'COMMAND_COOLDOWN': 0.8,
            
            # Intent detection
            'INTENT_DETECTION': True,
            'INTENTIONAL_GAZE_DURATION': 1.0,
            'VELOCITY_THRESHOLD_SLOW': 10,
            'VELOCITY_THRESHOLD_FAST': 100,
            
            # Features
            'SIMULATION_MODE': True,
            'ENABLE_BASIC_CONTROLS': True,
            'ENABLE_ADVANCED_CONTROLS': True,
            'ENABLE_ASSISTIVE_CONTROLS': True,
            'ENABLE_AUDIO_FEEDBACK': True,
        }


# ==================== PRESET MANAGER ====================

class PresetManager:
    """Manage and apply configuration presets"""
    
    PRESETS = {
        'high_performance': HighPerformancePreset,
        'balanced': BalancedPreset,
        'power_saver': PowerSaverPreset,
        'gaming': GamingPreset,
        'assistive': AssistiveDevicePreset,
        'productivity': ProductivityPreset,
        'accessibility': AccessibilityPreset,
        'demo': DemoPreset,
    }
    
    @classmethod
    def list_presets(cls):
        """List all available presets"""
        print("\n" + "="*70)
        print("📋 AVAILABLE CONFIGURATION PRESETS")
        print("="*70)
        
        for i, (key, preset_class) in enumerate(cls.PRESETS.items(), 1):
            preset = preset_class()
            print(f"\n{i}. {preset.name}")
            print(f"   Key: '{key}'")
            print(f"   {preset.description}")
        
        print("\n" + "="*70)
    
    @classmethod
    def get_preset(cls, preset_name):
        """Get preset by name"""
        if preset_name in cls.PRESETS:
            return cls.PRESETS[preset_name]()
        else:
            print(f"❌ Preset '{preset_name}' not found!")
            print("Available presets:", list(cls.PRESETS.keys()))
            return None
    
    @classmethod
    def apply_preset(cls, config_obj, preset_name):
        """Apply preset to config object"""
        preset = cls.get_preset(preset_name)
        if preset:
            preset.apply_to_config(config_obj)
            return True
        return False
    
    @classmethod
    def interactive_select(cls):
        """Interactive preset selection"""
        cls.list_presets()
        
        print("\nEnter preset name or number (or 'cancel' to skip):")
        choice = input("> ").strip().lower()
        
        if choice == 'cancel':
            return None
        
        # Try by number
        try:
            num = int(choice)
            preset_keys = list(cls.PRESETS.keys())
            if 1 <= num <= len(preset_keys):
                return cls.get_preset(preset_keys[num - 1])
        except ValueError:
            pass
        
        # Try by name/key
        return cls.get_preset(choice)


# ==================== USAGE EXAMPLES ====================

def example_usage():
    """Example of how to use presets"""
    print("\n" + "="*70)
    print("📖 PRESET USAGE EXAMPLES")
    print("="*70)
    
    print("""
Example 1: Apply preset in code
--------------------------------
from config_presets import PresetManager
from eye_control_optimized import config

# Apply balanced preset
PresetManager.apply_preset(config, 'balanced')

# Or apply gaming preset
PresetManager.apply_preset(config, 'gaming')


Example 2: Interactive selection
---------------------------------
from config_presets import PresetManager

preset_manager = PresetManager()
preset = preset_manager.interactive_select()
if preset:
    preset.apply_to_config(config)


Example 3: List all presets
----------------------------
from config_presets import PresetManager

PresetManager.list_presets()


Example 4: Manual preset application
-------------------------------------
from config_presets import GamingPreset

preset = GamingPreset()
preset.apply_to_config(config)


Example 5: Create custom preset
--------------------------------
from config_presets import ConfigPreset

class MyCustomPreset(ConfigPreset):
    def __init__(self):
        super().__init__(
            "My Custom",
            "My personalized settings"
        )
        self.settings = {
            'SKIP_FRAMES': 2,
            'DWELL_TIME': 1.0,
            'USE_KALMAN_FILTER': True,
            # Add your custom settings...
        }

preset = MyCustomPreset()
preset.apply_to_config(config)
""")


# ==================== COMMAND LINE INTERFACE ====================

if __name__ == "__main__":
    import sys
    
    print("🎛️  Eye-Tracking Configuration Preset Manager")
    print("="*70)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'list':
            PresetManager.list_presets()
        
        elif command == 'info':
            if len(sys.argv) > 2:
                preset = PresetManager.get_preset(sys.argv[2])
                if preset:
                    print(f"\n{preset.name}")
                    print(f"{preset.description}")
                    print("\nSettings:")
                    for key, value in preset.settings.items():
                        print(f"  {key}: {value}")
            else:
                print("Usage: python config_presets.py info <preset_name>")
        
        elif command == 'example':
            example_usage()
        
        elif command == 'interactive':
            preset = PresetManager.interactive_select()
            if preset:
                print(f"\n✓ Selected: {preset.name}")
                print("\nTo apply this preset in your code:")
                print(f"  PresetManager.apply_preset(config, '{list(PresetManager.PRESETS.keys())[list(PresetManager.PRESETS.values()).index(preset.__class__)]}')") 
        
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  list - List all presets")
            print("  info <preset_name> - Show preset details")
            print("  example - Show usage examples")
            print("  interactive - Interactive preset selection")
    
    else:
        # Default: show list
        PresetManager.list_presets()
        print("\n💡 TIP: Run with commands:")
        print("  python config_presets.py list")
        print("  python config_presets.py info balanced")
        print("  python config_presets.py example")
        print("  python config_presets.py interactive")
        
        print("\n📖 Quick Start:")
        print("  1. Import: from config_presets import PresetManager")
        print("  2. Apply: PresetManager.apply_preset(config, 'balanced')")
