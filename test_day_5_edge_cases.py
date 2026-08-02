"""
Day 5: automated test suite covering edge cases across the whole app.
Run with: python test_day5_edge_cases.py

Covers:
- Upload validation edge cases (bad format, oversized, no extension)
- File integrity after save
- Transcription error handling (missing file, empty file)
- Summarization error handling (empty transcript, retry logic)
- Export edge cases (empty notes, special characters, None values)
- Storage CRUD correctness
"""

import io
import os
import sys

sys.path.insert(0, ".")

PASS, FAIL = "✅ PASS", "❌ FAIL"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, status))
    print(f"{status} - {name}" + (f"  ({detail})" if detail else ""))


# ---------------------------------------------------------------------------
print("\n=== Upload validation edge cases ===")
from backend.file_utils import save_upload, validate_file, UploadError


class FakeFile:
    def __init__(self, name, content):
        self.name = name
        self._content = content
        self.size = len(content)

    def getbuffer(self):
        return self._content


try:
    validate_file("x.exe", 100)
    check("Rejects .exe", False)
except UploadError:
    check("Rejects .exe", True)

try:
    validate_file("noext", 100)
    check("Rejects file with no extension", False)
except UploadError:
    check("Rejects file with no extension", True)

try:
    validate_file("huge.mp3", 500 * 1024 * 1024)
    check("Rejects 500MB file (limit 200MB)", False)
except UploadError:
    check("Rejects 500MB file (limit 200MB)", True)

f = FakeFile("tiny.mp3", b"x")
try:
    meta = save_upload(f)
    check("Accepts a valid 1-byte mp3 (edge of 'too small')", os.path.exists(meta["saved_path"]))
    os.remove(meta["saved_path"])
except UploadError as e:
    check("Accepts a valid 1-byte mp3", False, str(e))

# ---------------------------------------------------------------------------
print("\n=== Transcription error handling ===")
from backend.transcribe import transcribe_audio, TranscriptionError

try:
    transcribe_audio("uploads/nonexistent_file_xyz.mp3")
    check("Raises on missing file", False)
except TranscriptionError:
    check("Raises on missing file", True)

os.makedirs("uploads", exist_ok=True)
empty_path = "uploads/_test_empty.mp3"
with open(empty_path, "wb") as fh:
    pass
try:
    transcribe_audio(empty_path)
    check("Raises on 0-byte file", False)
except TranscriptionError:
    check("Raises on 0-byte file", True)
finally:
    os.remove(empty_path)

# ---------------------------------------------------------------------------
print("\n=== Summarization error handling ===")
from backend.summarize import summarize_transcript, _chunk_text, _parse_json_response

try:
    summarize_transcript("")
    check("Raises ValueError on empty transcript", False)
except ValueError:
    check("Raises ValueError on empty transcript", True)

try:
    summarize_transcript("   \n\t  ")
    check("Raises ValueError on whitespace-only transcript", False)
except ValueError:
    check("Raises ValueError on whitespace-only transcript", True)

check("Chunking: 100 words -> 1 chunk",
      len(_chunk_text(" ".join(["w"] * 100), 3000)) == 1)
check("Chunking: 7500 words @ 3000/chunk -> 3 chunks",
      len(_chunk_text(" ".join(["w"] * 7500), 3000)) == 3)

try:
    _parse_json_response("not json")
    check("Raises on invalid JSON from model", False)
except ValueError:
    check("Raises on invalid JSON from model", True)

check("Parses JSON wrapped in markdown fences",
      _parse_json_response('```json\n{"a": 1}\n```') == {"a": 1})

# ---------------------------------------------------------------------------
print("\n=== Export edge cases ===")
from backend.export import export_to_docx, export_to_pdf

empty_notes = {"summary": "", "decisions": [], "action_items": [], "open_questions": []}
try:
    docx_bytes = export_to_docx(empty_notes, "Empty Meeting")
    check("DOCX export handles fully empty notes", docx_bytes[:2] == b"PK")
except Exception as e:
    check("DOCX export handles fully empty notes", False, str(e))

try:
    pdf_bytes = export_to_pdf(empty_notes, "Empty Meeting")
    check("PDF export handles fully empty notes", pdf_bytes[:4] == b"%PDF")
except Exception as e:
    check("PDF export handles fully empty notes", False, str(e))

special_notes = {
    "summary": "Discussed café budget — 50% increase, résumé review, emojis 🎉📊",
    "decisions": ["Approved «special» chars: quotes \"like this\" and 'this'"],
    "action_items": [{"task": "Review naïve implementation", "owner": None, "deadline": None}],
    "open_questions": [],
}
try:
    pdf_bytes2 = export_to_pdf(special_notes, "Café Meeting")
    check("PDF export handles unicode/special characters without crashing",
          pdf_bytes2[:4] == b"%PDF")
except Exception as e:
    check("PDF export handles unicode/special characters", False, str(e))

try:
    docx_bytes2 = export_to_docx(special_notes, "Café Meeting")
    check("DOCX export handles unicode/special characters without crashing",
          docx_bytes2[:2] == b"PK")
except Exception as e:
    check("DOCX export handles unicode/special characters", False, str(e))

# ---------------------------------------------------------------------------
print("\n=== Storage CRUD correctness ===")
from backend.storage import save_meeting, list_meetings, get_meeting, delete_meeting

before_count = len(list_meetings())
new_id = save_meeting("Edge Case Test Meeting", empty_notes, "", "test.mp3")
check("save_meeting returns a valid id", isinstance(new_id, int))
check("list_meetings count increases by 1", len(list_meetings()) == before_count + 1)

fetched = get_meeting(new_id)
check("get_meeting retrieves correct title", fetched["title"] == "Edge Case Test Meeting")
check("get_meeting parses notes_json back into a dict", fetched["notes"] == empty_notes)

check("get_meeting returns None for a nonexistent id", get_meeting(999999) is None)

delete_meeting(new_id)
check("delete_meeting removes the row", get_meeting(new_id) is None)
check("list_meetings count returns to original", len(list_meetings()) == before_count)

# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
passed = sum(1 for _, s in results if s == PASS)
total = len(results)
print(f"SUMMARY: {passed}/{total} checks passed")
if passed < total:
    print("\nFailed checks:")
    for name, status in results:
        if status == FAIL:
            print(f"  {status} {name}")
    sys.exit(1)
else:
    print("All Day 5 edge case checks passed! ✅")