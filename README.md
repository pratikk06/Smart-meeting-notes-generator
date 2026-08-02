# Smart Meeting Notes Generator

Upload a meeting recording → get a transcript, summary, decisions, and action items.

## Status: Day 1 of 5 ✅
Upload pipeline works end-to-end (validation, saving, metadata display).
Transcription and summarization are stubbed for Day 2/3.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your API key(s)
```

> Note: Whisper needs `ffmpeg` installed on your system.
> - Mac: `brew install ffmpeg`
> - Ubuntu/Debian: `sudo apt install ffmpeg`
> - Windows: download from ffmpeg.org and add to PATH

## Run

```bash
streamlit run app.py
```