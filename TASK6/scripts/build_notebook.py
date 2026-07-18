from __future__ import annotations

import json
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

from config import OUTPUT_DIR, PROJECT_DIR, TITLE


def build_notebook() -> Path:
    summary = json.loads((OUTPUT_DIR / "analysis_summary.json").read_text(encoding="utf-8"))
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            f"# {TITLE}\n\n## Goal\n\n"
            "本 Notebook 是 TASK6 的教学型审计伴随文件。它读取脚本生成的季度面板、模型指标和回测结果，复核核心计算并展示关键图形。"
        ),
        nbf.v4.new_markdown_cell(
            "## Setup\n\n### Key Assumptions\n\n"
            "- 股票池为抓取日的中证 300 当前成分股，存在幸存者偏差。\n"
            "- 因子在季度末形成，标签为下一季度首个交易日开盘到再下一季度首个交易日开盘的收益。\n"
            "- 测试期逐季度扩展窗口重训；主策略每季度等权持有预测前 30。\n"
            "- 净收益按组合换手率乘以单边 0.2% 综合成本扣减。"
        ),
        nbf.v4.new_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import numpy as np\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n\n"
            "ROOT = Path.cwd()\n"
            "TASK_DIR = ROOT / 'TASK6' if (ROOT / 'TASK6').exists() else ROOT\n"
            "OUTPUT_DIR = TASK_DIR / 'outputs'\n"
            "PANEL_PATH = TASK_DIR / 'data' / 'processed' / 'quarterly_panel.csv'\n"
            "assert OUTPUT_DIR.exists() and PANEL_PATH.exists()\n"
            "plt.style.use('seaborn-v0_8-whitegrid')"
        ),
        nbf.v4.new_markdown_cell("## Steps\n\n### 1. Load and validate the quarterly panel"),
        nbf.v4.new_code_cell(
            "panel = pd.read_csv(PANEL_PATH, dtype={'ts_code': str})\n"
            "quality = json.loads((OUTPUT_DIR / 'data_quality.json').read_text(encoding='utf-8'))\n"
            "print({k: quality[k] for k in ['panel_rows','panel_stock_count','panel_quarters','panel_duplicate_keys']})\n"
            "assert panel.duplicated(['ts_code','quarter_index']).sum() == 0\n"
            "panel[['quarter','ts_code','signal_date','entry_date','exit_date','forward_return','target_rank']].head()"
        ),
        nbf.v4.new_markdown_cell("### 2. Inspect time splits and model prediction metrics"),
        nbf.v4.new_code_cell(
            "split_summary = pd.read_csv(OUTPUT_DIR / 'split_summary.csv')\n"
            "model_metrics = pd.read_csv(OUTPUT_DIR / 'model_metrics.csv')\n"
            "display(split_summary)\n"
            "display(model_metrics[['model_zh','mae_rank','rmse_rank','r2_rank','mean_rank_ic','positive_ic_ratio']])"
        ),
        nbf.v4.new_markdown_cell("### 3. Plot quarterly Rank IC"),
        nbf.v4.new_code_cell(
            "quarterly_ic = pd.read_csv(OUTPUT_DIR / 'quarterly_ic.csv')\n"
            "pivot_ic = quarterly_ic.pivot(index='quarter', columns='model_zh', values='rank_ic')\n"
            "ax = pivot_ic.plot(figsize=(9, 4), marker='o')\n"
            "ax.axhline(0, color='black', linestyle=':', linewidth=1)\n"
            "ax.set_title('Test-period quarterly Rank IC')\n"
            "ax.set_ylabel('Spearman Rank IC')\n"
            "plt.xticks(rotation=40, ha='right')\n"
            "plt.tight_layout(); plt.show()"
        ),
        nbf.v4.new_markdown_cell("### 4. Inspect Top 30 backtest metrics"),
        nbf.v4.new_code_cell(
            "backtest_metrics = pd.read_csv(OUTPUT_DIR / 'backtest_metrics.csv')\n"
            "quarterly_returns = pd.read_csv(OUTPUT_DIR / 'quarterly_returns.csv')\n"
            "display(backtest_metrics[['model_zh','cumulative_return','annualized_return','annualized_volatility','max_drawdown','information_ratio']])"
        ),
        nbf.v4.new_markdown_cell("## Checks\n\n### 5. Independently recompute cumulative return and maximum drawdown"),
        nbf.v4.new_code_cell(
            "checks = []\n"
            "for model, group in quarterly_returns.groupby('model'):\n"
            "    group = group.sort_values('quarter_index')\n"
            "    nav = (1 + group['net_return']).cumprod()\n"
            "    cumulative = nav.iloc[-1] - 1\n"
            "    max_drawdown = (nav / nav.cummax() - 1).min()\n"
            "    saved = backtest_metrics.set_index('model').loc[model]\n"
            "    checks.append({'model': model, 'cumulative_saved': saved.cumulative_return, 'cumulative_recomputed': cumulative, 'max_dd_saved': saved.max_drawdown, 'max_dd_recomputed': max_drawdown})\n"
            "checks = pd.DataFrame(checks)\n"
            "assert np.allclose(checks['cumulative_saved'], checks['cumulative_recomputed'])\n"
            "assert np.allclose(checks['max_dd_saved'], checks['max_dd_recomputed'])\n"
            "checks"
        ),
        nbf.v4.new_markdown_cell(
            "## Next Steps\n\n"
            f"本次测试期平均 Rank IC 最佳模型为 **{summary['best_model_zh']}**，平均 Rank IC 为 **{summary['best_mean_rank_ic']:.3f}**。"
            "后续最重要的改进是使用逐季度历史成分股和公告日对齐的财务因子，并完整模拟停牌、涨跌停、佣金、印花税与冲击成本。"
        ),
    ]
    output = PROJECT_DIR / "TASK6_walkthrough.ipynb"
    nbf.write(notebook, output)
    client = NotebookClient(notebook, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(PROJECT_DIR.parent)}})
    client.execute()
    nbf.write(notebook, output)
    print(f"Notebook created and executed: {output}")
    return output


def main() -> int:
    build_notebook()
    return 0


if __name__ == "__main__":
    sys.exit(main())
