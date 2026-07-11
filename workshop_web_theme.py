from __future__ import annotations

from html import escape


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
html { scroll-behavior:smooth; }
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
"""


TASKS = (
    ("TASK1", "../../Task1/web/index.html"),
    ("TASK2", "../../Task2/web/index.html"),
    ("TASK3", "../../Task3/web/index.html"),
    ("TASK4", "../../Task4/web/index.html"),
)


def task_navigation(current_task: int, *, root_prefix: str = "../..") -> str:
    links = []
    for index, (label, href) in enumerate(TASKS, start=1):
        normalized_href = href.removeprefix("../..")
        href = f"{root_prefix}{normalized_href}" if root_prefix else normalized_href.lstrip("/")
        active = ' class="active" aria-current="page"' if index == current_task else ""
        links.append(f'<a href="{href}"{active}>{label}</a>')
    return (
        '<nav class="task-nav" aria-label="工作坊任务导航">'
        '<div class="brand">PKU Workshop · Quantitative Trading</div>'
        f'<div class="nav-links">{"".join(links)}</div>'
        '</nav>'
    )


def render_page(
    *,
    current_task: int,
    document_title: str,
    hero_title: str,
    hero_subtitle: str,
    body_html: str,
    footer_text: str,
) -> str:
    task_label = f"PKU WORKSHOP · TASK{current_task}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(document_title)}</title>
  <style>{WORKSHOP_CSS}</style>
</head>
<body>
  <header class="hero">
    <div class="wrap">
      {task_navigation(current_task)}
      <div class="tag">{task_label}</div>
      <h1>{hero_title}</h1>
      <p>{escape(hero_subtitle)}</p>
    </div>
  </header>
  <main>{body_html}</main>
  <footer><div class="wrap">{escape(footer_text)}</div></footer>
</body>
</html>
"""
