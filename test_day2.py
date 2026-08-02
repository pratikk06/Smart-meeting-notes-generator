"""
Day 2 verification script.
Run this from your project root: python test_day2.py

Checks:
1. All required files exist
2. All dependencies import correctly
3. File validation logic works (good/bad cases)
4. Save-to-disk logic works and preserves file integrity
5. Actual Whisper transcription works on a real speech file
"""

import os
import sys
import subprocess
from pathlib import Path



PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    print(f"{status} - {name}" + (f" ({detail})" if detail else ""))


# ---------- 1. File existence ----------
print("\n=== 1. Checking project files exist ===")
required_files = [
    "app.py",
    "backend/__init__.py",
    "backend/config.py",
    "backend/file_utils.py",
    "backend/transcribe.py",
    "requirements.txt",
]
for f in required_files:
    check(f"File exists: {f}", Path(f).exists())

# ---------- 2. Imports ----------
print("\n=== 2. Checking dependencies import ===")
sys.path.insert(0, ".")

try:
    import streamlit
    check("streamlit imports", True, streamlit.__version__)
except Exception as e:
    check("streamlit imports", False, str(e))

try:
    import whisper
    check("whisper imports", True)
except Exception as e:
    check("whisper imports", False, str(e))

try:
    import torch
    check("torch imports", True, torch.__version__)
except Exception as e:
    check("torch imports", False, str(e))

try:
    from backend.config import UPLOAD_DIR, SUPPORTED_FORMATS, MAX_UPLOAD_SIZE_MB
    check("backend.config imports", True)
except Exception as e:
    check("backend.config imports", False, str(e))

try:
    from backend.file_utils import save_upload, validate_file, UploadError
    check("backend.file_utils imports", True)
except Exception as e:
    check("backend.file_utils imports", False, str(e))

try:
    from backend.transcribe import transcribe_audio
    check("backend.transcribe imports", True)
except Exception as e:
    check("backend.transcribe imports", False, str(e))

# ---------- 3. Validation logic ----------
print("\n=== 3. Testing file validation logic ===")

try:
    validate_file("meeting.exe", 1000)
    check("Rejects bad extension (.exe)", False, "did not raise error")
except UploadError:
    check("Rejects bad extension (.exe)", True)

try:
    validate_file("meeting.mp3", 999_999_999_999)
    check("Rejects oversized file", False, "did not raise error")
except UploadError:
    check("Rejects oversized file", True)

try:
    validate_file("meeting.mp3", 5_000_000)
    check("Accepts valid mp3", True)
except UploadError as e:
    check("Accepts valid mp3", False, str(e))

# ---------- 4. Save + integrity check ----------
print("\n=== 4. Testing save_upload() + file integrity ===")


class FakeUploadedFile:
    def __init__(self, name, content):
        self.name = name
        self._content = content
        self.size = len(content)

    def getbuffer(self):
        return self._content


test_content = b"INTEGRITY_TEST_BYTES_1234567890"
fake_file = FakeUploadedFile("integrity_test.wav", test_content)

try:
    meta = save_upload(fake_file)
    saved_ok = os.path.exists(meta["saved_path"])
    check("save_upload() creates file on disk", saved_ok, meta["saved_path"])

    with open(meta["saved_path"], "rb") as f:
        saved_content = f.read()
    check("Saved file content matches original (no corruption)",
          saved_content == test_content)
except Exception as e:
    check("save_upload() works", False, str(e))

# ---------- 5. Real transcription test ----------
print("\n=== 5. Testing actual Whisper transcription ===")
print("Generating a test speech file using macOS 'say' command...")

test_audio_path = "uploads/_test_day2_speech.wav"
os.makedirs("uploads", exist_ok=True)

try:
    # macOS built-in text-to-speech -> AIFF, then convert to WAV
    aiff_path = "/tmp/_test_day2_speech.aiff"
    subprocess.run(
        ["say", "-o", aiff_path,
         "We will finish the budget review by Friday. "
         "John will send the report to the client."],
        check=True
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", aiff_path, test_audio_path],
        check=True, capture_output=True
    )
    check("Generated test speech audio file", True, test_audio_path)

    print("Running transcription (first time downloads the model, ~140MB for 'base')...")
    result = transcribe_audio(test_audio_path, model_size="base")

    check("transcribe_audio() returned text", len(result["text"]) > 0, result["text"])
    check("transcribe_audio() returned segments", len(result["segments"]) > 0,
          f"{len(result['segments'])} segments")
    check("Detected language present", result["language"] is not None, result["language"])

    # Rough sanity check: did it get anything close to what we said?
    lower_text = result["text"].lower()
    keyword_hit = any(w in lower_text for w in ["budget", "friday", "john", "report"])
    check("Transcript contains expected keywords (sanity check)", keyword_hit, lower_text)

except FileNotFoundError:
    check("macOS 'say' command available", False,
          "Not on macOS, or ffmpeg missing. Provide your own audio file instead — "
          "see instructions printed below.")
except Exception as e:
    check("Transcription pipeline", False, str(e))

# ---------- Summary ----------
print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)
passed = sum(1 for _, status, _ in results if status == PASS)
total = len(results)
for name, status, detail in results:
    print(f"{status}  {name}")
print(f"\n{passed}/{total} checks passed")

if passed < total:
    print("\nSome checks failed — see details above.")
    sys.exit(1)
else:
    print("\nAll checks passed. Day 2 is working correctly! ✅")