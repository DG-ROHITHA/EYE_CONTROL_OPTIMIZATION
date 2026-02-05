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

## 🎓 Best Practices

1. **Always calibrate** when starting a session
2. **Start in simulation mode** for safety
3. **Take regular breaks** to prevent eye strain
4. **Good lighting** improves tracking significantly
5. **Consistent positioning** of camera and user
---


**Remember:** This is an assistive tool. 
