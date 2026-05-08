import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None


# MediaPipe is optional at import-time; runtime will safely fall back.
_face_mesh = None
if mp is not None and hasattr(mp, 'solutions'):
    _face_mesh = mp.solutions.face_mesh.FaceMesh(
        refine_landmarks=True,
        max_num_faces=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )



def gaze_tracking(frame):
    """Detect gaze direction (left, right, center).

    Returns a dict: {"gaze": "left"|"right"|"center"}

    If MediaPipe isn't available, defaults to center.
    """
    if frame is None:
        return {"gaze": "center"}
    if _face_mesh is None:
        return {"gaze": "center"}


    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = _face_mesh.process(frame_rgb)

    if results.multi_face_landmarks:
        landmarks = results.multi_face_landmarks[0]
        left_eye = [landmarks.landmark[33], landmarks.landmark[159]]
        right_eye = [landmarks.landmark[362], landmarks.landmark[386]]

        left_eye_center_x = float(np.mean([p.x for p in left_eye]))
        right_eye_center_x = float(np.mean([p.x for p in right_eye]))

        if left_eye_center_x < 0.4:
            return {"gaze": "left"}
        if right_eye_center_x > 0.6:
            return {"gaze": "right"}
        return {"gaze": "center"}

    return {"gaze": "center"}

