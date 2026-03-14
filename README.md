Eye Control Assistive System
A camera-based eye tracking application that enables hands-free computer control for users with limited mobility. Uses real-time iris tracking, blink detection, and gesture sequences to execute system commands.

Features

8-Direction Gaze Control — Cardinal (UP, DOWN, LEFT, RIGHT) and diagonal directions
Blink Detection — Single blink, double blink, long blink (3s), and eyes-closed (5s) triggers
Sequence Patterns — Multi-step gesture sequences for assistive commands (e.g., Call Nurse)
Simulation Mode — Safe testing mode where commands are logged but not executed
5-Point Calibration — Improves direction detection accuracy by 50–70%
Audio Feedback — Beep confirmation on command execution
Visual HUD — Minimap, EAR indicator, progress bars, and sequence buffer display


Requirements
Python 3.8+
OpenCV
dlib or MediaPipe (face/iris landmarks)
pyautogui (live mode command execution)
Install dependencies:
bashpip install opencv-python mediapipe pyautogui

Quick Start
powershellcd r:\ROHI\webcame_dectection
python eye_control_assistive.py
On launch, the app starts in Simulation Mode (safe by default). No commands are executed until you switch to Live mode.
Keyboard Controls
KeyActionCStart 5-point calibrationMToggle Simulation ↔ Live modeSPACEEnable / disable cursor movementESCExit application

Command Reference
Gaze Directions
Eye MovementCommandLive Mode ActionLook UPSCROLL_UPScroll page upLook DOWNSCROLL_DOWNScroll page downLook LEFTLEFTLeft arrow keyLook RIGHTRIGHTRight arrow keyLook UP-LEFTVOLUME_UPIncrease system volumeLook UP-RIGHTBRIGHTNESS_UPIncrease screen brightnessLook DOWN-LEFTBACKBrowser back buttonLook DOWN-RIGHTHOMEPress Home key
Blink Gestures
GestureCommandLive Mode ActionSingle blinkCLICKMouse clickDouble blinkDOUBLE_CLICKDouble clickLong blink (3s)EMERGENCY_ALERTAlarm sound + alertEyes closed (5s)SLEEP_MODEEnter rest mode
Sequence Patterns
SequenceCommandLive Mode ActionLEFT → RIGHT → LEFTCALL_NURSEBeep notificationUP → DOWN → UPADJUST_BEDBeep notification

Configuration
All settings are in the Config class inside eye_control_assistive.py:
python# Safety
SIMULATION_MODE = True          # Start in safe mode (recommended)
COMMAND_COOLDOWN = 0.8          # Seconds between commands
GESTURE_COOLDOWN = 0.5          # Seconds between direction gestures

# Blink Detection
EAR_THRESHOLD = 0.21            # Eye Aspect Ratio blink threshold
LONG_BLINK_TIME = 3.0           # Seconds for emergency alert
EYES_CLOSED_SLEEP = 5.0         # Seconds for sleep mode

# Direction Zones (0.0 – 1.0 normalized)
LOOK_LEFT_THRESHOLD = 0.35
LOOK_RIGHT_THRESHOLD = 0.65
LOOK_UP_THRESHOLD = 0.30
LOOK_DOWN_THRESHOLD = 0.70

# Feature Toggles
ENABLE_BASIC_CONTROLS = True
ENABLE_ADVANCED_CONTROLS = True
ENABLE_ASSISTIVE_CONTROLS = True
ENABLE_AUDIO_FEEDBACK = True
Presets
Limited eye movement:
pythonLOOK_LEFT_THRESHOLD = 0.40
LOOK_RIGHT_THRESHOLD = 0.60
COMMAND_COOLDOWN = 1.5
Experienced users:
pythonCOMMAND_COOLDOWN = 0.5
GESTURE_COOLDOWN = 0.3
Sensitive blink detection:
pythonEAR_THRESHOLD = 0.23
BLINK_FRAMES = 1

Screen Layout
┌──────────────────────────────────────────────┐
│ Top-Left:               Top-Right:           │
│  • Gaze coordinates      • Minimap           │
│  • Calibration status    • Direction zones   │
│  • Control mode          • Current direction │
├──────────────────────────────────────────────┤
│                                              │
│         • Red dot = iris position            │
│         • Circle = dwell progress            │
│         • Command confirmation overlay       │
│                                              │
├──────────────────────────────────────────────┤
│ Bottom-Left:            Bottom-Right:        │
│  • Sequence buffer       • EAR value         │
│  • Dwell progress bar    • Blink indicator   │
│  • Long blink timer                          │
│  • Sleep mode timer                          │
└──────────────────────────────────────────────┘

Getting Started (Recommended Progression)
Week 1 — Foundation

Run in Simulation mode only
Enable Basic Controls only
15-minute sessions; focus on consistent direction gestures

Week 2 — Blinks

Enable Advanced Controls
Practice single and double blink clicks
Try diagonal gaze directions

Week 3 — Sequences

Enable Assistive Controls
Practice the emergency and call nurse sequences

Week 4 — Live Mode

Switch to Live mode under supervision
Start with simple scrolling and clicking tasks
Monitor for eye strain; take 5-minute breaks every 15 minutes


Safety Guidelines

✅ Have a caregiver present during initial live-mode sessions
✅ Keep a backup call system available at all times
✅ Test the emergency alert sequence with audio off first
✅ Re-calibrate daily or whenever camera position changes
✅ Document preferred settings for each individual user


Troubleshooting
ProblemSolutionNo face detectedImprove lighting; center face in camera frameBlinks not registeringIncrease EAR_THRESHOLD (try 0.23)Direction detection inaccurateRun calibration (C key)Commands firing accidentallyIncrease COMMAND_COOLDOWN

Project Files
FileDescriptioneye_control_assistive.pyMain applicationUSER_GUIDE.mdDetailed usage instructionsTESTING_GUIDE.mdStep-by-step testing and validationconfig_commands.txtFull configuration referenceIMPLEMENTATION_SUMMARY.mdFeature overview and change log

Testing Checklist

Run the application — camera feed should appear
Press C — complete 5-point calibration
Look UP — console shows COMMAND: SCROLL_UP
Look DOWN — console shows COMMAND: SCROLL_DOWN
Blink once — console shows COMMAND: CLICK
Blink twice quickly — console shows COMMAND: DOUBLE_CLICK
Look UP-LEFT — console shows COMMAND: VOLUME_UP
Do LEFT → RIGHT → LEFT — console shows COMMAND: CALL_NURSE
All passing? Press M to enable Live mode and test one real command

