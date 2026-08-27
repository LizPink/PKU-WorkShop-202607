from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

from build_report import OUTPUT_DIR, REPORT_DIR, SUBMISSION_STEM, TOC_ENTRIES


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("．", ".")


def main() -> None:
    pdf_path = REPORT_DIR / f"{SUBMISSION_STEM}.pdf"
    output_path = OUTPUT_DIR / "toc_pages.json"
    pages: dict[str, int] = {"摘要": 2, "技术摘要": 2}

    with pdfplumber.open(pdf_path) as pdf:
        extracted = [
            normalize(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
            for page in pdf.pages
        ]

    for _, title in TOC_ENTRIES:
        if title in pages:
            continue
        needle = normalize(title)
        for page_number, page_text in enumerate(extracted, start=1):
            if page_number <= 3:
                continue
            if needle in page_text:
                pages[title] = page_number
                break

    missing = [title for _, title in TOC_ENTRIES if title not in pages]
    if missing:
        raise RuntimeError(f"未能定位以下目录条目：{missing}")

    output_path.write_text(
        json.dumps(pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写入 {output_path}")
    for _, title in TOC_ENTRIES:
        print(f"{title}: {pages[title]}")


if __name__ == "__main__":
    main()
