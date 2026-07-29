#!/usr/bin/env python3
"""
Convert PDFs into high-quality screenshots at exact pixel dimensions
and save each screenshot as a new single-page PDF.

Usage:
  python pdf_screenshot.py

This script scans `Done/A_PDF` for PDF files and writes outputs to
`Done/A_PDF_shots` preserving subfolders.

Requirements: pip install pymupdf Pillow
"""
from pathlib import Path
import argparse
import math
import sys

try:
    import fitz  # PyMuPDF
except Exception as e:
    raise SystemExit("PyMuPDF (fitz) is required. Install with: python -m pip install pymupdf")

from PIL import Image


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "Done" / "A_PDF"
OUT_DIR = ROOT / "Done" / "A_PDF_shots"


def target_size_for_name(name: str):
    lower = name.lower()
    if "certificate" in lower:
        return (1280, 908)
    return (int(round(1175.44)), int(round(908.2)))


def render_pdf_page_to_image(pdf_path: Path, scale: float = 3.0):
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    mode = "RGB"
    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    return img


def process_pdf(pdf_path: Path, out_root: Path, scale: float = 3.0, dpi: int = 300):
    target_w, target_h = target_size_for_name(pdf_path.name)
    img = render_pdf_page_to_image(pdf_path, scale=scale)

    # Resize to exact target pixel dimensions with high-quality resampling
    resized = img.resize((int(target_w), int(target_h)), Image.LANCZOS)

    # Prepare output path
    rel = pdf_path.relative_to(SRC_DIR)
    out_pdf_path = out_root / rel
    out_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Save as single-page PDF with high DPI
    # Pillow will embed the image as a PDF page
    resized = resized.convert("RGB")
    resized.save(out_pdf_path, "PDF", resolution=dpi, quality=95)
    return out_pdf_path


def discover_pdfs(src: Path):
    return sorted(src.rglob("*.pdf"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(SRC_DIR))
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--scale", type=float, default=3.0, help="render scale (device pixel ratio)")
    parser.add_argument("--dpi", type=int, default=300, help="PDF output DPI")
    args = parser.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pdfs = discover_pdfs(src)
    if not pdfs:
        print(f"No PDFs found in {src}")
        return

    print(f"Found {len(pdfs)} PDF(s). Rendering with scale={args.scale}, dpi={args.dpi}")
    for p in pdfs:
        try:
            outp = process_pdf(p, out, scale=args.scale, dpi=args.dpi)
            print(f"Saved: {outp}")
        except Exception as e:
            print(f"Failed {p}: {e}")


if __name__ == "__main__":
    main()
