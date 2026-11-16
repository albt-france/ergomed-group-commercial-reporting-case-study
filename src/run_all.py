"""Rerun the whole pipeline from the collected public data (the collection scripts are run separately, see README).

simulate -> prepare -> analysis -> check_truth -> Power BI (TMDL + PBIR) -> governance docs -> ad hoc note
-> weekly report -> monthly pack -> notebook -> PDF.   Usage: python src/run_all.py [--no-notebook]
Close Power BI Desktop first (the model files are rewritten)."""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
STEPS = ["extract_accounts", "extract_competitors", "prepare_public", "simulate", "prepare", "analysis", "check_truth",
         "build_tmdl", "build_report_pages", "build_docs", "build_adhoc", "weekly_report", "build_monthly_pack",
         "build_notebook", "build_pdf", "clean_metadata"]


def main():
    for step in STEPS:
        if step == "build_notebook" and "--no-notebook" in sys.argv:
            continue
        print(f"--> {step}", flush=True)
        subprocess.run([sys.executable, str(SRC / f"{step}.py")], check=True, cwd=SRC)


if __name__ == "__main__":
    main()
