import streamlit as st
import os
import time
import json
from pathlib import Path
from processor import process_pptx
from github_push import push_to_github

st.set_page_config(
    page_title="PPTX Diagram Reconstructor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("📊 PPTX Diagram Reconstructor")
st.markdown(
    "Upload a PowerPoint file to detect diagrams, reconstruct them as editable vector shapes, "
    "and export to PPTX / SVG / PNG."
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Session state defaults ──────────────────────────────────────────────────
for key, val in {
    "processing": False,
    "result": None,
    "log": [],
    "uploaded_path": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val


def add_log(msg: str):
    ts = time.strftime("%H:%M:%S")
    st.session_state.log.append(f"[{ts}] {msg}")


# ── Upload section ──────────────────────────────────────────────────────────
st.header("1. Upload")
uploaded_file = st.file_uploader("Choose a .pptx file", type=["pptx"])

if uploaded_file:
    save_path = UPLOAD_DIR / uploaded_file.name
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.session_state.uploaded_path = str(save_path)
    st.success(f"✅ Uploaded: {uploaded_file.name}")

# ── Analysis trigger ────────────────────────────────────────────────────────
st.header("2. Analyse & Reconstruct")

col1, col2 = st.columns([1, 4])
with col1:
    start_btn = st.button(
        "▶ Start Analysis",
        disabled=(st.session_state.uploaded_path is None or st.session_state.processing),
        use_container_width=True,
    )

if start_btn:
    st.session_state.processing = True
    st.session_state.log = []
    st.session_state.result = None

    progress_bar = st.progress(0, text="Initialising…")
    log_box = st.empty()

    def log_cb(msg: str, pct: int = None):
        add_log(msg)
        if pct is not None:
            progress_bar.progress(pct, text=msg)
        log_box.text_area("Execution log", "\n".join(st.session_state.log), height=200)

    try:
        result = process_pptx(st.session_state.uploaded_path, str(OUTPUT_DIR), log_cb)
        st.session_state.result = result
        progress_bar.progress(100, text="Done ✅")
    except Exception as exc:
        st.error(f"Processing failed: {exc}")
    finally:
        st.session_state.processing = False
    st.rerun()

# ── Persistent log display ──────────────────────────────────────────────────
if st.session_state.log:
    with st.expander("📋 Execution log", expanded=False):
        st.text_area("", "\n".join(st.session_state.log), height=220, label_visibility="collapsed")

# ── Results ─────────────────────────────────────────────────────────────────
result = st.session_state.result
if result:
    st.header("3. Results")

    slides = result.get("slides", [])
    st.subheader(f"Slides processed: {len(slides)}")

    for slide_info in slides:
        idx = slide_info["index"]
        diagrams = slide_info.get("diagrams", [])
        label = f"Slide {idx + 1} — {len(diagrams)} diagram(s) detected"
        with st.expander(label, expanded=(len(diagrams) > 0)):
            if diagrams:
                for d in diagrams:
                    st.markdown(f"- **{d['type']}** — {d['description']}")
                    if d.get("preview_png"):
                        st.image(d["preview_png"], caption=f"Reconstructed diagram {d['index']}", use_container_width=True)
            else:
                st.info("No diagrams detected on this slide.")

    st.header("4. Download")
    dcol1, dcol2, dcol3 = st.columns(3)

    pptx_out = result.get("pptx_out")
    if pptx_out and Path(pptx_out).exists():
        with open(pptx_out, "rb") as f:
            dcol1.download_button("⬇ Download PPTX", f, file_name="reconstructed.pptx",
                                  mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                  use_container_width=True)

    svg_out = result.get("svg_out")
    if svg_out and Path(svg_out).exists():
        with open(svg_out, "rb") as f:
            dcol2.download_button("⬇ Download SVG", f, file_name="diagram.svg",
                                  mime="image/svg+xml", use_container_width=True)

    png_out = result.get("png_out")
    if png_out and Path(png_out).exists():
        with open(png_out, "rb") as f:
            dcol3.download_button("⬇ Download PNG", f, file_name="diagram.png",
                                  mime="image/png", use_container_width=True)

    # ── GitHub push ─────────────────────────────────────────────────────────
    st.header("5. Push to GitHub")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    repo_url = st.text_input(
        "GitHub repository URL",
        value="https://github.com/fa78383012731al-collab/background1",
        help="The full HTTPS URL of your GitHub repository",
    )

    if st.button("🚀 Push to GitHub", use_container_width=False):
        if not github_token:
            st.error("GITHUB_TOKEN secret not set.")
        else:
            with st.spinner("Pushing…"):
                ok, msg = push_to_github(
                    repo_url=repo_url,
                    token=github_token,
                    files_to_push=[
                        pptx_out,
                        svg_out,
                        png_out,
                        "app.py",
                        "processor.py",
                        "rebuild_diagram.py",
                        "export_svg.py",
                        "export_png.py",
                        "requirements.txt",
                        "README.md",
                        ".gitignore",
                        "Dockerfile",
                    ],
                    output_dir=str(OUTPUT_DIR),
                )
            if ok:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
