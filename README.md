# PPTX Diagram Reconstructor

A professional web application that analyses PowerPoint presentations, detects embedded diagrams, and reconstructs them as fully-editable vector shapes inside a new PPTX file.

## Features

- Upload `.pptx` files via a clean web interface
- Detect diagrams, flowcharts, infographics, and process charts inside slides
- Reconstruct them as native PowerPoint shapes (rectangles, ovals, connectors, text boxes)
- OCR support for Arabic and English text inside images
- Export to **PPTX**, **SVG**, and **PNG**
- One-click push to GitHub

## Installation

```bash
pip install -r requirements.txt
# Also install Tesseract OCR (system):
# Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-ara
# macOS:         brew install tesseract tesseract-lang
```

## Running

```bash
streamlit run app.py --server.port 5000
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Usage

1. **Upload** — drag & drop or browse for a `.pptx` file.
2. **Start Analysis** — the system parses each slide, detects diagrams, and reconstructs them.
3. **Download** — grab the new `reconstructed.pptx`, `diagram.svg`, or `diagram.png`.
4. **Push to GitHub** — enter your repo URL and click **Push to GitHub**.

## Environment Variables

| Variable | Purpose |
|---|---|
| `GITHUB_TOKEN` | Personal Access Token for GitHub push |

## Project Structure

```
app.py              — Streamlit web interface
processor.py        — PPTX parsing, detection orchestration
rebuild_diagram.py  — Editable shape reconstruction
export_svg.py       — SVG export
export_png.py       — High-DPI PNG export
github_push.py      — GitHub REST API push
requirements.txt
Dockerfile
tests/
```

## GitHub Push

Requires a GitHub Personal Access Token with `repo` scope stored as the `GITHUB_TOKEN` environment variable.

## Docker

```bash
docker build -t pptx-reconstructor .
docker run -p 5000:5000 -e GITHUB_TOKEN=your_token pptx-reconstructor
```

## Arabic Support

Arabic text is automatically reshaped and displayed right-to-left using `arabic-reshaper` and `python-bidi`. Tesseract's Arabic language pack (`ara`) must be installed for OCR.

## License

MIT
