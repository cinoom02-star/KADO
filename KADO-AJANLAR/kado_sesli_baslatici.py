import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import psutil
from kado_agent_lock import AgentLock

ROOT = Path(__file__).resolve().parent
DB = ROOT / "memory" / "kado_company.db"

def stop_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for proc in reversed(children):
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                pass
        gone, alive = psutil.wait_procs(children, timeout=5)
        for proc in alive:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(alive, timeout=5)
        try:
            parent.terminate()
            parent.wait(timeout=5)
        except psutil.TimeoutExpired:
            parent.kill()
            parent.wait(timeout=5)
    except psutil.NoSuchProcess:
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    if args.task_id < 1:
        parser.error("Gecersiz gorev numarasi")

    lock = AgentLock()
    if not lock.acquire():
        print("HATA: Baska bir toplantisi calisiyor.", flush=True)
        return 3

    try:
        if args.check_only:
            print("BASARILI: Kilit ve guvenli baslatici hazir.")
            print("Ajanlar calistirilmadi.")
            return 0

        if not DB.is_file():
            print("HATA: Veritabani bulunamadi.", flush=True)
            return 2

        with sqlite3.connect(DB) as db:
            task = db.execute(
                "SELECT id,status FROM tasks WHERE id=?",
                (args.task_id,)
            ).fetchone()

        if not task or task[1] == "tamam":
            print("HATA: Gorev bulunamadi veya tamamlanmis.", flush=True)
            return 2

        if not (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        ):
            print("HATA: Ajan API anahtari bulunamadi.", flush=True)
            return 2

        runner = ROOT / "kado_otomatik_akis.py"
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                str(runner),
                "--task-id",
                str(args.task_id)
            ],
            cwd=str(ROOT),
            env=os.environ.copy()
        )

        try:
            return process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            print("HATA: Toplanti zaman asimina ugradi.", flush=True)
            stop_tree(process.pid)
            return 4
        except KeyboardInterrupt:
            stop_tree(process.pid)
            return 130
    finally:
        lock.release()

if __name__ == "__main__":
    sys.exit(main())
