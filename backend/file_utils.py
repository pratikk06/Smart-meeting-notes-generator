"""
Day 1 scope: handle file upload, validation, and saving to disk.
Transcription (Day 2) and summarization (Day 3) will build on top of this.
"""

import uuid
from pathlib import Path
from datetime import datetime

from backend.config import UPLOAD_DIR, MAX_UPLOAD_SIZE_MB, SUPPORTED_FORMATS


class UploadError(Exception):
    """Raised when an uploaded file fails validation."""
    pass


def validate_file(filename: str, size_bytes: int) -> None:
    """Raise UploadError if the file is unsupported or too large."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise UploadError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )

    size_mb = size_bytes / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise UploadError(
            f"File is {size_mb:.1f} MB, exceeds limit of {MAX_UPLOAD_SIZE_MB} MB."
        )


def save_upload(uploaded_file) -> dict:
    """
    Save a Streamlit UploadedFile object to disk with a unique name.
    Returns metadata dict used by the rest of the pipeline.
    """
    validate_file(uploaded_file.name, uploaded_file.size)

    file_id = str(uuid.uuid4())[:8]
    ext = Path(uploaded_file.name).suffix.lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file_id}{ext}"
    dest_path = UPLOAD_DIR / safe_name

    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return {
        "file_id": file_id,
        "original_name": uploaded_file.name,
        "saved_path": str(dest_path),
        "size_mb": round(uploaded_file.size / (1024 * 1024), 2),
        "uploaded_at": timestamp,
    }