import os
import sys
import msvcrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCK = ROOT / "memory" / "kado_agent_run.lock"

class AgentLock:
    def __init__(self):
        self.file = None

    def acquire(self):
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(LOCK, "a+b")
        try:
            self.file.seek(0)
            if self.file.read(1) == b"":
                self.file.seek(0)
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            self.file.close()
            self.file = None
            return False

    def release(self):
        if self.file:
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close()
            self.file = None

if __name__ == "__main__":
    lock = AgentLock()
    if lock.acquire():
        print("KILIT TESTI BASARILI")
        lock.release()
    else:
        print("BASKA BIR GOREV CALISIYOR")
        sys.exit(1)
