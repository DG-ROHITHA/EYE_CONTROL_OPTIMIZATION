import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# -------------------- INITIALIZATION --------------------

# Set webcam
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

prev_gray = None

# Path to the built-in face_landmarker.task model
# Update this path based on your system
model_path = r"R:\ROHI\webcame_dectection\face_landmarker.task"


# Initialize FaceLandmarker
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    num_faces=1
)
face_mesh = vision.FaceLandmarker.create_from_options(options)

# -------------------- MAIN LOOP --------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    h, w, _ = frame.shape

    # -------------------- PREPROCESSING --------------------
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    # -------------------- MOTION DETECTION --------------------
    if prev_gray is not None:
        diff = cv2.absdiff(prev_gray, gray)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for c in contours:
            if cv2.contourArea(c) < 1200:
                continue
            x, y, cw, ch = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x+cw, y+ch), (0, 255, 0), 2)
    prev_gray = gray.copy()

    # -------------------- FACE & LANDMARKS --------------------
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    results = face_mesh.detect(mp_image)

    if results.face_landmarks:
        face = results.face_landmarks[0]

        # -------------------- EYE TRACKING --------------------
        # Left and right iris landmark indices in MediaPipe 468-landmark format
        left_iris_ids = [474, 475, 476, 477]
        right_iris_ids = [469, 470, 471, 472]

        for eye_ids in [left_iris_ids, right_iris_ids]:
            xs, ys = [], []
            for i in eye_ids:
                lm = face[i]
                xs.append(lm.x * w)
                ys.append(lm.y * h)
            cx, cy = int(np.mean(xs)), int(np.mean(ys))
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

        # -------------------- HEAD POSE ESTIMATION --------------------
        landmark_ids = [33, 263, 1, 61, 291, 199]
        face_2d = []
        face_3d = []
        for idx in landmark_ids:
            lm = face[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            face_2d.append([x, y])
            face_3d.append([x, y, lm.z * 3000])

        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)

        cam_matrix = np.array([
            [w, 0, w / 2],
            [0, w, h / 2],
            [0, 0, 1]
        ], dtype=np.float64)

        dist_coeffs = np.zeros((4, 1))
        success, rot_vec, trans_vec = cv2.solvePnP(
            face_3d, face_2d, cam_matrix, dist_coeffs
        )

        rmat, _ = cv2.Rodrigues(rot_vec)
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
        yaw, pitch, roll = angles

        cv2.putText(frame, f"Yaw: {yaw:.2f}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        cv2.putText(frame, f"Pitch: {pitch:.2f}", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    # -------------------- DISPLAY --------------------
    cv2.imshow("Integrated Vision System", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC key
        break

cap.release()
cv2.destroyAllWindows()
