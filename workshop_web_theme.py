from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Iterable


WORKSHOP_CSS = """
:root {
  --ink:#172033;
  --muted:#64748b;
  --line:#dbe4ee;
  --panel:#ffffff;
  --blue:#2563eb;
  --blue-dark:#173b76;
  --blue-soft:#dbeafe;
  --orange:#d97706;
  --orange-soft:#fff7ed;
  --bg:#f4f7fb;
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; color-scheme:light; }
body {
  margin:0;
  font-family:"Microsoft YaHei","PingFang SC",system-ui,-apple-system,sans-serif;
  color:var(--ink);
  background:var(--bg);
  line-height:1.7;
}
a { color:inherit; }
.wrap { width:min(1180px, calc(100% - 32px)); margin:0 auto; }
.hero { padding:24px 0 58px; background:linear-gradient(135deg,#0f172a,#173b76); color:white; }
.task-nav { display:flex; align-items:center; justify-content:space-between; gap:18px; margin-bottom:54px; }
.brand { font-size:13px; font-weight:800; letter-spacing:.08em; color:#dbeafe; text-transform:uppercase; }
.nav-links { display:flex; flex-wrap:wrap; gap:8px; }
.nav-links a {
  text-decoration:none;
  color:#dbeafe;
  border:1px solid rgba(219,234,254,.28);
  border-radius:999px;
  padding:6px 12px;
  font-size:13px;
  transition:.18s ease;
}
.nav-links a:hover,.nav-links a.active { color:white; background:rgba(255,255,255,.14); border-color:rgba(255,255,255,.48); }
.tag { display:inline-block; padding:4px 10px; border-radius:999px; background:var(--blue-soft); color:#1d4ed8; font-size:12px; font-weight:800; }
.hero .tag { margin-bottom:16px; }
.hero h1 { font-size:clamp(34px,5vw,58px); line-height:1.12; margin:0; letter-spacing:-.03em; max-width:900px; }
.hero p { max-width:840px; color:#dbeafe; font-size:18px; margin:16px 0 0; }
main { display:block; }
section { padding:42px 0; }
section.compact { padding-top:14px; }
h2 { font-size:28px; line-height:1.3; margin:0 0 18px; }
h3 { margin:5px 0 0; font-size:20px; line-height:1.4; }
h3 small { font-weight:500; color:var(--muted); font-size:13px; }
.section-lede { max-width:820px; margin:-8px 0 20px; color:#475569; }
.metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-top:-32px; position:relative; }
.metric,.card,.chart-card,.figure { background:var(--panel); border:1px solid var(--line); border-radius:18px; box-shadow:0 10px 30px rgba(15,23,42,.06); }
.metric { padding:22px; min-height:112px; }
.metric span { display:block; color:var(--muted); font-size:13px; }
.metric strong { display:block; font-size:27px; line-height:1.25; margin-top:6px; overflow-wrap:anywhere; }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.grid.two { grid-template-columns:repeat(2,1fr); }
.card { padding:24px; }
.card p { margin:8px 0 0; color:#475569; }
.rules { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.rule { border-left:4px solid var(--blue); }
.rule.sell { border-left-color:var(--orange); }
.figure-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.figure { padding:14px; }
.figure.wide { grid-column:1/-1; }
.figure h3 { padding:3px 5px 12px; }
.figure img,.chart-card img,.hero-figure img { width:100%; height:auto; display:block; border-radius:12px; border:1px solid var(--line); background:white; }
.chart-list { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.chart-card { padding:14px; }
.chart-copy { padding:4px 5px 12px; }
.chart-card a { display:block; text-decoration:none; }
.table-shell { overflow:auto; background:white; border:1px solid var(--line); border-radius:16px; box-shadow:0 10px 30px rgba(15,23,42,.04); }
.data-table { width:100%; border-collapse:collapse; font-size:14px; }
.data-table th { position:sticky; top:0; background:#eaf1fb; color:#334155; text-align:left; }
.data-table th,.data-table td { padding:11px 13px; border-bottom:1px solid var(--line); white-space:nowrap; }
.data-table tr:last-child td { border-bottom:0; }
.data-table tbody tr:hover { background:#f8fafc; }
.indicator-table th,.indicator-table td { text-align:left; vertical-align:top; white-space:normal; min-width:150px; line-height:1.55; }
.note { background:var(--orange-soft); border:1px solid #fed7aa; border-radius:14px; padding:16px 18px; color:#7c2d12; margin-top:18px; }
.note.blue { background:#eff6ff; border-color:#bfdbfe; color:#1e3a8a; }
.pill-row { display:flex; flex-wrap:wrap; gap:9px; margin-top:14px; }
.pill { padding:5px 10px; border-radius:999px; background:#eef2ff; color:#3730a3; font-size:12px; font-weight:700; }
footer { padding:32px 0 48px; color:var(--muted); font-size:13px; }
@media (max-width:850px) {
  .grid,.grid.two,.rules,.figure-grid,.chart-list { grid-template-columns:1fr; }
  .figure.wide { grid-column:auto; }
  .task-nav { align-items:flex-start; flex-direction:column; margin-bottom:42px; }
}
@media (max-width:560px) {
  .hero { padding-top:20px; }
  .hero p { font-size:16px; }
  .nav-links a { padding:5px 9px; }
  section { padding:34px 0; }
  h2 { font-size:24px; }
}
""".strip()


def task_path(task: int) -> str:
    directory = f"TASK{task}" if task >= 5 else f"Task{task}"
    return f"../../{directory}/web/index.html"


def render_task_nav(current_task: int) -> str:
    links = []
    for task in range(1, 7):
        active = ' class="active" aria-current="page"' if task == current_task else ""
        links.append(f'<a href="{task_path(task)}"{active}>TASK{task}</a>')
    return (
        '<nav class="task-nav" aria-label="工作坊任务导航">'
        '<div class="brand">PKU Workshop · Quantitative Trading</div>'
        f'<div class="nav-links">{"".join(links)}</div>'
        "</nav>"
    )


def render_hero(current_task: int, title: str, subtitle: str, *, class_name: str = "hero") -> str:
    return f"""
  <header class="{class_name}">
    <div class="wrap">
      {render_task_nav(current_task)}
      <div class="tag">PKU WORKSHOP · TASK{current_task}</div>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </div>
  </header>
""".strip()


def render_page(
    *,
    current_task: int,
    document_title: str,
    hero_title: str,
    hero_subtitle: str,
    body_html: str,
    footer_text: str,
) -> str:
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(document_title)}</title>
  <style>
{WORKSHOP_CSS}
  </style>
</head>
<body>
  {render_hero(current_task, hero_title, hero_subtitle)}
  <main>
{body_html}
  </main>
  <footer><div class="wrap">{footer_text}</div></footer>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in html.splitlines()) + "\n"


def render_metrics(metrics: Iterable[tuple[str, str]]) -> str:
    cards = "".join(
        f'<div class="metric"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        for label, value in metrics
    )
    return f'<div class="wrap metrics workshop-metrics">{cards}</div>'


PORTABLE_REPORT_OVERRIDE_CSS = f"""
{WORKSHOP_CSS}
.workshop-hero {{ padding:24px 0 58px; background:linear-gradient(135deg,#0f172a,#173b76); color:white; }}
.workshop-hero .tag {{ margin-bottom:16px; }}
.workshop-hero h1 {{ font-size:clamp(34px,5vw,58px); line-height:1.12; margin:0; letter-spacing:-.03em; max-width:900px; }}
.workshop-hero p {{ max-width:840px; color:#dbeafe; font-size:18px; margin:16px 0 0; }}
:root {{ color-scheme:light!important; --portable-canvas:#f4f7fb!important; --portable-surface:#fff!important; --portable-surface-subtle:#eaf1fb!important; --portable-ink:#172033!important; --portable-muted:#64748b!important; --portable-tertiary:#64748b!important; --portable-table-text:#475569!important; --portable-border:#dbe4ee!important; --portable-accent:#2563eb!important; }}
body {{ background:#f4f7fb!important; color:#172033!important; }}
.portable-fallback {{ width:min(1180px,calc(100% - 32px))!important; max-width:none!important; margin:0 auto!important; padding:36px 0 72px!important; }}
.portable-page-header {{ display:none!important; }}
.portable-block-stack {{ display:grid!important; grid-template-columns:repeat(2,minmax(0,1fr))!important; gap:18px!important; margin-top:0!important; }}
.portable-layout-full {{ grid-column:1/-1!important; }}
.portable-block[data-artifact-block-id="headline_metrics"] {{ display:none!important; }}
.portable-markdown,.portable-content-card {{ padding:24px!important; border:1px solid #dbe4ee!important; border-radius:18px!important; background:#fff!important; box-shadow:0 10px 30px rgba(15,23,42,.06)!important; }}
.portable-markdown h2,.portable-content-card h2 {{ margin:0 0 12px!important; color:#172033!important; font-size:28px!important; font-weight:700!important; line-height:1.3!important; }}
.portable-markdown h3 {{ color:#172033!important; font-size:20px!important; font-weight:700!important; }}
.portable-markdown p,.portable-markdown li,.portable-visual-header p {{ color:#475569!important; line-height:1.7!important; }}
.portable-metric-card {{ border:1px solid #dbe4ee!important; border-radius:18px!important; background:#fff!important; box-shadow:0 10px 30px rgba(15,23,42,.06)!important; }}
.portable-table-scroll {{ border:1px solid #dbe4ee!important; border-radius:14px!important; }}
.portable-table-scroll th {{ background:#eaf1fb!important; color:#334155!important; }}
.portable-custom-html iframe {{ border-radius:12px!important; }}
.portable-sources {{ padding:24px!important; border:1px solid #dbe4ee!important; border-radius:18px!important; background:#fff!important; }}
.workshop-footer {{ padding:0 0 48px; color:#64748b; font-size:13px; }}
@media(max-width:760px) {{
  .portable-fallback {{ width:min(100% - 28px,1180px)!important; padding-top:28px!important; }}
  .portable-block-stack {{ grid-template-columns:1fr!important; gap:14px!important; }}
  .portable-layout-full {{ grid-column:1!important; }}
  .portable-markdown,.portable-content-card {{ padding:20px!important; }}
  .workshop-hero p {{ font-size:16px; }}
}}
""".strip()


def restyle_portable_report(
    path: Path,
    *,
    current_task: int,
    hero_title: str,
    hero_subtitle: str,
    metrics: Iterable[tuple[str, str]],
    footer_text: str,
) -> None:
    html = path.read_text(encoding="utf-8")
    html = re.sub(
        r'<style data-workshop-theme="true">.*?</style>',
        "",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'<header class="workshop-hero">.*?</header>\s*<div class="wrap metrics workshop-metrics">.*?</div>\s*',
        "",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'<footer class="workshop-footer">.*?</footer>\s*',
        "",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'<meta name="color-scheme" content="[^"]+"\s*/?>',
        '<meta name="color-scheme" content="light" />',
        html,
        count=1,
    )
    style = f'<style data-workshop-theme="true">\n{PORTABLE_REPORT_OVERRIDE_CSS}\n</style>\n'
    html = html.replace("</head>", f"{style}</head>", 1)
    header = render_hero(current_task, hero_title, hero_subtitle, class_name="workshop-hero")
    html = html.replace("<body>", f"<body>\n{header}\n{render_metrics(metrics)}", 1)
    footer = f'<footer class="workshop-footer"><div class="wrap">{escape(footer_text)}</div></footer>'
    html = html.replace("</body>", f"{footer}\n</body>", 1)
    path.write_text(html, encoding="utf-8")
