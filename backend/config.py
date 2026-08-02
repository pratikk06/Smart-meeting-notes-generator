"""
Central config for the Smart Meeting Notes Generator.
Keeps all paths/settings in one place so nothing is hardcoded elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root = one level up from /backend
PROJECT_ROOT = Path(__file__).resolve().parent.parent

UPLOAD_DIR = PROJECT_ROOT / os.getenv("UPLOAD_DIR", "uploads")
DATA_DIR = PROJECT_ROOT / "data"

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", 200))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SUPPORTED_FORMATS = [".mp3", ".mp4", ".wav", ".m4a", ".mov", ".webm"]

# Make sure required folders exist at import time
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)