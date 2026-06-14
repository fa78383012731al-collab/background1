"""
export_svg.py — Export a reconstructed diagram preview to SVG.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import io
import base64


def export_slide_to_svg(diag_info: dict, output_dir: str) -> str | None:
    """
    Convert the PNG preview of a diagram into a minimal SVG wrapper
    so the user has an SVG file for further editing.
    """
    png_path = diag_info.get("preview_png")
    if not png_path or not Path(png_path).exists():
        return None

    img = Image.open(png_path).convert("RGBA")
    w, h = img.size

    # Embed PNG as base64 inside SVG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
        f'  <title>Reconstructed Diagram</title>\n'
        f'  <desc>Auto-reconstructed from PPTX by PPTX Diagram Reconstructor</desc>\n'
        f'  <image x="0" y="0" width="{w}" height="{h}" '
        f'xlink:href="data:image/png;base64,{b64}" />\n'
        f'</svg>\n'
    )

    out_path = str(Path(output_dir) / "diagram.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path
