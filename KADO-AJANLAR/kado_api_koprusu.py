import argparse
import os
import subprocess
import sys
from pathlib import Path

KADO_DIR = Path(r"C:\KADO\kado\sistem")
AGENT_DIR = Path(__file__).resolve().parent

def get_key():
    sys.path.insert(0, str(KADO_DIR))
    from app_config import get_app_config_value

    key = get_app_config_value("gemini_api_key")

    if not isinstance(key, str) or not key.strip():
        raise RuntimeError("KADO Gemini API anahtari bulunamadi")

    return key.strip()

def run_agent(task_id):
    if task_id < 1:
        raise ValueError("Gecersiz gorev numarasi")

    key = get_key()

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUTF8"] = "1"
    env["GEMINI_API_KEY"] = key
    env["GOOGLE_API_KEY"] = key

    python = AGENT_DIR / ".venv" / "Scripts" / "python.exe"
    launcher = AGENT_DIR / "kado_sesli_baslatici.py"

    if not python.is_file() or not launcher.is_file():
        raise RuntimeError("Ajan baslaticisi bulunamadi")

    completed = subprocess.run(
        [
            str(python),
            str(launcher),
            "--task-id",
            str(task_id),
        ],
        cwd=str(AGENT_DIR),
        env=env,
        check=False,
    )

    return completed.returncode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--task-id", type=int)
    args = parser.parse_args()

    if args.check_only:
        get_key()
        print("BASARILI: API anahtari okunuyor.")
        print("Ajanlar baslatilmadi.")
        return 0

    if args.task_id is None:
        parser.error("--task-id gerekli")

    return run_agent(args.task_id)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("HATA:", type(exc).__name__, str(exc))
        sys.exit(1)
