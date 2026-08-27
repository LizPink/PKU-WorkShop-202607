from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import pdfplumber
from docx import Document
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DOCX = ROOT / "TASK8/report/李子平TASK8.docx"
PDF = ROOT / "TASK8/report/李子平TASK8.pdf"
FIG_DIR = ROOT / "TASK8/outputs/figures"
OUT = ROOT / "TASK8/outputs/validation_report.md"


def check(condition: bool, label: str, detail: str = "") -> tuple[bool, str]:
    suffix = f" - {detail}" if detail else ""
    return condition, f"- [{'PASS' if condition else 'FAIL'}] {label}{suffix}"


def main() -> int:
    checks: list[tuple[bool, str]] = []
    checks.append(check(DOCX.exists() and DOCX.stat().st_size > 100_000, "DOCX存在且非空", str(DOCX)))
    checks.append(check(PDF.exists() and PDF.stat().st_size > 100_000, "PDF存在且非空", str(PDF)))

    doc = Document(DOCX)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    required = ["摘要", "量化交易核心概念", "量化交易策略综合分析", "机器学习在量化交易中的应用总结", "结论与展望", "附录 改进建议"]
    for item in required:
        checks.append(check(item in full_text, f"必需章节：{item}"))
    checks.append(check("TASK7" not in full_text, "未使用TASK7内容"))
    checks.append(check("导师反馈" not in full_text, "未虚构导师反馈"))
    checks.append(check("待更新" not in full_text and "[[TOC]]" not in full_text, "目录无占位符"))

    abstract_match = re.search(r"摘要\n(.+?)\n关键词", full_text, flags=re.S)
    abstract = re.sub(r"\s+", "", abstract_match.group(1)) if abstract_match else ""
    checks.append(check(200 <= len(abstract) <= 300, "摘要长度200-300字", f"实际{len(abstract)}字"))

    figure_numbers = [int(x) for x in re.findall(r"图(\d+) ", full_text)]
    table_numbers = [int(x) for x in re.findall(r"表(\d+) ", full_text)]
    checks.append(check(sorted(set(figure_numbers)) == list(range(1, 10)), "图号1-9连续", str(sorted(set(figure_numbers)))))
    checks.append(check(sorted(set(table_numbers)) == list(range(1, 8)), "表号1-7连续", str(sorted(set(table_numbers)))))

    section = doc.sections[0]
    page_w = section.page_width.cm
    page_h = section.page_height.cm
    checks.append(check(abs(page_w - 21.0) < 0.05 and abs(page_h - 29.7) < 0.05, "DOCX为A4页面", f"{page_w:.2f}x{page_h:.2f}cm"))
    normal = doc.styles["Normal"]
    checks.append(check(normal.font.name == "SimSun" and abs(normal.font.size.pt - 10.5) < 0.1, "正文宋体五号"))
    checks.append(check(abs(float(normal.paragraph_format.line_spacing) - 1.5) < 0.01, "正文1.5倍行距"))
    checks.append(check(normal.paragraph_format.space_before.pt == 0 and normal.paragraph_format.space_after.pt == 0, "正文0磅段间距"))

    with zipfile.ZipFile(DOCX) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    checks.append(check(xml.count("<w:cantSplit") >= 40, "表格行禁止跨页"))
    checks.append(check(xml.count("<wp:inline") == 9, "9幅图均为嵌入式图片"))

    figures = sorted(FIG_DIR.glob("figure_*.png"))
    checks.append(check(len(figures) == 9, "生成9幅图", str(len(figures))))
    for figure in figures:
        with Image.open(figure) as image:
            width, height = image.size
        checks.append(check(width >= 1400 and height >= 700, f"图表清晰：{figure.name}", f"{width}x{height}"))

    with pdfplumber.open(PDF) as pdf:
        page_count = len(pdf.pages)
        pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        sizes_ok = all(abs(float(page.width) - 595.3) < 3 and abs(float(page.height) - 841.9) < 3 for page in pdf.pages)
    checks.append(check(15 <= page_count <= 35, "PDF页数合理", f"{page_count}页"))
    checks.append(check(sizes_ok, "PDF全部页面为A4"))
    checks.append(check("李子平" in pdf_text and "TASK8" in pdf_text, "PDF封面姓名与任务标识正确"))
    checks.append(check("—" not in "\n".join(pdf_text.splitlines()[0:120]), "目录页码已填充"))

    passed = sum(ok for ok, _ in checks)
    report = ["# TASK8 Validation Report", "", f"## Overall: {passed}/{len(checks)} passed", ""] + [line for _, line in checks]
    OUT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
