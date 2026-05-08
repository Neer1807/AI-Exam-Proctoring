"""Audio cheating detection.

IMPORTANT (Windows / wheel-only requirement):
- The original implementation used `pyaudio`, which typically requires native build tools.
- To keep `python -m pip install -r requirements.txt` working on Windows, this module
  now degrades gracefully when `pyaudio` is not available.

If `pyaudio` is installed in your environment manually, the module will use it.
Otherwise, `audio_detection()` returns `audio_detected=False`.
"""

from __future__ import annotations

import time
import numpy as np

try:
    import pyaudio  # type: ignore
    import wave  # noqa: F401

    _HAVE_PYAUDIO = True
except ModuleNotFoundError:
    pyaudio = None  # type: ignore
    _HAVE_PYAUDIO = False


# Parameters (only used when pyaudio is present)
THRESHOLD = 2000  # Adjust based on environment
CHUNK = 2048  # Larger chunk size for smoother audio
CHANNELS = 1
RATE = 48000  # High-quality audio
SOUND_END_DELAY = 4  # Time in seconds to stop recording after sound ends


def _record_segment(frames: list[bytes]) -> bytes:
    """Converts audio frames to bytes."""
    return b"".join(frames)


def audio_detection():
    """Detects speaking and returns audio segments during speaking.

    Returns:
        dict: {"audio_detected": bool, "audio_data": bytes|None}
    """
    if not _HAVE_PYAUDIO:
        # Wheel-only environment: no native audio backend available.
        time.sleep(1)
        return {"audio_detected": False, "audio_data": None}

    # Lazily create the stream when called.
    # (Avoids import-time failures and makes it play nicer with Django checks.)
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    try:
        sound_detected = False
        last_sound_time = 0.0
        frames: list[bytes] = []

        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)

            if np.max(np.abs(audio_data)) > THRESHOLD:
                if not sound_detected:
                    sound_detected = True
                last_sound_time = time.time()
                frames.append(data)

            if sound_detected and (time.time() - last_sound_time > SOUND_END_DELAY):
                audio_bytes = _record_segment(frames)
                frames = []
                sound_detected = False
                return {"audio_detected": True, "audio_data": audio_bytes}

    finally:
        try:
            stream.stop_stream()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
        try:
            p.terminate()
        except Exception:
            pass

    return {"audio_detected": False, "audio_data": None}

