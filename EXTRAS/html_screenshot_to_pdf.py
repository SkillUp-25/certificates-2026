#!/usr/bin/env python3
"""Render certificate and marks HTML files to high-quality screenshot PDFs.

This script scans the `Done` folder for student HTML files and writes output
PDFs into `Done/A_PDF/<student_name>/`.

Usage:
  python html_screenshot_to_pdf.py

Requirements:
  python -m pip install playwright Pillow
  python -m playwright install chromium
"""
from pathlib import Path
import math
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DONE_ROOT = ROOT / "Done"
OUTPUT_ROOT = DONE_ROOT / "A_PDF"

CERT_SIZE = (1280, 908)
MARKS_SIZE = (1175.44, 908.2)


def discover_html_files(root: Path):
    html_files = []
    for student_dir in sorted(root.iterdir()):
        if not student_dir.is_dir() or student_dir.name == OUTPUT_ROOT.name:
            continue
        for path in student_dir.rglob("*.html"):
            if path.name.upper() in {"CERTIFICATE.HTML", "MARKS.HTML"}:
                html_files.append(path)
    return sorted(html_files)


def get_target_size(html_path: Path):
    if html_path.name.upper() == "CERTIFICATE.HTML":
        return CERT_SIZE
    return MARKS_SIZE


def screenshot_html_to_png(html_path: Path, output_png: Path, target_w: float, target_h: float, scale: float = 3.0):
    css_width = int(math.ceil(target_w))
    css_height = int(math.ceil(target_h))
    viewport = {"width": css_width, "height": css_height}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport, device_scale_factor=scale)
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(1000)

        element = page.locator(".certificate-container")
        if element.count() > 0:
            element.screenshot(path=str(output_png), omit_background=False)
        else:
            page.screenshot(path=str(output_png), omit_background=False)

        browser.close()


def save_png_as_pdf(png_path: Path, pdf_path: Path, target_w: float, target_h: float, dpi: int = 300):
    img = Image.open(png_path)
    img = img.convert("RGB")
    resized = img.resize((int(round(target_w)), int(round(target_h))), Image.LANCZOS)
    resized.save(pdf_path, "PDF", resolution=dpi, quality=95)


def build_output_path(html_path: Path):
    student_name = html_path.parent.parent.name
    out_dir = OUTPUT_ROOT / student_name
    out_dir.mkdir(parents=True, exist_ok=True)
    if html_path.name.upper() == "CERTIFICATE.HTML":
        filename = f"{html_path.parent.name}.pdf"
    else:
        filename = f"{html_path.parent.name}.pdf"
    return out_dir / filename


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    html_files = discover_html_files(DONE_ROOT)
    if not html_files:
        print(f"No HTML files found in {DONE_ROOT}")
        return

    print(f"Found {len(html_files)} HTML files to convert")
    for html_path in html_files:
        target_w, target_h = get_target_size(html_path)
        output_pdf = build_output_path(html_path)
        print(f"Rendering {html_path} -> {output_pdf}")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            png_path = Path(tmp.name)
        try:
            screenshot_html_to_png(html_path, png_path, target_w, target_h, scale=3.0)
            save_png_as_pdf(png_path, output_pdf, target_w, target_h, dpi=300)
            print(f"Saved PDF: {output_pdf}")
        finally:
            try:
                png_path.unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == "__main__":
    main()
