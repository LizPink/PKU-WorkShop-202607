from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from config import PROJECT_DIR, REPORT_DIR, SUBMISSION_STEM


def run_python(script_name: str) -> None:
    script_path = PROJECT_DIR / "scripts" / script_name
    subprocess.run([sys.executable, str(script_path)], cwd=PROJECT_DIR.parent, check=True)


def main() -> int:
    run_python("train_and_evaluate.py")
    run_python("validate_outputs.py")
    run_python("build_site.py")
    run_python("build_report.py")
    if sys.platform == "win32":
        docx_path = REPORT_DIR / f"{SUBMISSION_STEM}.docx"
        pdf_path = REPORT_DIR / f"{SUBMISSION_STEM}.pdf"
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(PROJECT_DIR / "scripts" / "export_pdf.ps1"),
                "-InputDocx",
                str(docx_path),
                "-OutputPdf",
                str(pdf_path),
            ],
            cwd=PROJECT_DIR.parent,
            check=True,
        )
    run_python("validate_artifacts.py")
    print("TASK5 全流程执行完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
