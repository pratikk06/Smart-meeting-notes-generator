"""
Day 6 (bonus) scope: accept a video URL (YouTube, Vimeo, and hundreds of
other sites yt-dlp supports) instead of a manual file upload, download just
the audio track, and feed it into the same transcription pipeline used for
uploaded files.

Design notes:
- We download audio-only (not video) since Whisper only needs the audio
  track — this is much faster and uses far less disk/bandwidth than pulling
  the full video.
- We reuse the same UPLOAD_DIR and the same downstream transcribe/summarize
  functions, so this is purely an alternate "input source" — everything
  after this step in the pipeline doesn't know or care whether the file
  came from a manual upload or a URL download.
- yt-dlp errors (invalid URL, private/deleted video, geo-restricted, no
  audio stream, etc.) are wrapped into one clear exception type so the UI
  can show a helpful message instead of a raw traceback.
"""

import uuid
from pathlib import Path
from datetime import datetime

import yt_dlp

from backend.config import UPLOAD_DIR, MAX_UPLOAD_SIZE_MB


class URLDownloadError(Exception):
    """Raised when a video URL can't be downloaded or processed."""
    pass


def download_from_url(url: str) -> dict:
    """
    Download the audio track from a video URL and save it to UPLOAD_DIR,
    mirroring the metadata shape returned by file_utils.save_upload() so
    the rest of the app can treat both input sources identically.

    Returns:
        {
            "file_id": "...",
            "original_name": "<video title>.mp3",
            "saved_path": "...",
            "size_mb": ...,
            "uploaded_at": "...",
            "source_url": url,
            "video_title": "...",
        }
    """
    if not url or not url.strip():
        raise URLDownloadError("Please paste a video URL.")

    file_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # yt-dlp appends the extension itself based on the chosen audio format,
    # so we give it a template without an extension.
    output_template = str(UPLOAD_DIR / f"{timestamp}_{file_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noplaylist": True,  # if a playlist URL is pasted, only take the first video
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_UPLOAD_SIZE_MB * 1024 * 1024,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise URLDownloadError(
            f"Could not download this video. It may be private, deleted, "
            f"region-restricted, or the URL may be invalid. Details: {e}"
        ) from e
    except Exception as e:
        raise URLDownloadError(f"Unexpected error downloading video: {e}") from e

    video_title = info.get("title", "Untitled video")

    # After postprocessing, the final file has the .mp3 extension we requested
    saved_path = Path(str(UPLOAD_DIR / f"{timestamp}_{file_id}.mp3"))
    if not saved_path.exists():
        raise URLDownloadError(
            "Download appeared to succeed but the audio file wasn't found on disk. "
            "This can happen if the video has no audio track."
        )

    size_mb = round(saved_path.stat().st_size / (1024 * 1024), 2)

    return {
        "file_id": file_id,
        "original_name": f"{video_title}.mp3",
        "saved_path": str(saved_path),
        "size_mb": size_mb,
        "uploaded_at": timestamp,
        "source_url": url,
        "video_title": video_title,
    }