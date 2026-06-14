"""
run_pipeline.py — Run the full PPTX processing pipeline inside GitHub Actions.
"""
import argparse, os, sys, json
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from processor import process_pptx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

def update_job(job_id: str, data: dict):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs?id=eq.{job_id}",
        headers=HEADERS, json=data,
    )
    print(f"  Job update {list(data.keys())}: HTTP {r.status_code}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    args = ap.parse_args()

    work_dir    = Path(f"work/{args.job_id}")
    input_pptx  = work_dir / "input.pptx"
    output_dir  = work_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_pptx.exists():
        update_job(args.job_id, {"status": "error",
                                 "log": "Input PPTX not found."})
        sys.exit(1)

    logs = []
    def log_cb(msg: str, pct: int | None = None):
        logs.append(msg)
        print(msg)
        upd = {"log": "\n".join(logs[-20:])}
        if pct is not None:
            upd["progress"] = 15 + int(pct * 0.7)   # map 0-100 → 15-85
        update_job(args.job_id, upd)

    try:
        result = process_pptx(str(input_pptx), str(output_dir), log_cb)
        # Write result manifest for upload step
        manifest = {
            "pptx_out":      result.get("pptx_out"),
            "svg_out":       result.get("svg_out"),
            "png_out":       result.get("png_out"),
            "diagram_count": result.get("diagram_count", 0),
            "slide_count":   len(result.get("slides", [])),
            "previews": [
                {
                    "slide":       s["index"] + 1,
                    "type":        d.get("type", ""),
                    "description": d.get("description", ""),
                    "preview_png": d.get("preview_png"),
                }
                for s in result.get("slides", [])
                for d in s.get("diagrams", [])
            ],
        }
        (work_dir / "manifest.json").write_text(
            __import__("json").dumps(manifest, indent=2, default=str)
        )
        update_job(args.job_id, {
            "progress": 85,
            "log": f"Processing done. {manifest['diagram_count']} diagram(s) reconstructed.",
        })
        print("Pipeline complete ✅")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        update_job(args.job_id, {"status": "error", "log": f"ERROR: {e}\n{tb[:500]}"})
        sys.exit(1)
