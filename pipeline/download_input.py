"""
download_input.py — Download PPTX from Supabase Storage and update job status.
"""
import argparse, os, sys, json
from pathlib import Path
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

def update_job(job_id: str, data: dict):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/jobs?id=eq.{job_id}",
        headers={**HEADERS, "Prefer": "return=minimal"},
        json=data,
    )
    print(f"Job update {data}: HTTP {r.status_code}")

def download_file(file_path: str, dest: Path):
    url = f"{SUPABASE_URL}/storage/v1/object/pptx-inputs/{file_path}"
    r = requests.get(url, headers=HEADERS, stream=True)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Downloaded {file_path} → {dest}  ({dest.stat().st_size} bytes)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id",    required=True)
    ap.add_argument("--file-path", required=True)
    args = ap.parse_args()

    update_job(args.job_id, {"status": "processing", "progress": 5,
                             "log": "Downloading PPTX from storage…"})

    dest = Path(f"work/{args.job_id}/input.pptx")
    try:
        download_file(args.file_path, dest)
        update_job(args.job_id, {"status": "processing", "progress": 15,
                                 "log": "PPTX downloaded. Starting analysis…"})
    except Exception as e:
        update_job(args.job_id, {"status": "error", "log": str(e)})
        sys.exit(1)
