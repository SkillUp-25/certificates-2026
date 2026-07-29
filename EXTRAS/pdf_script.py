import base64
import re
import tempfile
from pathlib import Path
from urllib import request as urllib_request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DONE_ROOT = ROOT / "Done"
A_PDF_ROOT = DONE_ROOT / "A_PDF"

HTML_PATTERNS = ["**/CERTIFICATE.html", "**/MARKS.html"]


def discover_html_files(start_dir: Path):
    if not start_dir.exists():
        return []

    html_files = []
    for pattern in HTML_PATTERNS:
        html_files.extend(start_dir.rglob(pattern))

    return sorted({path.resolve() for path in html_files})


def rewrite_local_asset_urls(html_text: str, html_path: Path) -> str:
    def replace_attr(match: re.Match[str]) -> str:
        prefix, value, quote = match.groups()
        if not value or value.startswith(("http://", "https://", "data:", "//", "#", "mailto:")):
            return match.group(0)
        if value.startswith("/"):
            return match.group(0)

        candidate = (html_path.parent / value).resolve()
        if candidate.exists():
            return f"{prefix}{candidate.as_uri()}{quote}"
        return match.group(0)

    pattern = re.compile(r'(<(?:img|link|script)\b[^>]*\b(?:src|href)=["\'])([^"\']+)(["\'])', re.IGNORECASE)
    return pattern.sub(replace_attr, html_text)


def embed_remote_images(html_text: str) -> str:
    def replace_src(match: re.Match[str]) -> str:
        prefix, url, quote = match.groups()
        if not url.startswith(("http://", "https://")):
            return match.group(0)

        try:
            with urllib_request.urlopen(url, timeout=20) as response:
                content_type = response.headers.get_content_type() or "image/jpeg"
                data = response.read()
        except Exception:
            return match.group(0)

        encoded = base64.b64encode(data).decode("ascii")
        return f"{prefix}data:{content_type};base64,{encoded}{quote}"

    pattern = re.compile(r'(<img\b[^>]*\bsrc=["\'])(https?://[^"\']+)(["\'])', re.IGNORECASE)
    return pattern.sub(replace_src, html_text)


def inject_print_css(html_text: str) -> str:
    css = """
    <style>
    @page { size: A4 landscape; margin: 0; }
    html, body { margin: 0; padding: 0; width: 297mm; height: 210mm; }
    .certificate-container { width: 297mm !important; height: 210mm !important; overflow: hidden; }
    img { width: 297mm !important; height: 210mm !important; object-fit: cover; }
    </style>
    """

    if "</head>" in html_text:
        return html_text.replace("</head>", css + "</head>")
    return css + html_text


def build_pdf_from_html(html_path: Path) -> Path:
    html_path = html_path.resolve()
    output_dir = A_PDF_ROOT / html_path.parent.parent.name
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_name = f"{html_path.parent.name}.pdf"
    output_path = output_dir / pdf_name

    html_text = html_path.read_text(encoding="utf-8")
    html_text = rewrite_local_asset_urls(html_text, html_path)
    html_text = embed_remote_images(html_text)
    html_text = inject_print_css(html_text)

    # write the full rendered page to a temp file so the browser can load it
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False, dir=str(html_path.parent)) as temp_file:
        temp_file.write(html_text)
        temp_full_path = Path(temp_file.name)

    # target pixel sizes requested by user (CSS pixels)
    if html_path.name.lower().startswith("certificate") or "certificate" in str(html_path).lower():
        target_w, target_h = 1280, 908
    else:
        target_w, target_h = 1175.44, 908.2

    screenshot_png = output_path.with_suffix('.png')
    try:
        from PIL import Image
    except Exception:
        raise SystemExit("Pillow is required. Install with: python -m pip install Pillow")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # render at exact pixel viewport to match HTML preview
            # render at higher device pixel ratio for a crisp screenshot
            page = browser.new_page(viewport={"width": int(round(target_w)), "height": int(round(target_h))}, device_scale_factor=3)
            page.goto(temp_full_path.as_uri(), wait_until="networkidle")
            page.emulate_media(media="print")
            page.wait_for_timeout(800)

            element = page.query_selector('.certificate-container') or page.query_selector('body')
            if element is None:
                element = page

            # screenshot the element exactly (no background omission)
            element.screenshot(path=str(screenshot_png), omit_background=False)

            browser.close()

        # convert PNG to PDF with Pillow at high quality (300 DPI)
        img = Image.open(screenshot_png)
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg

        img.save(output_path, "PDF", resolution=300, quality=95)
    finally:
        try:
            temp_full_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            screenshot_png.unlink(missing_ok=True)
        except Exception:
            pass

    return output_path


def main():
    html_files = discover_html_files(DONE_ROOT)
    if not html_files:
        print(f"No HTML files found under {DONE_ROOT}")
        return

    A_PDF_ROOT.mkdir(parents=True, exist_ok=True)
    generated = []

    for html_file in html_files:
        output_path = build_pdf_from_html(html_file)
        generated.append(output_path)
        print(f"Created PDF: {output_path}")

    print(f"\nFinished. Created {len(generated)} PDF(s) in {A_PDF_ROOT}")


if __name__ == "__main__":
    main()
