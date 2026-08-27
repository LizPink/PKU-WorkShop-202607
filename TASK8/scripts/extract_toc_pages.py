from __future__ import annotations

import argparse
import json
from pathlib import Path

import pdfplumber


TOC_ENTRIES = [
    "摘要",
    "1 量化交易核心概念与研究框架",
    "1.1 从数据到决策的完整链条",
    "1.2 核心价值、评价原则与研究边界",
    "1.3 六项任务形成的递进式学习路线",
    "2 量化交易策略综合分析",
    "2.1 技术指标是信息压缩工具而非独立答案",
    "2.2 双均线策略具有趋势捕捉能力但超额收益不足",
    "2.3 海龟策略以风险预算换取更平稳的损失路径",
    "2.4 不同策略的适用场景、关联性与互补性",
    "2.5 多策略量化交易系统的构建思路",
    "3 机器学习在量化交易中的应用总结",
    "3.1 从通用分类实验到金融预测问题",
    "3.2 数据预处理、特征工程与防止信息泄漏",
    "3.3 模型选择、训练与评价",
    "3.4 机器学习选股取得正收益但未形成稳定超额",
    "3.5 机器学习的优势、局限与发展趋势",
    "4 结论与展望",
    "4.1 主要结论",
    "4.2 学习收获与能力提升",
    "4.3 后续研究计划",
    "参考文献",
    "附录 改进建议",
]


def normalize(text: str) -> str:
    return "".join((text or "").split()).replace("–", "-").replace("—", "-")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    page_texts = []
    with pdfplumber.open(args.pdf) as pdf:
        for page in pdf.pages:
            page_texts.append(normalize(page.extract_text() or ""))
    mapping: dict[str, int] = {}
    # Cover is page 1, abstract begins on page 2, and the two-page TOC ends on page 3.
    for heading in TOC_ENTRIES:
        if heading == "摘要":
            mapping[heading] = 2
            continue
        needle = normalize(heading)
        for page_number, text in enumerate(page_texts, start=1):
            if page_number <= 3:
                continue
            if needle in text:
                mapping[heading] = page_number
                break
    missing = [heading for heading in TOC_ENTRIES if heading not in mapping]
    if missing:
        raise RuntimeError(f"Missing headings in PDF: {missing}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(mapping, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
