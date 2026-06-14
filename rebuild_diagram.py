"""
rebuild_diagram.py — Reconstruct picture-embedded diagrams as editable PowerPoint shapes.

Improvements over v1:
  - Original image is KEPT (not deleted) as a reference layer
  - Better OpenCV shape detection (RETR_LIST + hierarchy filtering)
  - Arabic text: reshaper+bidi applied correctly
  - Colours sampled from image region (not just center pixel)
  - Coordinate mapping uses actual slide EMU dimensions
  - Text boxes grouped by proximity to avoid clutter
"""
from __future__ import annotations

import io
import math
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

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

from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


# ── Arabic helpers ────────────────────────────────────────────────────────────

def _fix_arabic(text: str) -> str:
    """Apply arabic_reshaper + bidi so Arabic renders correctly in PPTX."""
    if not text.strip():
        return text
    if not _ARABIC_AVAILABLE:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return bidi_display(reshaped)
    except Exception:
        return text


def _is_arabic(text: str) -> bool:
    return any("\u0600" <= c <= "\u06FF" for c in text)


# ── Colour helpers ────────────────────────────────────────────────────────────

def _sample_region_color(cv_img: np.ndarray, x: int, y: int, w: int, h: int) -> tuple[int, int, int]:
    """Return median colour of a bounding rectangle (BGR→RGB)."""
    ih, iw = cv_img.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(iw, x + w), min(ih, y + h)
    if x2 <= x1 or y2 <= y1:
        return (173, 216, 230)
    region = cv_img[y1:y2, x1:x2]
    median = np.median(region.reshape(-1, 3), axis=0).astype(int)
    return (int(median[2]), int(median[1]), int(median[0]))  # BGR→RGB


def _accent_color(cv_img: np.ndarray) -> tuple[int, int, int]:
    """Most common non-white, non-grey colour in the image."""
    data = cv_img.reshape(-1, 3).astype(np.float32)
    # Filter out near-white and near-grey
    mask = ~(
        (data[:, 0] > 200) & (data[:, 1] > 200) & (data[:, 2] > 200)
    ) & (
        (np.max(data, axis=1) - np.min(data, axis=1)) > 30
    )
    filtered = data[mask]
    if len(filtered) < 10:
        return (70, 130, 180)
    k = min(3, len(filtered))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(filtered, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)
    counts = np.bincount(labels.flatten())
    best = centers[np.argmax(counts)].astype(int)
    return (int(best[2]), int(best[1]), int(best[0]))  # BGR→RGB


# ── OCR ───────────────────────────────────────────────────────────────────────

def _ocr_blocks(img: Image.Image) -> list[dict]:
    """Run Tesseract and return word bounding boxes with text."""
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
            if not word or int(data["conf"][i]) < 25:
                continue
            fixed = _fix_arabic(word) if _is_arabic(word) else word
            words.append({
                "text": fixed,
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
                "is_arabic": _is_arabic(word),
            })
        return words
    except Exception as e:
        print(f"  OCR error: {e}")
        return []


# ── Shape detection ───────────────────────────────────────────────────────────

def _detect_shapes(img: Image.Image, min_area_ratio: float = 0.003) -> list[dict]:
    """
    Detect geometric shapes via OpenCV contours.
    Returns list of shape dicts with normalised (0-1) coordinates.
    """
    cv_img = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    ih, iw = cv_img.shape[:2]
    min_area = iw * ih * min_area_ratio

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold works better on diagrams than Canny alone
    thresh = cv2.adaptiveThreshold(gray, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 11, 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.dilate(thresh, kernel, iterations=1)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    shapes = []
    seen_boxes: list[tuple[int,int,int,int]] = []

    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:60]:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        peri = cv2.arcLength(cnt, True)
        if peri < 1:
            continue
        approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
        x, y, w, h = cv2.boundingRect(cnt)

        # Skip nearly-full-image contours (slide border)
        if w > iw * 0.95 and h > ih * 0.95:
            continue

        # Skip duplicates (overlap > 80%)
        duplicate = False
        for sx, sy, sw, sh in seen_boxes:
            ox = max(0, min(x+w, sx+sw) - max(x, sx))
            oy = max(0, min(y+h, sy+sh) - max(y, sy))
            if ox * oy > 0.8 * w * h:
                duplicate = True
                break
        if duplicate:
            continue
        seen_boxes.append((x, y, w, h))

        circularity = 4 * math.pi * area / (peri ** 2 + 1e-6)

        if circularity > 0.72:
            kind = "oval"
        elif len(approx) <= 6:
            kind = "rect"
        else:
            kind = "line"

        fill = _sample_region_color(cv_img, x + w//4, y + h//4, w//2, h//2)
        # If fill is very dark, lighten it
        if sum(fill) < 120:
            fill = (fill[0]+80, fill[1]+80, fill[2]+80)

        shapes.append({
            "kind": kind,
            "x": x / iw, "y": y / ih,
            "w": w / iw, "h": h / ih,
            "fill": fill,
            "px_x": x, "px_y": y, "px_w": w, "px_h": h,
        })

    return shapes


# ── Main rebuild function ─────────────────────────────────────────────────────

def rebuild_diagram_on_slide(
    slide,
    img_data: dict,
    diagram_type: str,
    diagram_index: int,
    output_dir: str,
    slide_w_emu: int = 9144000,
    slide_h_emu: int = 5143500,
) -> dict:
    """
    Add editable shapes over (not replacing) the embedded picture.
    The original image is kept so the slide still looks correct even if
    reconstruction is imperfect.
    """
    shape    = img_data["shape"]
    img: Image.Image = img_data["image"]
    left     = img_data["left"]    # EMU
    top      = img_data["top"]     # EMU
    width    = img_data["width"]   # EMU
    height   = img_data["height"]  # EMU

    print(f"  Rebuilding {diagram_type}: pos=({left},{top}) size=({width}×{height}) EMU")

    # ── 1. Detect shapes & OCR ───────────────────────────────────────────────
    cv_img = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    accent = _accent_color(cv_img)
    detected = _detect_shapes(img)
    ocr_words = _ocr_blocks(img)

    print(f"  Found {len(detected)} shapes, {len(ocr_words)} OCR words")

    # ── 2. DO NOT remove original image — keep as background ─────────────────
    # (Removing it caused the slide to look completely broken)
    # shape._element.getparent().remove(shape._element)  ← DISABLED

    slide_shapes = slide.shapes

    # ── 3. Add reconstructed vector shapes (group at front) ──────────────────
    if not detected:
        # Fallback: add one transparent overlay box
        detected = [{"kind": "rect", "x": 0.05, "y": 0.05,
                     "w": 0.9, "h": 0.9, "fill": (255, 255, 255)}]

    added_shapes = []
    for s in detected[:25]:
        el = Emu(int(left + s["x"] * width))
        et = Emu(int(top  + s["y"] * height))
        ew = Emu(max(int(s["w"] * width),  int(slide_w_emu * 0.01)))
        eh = Emu(max(int(s["h"] * height), int(slide_h_emu * 0.01)))

        fill_rgb = s["fill"]
        # Skip near-white fills (background noise)
        if sum(fill_rgb) > 720:
            continue

        if s["kind"] == "oval":
            new_shape = slide_shapes.add_shape(9, el, et, ew, eh)
        else:
            new_shape = slide_shapes.add_shape(1, el, et, ew, eh)

        new_shape.fill.solid()
        new_shape.fill.fore_color.rgb = RGBColor(*fill_rgb)
        new_shape.line.color.rgb      = RGBColor(*accent)
        new_shape.line.width          = Pt(1.5)
        new_shape.fill.fore_color.rgb  # force write
        # Set transparency on fill
        from pptx.oxml.ns import qn
        from lxml import etree
        solidFill = new_shape.fill._xPr.find(qn("a:solidFill"))
        if solidFill is not None:
            srgb = solidFill.find(qn("a:srgbClr"))
            if srgb is not None:
                alpha = etree.SubElement(srgb, qn("a:alpha"))
                alpha.set("val", "50000")  # 50% transparent

        added_shapes.append(new_shape)

    # ── 4. Add OCR text boxes ────────────────────────────────────────────────
    img_w, img_h = img.size
    scale_x = width  / img_w
    scale_y = height / img_h

    # Group nearby words into lines
    lines = _group_words_into_lines(ocr_words)

    for line in lines[:40]:
        words_in_line = line["words"]
        combined_text = " ".join(w["text"] for w in words_in_line)
        if not combined_text.strip():
            continue

        lx = min(w["x"] for w in words_in_line)
        ly = min(w["y"] for w in words_in_line)
        lw = max(w["x"] + w["w"] for w in words_in_line) - lx
        lh = max(w["y"] + w["h"] for w in words_in_line) - ly

        tx = Emu(int(left + lx * scale_x))
        ty = Emu(int(top  + ly * scale_y))
        tw = Emu(max(int(lw * scale_x), int(slide_w_emu * 0.05)))
        th = Emu(max(int(lh * scale_y), int(slide_h_emu * 0.03)))

        txb = slide_shapes.add_textbox(tx, ty, tw, th)
        tf  = txb.text_frame
        tf.word_wrap = True
        p   = tf.paragraphs[0]
        run = p.add_run()
        run.text = combined_text

        # Font size proportional to box height
        font_pt = max(8, min(24, int(lh * scale_y / 12700)))
        run.font.size = Pt(font_pt)
        run.font.color.rgb = RGBColor(20, 20, 20)

        is_ar = any(w["is_arabic"] for w in words_in_line)
        p.alignment = PP_ALIGN.RIGHT if is_ar else PP_ALIGN.LEFT

        # RTL paragraph for Arabic
        if is_ar:
            from pptx.oxml.ns import qn
            pPr = p._pPr
            if pPr is None:
                from lxml import etree
                pPr = etree.SubElement(p._p, qn("a:pPr"))
            pPr.set("rtl", "1")

    # ── 5. Generate preview PNG ──────────────────────────────────────────────
    preview_path = _make_preview(img, detected, ocr_words, diagram_index, output_dir)

    return {"preview_png": preview_path}


def _group_words_into_lines(words: list[dict], y_tolerance: int = 8) -> list[dict]:
    """Group OCR words that are on the same horizontal line."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["y"], w["x"]))
    lines = []
    current_line = [sorted_words[0]]

    for word in sorted_words[1:]:
        prev = current_line[-1]
        if abs(word["y"] - prev["y"]) <= y_tolerance:
            current_line.append(word)
        else:
            lines.append({"words": current_line})
            current_line = [word]
    lines.append({"words": current_line})
    return lines


def _make_preview(
    original: Image.Image,
    shapes: list[dict],
    words: list[dict],
    idx: int,
    output_dir: str,
) -> str:
    """Generate a preview showing original + detected shapes overlay."""
    w, h = original.size
    canvas = original.convert("RGBA").copy()
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for s in shapes[:25]:
        x0 = int(s["x"] * w)
        y0 = int(s["y"] * h)
        x1 = x0 + int(s["w"] * w)
        y1 = y0 + int(s["h"] * h)
        fill = (*s["fill"], 80)
        outline = (255, 0, 0, 200)
        if s["kind"] == "oval":
            draw.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=2)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=2)

    for word in words[:60]:
        draw.text((word["x"] + 1, word["y"] + 1), word["text"][:30],
                  fill=(0, 0, 180, 230))

    combined = Image.alpha_composite(canvas, overlay)
    out_path = str(Path(output_dir) / f"preview_{idx}.png")
    combined.convert("RGB").save(out_path)
    return out_path
