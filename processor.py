"""
processor.py — Parse PPTX, detect diagrams, orchestrate reconstruction.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Callable

from pptx import Presentation
from pptx.util import Inches, Pt
from PIL import Image

from rebuild_diagram import rebuild_diagram_on_slide
from export_svg import export_slide_to_svg
from export_png import export_slide_to_png


# ── Diagram-detection heuristics ────────────────────────────────────────────

def _is_diagram_image(img: Image.Image) -> tuple[bool, str]:
    """
    Simple heuristic: diagrams tend to have:
      - High colour variation (not photos) OR very limited palette (icons/charts)
      - Significant non-white pixel density without being a photo
    Returns (is_diagram, description).
    """
    img_rgb = img.convert("RGB")
    w, h = img_rgb.size
    if w < 50 or h < 50:
        return False, "too small"

    pixels = list(img_rgb.getdata())
    total = len(pixels)

    non_white = sum(1 for r, g, b in pixels if not (r > 230 and g > 230 and b > 230))
    non_white_ratio = non_white / total

    # Count unique colours (sample)
    sampled = pixels[::max(1, total // 2000)]
    unique_colours = len(set(sampled))

    # Diagrams: moderate non-white content, limited colour palette
    if 0.05 < non_white_ratio < 0.85 and unique_colours < 800:
        return True, f"diagram-like ({non_white_ratio:.0%} content, {unique_colours} colours)"
    if non_white_ratio < 0.05:
        return False, "mostly blank"
    return False, f"likely photo ({unique_colours} colours)"


def _extract_images_from_slide(slide) -> list[dict]:
    """Return list of dicts with image data from a slide's shapes."""
    images = []
    for shape in slide.shapes:
        if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
            try:
                blob = shape.image.blob
                img = Image.open(io.BytesIO(blob))
                images.append({
                    "shape": shape,
                    "image": img,
                    "left": shape.left,
                    "top": shape.top,
                    "width": shape.width,
                    "height": shape.height,
                })
            except Exception:
                pass
    return images


def _classify_diagram_type(img: Image.Image) -> str:
    """Rough classifier based on aspect ratio and colour patterns."""
    w, h = img.size
    ratio = w / h if h else 1

    img_rgb = img.convert("RGB")
    pixels = list(img_rgb.getdata())[::max(1, len(list(img_rgb.getdata())) // 500)]
    unique = len(set(pixels))

    if unique < 20:
        return "Flowchart / SmartArt"
    if ratio > 1.8:
        return "Process Chart"
    if ratio < 0.6:
        return "Vertical Diagram"
    if unique < 100:
        return "Infographic"
    return "Generic Diagram"


# ── Main processor ───────────────────────────────────────────────────────────

def process_pptx(
    pptx_path: str,
    output_dir: str,
    log: Callable[[str, int], None] | None = None,
) -> dict:
    """
    Full pipeline: parse → detect → reconstruct → export.
    Returns a result dict consumed by app.py.
    """
    def _log(msg: str, pct: int | None = None):
        if log:
            log(msg, pct)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log("Opening PPTX file…", 5)
    prs = Presentation(pptx_path)
    slides = prs.slides
    n_slides = len(slides)
    _log(f"Found {n_slides} slide(s).", 10)

    slide_results = []
    all_diagram_count = 0

    for idx, slide in enumerate(slides):
        pct_start = 10 + int(70 * idx / max(n_slides, 1))
        _log(f"Processing slide {idx + 1}/{n_slides}…", pct_start)

        images = _extract_images_from_slide(slide)
        diagram_list = []

        for img_data in images:
            img = img_data["image"]
            is_diag, reason = _is_diagram_image(img)
            if not is_diag:
                _log(f"  Slide {idx+1}: image skipped ({reason})")
                continue

            diag_type = _classify_diagram_type(img)
            _log(f"  Slide {idx+1}: {diag_type} detected — {reason}")

            # Reconstruct
            diag_info = rebuild_diagram_on_slide(
                slide=slide,
                img_data=img_data,
                diagram_type=diag_type,
                diagram_index=all_diagram_count,
                output_dir=str(output_dir),
            )
            diag_info["type"] = diag_type
            diag_info["description"] = reason
            diag_info["index"] = all_diagram_count
            diagram_list.append(diag_info)
            all_diagram_count += 1

        slide_results.append({"index": idx, "diagrams": diagram_list})

    # Save reconstructed PPTX
    pptx_out = str(output_dir / "reconstructed.pptx")
    _log("Saving reconstructed PPTX…", 82)
    prs.save(pptx_out)

    # Export combined SVG / PNG for first diagram found
    svg_out = png_out = None
    first_diag = next(
        (d for s in slide_results for d in s["diagrams"]), None
    )
    if first_diag and first_diag.get("preview_png"):
        _log("Exporting SVG…", 88)
        svg_out = export_slide_to_svg(first_diag, str(output_dir))
        _log("Exporting PNG…", 93)
        png_out = export_slide_to_png(first_diag, str(output_dir))

    _log("All done.", 98)

    return {
        "slides": slide_results,
        "pptx_out": pptx_out,
        "svg_out": svg_out,
        "png_out": png_out,
        "diagram_count": all_diagram_count,
    }
