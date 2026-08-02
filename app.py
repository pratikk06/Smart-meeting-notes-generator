"""
Smart Meeting Notes Generator — Day 1
Scope today: upload a meeting recording, validate it, save it, and show
confirmation + metadata. Transcription and summarization come in Day 2/3.
"""

import streamlit as st
from backend.file_utils import save_upload, UploadError
from backend.url_download import download_from_url, URLDownloadError
from backend.config import SUPPORTED_FORMATS, MAX_UPLOAD_SIZE_MB
from backend.transcribe import transcribe_audio, TranscriptionError
from backend.summarize import summarize_transcript
from backend.export import export_to_docx, export_to_pdf
from backend.storage import save_meeting, list_meetings, get_meeting, delete_meeting

st.set_page_config(
    page_title="Smart Meeting Notes Generator",
    page_icon="📝",
    layout="centered",
)

# Initialize ALL session state up front, before anything reads it
if "uploaded_meta" not in st.session_state:
    st.session_state.uploaded_meta = None
if "transcript" not in st.session_state:
    st.session_state.transcript = None
if "notes" not in st.session_state:
    st.session_state.notes = None
if "meeting_title" not in st.session_state:
    st.session_state.meeting_title = ""
if "viewing_history_id" not in st.session_state:
    st.session_state.viewing_history_id = None

st.title("📝 Smart Meeting Notes Generator")
st.caption("Upload a meeting recording → get a transcript, summary, and action items.")

# --- Sidebar: meeting history ---
with st.sidebar:
    st.header("📚 Meeting History")
    past_meetings = list_meetings()
    if not past_meetings:
        st.caption("No saved meetings yet.")
    else:
        for m in past_meetings:
            col_a, col_b = st.columns([4, 1])
            with col_a:
                if st.button(f"{m['title']}", key=f"open_{m['id']}", help=m["created_at"]):
                    st.session_state.viewing_history_id = m["id"]
            with col_b:
                if st.button("🗑️", key=f"del_{m['id']}"):
                    delete_meeting(m["id"])
                    if st.session_state.viewing_history_id == m["id"]:
                        st.session_state.viewing_history_id = None
                    st.rerun()

# --- Viewing a saved meeting from history ---
if st.session_state.viewing_history_id is not None:
    meeting = get_meeting(st.session_state.viewing_history_id)
    if meeting is None:
        st.session_state.viewing_history_id = None
    else:
        st.divider()
        st.subheader(f"📖 {meeting['title']}")
        st.caption(f"Saved on {meeting['created_at']}")

        notes = meeting["notes"]
        st.markdown("**Summary**")
        st.write(notes.get("summary", ""))
        st.markdown("**Decisions**")
        for d in notes.get("decisions", []) or ["No decisions detected."]:
            st.markdown(f"- {d}")
        st.markdown("**Action Items**")
        items = notes.get("action_items", [])
        if items:
            for item in items:
                owner = item.get("owner") or "Unassigned"
                deadline = item.get("deadline") or "No deadline given"
                st.markdown(f"- **{item.get('task', '')}** — {owner} ({deadline})")
        else:
            st.caption("No action items detected.")
        st.markdown("**Open Questions**")
        for q in notes.get("open_questions", []) or ["No open questions detected."]:
            st.markdown(f"- {q}")

        dl_col1, dl_col2, dl_col3 = st.columns(3)
        with dl_col1:
            st.download_button(
                "⬇️ Word (.docx)",
                data=export_to_docx(notes, meeting["title"], meeting["transcript_text"]),
                file_name=f"{meeting['title']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with dl_col2:
            st.download_button(
                "⬇️ PDF",
                data=export_to_pdf(notes, meeting["title"], meeting["transcript_text"]),
                file_name=f"{meeting['title']}.pdf",
                mime="application/pdf",
            )
        with dl_col3:
            if st.button("Close"):
                st.session_state.viewing_history_id = None
                st.rerun()
        st.divider()
        st.caption("⬆️ To start a new meeting, upload a file below.")

st.divider()
st.subheader("1. Provide your meeting recording")

tab_upload, tab_url = st.tabs(["📁 Upload a file", "🔗 Paste a video link"])

with tab_upload:
    uploaded_file = st.file_uploader(
        label=f"Supported formats: {', '.join(SUPPORTED_FORMATS)} | Max size: {MAX_UPLOAD_SIZE_MB} MB",
        type=[ext.strip(".") for ext in SUPPORTED_FORMATS],
    )

    if uploaded_file is not None:
        try:
            with st.spinner("Saving file..."):
                meta = save_upload(uploaded_file)
            st.session_state.uploaded_meta = meta
            st.session_state.transcript = None  # clear any previous transcript
            st.session_state.notes = None  # clear any previous notes
            st.success("File uploaded successfully!")
        except UploadError as e:
            st.error(str(e))
            st.session_state.uploaded_meta = None

with tab_url:
    st.caption("Works with YouTube, Vimeo, and hundreds of other video sites. "
               "Only the audio track is downloaded (faster, smaller).")
    video_url = st.text_input("Video URL", placeholder="https://www.youtube.com/watch?v=...")

    if st.button("Fetch Video", type="primary", disabled=not video_url):
        with st.spinner("Downloading audio from the video... this can take a "
                         "moment depending on video length."):
            try:
                meta = download_from_url(video_url)
                st.session_state.uploaded_meta = meta
                st.session_state.transcript = None
                st.session_state.notes = None
                st.success(f"Downloaded: {meta['video_title']}")
            except URLDownloadError as e:
                st.error(str(e))

# Show metadata + next-step placeholders
if st.session_state.uploaded_meta:
    meta = st.session_state.uploaded_meta
    st.divider()
    st.subheader("2. File details")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("File size", f"{meta['size_mb']} MB")
    with col2:
        st.metric("File ID", meta["file_id"])
    st.text(f"Original name: {meta['original_name']}")
    st.text(f"Saved at: {meta['saved_path']}")
    if meta.get("source_url"):
        st.caption(f"🔗 Source: {meta['source_url']}")

    st.divider()
    st.subheader("3. Transcribe")

    model_size = st.selectbox(
        "Model size (bigger = more accurate, slower)",
        options=["tiny", "base", "small", "medium"],
        index=1,  # default: base
        help="'tiny'/'base' are fast and good for testing. Use 'small' or "
             "'medium' for better accuracy once you're ready to rely on it.",
    )

    if st.button("Generate Transcript", type="primary"):
        with st.spinner(f"Transcribing with Whisper ({model_size} model)... "
                         f"first run may take longer while the model loads."):
            try:
                result = transcribe_audio(meta["saved_path"], model_size=model_size)
                if result["is_silent"]:
                    st.warning(
                        "No speech was detected in this file. It may be silent, "
                        "have very low volume, or be background noise only. "
                        "Try a different recording, or check the file plays correctly."
                    )
                    st.session_state.transcript = None
                else:
                    st.session_state.transcript = result
                    st.success("Transcript ready!")
            except TranscriptionError as e:
                st.error(str(e))
                st.session_state.transcript = None

    # Show transcript if we have one for this session
    if st.session_state.get("transcript"):
        transcript = st.session_state.transcript
        st.divider()
        st.subheader("4. Transcript")
        st.caption(f"Detected language: {transcript['language']}")

        tab_full, tab_segments = st.tabs(["Full text", "With timestamps"])

        with tab_full:
            st.text_area("Transcript", transcript["text"], height=250)

        with tab_segments:
            for seg in transcript["segments"]:
                st.markdown(f"**[{seg['start']}s → {seg['end']}s]** {seg['text']}")

        st.divider()
        st.subheader("5. Generate Meeting Notes")

        if st.button("Summarize", type="primary"):
            word_count = len(transcript["text"].split())
            if word_count < 15:
                st.warning(
                    f"This transcript is very short ({word_count} words) — the "
                    "summary may not be meaningful. Proceeding anyway."
                )
            with st.spinner("Summarizing with Claude..."):
                try:
                    notes = summarize_transcript(transcript["text"])
                    st.session_state.notes = notes
                    st.success("Notes ready!")
                except ValueError as e:
                    # e.g. empty transcript — a user-facing input problem, not a system failure
                    st.warning(str(e))
                    st.session_state.notes = None
                except RuntimeError as e:
                    # e.g. API retries exhausted — a real failure worth surfacing clearly
                    st.error(str(e))
                    st.session_state.notes = None

        if st.session_state.get("notes"):
            notes = st.session_state.notes
            st.divider()
            st.subheader("6. Meeting Notes")

            st.markdown("**Summary**")
            st.write(notes.get("summary", ""))

            st.markdown("**Decisions**")
            decisions = notes.get("decisions", [])
            if decisions:
                for d in decisions:
                    st.markdown(f"- {d}")
            else:
                st.caption("No decisions detected.")

            st.markdown("**Action Items**")
            action_items = notes.get("action_items", [])
            if action_items:
                for item in action_items:
                    owner = item.get("owner") or "Unassigned"
                    deadline = item.get("deadline") or "No deadline given"
                    st.markdown(f"- **{item.get('task', '')}** — {owner} ({deadline})")
            else:
                st.caption("No action items detected.")

            st.markdown("**Open Questions**")
            open_qs = notes.get("open_questions", [])
            if open_qs:
                for q in open_qs:
                    st.markdown(f"- {q}")
            else:
                st.caption("No open questions detected.")

            st.divider()
            st.subheader("7. Save & Export")

            default_title = meta["original_name"].rsplit(".", 1)[0]
            meeting_title = st.text_input("Meeting title", value=default_title)

            save_col, docx_col, pdf_col = st.columns(3)
            with save_col:
                if st.button("💾 Save to History"):
                    new_id = save_meeting(
                        title=meeting_title,
                        notes=notes,
                        transcript_text=transcript["text"],
                        original_filename=meta["original_name"],
                    )
                    st.success(f"Saved! (id {new_id}) — see it in the sidebar.")
            with docx_col:
                st.download_button(
                    "⬇️ Word (.docx)",
                    data=export_to_docx(notes, meeting_title, transcript["text"]),
                    file_name=f"{meeting_title}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            with pdf_col:
                st.download_button(
                    "⬇️ PDF",
                    data=export_to_pdf(notes, meeting_title, transcript["text"]),
                    file_name=f"{meeting_title}.pdf",
                    mime="application/pdf",
                )
else:
    st.caption("No file uploaded yet.")