"""
rebuild_diagram.py — Reconstruct detected diagrams as editable PowerPoint shapes.

Strategy:
  1. Run OCR on the image to extract text blocks.
  2. Detect dominant shapes via OpenCV contour analysis.
  3. Re-create the diagram using python-pptx primitives:
       - Rectangles / rounded rectangles for boxes
       - Ovals for circles
       - Connectors / lines for arrows
       - TextBoxes for labels
  4. Remove (hide) the original flat image from the slide.
  5. Save a PNG preview of the reconstructed region.
"""
from __future__ import annotations

import io
import math
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import pytesseract
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display as bidi_display
    _ARABIC_AVAILABLE = True
except ImportError:
    _ARABIC_AVAILABLE = False

from pptx import Presentation
from pptx.util import Emu, Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _fix_arabic(text: str) -> str:
    if not _ARABIC_AVAILABLE:
        return text
    reshaped = arabic_reshaper.reshape(text)
    return bidi_display(reshaped)


def _dominant_colors(img: Image.Image, k: int = 5) -> list[tuple[int, int, int]]:
    """K-means dominant colours from the image."""
    data = np.array(img.convert("RGB")).reshape(-1, 3).astype(np.float32)
    if len(data) < k:
        return [(70, 130, 180)]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(data, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)
    counts = np.bincount(labels.flatten())
    sorted_colors = [centers[i] for i in np.argsort(-counts)]
    return [(int(c[0]), int(c[1]), int(c[2])) for c in sorted_colors]


def _ocr_image(img: Image.Image) -> list[dict]:
    """Run Tesseract OCR and return word bounding boxes."""
    if not _OCR_AVAILABLE:
        return []
    try:
        data = pytesseract.image_to_data(
            img, output_type=pytesseract.Output.DICT,
            config="--psm 11 -l ara+eng"
        )
        words = []
        for i, word in enumerate(data["text"]):
            word = word.strip()
            if not word or data["conf"][i] < 30:
                continue
            words.append({
                "text": _fix_arabic(word),
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
            })
        return words
    except Exception:
        return []


def _detect_shapes(img: Image.Image) -> list[dict]:
    """
    Use OpenCV to detect contours → classify as rectangle, circle, or line.
    Returns list of shape dicts with normalised coords (0-1).
    """
    cv_img = _pil_to_cv(img)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    ih, iw = cv_img.shape[:2]
    shapes = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < (iw * ih * 0.002):   # skip tiny blobs
            continue

        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        x, y, w, h = cv2.boundingRect(cnt)

        # Normalise to 0-1
        nx, ny, nw, nh = x / iw, y / ih, w / iw, h / ih

        # Circularity
        circularity = 4 * math.pi * area / (peri ** 2 + 1e-6)

        if circularity > 0.75:
            kind = "oval"
        elif len(approx) <= 6:
            kind = "rect"
        else:
            kind = "line"

        # Sample fill colour from centre
        cx, cy = x + w // 2, y + h // 2
        cx = min(cx, iw - 1)
        cy = min(cy, ih - 1)
        bgr = cv_img[cy, cx].tolist()
        fill = (bgr[2], bgr[1], bgr[0])  # RGB

        shapes.append({
            "kind": kind,
            "x": nx, "y": ny, "w": nw, "h": nh,
            "fill": fill,
        })

    return shapes


# ── Main rebuild function ─────────────────────────────────────────────────────

def rebuild_diagram_on_slide(
    slide,
    img_data: dict,
    diagram_type: str,
    diagram_index: int,
    output_dir: str,
) -> dict:
    """
    Replace the flat image shape on *slide* with editable PowerPoint shapes.
    Returns a dict with 'preview_png' path.
    """
    shape = img_data["shape"]
    img: Image.Image = img_data["image"]
    left = img_data["left"]
    top = img_data["top"]
    width = img_data["width"]
    height = img_data["height"]

    # ── 1. Extract information ───────────────────────────────────────────────
    ocr_words = _ocr_image(img)
    detected_shapes = _detect_shapes(img)
    colors = _dominant_colors(img)

    accent = colors[1] if len(colors) > 1 else (70, 130, 180)
    # Make sure accent isn't near-white
    if sum(accent) > 650:
        accent = (70, 130, 180)

    # ── 2. Remove original image shape ──────────────────────────────────────
    sp = shape._element
    sp.getparent().remove(sp)

    # ── 3. Add reconstructed shapes ─────────────────────────────────────────
    slide_shapes = slide.shapes

    if not detected_shapes:
        # Fallback: draw a single placeholder box with OCR text
        detected_shapes = [{"kind": "rect", "x": 0, "y": 0, "w": 1, "h": 1,
                            "fill": (255, 255, 255)}]

    added = []
    for s in detected_shapes[:30]:  # cap at 30 shapes
        el = Emu(left + int(s["x"] * width))
        et = Emu(top + int(s["y"] * height))
        ew = Emu(max(int(s["w"] * width), 914400 // 10))   # min ~0.1 inch
        eh = Emu(max(int(s["h"] * height), 914400 // 10))

        fill_rgb = RGBColor(*s["fill"])

        if s["kind"] == "oval":
            new_shape = slide_shapes.add_shape(
                9,  # MSO_SHAPE_TYPE oval
                el, et, ew, eh
            )
        else:
            new_shape = slide_shapes.add_shape(
                1,  # rectangle
                el, et, ew, eh
            )

        # Style
        new_shape.fill.solid()
        new_shape.fill.fore_color.rgb = fill_rgb
        new_shape.line.color.rgb = RGBColor(*accent)
        new_shape.line.width = Pt(1.5)
        added.append(new_shape)

    # ── 4. Add OCR text boxes ────────────────────────────────────────────────
    for word in ocr_words[:60]:
        # Map pixel coords to EMU relative to shape position
        px_scale_x = width / img.width
        px_scale_y = height / img.height
        tx = Emu(left + int(word["x"] * px_scale_x))
        ty = Emu(top + int(word["y"] * px_scale_y))
        tw = Emu(max(int(word["w"] * px_scale_x), 914400 // 5))
        th = Emu(max(int(word["h"] * px_scale_y), 914400 // 10))

        txb = slide_shapes.add_textbox(tx, ty, tw, th)
        tf = txb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = word["text"]
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(30, 30, 30)
        p.alignment = PP_ALIGN.RIGHT  # default RTL-friendly

    # ── 5. Generate PNG preview ──────────────────────────────────────────────
    preview_path = _make_preview(img, detected_shapes, ocr_words, diagram_index, output_dir)

    return {"preview_png": preview_path}


def _make_preview(
    original: Image.Image,
    shapes: list[dict],
    words: list[dict],
    idx: int,
    output_dir: str,
) -> str:
    """Draw a clean preview PNG showing the reconstructed layout."""
    w, h = original.size
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")

    for s in shapes[:30]:
        x0 = int(s["x"] * w)
        y0 = int(s["y"] * h)
        x1 = x0 + int(s["w"] * w)
        y1 = y0 + int(s["h"] * h)
        fill = (*s["fill"], 180)
        outline = (50, 50, 50, 255)
        if s["kind"] == "oval":
            draw.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=2)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=2)

    for word in words[:60]:
        draw.text((word["x"] + 2, word["y"] + 2), word["text"],
                  fill=(20, 20, 20, 255))

    out_path = str(Path(output_dir) / f"preview_diagram_{idx}.png")
    canvas.save(out_path)
    return out_path
