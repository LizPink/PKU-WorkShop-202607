from __future__ import annotations

import subprocess
import sys

from analyze_results import build_analysis_outputs
from build_report_artifact import build_artifact
from build_site import build_site
from build_walkthrough_notebook import build_notebook
from turtle_backtest import run_all_backtests


def main() -> None:
    summary, industry_summary = run_all_backtests()
    print(f"参数回测结果：{len(summary)} 行")
    print(f"行业汇总结果：{len(industry_summary)} 行")
    for name, path in build_analysis_outputs().items():
        print(f"{name}: {path}")
    notebook = build_notebook()
    print(f"notebook: {notebook}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--execute",
            "--to",
            "notebook",
            "--inplace",
            str(notebook),
        ],
        check=True,
    )
    print("Notebook executed successfully.")
    artifact = build_artifact()
    print(f"portable report artifact: {artifact}")
    website = build_site()
    print(f"website: {website}")


if __name__ == "__main__":
    main()
