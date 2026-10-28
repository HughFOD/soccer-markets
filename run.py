"""Run the whole analysis: python run.py"""
from pathlib import Path

from markets import report

ROOT = Path(__file__).parent

if __name__ == "__main__":
    report.run(ROOT / "data" / "raw", ROOT / "output")
