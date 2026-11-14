import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "memory" / "kado_company.db"
STATE = ROOT / "memory" / "agent_live_state.json"

def durum():
    if not DB.is_file():
        return {"ok": False, "message": "Veritabani bulunamadi"}

    with sqlite3.connect(
        f"file:{DB.as_posix()}?mode=ro", uri=True
    ) as db:
        task = db.execute(
            "SELECT id,title,status FROM tasks ORDER BY id DESC LIMIT 1"
        ).fetchone()

        meeting = None
        if task:
            prefix = f"Panel gorevi #{task[0]}:"
            meeting = db.execute(
                """
                SELECT id,topic,status
                FROM meetings
                WHERE substr(topic,1,?)=?
                ORDER BY id DESC LIMIT 1
                """,
                (len(prefix), prefix)
            ).fetchone()

    state = {}
    if STATE.is_file():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    matching_state = (
        state if task and state.get("task_id") == task[0]
        else {}
    )

    return {
        "ok": True,
        "last_task": {
            "id": task[0],
            "title": task[1],
            "status": task[2]
        } if task else None,
        "last_task_meeting": {
            "id": meeting[0],
            "topic": meeting[1],
            "status": meeting[2]
        } if meeting else None,
        "agent_state": matching_state,
        "message": (
            "Bu gorev icin henuz toplanti kaydi yok."
            if task and not meeting
            else "Gorev ve toplanti kayitlari eslestirildi."
        )
    }

def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "status"

    if command == "status":
        print(json.dumps(durum(), ensure_ascii=False))
        return 0

    if command == "create":
        if len(sys.argv) < 3:
            print(json.dumps({"ok": False, "message": "Gorev basligi eksik."}, ensure_ascii=False))
            return 2

        title = sys.argv[2].strip()
        details = sys.argv[3].strip() if len(sys.argv) > 3 else ""

        if not 5 <= len(title) <= 150 or len(details) > 2000:
            print(json.dumps({"ok": False, "message": "Gorev metni gecersiz."}, ensure_ascii=False))
            return 2

        if not DB.is_file():
            print(json.dumps({"ok": False, "message": "Veritabani bulunamadi."}, ensure_ascii=False))
            return 2

        with sqlite3.connect(DB, timeout=10) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
            if not {"title", "details", "status"}.issubset(columns):
                raise RuntimeError("Beklenmeyen gorev tablosu.")

            cur = db.execute(
                "INSERT INTO tasks(title,details,status,created_at) VALUES(?,?,?,datetime('now'))",
                (title, details, "devam")
            )
            db.commit()
            task_id = cur.lastrowid

        print(json.dumps({
            "ok": True,
            "task_id": task_id,
            "message": "Gorev kaydedildi. Ajanlar henuz baslatilmadi."
        }, ensure_ascii=False))
        return 0

    print(json.dumps({
        "ok": False,
        "message": "Bu surumde yalnizca durum sorgulama acik."
    }, ensure_ascii=False))
    return 2

if __name__ == "__main__":
    sys.exit(main())
