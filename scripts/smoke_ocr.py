#!/usr/bin/env python3
"""
Smoke test script for OCR and Pdf integration.

Usage:
    python scripts/smoke_ocr.py /path/to/file.pdf

If no path provided, defaults to /root/pdf2md-master/test.pdf
"""
import sys
import os
from difflib import unified_diff

from src.ocr_processor import OCRProcessor
from src.pdf.pdf import Pdf


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else '/root/pdf2md-master/test.pdf'

    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found: {pdf_path}")
        return 2

    print(f"Using PDF: {pdf_path}")

    # 1) Run OCRProcessor on first page
    ocr = OCRProcessor()
    try:
        page0_text = ocr.process_single_page(pdf_path, 0, lang='eng')
    except Exception as e:
        print(f"OCRProcessor.process_single_page failed: {e}")
        page0_text = ''

    print("\n--- OCRProcessor page 0 (first 800 chars) ---")
    print(page0_text[:800])

    # 2) Initialize Pdf (forces building elements, uses internal OCR)
    cache_dir = os.path.abspath('./cache_smoke')
    os.makedirs(cache_dir, exist_ok=True)

    try:
        pdf = Pdf(pdf_path, cache_dir, ignore_cache=True)
    except Exception as e:
        print(f"Pdf initialization failed: {e}")
        return 3

    total_pages = len(pdf.context.pages)
    print(f"\nPdf context pages: {total_pages}")

    if total_pages > 0:
        elems = pdf.context.pages[0].elements
        print(f"Page 1 element count: {len(elems)}")
        print("First 10 elements (key, text excerpt):")
        for i, (key, el) in enumerate(elems[:10]):
            text = (el.text or '')
            print(f"  {i}: key={key} len={len(text)} excerpt={text[:120]!r}")

        # 3) Pdf.get_page_text
        page_text_from_pdf = pdf.get_page_text(0)
        print("\n--- Pdf.get_page_text page 0 (first 800 chars) ---")
        print(page_text_from_pdf[:800])

        # 4) Diff OCRProcessor vs Pdf.get_page_text
        print("\n--- Diff (OCRProcessor vs Pdf.get_page_text) ---")
        a_lines = page0_text.splitlines()
        b_lines = page_text_from_pdf.splitlines()
        diff = list(unified_diff(a_lines[:200], b_lines[:200], fromfile='ocr_processor', tofile='pdf.get_page_text', lineterm=''))
        if diff:
            for line in diff[:200]:
                print(line)
        else:
            print("No differences in first 200 lines (or both empty)")

    else:
        print("Pdf context contained no pages")

    # 5) Export a short structured markdown using pdf.get_text()
    try:
        text_all = pdf.get_text()
        print("\n--- Aggregated get_text (first 800 chars) ---")
        print(text_all[:800])
    except Exception as e:
        print(f"pdf.get_text failed: {e}")

    print("\nSmoke test finished.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
