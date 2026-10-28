"""One click: set up (first time only), download the latest data, rerun every analysis,
price this week's matches and rebuild the website. Takes about 10 minutes the first time.
Click the green ▶ next to `if __name__ == "__main__":` below."""
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def step(msg, *args):
    print(f"\n=== {msg} ===", flush=True)
    subprocess.check_call([str(PY), *args], cwd=HERE)


if __name__ == "__main__":
    if not PY.exists():
        print("=== First run: creating .venv ===", flush=True)
        venv.create(HERE / ".venv", with_pip=True)
        subprocess.check_call([str(PY), "-m", "pip", "install", "-q", "-r", str(HERE / "requirements.txt")])
    step("Downloading match data (2005 to now, 6 leagues)", "-c",
         "from pathlib import Path; from markets import data; "
         "data.download(Path('data/raw'), leagues=('E0','E1','SP1','D1','I1','F1'), first=2005, last=2026)")
    step("Running every analysis", "run.py")
    step("Pricing this week's matches", "-m", "markets.weekly")
    step("Rebuilding the website", "-m", "markets.website")
    step("Rewriting the README", "-m", "markets.readme")
    print("\n✅ All done. Open docs/index.html and docs/this-week.html in a browser.")
