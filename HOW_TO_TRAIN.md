# How to Train Your Personal Gaze Model

## Step 1 — Collect your data (10 minutes)
python gaze_recorder.py
- Sit 50–70cm from your webcam, normal posture
- Keep your head still, only move your eyes
- Wear your glasses if you normally use them
- Good lighting on your face — no strong backlight
- Repeat for 3 full passes when prompted

## Step 2 — Prepare dataset (1 minute)
python prep_data.py

## Step 3 — Train the model (5–15 minutes on GPU)
python train_gaze.py
# CPU training is possible but takes 45–90 minutes

## Step 4 — Export to ONNX (30 seconds)
python export_model.py

## Step 5 — Verify (30 seconds)
python check_model.py

## Step 6 — Use in NeuroGaze Elite
python main_app.py --gaze-model personal_gaze_model --hud standard

