# 🧪 Testing Guide - Eye Control Commands

## Quick Test Commands

Run the system and try each command type:

### ✅ **TEST 1: Basic Directions** (Should work immediately)
```
1. Look at the TOP of your screen → Should print: SCROLL_UP
2. Look at the BOTTOM → Should print: SCROLL_DOWN
3. Look FAR LEFT → Should print: LEFT
4. Look FAR RIGHT → Should print: RIGHT
```

**Expected Console Output:**
```
🎮 [HH:MM:SS] COMMAND: SCROLL_UP
🎮 [HH:MM:SS] COMMAND: LEFT
```

---

### ✅ **TEST 2: Blink Detection**
```
1. Watch the EAR value (bottom-right)
2. Blink once → Should print: CLICK
3. Wait 1 second
4. Blink twice quickly → Should print: DOUBLE_CLICK
```

**What to Look For:**
- EAR changes from ~0.25 (open) to ~0.15 (closed)
- Green text when eyes open, Red when closed
- Command appears in console and on-screen

---

### ✅ **TEST 3: Diagonal Movements**
```
1. Look TOP-LEFT corner → Should print: VOLUME_UP
2. Look TOP-RIGHT corner → Should print: BRIGHTNESS_UP  
3. Look BOTTOM-LEFT → Should print: BACK
4. Look BOTTOM-RIGHT → Should print: HOME
```

---

### ✅ **TEST 4: Sequence Patterns**
```
Test 1: Call Nurse
1. Look LEFT (hold 0.5s)
2. Look RIGHT (hold 0.5s)
3. Look LEFT (hold 0.5s)
→ Should print: CALL_NURSE with beep

Test 2: Adjust Bed
1. Look UP (hold 0.5s)
2. Look DOWN (hold 0.5s)
3. Look UP (hold 0.5s)
→ Should print: ADJUST_BED with beep
```

**Watch For:**
- Sequence buffer at bottom-left: "LEFT > RIGHT > LEFT"
- Must complete within 3 seconds

---

### ✅ **TEST 5: Long Blink (Emergency)**
```
⚠️ Test with sound OFF first!

1. Close your eyes
2. Keep closed for 3+ seconds
3. Progress bar should appear and fill
→ Should trigger: EMERGENCY_ALERT with alarm sound
```

---

### ✅ **TEST 6: Sleep Mode**
```
1. Close your eyes
2. Keep closed for 5+ seconds
3. Progress bar appears
→ Should print: SLEEP_MODE
```

---

## 🎯 Visual Feedback Checklist

While testing, verify you see:

- ✅ Red dot following your iris
- ✅ Green dot in minimap showing gaze position
- ✅ Direction zones (grid lines in minimap)
- ✅ Current direction label (UP, DOWN, LEFT, RIGHT, etc.)
- ✅ EAR value changing with blinks
- ✅ Progress bars for long actions
- ✅ Sequence buffer showing movement history
- ✅ Command confirmation appearing on screen
- ✅ Status showing SIMULATION mode

---

## 🔍 Troubleshooting Each Test

### **Basic Directions Not Working?**
```python
# Make zones larger (easier to trigger)
LOOK_LEFT_THRESHOLD = 0.40  # Was 0.35
LOOK_RIGHT_THRESHOLD = 0.60  # Was 0.65
```

### **Blinks Not Detected?**
```python
# Make blinks easier to trigger
EAR_THRESHOLD = 0.23  # Was 0.21 (higher = easier)
BLINK_FRAMES = 1      # Was 2 (fewer frames needed)
```

### **Diagonals Not Working?**
- Look to the EXTREME corners
- Hold gaze steady
- Watch minimap - dot should be in corner quadrant

### **Sequences Timing Out?**
```python
# Give more time
SEQUENCE_TIMEOUT = 5.0     # Was 3.0
DIRECTION_HOLD_TIME = 0.3  # Was 0.4 (faster registration)
```

### **Too Many False Commands?**
```python
# Add more delay between commands
COMMAND_COOLDOWN = 1.2     # Was 0.8
GESTURE_COOLDOWN = 0.7     # Was 0.5
```

---

## 📊 Expected Behavior Summary

| Feature | Expected Trigger Time | Visual Feedback |
|---------|----------------------|----------------|
| Basic Direction | Immediate | Direction label in minimap |
| Single Blink | 0.1s | EAR turns red briefly |
| Double Blink | Within 0.6s | Two red flashes |
| Long Blink | 3 seconds | Progress bar fills (red) |
| Sleep Mode | 5 seconds | Progress bar fills (purple) |
| Sequence | Within 3s | Buffer shows: "A > B > C" |
| Command Cooldown | 0.8s minimum | Prevents rapid repeats |

---

## 🎬 Testing Session Script

**Complete 10-Minute Test:**

```
[0:00-2:00] Calibration
- Press C
- Complete 5-point calibration
- Verify "CALIBRATED" status

[2:00-4:00] Basic Directions
- Test all 4 cardinal directions
- Verify commands in console
- Check minimap accuracy

[4:00-6:00] Blink Detection
- Test single blinks (5x)
- Test double blinks (5x)
- Watch EAR values

[6:00-7:30] Diagonal Controls
- Test all 4 corners
- Verify correct commands

[7:30-9:00] Sequences
- Test CALL_NURSE pattern (3x)
- Test ADJUST_BED pattern (3x)
- Watch sequence buffer

[9:00-10:00] Long Actions
- Test long blink (sound OFF)
- Test sleep mode
- Verify progress bars

✅ All tests pass? Ready for LIVE mode!
❌ Issues? Check troubleshooting above
```

---

## 🔄 Switching to LIVE Mode Test

**Only after simulation tests pass!**

```
1. Press M to switch to LIVE mode
2. Status changes to "LIVE"
3. Test ONE basic direction
   - Should actually scroll or press arrow key
4. If working correctly:
   - Try blink → should actually click
   - Try diagonals → should change volume/brightness
5. Press M again to return to SIMULATION if needed
```

**⚠️ IMPORTANT:** 
- Have cursor over empty area for click tests
- Be ready to press ESC to exit
- Don't test emergency alert in public spaces (loud!)

---

## 📋 Test Results Template

Copy and fill this out:

```
=== EYE CONTROL TEST RESULTS ===

Date: __________
User: __________
Camera Model: __________
Lighting: Good / Fair / Poor

CALIBRATION:
[ ] Completed successfully
[ ] Issues: _______________

BASIC DIRECTIONS:
[ ] UP works
[ ] DOWN works  
[ ] LEFT works
[ ] RIGHT works

BLINK DETECTION:
[ ] Single blink works
[ ] Double blink works
[ ] EAR threshold good: ____
[ ] Issues: _______________

DIAGONAL CONTROLS:
[ ] UP-LEFT works
[ ] UP-RIGHT works
[ ] DOWN-LEFT works
[ ] DOWN-RIGHT works

SEQUENCES:
[ ] CALL_NURSE works
[ ] ADJUST_BED works
[ ] Buffer displays correctly

LONG ACTIONS:
[ ] Long blink works (3s)
[ ] Sleep mode works (5s)
[ ] Progress bars visible

LIVE MODE (if tested):
[ ] Basic direction executed
[ ] Click executed
[ ] All commands safe
[ ] Ready for deployment: YES / NO

CUSTOM SETTINGS USED:
EAR_THRESHOLD: _____
COMMAND_COOLDOWN: _____
Other changes: _______________

NOTES:
________________________
________________________
________________________

OVERALL STATUS: PASS / NEEDS ADJUSTMENT / FAIL
```

---

## 🎯 Success Criteria

**System is ready when:**
- ✅ 90%+ direction accuracy
- ✅ Blinks detected reliably (8/10 attempts)
- ✅ Sequences complete without timeout
- ✅ No false commands during 2-minute idle period
- ✅ Visual feedback clear and helpful
- ✅ User comfortable with all gestures
- ✅ LIVE mode tested and working

**Need more practice if:**
- ❌ Frequent false commands
- ❌ Missing blink detections
- ❌ Sequences timeout often
- ❌ User finds movements uncomfortable
- ❌ Tracking lost frequently

---

## 🚀 Ready for Deployment?

**Pre-Deployment Checklist:**
- [ ] All simulation tests passed
- [ ] LIVE mode tested safely
- [ ] Settings documented
- [ ] User trained on all features
- [ ] Emergency procedures established
- [ ] Backup system available
- [ ] Caregiver informed
- [ ] Break schedule planned

**Good to go! 🎉**

---

Remember: Testing in SIMULATION mode is completely safe. Take your time, adjust settings as needed, and only switch to LIVE mode when comfortable!
