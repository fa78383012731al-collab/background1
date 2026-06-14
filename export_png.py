"""
export_png.py — Export a high-resolution transparent PNG of the reconstructed diagram.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from PIL import Image


def export_slide_to_png(diag_info: dict, output_dir: str) -> str | None:
    """
    Copy / up-scale the preview PNG and save as diagram.png.
    Preserves transparency (RGBA).
    """
    png_path = diag_info.get("preview_png")
    if not png_path or not Path(png_path).exists():
        return None

    img = Image.open(png_path).convert("RGBA")

    # Up-scale to at least 1200px wide for high-DPI quality
    w, h = img.size
    if w < 1200:
        scale = 1200 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    out_path = str(Path(output_dir) / "diagram.png")
    img.save(out_path, format="PNG", dpi=(300, 300))
    return out_path
