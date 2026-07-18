from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from config import FIGURE_DIR, MODEL_ORDER, OUTPUT_DIR, REPORT_DIR, SUBMISSION_STEM, TITLE, ensure_directories


FONT_NAME = "SimSun"
BODY_SIZE = 10.5
CONTENT_WIDTH_DXA = 9025
INK = "1F2933"
BLUE = "31688E"
GOLD = "D39C2C"
LIGHT_BLUE = "E8F1F6"
LIGHT_GRAY = "F3F5F7"
GRID = "B9C3CC"


def set_run_font(run, size: float = BODY_SIZE, bold: bool | None = None, color: str = INK) -> None:
    run.font.name = FONT_NAME
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), FONT_NAME)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), FONT_NAME)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT_NAME)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold


def set_paragraph_format(
    paragraph,
    *,
    alignment: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.JUSTIFY,
    line_spacing: float = 1.5,
    keep_with_next: bool = False,
    first_line_chars: float | None = 2,
) -> None:
    fmt = paragraph.paragraph_format
    fmt.alignment = alignment
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = line_spacing
    fmt.keep_with_next = keep_with_next
    fmt.widow_control = True
    if first_line_chars is not None:
        fmt.first_line_indent = Pt(BODY_SIZE * first_line_chars)


def add_body(doc: Document, text: str, *, bold_lead: str | None = None) -> object:
    paragraph = doc.add_paragraph()
    set_paragraph_format(paragraph)
    if bold_lead and text.startswith(bold_lead):
        set_run_font(paragraph.add_run(bold_lead), bold=True)
        set_run_font(paragraph.add_run(text[len(bold_lead) :]))
    else:
        set_run_font(paragraph.add_run(text))
    return paragraph


def add_heading(doc: Document, text: str, level: int = 1) -> object:
    style_name = f"Heading {level}"
    paragraph = doc.add_paragraph(style=style_name)
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.LEFT, keep_with_next=True, first_line_chars=None)
    size = 12 if level == 1 else 10.5
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=True, color=INK if level == 1 else BLUE)
    return paragraph


def add_bullet(doc: Document, text: str) -> object:
    paragraph = doc.add_paragraph(style="List Bullet")
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line_chars=None)
    paragraph.paragraph_format.left_indent = Cm(0.74)
    paragraph.paragraph_format.first_line_indent = Cm(-0.37)
    set_run_font(paragraph.add_run(text))
    return paragraph


def add_numbered(doc: Document, text: str) -> object:
    paragraph = doc.add_paragraph(style="List Number")
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line_chars=None)
    paragraph.paragraph_format.left_indent = Cm(0.74)
    paragraph.paragraph_format.first_line_indent = Cm(-0.37)
    set_run_font(paragraph.add_run(text))
    return paragraph


def shade_paragraph(paragraph, fill: str) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    shd = ppr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        ppr.append(shd)
    shd.set(qn("w:fill"), fill)


def add_callout(doc: Document, label: str, text: str) -> object:
    paragraph = doc.add_paragraph()
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.LEFT, first_line_chars=None)
    shade_paragraph(paragraph, LIGHT_BLUE)
    set_run_font(paragraph.add_run(f"{label}："), bold=True, color=BLUE)
    set_run_font(paragraph.add_run(text))
    return paragraph


def add_code_block(doc: Document, code: str) -> None:
    for line in code.strip("\n").splitlines():
        paragraph = doc.add_paragraph()
        set_paragraph_format(
            paragraph,
            alignment=WD_ALIGN_PARAGRAPH.LEFT,
            line_spacing=1.0,
            first_line_chars=None,
        )
        paragraph.paragraph_format.left_indent = Cm(0.45)
        paragraph.paragraph_format.right_indent = Cm(0.3)
        shade_paragraph(paragraph, LIGHT_GRAY)
        run = paragraph.add_run(line if line else " ")
        set_run_font(run, size=8.5, color=INK)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 80, start: int = 120, bottom: int = 80, end: int = 120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths_dxa: list[int]) -> None:
    total = sum(widths_dxa)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(total))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")

    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)

    for row in table.rows:
        for index, cell in enumerate(row.cells):
            width = widths_dxa[index]
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)


def repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_table_caption(doc: Document, text: str) -> object:
    paragraph = doc.add_paragraph()
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, keep_with_next=True, first_line_chars=None)
    set_run_font(paragraph.add_run(text), bold=True)
    return paragraph


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths_dxa: list[int]) -> object:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    set_table_geometry(table, widths_dxa)
    repeat_table_header(table.rows[0])
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_shading(cell, LIGHT_BLUE)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None)
        set_run_font(paragraph.add_run(header), bold=True)
    for row_data in rows:
        row = table.add_row()
        for index, value in enumerate(row_data):
            cell = row.cells[index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            alignment = WD_ALIGN_PARAGRAPH.LEFT if index == 0 else WD_ALIGN_PARAGRAPH.CENTER
            set_paragraph_format(paragraph, alignment=alignment, first_line_chars=None)
            set_run_font(paragraph.add_run(str(value)))
    return table


def add_figure(doc: Document, image_path: Path, caption: str, width_cm: float = 14.2) -> None:
    paragraph = doc.add_paragraph()
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, keep_with_next=True, first_line_chars=None)
    inline_shape = paragraph.add_run().add_picture(str(image_path), width=Cm(width_cm))
    inline_shape._inline.docPr.set("descr", caption)
    inline_shape._inline.docPr.set("title", caption)
    caption_paragraph = doc.add_paragraph()
    set_paragraph_format(
        caption_paragraph,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        keep_with_next=False,
        first_line_chars=None,
    )
    set_run_font(caption_paragraph.add_run(caption), bold=True)


def add_page_number(paragraph) -> None:
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None)
    set_run_font(paragraph.add_run("第 "), size=9)
    run = paragraph.add_run()
    fld_char_begin = OxmlElement("w:fldChar")
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = "PAGE"
    fld_char_sep = OxmlElement("w:fldChar")
    fld_char_sep.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_char_begin, instr_text, fld_char_sep, text, fld_char_end])
    set_run_font(run, size=9)
    set_run_font(paragraph.add_run(" 页"), size=9)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.header_distance = Cm(1.25)
    section.footer_distance = Cm(1.25)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = FONT_NAME
    normal._element.rPr.rFonts.set(qn("w:ascii"), FONT_NAME)
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), FONT_NAME)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_NAME)
    normal.font.size = Pt(BODY_SIZE)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for style_name, size, color in (("Heading 1", 12, INK), ("Heading 2", 10.5, BLUE), ("Heading 3", 10.5, BLUE)):
        style = styles[style_name]
        style.font.name = FONT_NAME
        style._element.rPr.rFonts.set(qn("w:ascii"), FONT_NAME)
        style._element.rPr.rFonts.set(qn("w:hAnsi"), FONT_NAME)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_NAME)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.keep_with_next = True

    for style_name in ("List Bullet", "List Number"):
        style = styles[style_name]
        style.font.name = FONT_NAME
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_NAME)
        style.font.size = Pt(BODY_SIZE)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing = 1.5

    header = section.header
    header_paragraph = header.paragraphs[0]
    set_paragraph_format(header_paragraph, alignment=WD_ALIGN_PARAGRAPH.RIGHT, first_line_chars=None)
    set_run_font(header_paragraph.add_run("TASK5 · AI交易引擎"), size=9, color="66737F")
    footer = section.footer
    add_page_number(footer.paragraphs[0])


def build_document() -> Path:
    ensure_directories()
    metrics = pd.read_csv(OUTPUT_DIR / "metrics.csv").set_index("model")
    quality = json.loads((OUTPUT_DIR / "data_quality.json").read_text(encoding="utf-8"))
    params = json.loads((OUTPUT_DIR / "model_parameters.json").read_text(encoding="utf-8"))

    logistic = metrics.loc["logistic_regression"]
    tree = metrics.loc["decision_tree"]
    forest = metrics.loc["random_forest"]

    doc = Document()
    configure_document(doc)
    doc.core_properties.title = TITLE
    doc.core_properties.subject = "机器学习二分类算法与模型评价课程作业"
    doc.core_properties.author = ""
    doc.core_properties.keywords = "逻辑回归, 决策树, 随机森林, 混淆矩阵, ROC, AUC"

    title_paragraph = doc.add_paragraph()
    set_paragraph_format(title_paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, keep_with_next=True, first_line_chars=None)
    set_run_font(title_paragraph.add_run(TITLE), size=16, bold=True, color=INK)
    metadata = doc.add_paragraph()
    set_paragraph_format(metadata, alignment=WD_ALIGN_PARAGRAPH.CENTER, keep_with_next=True, first_line_chars=None)
    set_run_font(metadata.add_run("数据集：scikit-learn 乳腺癌二分类数据集  |  实验日期：2026年7月17日"), size=9, color="66737F")

    add_heading(doc, "摘要", 1)
    add_body(
        doc,
        f"本文围绕基础分类型机器学习算法及其评价方法展开，使用 scikit-learn 内置乳腺癌数据集构建逻辑回归、决策树和随机森林模型。数据集包含 {quality['samples']} 条样本和 {quality['features']} 个数值特征；为使风险事件对应正类，本文将恶性肿瘤编码为 1、良性肿瘤编码为 0。数据按 80%/20% 分层划分为训练集和测试集，测试集不参与模型拟合。结果表明，随机森林、逻辑回归和决策树的测试集 AUC 分别为 {forest['roc_auc']:.4f}、{logistic['roc_auc']:.4f} 和 {tree['roc_auc']:.4f}。逻辑回归与随机森林均表现出较强的区分能力，单棵决策树则在召回率和稳定性方面相对较弱。本文进一步结合混淆矩阵与 ROC 曲线解释模型差异，并讨论迁移到股票收益方向预测时需要防范的前视偏差、非平稳性和交易成本问题。",
    )
    add_callout(
        doc,
        "核心结论",
        f"若只看测试集 AUC，随机森林最高（{forest['roc_auc']:.4f}）；若更重视减少恶性样本漏判，逻辑回归在默认阈值下召回率更高（{logistic['recall']:.2%} 对 {forest['recall']:.2%}）。因此模型选择必须结合误判成本，而不能只依据单一指标。",
    )

    add_heading(doc, "1 分类机器学习算法", 1)
    add_heading(doc, "1.1 逻辑回归", 2)
    add_body(
        doc,
        "逻辑回归虽然名称中含有“回归”，本质上是常用的分类算法。它先计算特征的线性组合 z=β0+β1x1+…+βpxp，再通过 Sigmoid 函数 p=1/(1+e^(-z)) 把结果映射到 0 至 1 之间，将 p 解释为样本属于正类的概率。若默认阈值为 0.5，则 p≥0.5 时预测为正类，否则预测为负类。",
    )
    add_body(
        doc,
        "逻辑回归的优势是计算速度快、能够直接输出概率，而且系数方向便于解释；它适合作为分类任务的强基线。局限在于默认决策边界为线性，并且特征尺度差异会影响优化，因此本实验将 StandardScaler 与逻辑回归放入同一 Pipeline，只用训练集估计均值和标准差。量化交易中，它可用于预测未来收益是否为正、某个信号是否有效或公司是否进入风险状态。",
    )

    add_heading(doc, "1.2 决策树", 2)
    add_body(
        doc,
        "决策树通过不断选择特征和切分阈值，把样本空间划分为更纯的子区域。分类树常用基尼不纯度衡量节点中类别混杂程度，并选择能够最大幅度降低不纯度的切分。最终从根节点到叶节点形成一组易读的 if-then 规则。决策树可以拟合非线性关系和变量交互，也不要求特征标准化。",
    )
    add_body(
        doc,
        "单棵树容易把训练样本中的偶然噪声当成规则，导致过拟合，对样本的小幅变化也较敏感。因此本实验将最大深度限制为 4，并要求每个叶节点至少包含 5 个样本。量化场景中，决策树可以依据估值、盈利能力、动量和波动率形成可读的分类规则，但必须通过时间外样本检验规则是否稳定。",
    )

    add_heading(doc, "1.3 随机森林", 2)
    add_body(
        doc,
        "随机森林属于集成学习方法。它对训练数据进行多次 bootstrap 抽样，为每个样本子集训练一棵决策树，并在每次节点划分时只考虑随机抽取的一部分特征。分类时，多棵树对类别投票或对正类概率取平均。样本随机性与特征随机性降低了树之间的相关性，因此集成结果通常比单棵树更稳定。",
    )
    add_body(
        doc,
        "随机森林能够处理非线性和高阶交互，对异常值和噪声通常也更稳健；代价是模型体量增大、单一预测较难解释。本实验使用 500 棵树、叶节点最小样本数为 2，并使用平衡类别权重。量化交易中，它适合融合财务、估值、动量、情绪和微观结构特征预测收益方向或风险事件。",
    )

    add_heading(doc, "1.4 三种算法的比较", 2)
    add_table_caption(doc, "表 1 三种分类算法的特点与量化场景")
    add_table(
        doc,
        ["算法", "主要特点", "优势", "局限与量化应用"],
        [
            ["逻辑回归", "线性组合经 Sigmoid 输出概率", "速度快、可解释、强基线", "难以自动捕捉非线性；适合收益方向或事件概率预测"],
            ["决策树", "按不纯度递归切分形成规则", "规则直观、无需标准化", "容易过拟合；适合可读的因子条件组合"],
            ["随机森林", "多棵随机树平均概率或投票", "稳定、能拟合非线性与交互", "解释和计算成本较高；适合多源金融特征融合"],
        ],
        [1250, 2450, 1900, 3425],
    )

    add_heading(doc, "2 分类模型评价指标", 1)
    add_heading(doc, "2.1 混淆矩阵", 2)
    add_body(
        doc,
        "混淆矩阵把真实类别与预测类别交叉排列。本文统一规定恶性为正类（1）、良性为负类（0），横轴为预测类别、纵轴为真实类别。TN 表示良性被正确预测为良性；FP 表示良性被误判为恶性；FN 表示恶性被漏判为良性；TP 表示恶性被正确识别。明确正类与矩阵方向是解释所有后续指标的前提。",
    )
    add_table_caption(doc, "表 2 混淆矩阵与常用指标定义")
    add_table(
        doc,
        ["指标", "计算公式", "解释"],
        [
            ["Accuracy", "(TP+TN)/(TP+TN+FP+FN)", "全部样本中分类正确的比例；类别不均衡时可能误导"],
            ["Precision", "TP/(TP+FP)", "被预测为恶性的样本中，真实恶性的比例"],
            ["Recall / TPR", "TP/(TP+FN)", "真实恶性样本中，被模型识别出的比例"],
            ["Specificity", "TN/(TN+FP)", "真实良性样本中，被正确排除的比例"],
            ["F1", "2×Precision×Recall/(Precision+Recall)", "Precision 与 Recall 的调和平均"],
            ["FPR", "FP/(FP+TN)", "真实良性样本中，被错误标记为恶性的比例"],
        ],
        [1500, 3000, 4525],
    )

    add_heading(doc, "2.2 ROC 曲线与 AUC", 2)
    add_body(
        doc,
        "分类阈值决定概率如何被转换为 0 或 1。不断改变阈值，可以得到不同的 TPR 与 FPR 组合；以 FPR 为横轴、TPR 为纵轴连接这些点，就得到 ROC 曲线。理想模型的曲线靠近左上角，随机分类器的期望表现位于从 (0,0) 到 (1,1) 的对角线上。",
    )
    add_body(
        doc,
        "AUC 是 ROC 曲线下的面积，也可理解为随机抽取一个正类和一个负类时，模型把正类预测分数排在负类之前的概率。AUC=0.5 表示排序能力接近随机，越接近 1 表示区分能力越强。需要注意，AUC 不直接反映某个固定阈值下的误判数量，也不能代替医学诊断成本、交易手续费、滑点或策略收益分析。",
    )

    add_heading(doc, "3 Python 实验设计", 1)
    add_heading(doc, "3.1 数据来源与标签重编码", 2)
    add_body(
        doc,
        f"实验调用 sklearn.datasets.load_breast_cancer(as_frame=True) 加载 Wisconsin Diagnostic Breast Cancer 数据。共有 {quality['samples']} 条样本、{quality['features']} 个数值特征，无缺失值。scikit-learn 原始编码为恶性=0、良性=1；为使风险事件与正类一致，本文使用 y=1-y_original 将其重编码为恶性=1、良性=0。全样本含恶性 212 条、良性 357 条。",
    )
    add_code_block(
        doc,
        """from sklearn.datasets import load_breast_cancer

data = load_breast_cancer(as_frame=True)
X = data.data.copy()
y = 1 - data.target.astype(int)   # 恶性=1，良性=0""",
    )

    add_heading(doc, "3.2 训练集与测试集划分", 2)
    add_body(
        doc,
        f"使用 train_test_split 将数据按 80%/20% 分层划分，random_state 固定为 42。训练集 {quality['train_samples']} 条，用于拟合预处理参数和模型参数；测试集 {quality['test_samples']} 条，只用于最终评价。stratify=y 使两部分保持近似一致的类别比例。",
    )
    add_code_block(
        doc,
        """X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=42
)""",
    )
    add_figure(doc, FIGURE_DIR / "figure_1_class_distribution.png", "图 1 训练集与测试集类别分布", width_cm=12.2)
    add_body(
        doc,
        "图 1 显示训练集中良性 285 条、恶性 170 条，测试集中良性 72 条、恶性 42 条。两部分的恶性占比仅相差约 0.52 个百分点，说明分层划分保持了原有类别结构，测试结果不会因为类别比例明显偏移而失真。",
        bold_lead="图 1 显示",
    )

    add_heading(doc, "3.3 模型设定与训练", 2)
    add_table_caption(doc, "表 3 三种模型的实验设定")
    add_table(
        doc,
        ["模型", "预处理", "主要参数"],
        [
            ["逻辑回归", "StandardScaler Pipeline", "solver=liblinear；max_iter=5000；random_state=42"],
            ["决策树", "无", "criterion=gini；max_depth=4；min_samples_leaf=5；class_weight=balanced"],
            ["随机森林", "无", "n_estimators=500；min_samples_leaf=2；class_weight=balanced；random_state=42"],
        ],
        [1800, 2450, 4775],
    )
    add_body(
        doc,
        "逻辑回归的标准化在 Pipeline 内完成，因此 StandardScaler 只在训练集上拟合，避免把测试集均值和标准差提前泄漏给模型。树模型不依赖距离或梯度尺度，不需要标准化。所有模型均输出预测类别和恶性正类概率，后者用于 ROC 与 AUC 计算。",
    )

    add_heading(doc, "3.4 评价方法与不确定性", 2)
    add_body(
        doc,
        "测试集采用默认 0.5 阈值计算混淆矩阵、Accuracy、Precision、Recall、Specificity 和 F1；AUC 使用 predict_proba 输出的恶性概率计算，而不是使用离散的 0/1 预测类别。为描述有限测试样本带来的不确定性，本文对测试集进行 2,000 次有放回 bootstrap，并取 AUC 分布的 2.5% 与 97.5% 分位数作为 95% 区间。",
    )

    add_heading(doc, "4 模型结果与解读", 1)
    add_heading(doc, "4.1 综合评价结果", 2)
    metric_rows = []
    metric_labels = [
        ("Accuracy", "accuracy", ".2%"),
        ("Precision", "precision", ".2%"),
        ("Recall", "recall", ".2%"),
        ("Specificity", "specificity", ".2%"),
        ("F1", "f1", ".2%"),
        ("AUC", "roc_auc", ".4f"),
        ("AUC 95%区间", None, None),
    ]
    for label, field, fmt in metric_labels:
        values = []
        for row in (logistic, tree, forest):
            if field is None:
                values.append(f"[{row['auc_ci_low']:.3f}, {row['auc_ci_high']:.3f}]")
            else:
                values.append(format(row[field], fmt))
        metric_rows.append([label, *values])
    add_table_caption(doc, "表 4 三种分类模型的测试集评价结果")
    add_table(
        doc,
        ["评价指标", "逻辑回归", "决策树", "随机森林"],
        metric_rows,
        [2300, 2242, 2242, 2241],
    )
    add_body(
        doc,
        f"表 4 显示，逻辑回归与随机森林的测试集准确率均为 {logistic['accuracy']:.2%}。随机森林 AUC 最高，为 {forest['roc_auc']:.4f}，逻辑回归以 {logistic['roc_auc']:.4f} 紧随其后；两者的 bootstrap 区间高度重叠，不能据此断言随机森林在总体上必然更优。决策树 AUC 为 {tree['roc_auc']:.4f}，明显低于另外两个模型，且 Recall 只有 {tree['recall']:.2%}。",
    )

    add_heading(doc, "4.2 逻辑回归混淆矩阵", 2)
    add_figure(doc, FIGURE_DIR / "figure_2_logistic_regression_confusion_matrix.png", "图 2 逻辑回归测试集混淆矩阵", width_cm=8.8)
    add_body(
        doc,
        "图 2 中 TN=71、FP=1、FN=2、TP=40。逻辑回归只把 1 个良性样本误判为恶性，并漏判 2 个恶性样本。其 Recall 为 95.24%、Specificity 为 98.61%，说明默认阈值下对两类样本的识别较均衡。",
        bold_lead="图 2 中",
    )

    add_heading(doc, "4.3 决策树混淆矩阵", 2)
    add_figure(doc, FIGURE_DIR / "figure_3_decision_tree_confusion_matrix.png", "图 3 决策树测试集混淆矩阵", width_cm=8.8)
    add_body(
        doc,
        "图 3 中 TN=68、FP=4、FN=6、TP=36。决策树的错误总数为 10 个，其中 6 个恶性样本被漏判，使 Recall 降至 85.71%。虽然树深已受到限制，训练 AUC 仍为 99.16%，测试 AUC 只有 92.03%，二者差距为三种模型中最大，体现了单棵树较高的过拟合敏感性。",
        bold_lead="图 3 中",
    )

    add_heading(doc, "4.4 随机森林混淆矩阵", 2)
    add_figure(doc, FIGURE_DIR / "figure_4_random_forest_confusion_matrix.png", "图 4 随机森林测试集混淆矩阵", width_cm=8.8)
    add_body(
        doc,
        "图 4 中 TN=72、FP=0、FN=3、TP=39。随机森林没有把任何良性样本误判为恶性，因此 Precision 和 Specificity 均为 100%；但它漏判了 3 个恶性样本，Recall 为 92.86%，略低于逻辑回归。如果漏判代价显著高于误报代价，可以下调概率阈值以提高 Recall。",
        bold_lead="图 4 中",
    )

    add_heading(doc, "4.5 ROC 曲线与 AUC 比较", 2)
    add_figure(doc, FIGURE_DIR / "figure_5_roc_curves.png", "图 5 三种分类模型的 ROC 曲线", width_cm=14.6)
    add_body(
        doc,
        f"图 5 显示随机森林与逻辑回归的 ROC 曲线几乎贴近左上角，AUC 分别为 {forest['roc_auc']:.3f} 和 {logistic['roc_auc']:.3f}，说明两者对恶性和良性样本均有很强的排序区分能力。决策树曲线明显更接近随机基准，AUC 为 {tree['roc_auc']:.3f}。不过 AUC 不指定实际分类阈值，最终模型仍需结合 FP 与 FN 成本选择阈值。",
        bold_lead="图 5 显示",
    )

    add_heading(doc, "5 量化交易场景应用", 1)
    add_body(
        doc,
        "将上述流程迁移到量化交易时，可以把应变量定义为未来持有期收益是否大于 0、是否跑赢基准或是否进入收益率前分位；特征则可以包括财务质量、估值、价格动量、波动率、成交活跃度和市场状态。逻辑回归可作为可解释基线，决策树可形成条件规则，随机森林可捕捉非线性与因子交互。",
    )
    add_bullet(doc, "时间对齐：财务数据必须使用当时已经披露的版本，价格和成交量特征只能使用预测时点之前的信息。")
    add_bullet(doc, "数据划分：金融时间序列不能随机打乱，应采用按时间先后划分、滚动窗口或扩展窗口验证。")
    add_bullet(doc, "标签与阈值：标签应对应明确持有期，分类阈值应结合手续费、滑点、换手率、容量和错失机会选择。")
    add_bullet(doc, "评价体系：AUC 只衡量排序能力，策略还需检验年化收益、波动率、夏普比率、最大回撤和样本外稳定性。")
    add_bullet(doc, "模型更新：市场分布会随制度、参与者和宏观状态变化，需要持续监控特征漂移和模型失效。")

    add_heading(doc, "6 结论与局限", 1)
    add_body(
        doc,
        f"本实验完成了二分类建模的完整流程：加载数据、标签重编码、分层划分、训练三种模型、计算混淆矩阵和 AUC、绘制 ROC 曲线。测试结果显示，随机森林的 AUC 最高（{forest['roc_auc']:.4f}），但逻辑回归在默认阈值下对恶性样本的 Recall 更高（{logistic['recall']:.2%}），且模型更简洁。单棵决策树虽然规则直观，但测试 AUC 和 Recall 明显较低。因而模型评价必须同时关注概率排序、固定阈值误判结构、可解释性和业务成本。",
    )
    add_body(
        doc,
        "本研究的主要局限是只使用一次固定留出集，测试样本仅 114 条；bootstrap 区间不能替代外部验证或多次时间外检验。此外，乳腺癌样例近似独立同分布，不能直接代表金融市场的非平稳性。若换用股票收益数据，必须重新设计时间划分、标签口径、成本函数和回测指标。本实验仅用于课程中的机器学习方法演示，不构成医学诊断或投资建议。",
    )

    add_heading(doc, "附录：核心 Python 实现", 1)
    add_body(doc, "以下代码展示模型构建与 AUC/ROC 计算的核心逻辑。完整可复现脚本位于 TASK5/scripts/train_and_evaluate.py。")
    add_code_block(
        doc,
        """models = {
    "Logistic Regression": Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=5000, random_state=42)),
    ]),
    "Decision Tree": DecisionTreeClassifier(
        max_depth=4, min_samples_leaf=5, class_weight="balanced", random_state=42
    ),
    "Random Forest": RandomForestClassifier(
        n_estimators=500, min_samples_leaf=2,
        class_weight="balanced", random_state=42
    ),
}

for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    fpr, tpr, thresholds = roc_curve(y_test, y_prob, pos_label=1)""",
    )
    add_callout(
        doc,
        "复现命令",
        r"在仓库根目录运行：uv --cache-dir .uv-cache run python .\TASK5\scripts\run_all.py",
    )

    output_path = REPORT_DIR / f"{SUBMISSION_STEM}.docx"
    doc.save(output_path)
    source_notes = OUTPUT_DIR / "report_source_notes.md"
    source_notes.write_text(
        "\n".join(
            [
                "# Report Source Notes",
                "",
                "- Audience: technical",
                "- Delivery surfaces explicitly requested: offline HTML + DOCX + PDF",
                "- Primary data source: sklearn.datasets.load_breast_cancer",
                "- Reproducible analysis: scripts/train_and_evaluate.py",
                "- Metric evidence: outputs/metrics.csv and outputs/predictions.csv",
                "- Required structure mapping: 摘要→技术摘要；第4节→关键发现与视觉证据；第3节→范围/数据/方法；第6节→局限；第5节→下一步；HTML 末节→后续问题。",
                "- Named document override: standard_business_brief adjusted to A4, SimSun 10.5 pt, 1.5 line spacing, 0 pt paragraph spacing, justified body per assignment instructions.",
                "- Chart map: outputs/chart_map.csv",
                "- Validation evidence: outputs/validation_report.md",
            ]
        ),
        encoding="utf-8",
    )
    print(f"DOCX 报告已生成：{output_path}")
    return output_path


def main() -> int:
    build_document()
    return 0


if __name__ == "__main__":
    sys.exit(main())
