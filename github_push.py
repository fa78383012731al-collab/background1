"""
github_push.py — Push output files to a GitHub repository using the REST API.
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import requests


def _parse_repo(repo_url: str) -> tuple[str, str] | None:
    """Extract owner/repo from an HTTPS GitHub URL."""
    match = re.search(r"github\.com[:/]([^/]+)/([^/.\s]+?)(?:\.git)?$", repo_url)
    if match:
        return match.group(1), match.group(2)
    return None


def _get_file_sha(session: requests.Session, owner: str, repo: str, path: str) -> str | None:
    """Return the blob SHA of a file if it exists (needed for updates)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    r = session.get(url)
    if r.status_code == 200:
        return r.json().get("sha")
    return None


def push_to_github(
    repo_url: str,
    token: str,
    files_to_push: list[str | None],
    output_dir: str,
    branch: str = "main",
) -> tuple[bool, str]:
    """
    Push a list of local files to a GitHub repository.
    Returns (success, message).
    """
    parsed = _parse_repo(repo_url)
    if not parsed:
        return False, f"Cannot parse repository URL: {repo_url}"

    owner, repo = parsed

    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    })

    # Verify token / repo access
    r = session.get(f"https://api.github.com/repos/{owner}/{repo}")
    if r.status_code == 404:
        return False, f"Repository not found or no access: {owner}/{repo}"
    if r.status_code == 401:
        return False, "GitHub token is invalid or expired."

    pushed = []
    failed = []

    for file_path in files_to_push:
        if not file_path:
            continue
        local = Path(file_path)
        if not local.exists():
            # Try relative to current dir
            local = Path(output_dir) / local.name
        if not local.exists():
            failed.append(str(file_path))
            continue

        remote_name = local.name
        try:
            content = local.read_bytes()
        except Exception as exc:
            failed.append(f"{local.name} ({exc})")
            continue

        encoded = base64.b64encode(content).decode()
        sha = _get_file_sha(session, owner, repo, remote_name)

        payload: dict = {
            "message": f"chore: update {remote_name} via PPTX Reconstructor",
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{remote_name}"
        r = session.put(url, json=payload)
        if r.status_code in (200, 201):
            pushed.append(remote_name)
        else:
            failed.append(f"{remote_name} (HTTP {r.status_code}: {r.text[:120]})")

    if not pushed and failed:
        return False, f"All uploads failed: {', '.join(failed)}"

    msg = f"Pushed {len(pushed)} file(s) to {owner}/{repo}."
    if failed:
        msg += f" Failed: {', '.join(failed)}"
    return True, msg
