"""
Day 3 scope: turn a transcript into structured meeting notes.
Day 5 addition: retry with exponential backoff on transient API failures
(rate limits, overload, network blips) instead of failing the whole run.

Design notes (know these for your interview):
- We ask the model to return ONLY JSON (no preamble) so the frontend can
  parse it reliably instead of regex-scraping free text.
- We explicitly instruct the model to only use what's in the transcript,
  not invent names/dates/decisions — this is our main defense against
  hallucination, since these notes may be trusted at face value by a team.
- For long transcripts, we chunk + map-reduce: summarize each chunk first,
  then summarize the summaries. A single API call has a context limit, and
  even within the limit, quality drops on very long inputs ("lost in the
  middle" problem) — chunking keeps each call focused and more accurate.
- We retry only on errors that are actually worth retrying (rate limits,
  server overload, timeouts) and NOT on errors that will never succeed no
  matter how many times you retry (bad API key, malformed request) — retrying
  those just wastes time and hides the real problem from the user.
"""

import json
import os
import time
from anthropic import (
    Anthropic,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OverloadedError,
    RateLimitError,
)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-5"

# Rough chunking threshold. We estimate ~1.3 tokens per word for English text,
# and keep chunks well under the model's context window so each call has room
# for the prompt + JSON response too.
WORDS_PER_CHUNK = 3000

# Errors worth retrying: transient/server-side. Auth errors, bad requests,
# etc. are NOT in this list on purpose — retrying those can't help.
RETRYABLE_ERRORS = (RateLimitError, OverloadedError, InternalServerError,
                    APIConnectionError, APITimeoutError)
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 2

SYSTEM_PROMPT = """You are an assistant that converts meeting transcripts into structured notes.

Rules:
- Only use information present in the transcript. Never invent names, dates, or decisions.
- If something is unclear or not mentioned (e.g. no deadline given), leave that field empty rather than guessing.
- Be concise. Summary should be 3-5 sentences, not a re-narration of the whole meeting.
- Respond with ONLY valid JSON, no preamble, no markdown code fences, no explanation.

JSON schema to return:
{
  "summary": "string, 3-5 sentence overview",
  "decisions": ["string", ...],
  "action_items": [
    {"task": "string", "owner": "string or null if not mentioned", "deadline": "string or null if not mentioned"}
  ],
  "open_questions": ["string", ...]
}
"""

MERGE_SYSTEM_PROMPT = """You are merging multiple partial meeting-note summaries (from
consecutive chunks of the same meeting, in order) into one final set of notes.

Rules:
- Combine and de-duplicate decisions and action items that appear in more than one chunk.
- Keep the final summary to 3-5 sentences covering the whole meeting, not each chunk.
- Only use information present in the provided partial summaries. Never invent anything.
- Respond with ONLY valid JSON, no preamble, no markdown code fences, no explanation.

Use this exact JSON schema:
{
  "summary": "string, 3-5 sentence overview",
  "decisions": ["string", ...],
  "action_items": [
    {"task": "string", "owner": "string or null", "deadline": "string or null"}
  ],
  "open_questions": ["string", ...]
}
"""


def _parse_json_response(text: str) -> dict:
    """Strip accidental markdown fences and parse JSON, with a clear error if it fails."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON: {e}\nRaw response: {text[:300]}")


def _call_claude(system_prompt: str, user_content: str) -> dict:
    """
    Call Claude with automatic retry + exponential backoff on transient errors.
    Delay sequence: 2s, 4s, 8s (base_delay * 2^attempt).
    """
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            text = "".join(block.text for block in response.content if block.type == "text")
            return _parse_json_response(text)

        except RETRYABLE_ERRORS as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY_SECONDS * (2 ** attempt)
                time.sleep(delay)
            # else: fall through and raise after the loop

    raise RuntimeError(
        f"Claude API call failed after {MAX_RETRIES} attempts due to a transient "
        f"error ({type(last_error).__name__}). Please try again in a moment."
    ) from last_error


def _chunk_text(text: str, words_per_chunk: int = WORDS_PER_CHUNK) -> list:
    words = text.split()
    return [
        " ".join(words[i:i + words_per_chunk])
        for i in range(0, len(words), words_per_chunk)
    ]


def summarize_transcript(transcript_text: str) -> dict:
    """
    Turn a transcript into structured notes: summary, decisions, action items,
    open questions. Handles long transcripts via chunk + map-reduce.

    Raises:
        ValueError: if transcript_text is empty/whitespace only.
        RuntimeError: if the API call fails after retries.

    Returns:
        {
            "summary": "...",
            "decisions": [...],
            "action_items": [{"task": ..., "owner": ..., "deadline": ...}, ...],
            "open_questions": [...]
        }
    """
    if not transcript_text or not transcript_text.strip():
        raise ValueError(
            "Transcript is empty — there's nothing to summarize. This usually "
            "means the audio had no detectable speech (silence or very low volume)."
        )

    chunks = _chunk_text(transcript_text)

    if len(chunks) == 1:
        return _call_claude(SYSTEM_PROMPT, f"Transcript:\n\n{chunks[0]}")

    # Map step: summarize each chunk independently
    partial_summaries = []
    for i, chunk in enumerate(chunks):
        partial = _call_claude(
            SYSTEM_PROMPT,
            f"This is part {i + 1} of {len(chunks)} of a longer meeting transcript:\n\n{chunk}",
        )
        partial_summaries.append(partial)

    # Reduce step: merge all partial summaries into one final result
    merge_input = json.dumps(partial_summaries, indent=2)
    return _call_claude(
        MERGE_SYSTEM_PROMPT,
        f"Partial summaries in chronological order:\n\n{merge_input}",
    )