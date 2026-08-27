"""Validate the self-contained TASK6 HTML report."""

from __future__ import annotations

import base64
import re
from pathlib import Path

import config


def main() -> None:
    report_path = config.REPORT_DIR / "姓名TASK6.html"
    source = report_path.read_text(encoding="utf-8")
    encoded_images = re.findall(r'data:image/png;base64,([^"\']+)', source)

    checks = {
        "html_exists": report_path.exists(),
        "doctype_present": source.lstrip().lower().startswith("<!doctype html>"),
        "title_present": "TASK6 智能决策者" in source,
        "eight_charts_embedded": len(encoded_images) == 8,
        "embedded_images_are_png": all(
            base64.b64decode(item).startswith(b"\x89PNG") for item in encoded_images
        ),
        "no_template_markers": "@@" not in source,
        "no_external_assets": not re.search(r'(?:src|href)="https?://', source),
        "pdf_download_present": "姓名TASK6.pdf" in source,
        "notebook_download_present": "../TASK6_walkthrough.ipynb" in source,
        "spec_download_present": "../SPEC.md" in source,
    }

    failed = [name for name, passed in checks.items() if not passed]
    print(f"HTML: {report_path}")
    print(f"Size: {report_path.stat().st_size:,} bytes")
    for name, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    print(f"Result: {len(checks) - len(failed)}/{len(checks)} checks passed")

    if failed:
        raise SystemExit(f"Validation failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
