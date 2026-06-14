"""
upload_results.py — Upload output files to Supabase Storage and mark job done.
"""
import argparse, os, sys, json, mimetypes
from pathlib import Path
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]
HEADERS_JSON = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

def update_job(job_id: str, data: dict):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs?id=eq.{job_id}",
        headers=HEADERS_JSON, json=data,
    )
    print(f"  Job update {list(data.keys())}: HTTP {r.status_code}")

def upload_file(job_id: str, local_path: Path) -> str | None:
    """Upload file to pptx-outputs bucket. Returns public URL."""
    if not local_path or not local_path.exists():
        return None
    remote = f"{job_id}/{local_path.name}"
    mime   = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
    url    = f"{SUPABASE_URL}/storage/v1/object/pptx-outputs/{remote}"
    with open(local_path, "rb") as f:
        r = requests.post(
            url,
            headers={
                "apikey":        SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
                "Content-Type":  mime,
                "x-upsert":      "true",
            },
            data=f,
        )
    if r.status_code in (200, 201):
        public_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/pptx-outputs/{remote}"
        )
        print(f"  ✅ Uploaded {local_path.name} → {public_url}")
        return public_url
    print(f"  ❌ Upload failed {local_path.name}: HTTP {r.status_code} {r.text[:200]}")
    return None

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    args = ap.parse_args()

    work_dir     = Path(f"work/{args.job_id}")
    manifest_f   = work_dir / "manifest.json"

    if not manifest_f.exists():
        update_job(args.job_id, {"status": "error",
                                 "log": "manifest.json not found"})
        sys.exit(1)

    manifest = json.loads(manifest_f.read_text())

    urls = {}
    for key in ("pptx_out", "svg_out", "png_out"):
        p = manifest.get(key)
        if p:
            u = upload_file(args.job_id, Path(p))
            if u:
                urls[key] = u

    # Upload preview PNGs
    previews_with_urls = []
    for prev in manifest.get("previews", []):
        p = prev.get("preview_png")
        u = upload_file(args.job_id, Path(p)) if p else None
        previews_with_urls.append({**prev, "url": u})

    # Final job update
    update_job(args.job_id, {
        "status":        "done",
        "progress":      100,
        "log":           "All outputs uploaded to Supabase Storage ✅",
        "result_pptx":   urls.get("pptx_out"),
        "result_svg":    urls.get("svg_out"),
        "result_png":    urls.get("png_out"),
        "result_previews": json.dumps(previews_with_urls),
        "diagram_count": manifest.get("diagram_count", 0),
        "slide_count":   manifest.get("slide_count", 0),
    })
    print("Upload step complete ✅")
