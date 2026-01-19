# 👁️ Eye Control Assistive Device - User Guide

## 🚀 Quick Start

### 1. **Run the Application**
```powershell
cd r:\ROHI\webcame_dectection
python eye_control_assistive.py
```

### 2. **Initial Setup (First Time)**
- The application starts in **SIMULATION MODE** (safe testing)
- Press **C** to calibrate (highly recommended)
- Look at each calibration point for 2 seconds

### 3. **Practice Commands**
- Try looking in different directions
- Practice blinking once, twice
- Watch the console for command outputs
- Observe visual feedback on screen

### 4. **Enable Live Control** (When Ready)
- Press **M** to toggle to LIVE mode
- Commands will now execute real actions
- Press **M** again to return to simulation

---

## 🎮 Complete Command Reference

### **Basic Direction Controls** (Always Available)
| Eye Movement | Command | Action |
|--------------|---------|--------|
| Look UP | `SCROLL_UP` | Scroll up on page |
| Look DOWN | `SCROLL_DOWN` | Scroll down on page |
| Look LEFT | `LEFT` | Left arrow key |
| Look RIGHT | `RIGHT` | Right arrow key |

### **Blink Controls** (Advanced)
| Gesture | Command | Action |
|---------|---------|--------|
| Blink once | `CLICK` | Mouse click / Select |
| Blink twice quickly | `DOUBLE_CLICK` | Double click |
| Close eyes 3+ seconds | `EMERGENCY_ALERT` | Alarm sound + alert |
| Close eyes 5+ seconds | `SLEEP_MODE` | Enter rest mode |

### **Diagonal Controls** (Advanced)
| Eye Movement | Command | Action |
|--------------|---------|--------|
| Look UP-LEFT | `VOLUME_UP` | Increase volume |
| Look UP-RIGHT | `BRIGHTNESS_UP` | Increase brightness |
| Look DOWN-LEFT | `BACK` | Browser back button |
| Look DOWN-RIGHT | `HOME` | Home key |

### **Sequence Patterns** (Assistive)
| Sequence | Command | Action |
|----------|---------|--------|
| LEFT → RIGHT → LEFT | `CALL_NURSE` | Beep notification |
| UP → DOWN → UP | `ADJUST_BED` | Bed adjustment request |

---

## ⌨️ Keyboard Controls

| Key | Function |
|-----|----------|
| **C** | Start calibration process |
| **M** | Toggle Simulation ↔ Live mode |
| **SPACE** | Enable/Disable cursor movement |
| **ESC** | Exit application |

---

## 📊 Visual Feedback Guide

### **On Screen Display:**

1. **Top-Right Minimap**
   - Shows screen divided into zones
   - Green dot = your gaze position
   - Grid lines = direction thresholds

2. **Current Direction Label**
   - Shows detected direction (UP, DOWN, LEFT, etc.)
   - Appears above minimap

3. **EAR (Eye Aspect Ratio)**
   - Bottom-right corner
   - Green = eyes open
   - Red = eyes closed (blinking)

4. **Progress Bars**
   - **Dwell Click**: Appears when staring at one spot
   - **Long Blink**: Shows emergency alert progress
   - **Sleep Mode**: Shows eyes-closed duration

5. **Sequence Buffer**
   - Bottom-left corner
   - Shows your current direction sequence
   - Format: "LEFT > RIGHT > LEFT"

6. **Command Confirmation**
   - Center-bottom of screen
   - Shows last executed command
   - Fades after 2 seconds

7. **Status Information** (Top-left)
   - Screen coordinates
   - Calibration status
   - Control mode (SIMULATION/LIVE)

---

## 🎯 Calibration Process

**Why Calibrate?**
- Improves accuracy by 50-70%
- Adapts to your eye movement range
- Accounts for camera position

**How to Calibrate:**
1. Press **C** key
2. Look at CENTER point (2 seconds)
3. Look at LEFT point (2 seconds)
4. Look at RIGHT point (2 seconds)
5. Look at TOP point (2 seconds)
6. Look at BOTTOM point (2 seconds)
7. Done! ✓

**Tips:**
- Sit still during calibration
- Move only your eyes, not your head
- Good lighting improves results
- Re-calibrate if you move the camera

---

## ⚙️ Customization

### **Edit Settings in Code:**

Open `eye_control_assistive.py` and modify the `Config` class:

```python
class Config:
    # Make blink detection more/less sensitive
    EAR_THRESHOLD = 0.21  # Lower = easier to trigger (0.18-0.25)
    
    # Change direction zones
    LOOK_LEFT_THRESHOLD = 0.35  # Increase for smaller left zone
    LOOK_RIGHT_THRESHOLD = 0.65  # Decrease for smaller right zone
    
    # Adjust timing
    COMMAND_COOLDOWN = 0.8  # Increase to prevent accidental repeats
    LONG_BLINK_TIME = 3.0   # Time needed for emergency alert
    
    # Enable/Disable features
    ENABLE_BASIC_CONTROLS = True      # Direction controls
    ENABLE_ADVANCED_CONTROLS = True   # Blinks & diagonals
    ENABLE_ASSISTIVE_CONTROLS = True  # Emergency & sequences
    ENABLE_AUDIO_FEEDBACK = True      # Beep sounds
```

### **Common Adjustments:**

**For Limited Eye Movement:**
```python
LOOK_LEFT_THRESHOLD = 0.40    # Wider center zone
LOOK_RIGHT_THRESHOLD = 0.60
DIRECTION_HOLD_TIME = 0.6     # Longer hold time
```

**For Faster Control:**
```python
GESTURE_COOLDOWN = 0.3        # Quick response
COMMAND_COOLDOWN = 0.5
DIRECTION_HOLD_TIME = 0.3     # Fast sequences
```

---

## 🔧 Troubleshooting

### **Problem: No Face Detected**
- ✅ Check camera is connected
- ✅ Improve lighting (face the light)
- ✅ Remove glasses if causing glare
- ✅ Sit 40-60cm from camera

### **Problem: Blinks Not Working**
- ✅ Adjust `EAR_THRESHOLD` (lower = easier)
- ✅ Blink more deliberately
- ✅ Check EAR value on screen (should drop below 0.21)

### **Problem: Directions Not Accurate**
- ✅ Run calibration (press C)
- ✅ Check camera is centered on your face
- ✅ Adjust direction thresholds in code

### **Problem: Too Many False Commands**
- ✅ Increase `COMMAND_COOLDOWN` value
- ✅ Increase `DIRECTION_HOLD_TIME`
- ✅ Narrow direction zones (adjust thresholds)

### **Problem: Commands Too Slow**
- ✅ Decrease cooldown timers
- ✅ Decrease `DIRECTION_HOLD_TIME`
- ✅ Practice holding gaze steady in zones

---

## 🏥 For Paralysis Patients

### **Recommended Setup Process:**

**Week 1: Basic Training**
1. Start with SIMULATION_MODE = True
2. Enable only BASIC_CONTROLS
3. Practice 15 minutes daily
4. Focus on consistent eye movements

**Week 2: Advanced Features**
5. Enable ADVANCED_CONTROLS
6. Practice single blinks for clicking
7. Try diagonal movements
8. Still in simulation mode

**Week 3: Sequences**
9. Enable ASSISTIVE_CONTROLS
10. Practice emergency alert sequence
11. Test nurse call pattern
12. Build muscle memory

**Week 4: Live Deployment**
13. Switch to LIVE mode with supervision
14. Start with simple tasks
15. Document preferred settings
16. Establish break schedule

### **Safety Protocols:**

✅ **Always have caregiver present initially**
✅ **Test emergency alert with sound off first**
✅ **Take 5-minute breaks every 15 minutes**
✅ **Keep traditional call system as backup**
✅ **Document any eye strain immediately**
✅ **Re-calibrate if feeling discomfort**

### **Customization for Patients:**

```python
# Gentler settings for beginners
COMMAND_COOLDOWN = 1.5        # Slower, safer
LONG_BLINK_TIME = 4.0         # More time for emergency
EAR_THRESHOLD = 0.19          # Easier blink detection
DIRECTION_HOLD_TIME = 0.7     # Longer to prevent accidents

# Wider center "neutral" zone
LOOK_LEFT_THRESHOLD = 0.40
LOOK_RIGHT_THRESHOLD = 0.60
LOOK_UP_THRESHOLD = 0.35
LOOK_DOWN_THRESHOLD = 0.65
```

---

## 📝 Command Log

All commands are logged with timestamps. Check your console output:

```
🎮 [14:32:15] COMMAND: SCROLL_UP
🎮 [14:32:18] COMMAND: CLICK
🎮 [14:32:23] COMMAND: CALL_NURSE
🚨 EMERGENCY ALERT TRIGGERED
```

---

## 🆘 Emergency Procedures

### **If System Becomes Unresponsive:**
1. Press **ESC** key to exit immediately
2. Close application window
3. Restart application if needed

### **If Emergency Alert Triggered Accidentally:**
- It will stop after 3 beeps
- No permanent action taken
- Just a sound notification

### **If Patient Cannot Exit:**
- Caregiver: Press ESC on keyboard
- Application auto-stops if camera fails
- Window close button also works

---

## 📞 Support & Further Customization

For advanced customization or issues:

1. Check `config_commands.txt` for all settings
2. Review code comments in `eye_control_assistive.py`
3. Modify `Config` class for your specific needs
4. Test changes in SIMULATION_MODE first

---

## 🎓 Best Practices

1. **Always calibrate** when starting a session
2. **Start in simulation mode** for safety
3. **Take regular breaks** to prevent eye strain
4. **Good lighting** improves tracking significantly
5. **Consistent positioning** of camera and user
6. **Document** what works best for each user
7. **Gradual progression** from basic to advanced features
8. **Backup systems** should always be available for critical needs

---

## ✨ Tips for Success

- **Exaggerate movements** initially (look to far edges)
- **Hold gaze steady** for sequences (don't rush)
- **Practice blinking deliberately** (not too fast)
- **Use the minimap** to see your gaze position
- **Watch the EAR value** to understand your blink pattern
- **Establish routines** for common tasks
- **Customize thresholds** to your natural eye movement

---

**Remember:** This is an assistive tool. Start slow, practice safely, and customize to individual needs. Success comes with patience and proper configuration! 💪
