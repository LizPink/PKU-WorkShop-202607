from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from config import PROJECT_DIR, RAW_DIR


def run(script: str) -> None:
    subprocess.run([sys.executable, str(PROJECT_DIR / "scripts" / script)], check=True, cwd=PROJECT_DIR.parent)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild TASK6 analysis, notebook and DOCX from cached raw data.")
    parser.add_argument("--skip-notebook", action="store_true")
    args = parser.parse_args()
    if not (RAW_DIR / "csi300_current_constituents_daily_hfq.csv").exists():
        raise SystemExit("Raw data are missing. Run scripts/fetch_data.py with a Python environment that includes AkShare.")
    run("analyze_strategy.py")
    if not args.skip_notebook:
        run("build_notebook.py")
    run("build_report.py")
    print("Analysis, notebook and DOCX completed. Export the DOCX with export_pdf.ps1, then run validate_outputs.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
