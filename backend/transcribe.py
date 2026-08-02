"""
Day 2 scope: transcribe a saved audio/video file into text using Whisper.
Day 5 addition: clearer error handling for corrupt files, missing files,
and silent/no-speech audio (so the UI can show a helpful message instead
of a raw stack trace).

Design notes (know these for your interview):
- We load the Whisper model ONCE and cache it (loading is slow, ~seconds to
  minutes depending on model size). Re-loading per request would be wasteful.
- Whisper handles long audio internally by processing it in 30-second windows
  under the hood, so we don't need to manually chunk the file ourselves for
  local Whisper (this is different from calling a hosted STT API with a
  request-size limit, where manual chunking would be required).
- We return segments (with timestamps) AND the full text, because timestamps
  are useful later for action items ("at 12:34, X said...") and for showing
  a scrollable transcript with jump-to-timestamp in the UI.
"""

import os
import whisper

# Cache loaded models by size so switching models doesn't reload from disk
# every time, and so we don't reload the SAME model repeatedly either.
_MODEL_CACHE = {}


class TranscriptionError(Exception):
    """Raised when a file can't be transcribed (missing, corrupt, or unreadable)."""
    pass


def load_model(model_size: str = "base"):
    """
    Load (or fetch from cache) a Whisper model.
    Model size options: tiny, base, small, medium, large
    - tiny/base: fast, good for testing, lower accuracy
    - small/medium: better accuracy, slower, more RAM
    - large: best accuracy, needs a GPU realistically
    """
    if model_size not in _MODEL_CACHE:
        _MODEL_CACHE[model_size] = whisper.load_model(model_size)
    return _MODEL_CACHE[model_size]


def transcribe_audio(file_path: str, model_size: str = "base") -> dict:
    """
    Transcribe an audio/video file into text.

    Raises:
        TranscriptionError: if the file is missing, empty, corrupt, or
            otherwise fails to process. Wraps the underlying exception so
            the UI can show one clear message instead of a raw traceback.

    Returns:
        {
            "text": "full transcript as one string",
            "language": "detected language code, e.g. 'en'",
            "segments": [
                {"start": 0.0, "end": 4.2, "text": "Hello everyone, ..."},
                ...
            ],
            "is_silent": bool  # True if no speech was detected at all
        }
    """
    if not os.path.exists(file_path):
        raise TranscriptionError(f"File not found: {file_path}")

    if os.path.getsize(file_path) == 0:
        raise TranscriptionError("File is empty (0 bytes) — nothing to transcribe.")

    try:
        model = load_model(model_size)
        # fp16=False because we may be running on CPU (fp16 requires a GPU;
        # forcing fp32 avoids a runtime warning/crash on CPU-only machines)
        result = model.transcribe(file_path, fp16=False)
    except Exception as e:
        # Whisper/ffmpeg raise a variety of exception types for corrupt or
        # unsupported files. We normalize all of them into one clear error
        # rather than let the UI show a raw traceback.
        raise TranscriptionError(
            f"Could not transcribe this file — it may be corrupt or in an "
            f"unsupported format. Details: {e}"
        ) from e

    segments = [
        {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]

    full_text = result["text"].strip()

    return {
        "text": full_text,
        "language": result.get("language", "unknown"),
        "segments": segments,
        "is_silent": len(full_text) == 0,
    }