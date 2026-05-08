import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None

# Lightweight face registration + verification using MediaPipe FaceMesh.

# Approach:
# - detect exactly one face
# - compute a normalized landmark-based embedding (relative landmark positions)
# - compare embeddings with L2 distance

_mp_face_mesh = None
_mp_drawing = None
if mp is not None and hasattr(mp, 'solutions'):
    _mp_face_mesh = mp.solutions.face_mesh
    _mp_drawing = mp.solutions.drawing_utils



class FaceEmbeddingError(RuntimeError):
    pass


# MediaPipe FaceMesh is fairly heavy; initialize once.
# If MediaPipe isn't available, keep _face_mesh as None and let callers fail gracefully.
_face_mesh = None
if _mp_face_mesh is not None:
    _face_mesh = _mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

# OpenCV Haar cascade fallback for environments where MediaPipe is unavailable
_haar_cascade = None
try:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    _haar_cascade = cv2.CascadeClassifier(cascade_path)
    if _haar_cascade.empty():
        _haar_cascade = None
except Exception:
    _haar_cascade = None



# Select stable landmark indices that cover the face geometry.
# (These are MediaPipe FaceMesh indices.)
_STABLE_LANDMARKS = [
    # Contour / outline (top/middle/bottom)
    10, 338, 297, 332, 284, 251,
    69, 108, 151, 337, 299, 389,
    # Brows
    70, 63, 105, 66, 107, 336,
    # Eyes
    33, 133, 160, 158, 144, 153,
    362, 263, 387, 385, 380, 373,
    # Nose bridge / tip
    4, 6, 197, 195, 5,
    # Mouth
    61, 291, 78, 308, 13, 14, 17, 84, 181, 78,
]


def _normalize_landmarks(landmarks, width, height):
    """Convert landmarks to normalized embedding invariant to translation/scale."""
    pts = np.array([(lm.x * width, lm.y * height, lm.z * width) for lm in landmarks], dtype=np.float32)

    # Use an anchor point (approx. forehead / nose bridge)
    anchor = pts[0]
    pts_centered = pts - anchor

    # Scale normalization using a robust face width estimate
    # Right/left jaw-ish points if available
    scale = (np.linalg.norm(pts_centered[1] - pts_centered[2]) + 1e-6)
    pts_scaled = pts_centered / scale

    return pts_scaled.flatten()


def _landmarks_to_embedding(face_landmarks, image_shape):
    h, w = image_shape[:2]

    all_landmarks = face_landmarks.landmark
    # Guard: ensure indices exist
    indices = [i for i in _STABLE_LANDMARKS if i < len(all_landmarks)]
    selected = [all_landmarks[i] for i in indices]

    if len(selected) < 10:
        raise FaceEmbeddingError("Insufficient landmarks for embedding.")

    emb = _normalize_landmarks(selected, w, h)
    return emb


def _extract_opencv_embedding_bgr(frame_bgr):
    """Fallback embedding when MediaPipe FaceMesh is unavailable."""
    if _haar_cascade is None:
        raise FaceEmbeddingError("OpenCV Haar face detector is not available.")

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = _haar_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80),
    )
    if len(faces) == 0:
        raise FaceEmbeddingError("No face detected")

    # Pick the largest face for stability
    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
    face_roi = gray[y:y + h, x:x + w]

    # Normalize ROI and use compact intensity embedding
    face_small = cv2.resize(face_roi, (64, 64), interpolation=cv2.INTER_AREA)
    face_small = cv2.equalizeHist(face_small)
    emb = face_small.astype(np.float32).flatten() / 255.0
    return emb


def extract_face_embedding_bgr(frame_bgr):
    """Return a 1D float32 embedding for the largest/only face.

    Preferred: MediaPipe FaceMesh landmark embedding
    Fallback: OpenCV Haar ROI embedding (Python 3.14 compatible path)
    """
    if frame_bgr is None:
        raise FaceEmbeddingError("Input frame is None")
    if _face_mesh is None:
        return _extract_opencv_embedding_bgr(frame_bgr)


    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = _face_mesh.process(rgb)


    if not results.multi_face_landmarks:
        raise FaceEmbeddingError("No face detected")

    # Take first face
    face_landmarks = results.multi_face_landmarks[0]
    emb = _landmarks_to_embedding(face_landmarks, frame_bgr.shape)
    return emb.astype(np.float32)


def match_face_embeddings(embedding_a, embedding_b, threshold=0.8):
    """Return True if embeddings match within threshold."""
    a = np.asarray(embedding_a, dtype=np.float32).flatten()
    b = np.asarray(embedding_b, dtype=np.float32).flatten()

    if a.shape != b.shape:
        return False

    # Threshold tuning by embedding type:
    # - MediaPipe landmark embeddings are distance-comparable around 0.8
    # - OpenCV fallback embeddings use normalized pixel vectors and need a larger threshold
    if a.shape[0] == 64 * 64:
        threshold = 8.5

    dist = float(np.linalg.norm(a - b))
    return dist <= threshold

