"""
server.py — Flask web server: serves HTML frontend + REST API for PPTX processing.
"""
import os
import uuid
import threading
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from processor import process_pptx
from github_push import push_to_github

BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
CORS(app)

# ── In-memory job registry ────────────────────────────────────────────────────
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _update_job(job_id: str, **kwargs):
    with JOBS_LOCK:
        JOBS[job_id].update(kwargs)


def _run_job(job_id: str, pptx_path: str):
    """Worker thread: run the full pipeline and update job state."""
    logs = []

    def log_cb(msg: str, pct: int | None = None):
        logs.append(msg)
        update = {"logs": list(logs)}
        if pct is not None:
            update["progress"] = pct
        _update_job(job_id, **update)

    try:
        result = process_pptx(pptx_path, str(OUTPUT_DIR), log_cb)
        _update_job(
            job_id,
            status="done",
            progress=100,
            result=result,
            logs=list(logs),
        )
    except Exception as exc:
        tb = traceback.format_exc()
        logs.append(f"ERROR: {exc}")
        _update_job(job_id, status="error", error=str(exc), traceback=tb, logs=list(logs))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".pptx"):
        return jsonify({"error": "Only .pptx files accepted"}), 400

    filename  = secure_filename(f.filename)
    job_id    = uuid.uuid4().hex
    save_path = str(UPLOAD_DIR / f"{job_id}_{filename}")
    f.save(save_path)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "status":   "uploaded",
            "filename": filename,
            "path":     save_path,
            "progress": 0,
            "logs":     [],
            "result":   None,
            "error":    None,
        }

    return jsonify({"job_id": job_id, "filename": filename})


@app.route("/api/process/<job_id>", methods=["POST"])
def process(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] == "running":
        return jsonify({"error": "Already running"}), 409

    _update_job(job_id, status="running", progress=0, logs=[], error=None, result=None)
    t = threading.Thread(target=_run_job, args=(job_id, job["path"]), daemon=True)
    t.start()
    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/status/<job_id>")
def status(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    result = job.get("result") or {}
    downloads = {}
    if result.get("pptx_out") and Path(result["pptx_out"]).exists():
        downloads["pptx"] = f"/api/download/{Path(result['pptx_out']).name}"
    if result.get("svg_out") and Path(result["svg_out"]).exists():
        downloads["svg"]  = f"/api/download/{Path(result['svg_out']).name}"
    if result.get("png_out") and Path(result["png_out"]).exists():
        downloads["png"]  = f"/api/download/{Path(result['png_out']).name}"

    # Preview thumbnails
    slides = result.get("slides", [])
    previews = []
    for s in slides:
        for d in s.get("diagrams", []):
            p = d.get("preview_png")
            if p and Path(p).exists():
                previews.append({
                    "slide":       s["index"] + 1,
                    "type":        d.get("type",""),
                    "description": d.get("description",""),
                    "url":         f"/api/download/{Path(p).name}",
                })

    return jsonify({
        "job_id":         job_id,
        "status":         job["status"],
        "progress":       job.get("progress", 0),
        "logs":           job.get("logs", []),
        "error":          job.get("error"),
        "downloads":      downloads,
        "previews":       previews,
        "diagram_count":  result.get("diagram_count", 0),
        "slide_count":    len(slides),
    })


@app.route("/api/download/<filename>")
def download(filename: str):
    safe = Path(filename).name
    for folder in [OUTPUT_DIR, UPLOAD_DIR]:
        candidate = folder / safe
        if candidate.exists():
            return send_file(str(candidate), as_attachment=True)
    return jsonify({"error": "File not found"}), 404


@app.route("/api/github-push/<job_id>", methods=["POST"])
def github_push(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "Job not done or not found"}), 400

    body     = request.get_json(silent=True) or {}
    repo_url = body.get("repo_url", "https://github.com/fa78383012731al-collab/background1")
    token    = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return jsonify({"error": "GITHUB_TOKEN not set"}), 500

    result = job.get("result") or {}
    files  = [
        result.get("pptx_out"),
        result.get("svg_out"),
        result.get("png_out"),
        str(BASE_DIR / "server.py"),
        str(BASE_DIR / "processor.py"),
        str(BASE_DIR / "rebuild_diagram.py"),
        str(BASE_DIR / "export_svg.py"),
        str(BASE_DIR / "export_png.py"),
        str(BASE_DIR / "github_push.py"),
        str(BASE_DIR / "requirements.txt"),
        str(BASE_DIR / "README.md"),
        str(BASE_DIR / ".gitignore"),
        str(BASE_DIR / "Dockerfile"),
        str(BASE_DIR / "static" / "index.html"),
        str(BASE_DIR / "static" / "styles.css"),
        str(BASE_DIR / "static" / "app.js"),
    ]

    ok, msg = push_to_github(repo_url, token, files, str(OUTPUT_DIR))
    return jsonify({"success": ok, "message": msg})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
