"""
tests/test_processor.py — Basic smoke tests.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image


def _make_simple_diagram_image() -> Image.Image:
    """Create a synthetic image that looks like a diagram."""
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 150, 130], fill=(100, 149, 237), outline=(0, 0, 0))
    draw.ellipse([200, 50, 320, 130], fill=(255, 165, 0), outline=(0, 0, 0))
    draw.line([150, 90, 200, 90], fill=(0, 0, 0), width=2)
    draw.text((70, 85), "Step 1", fill=(0, 0, 0))
    draw.text((225, 85), "Step 2", fill=(0, 0, 0))
    return img


def test_is_diagram_image():
    from processor import _is_diagram_image
    img = _make_simple_diagram_image()
    is_diag, reason = _is_diagram_image(img)
    assert isinstance(is_diag, bool), "Should return bool"
    # The synthetic image has moderate content — should be flagged as diagram
    assert is_diag, f"Expected diagram detection, got False. Reason: {reason}"


def test_classify_diagram_type():
    from processor import _classify_diagram_type
    img = _make_simple_diagram_image()
    t = _classify_diagram_type(img)
    assert isinstance(t, str) and len(t) > 0


def test_detect_shapes():
    from rebuild_diagram import _detect_shapes
    img = _make_simple_diagram_image()
    shapes = _detect_shapes(img)
    assert isinstance(shapes, list)
    # Should detect at least one shape
    assert len(shapes) >= 1, f"Expected shapes, got {shapes}"


def test_dominant_colors():
    from rebuild_diagram import _dominant_colors
    img = _make_simple_diagram_image()
    colors = _dominant_colors(img, k=3)
    assert len(colors) == 3
    for c in colors:
        assert len(c) == 3


def test_make_preview(tmp_path):
    from rebuild_diagram import _make_preview
    img = _make_simple_diagram_image()
    shapes = [{"kind": "rect", "x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3, "fill": (100, 149, 237)}]
    words = [{"text": "Hello", "x": 60, "y": 80, "w": 50, "h": 20}]
    out = _make_preview(img, shapes, words, 0, str(tmp_path))
    assert Path(out).exists()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
