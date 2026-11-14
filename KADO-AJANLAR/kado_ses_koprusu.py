import sqlite3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "memory" / "kado_company.db"

def son_toplanti():
    if not DB.is_file():
        return {"error": "Veritabani bulunamadi"}

    with sqlite3.connect(
        f"file:{DB.as_posix()}?mode=ro", uri=True
    ) as db:
        db.row_factory = sqlite3.Row

        meeting = db.execute("""
            SELECT id, topic, status
            FROM meetings
            WHERE status = 'completed'
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if not meeting:
            return {"error": "Tamamlanmis toplanti yok"}

        reports = db.execute("""
            SELECT role, content
            FROM messages
            WHERE meeting_id = ?
            ORDER BY rowid
        """, (meeting["id"],)).fetchall()

        return {
            "meeting_id": meeting["id"],
            "topic": meeting["topic"],
            "status": meeting["status"],
            "reports": [
                {
                    "agent": r["role"],
                    "report": r["content"]
                }
                for r in reports
            ]
        }

if __name__ == "__main__":
    print(json.dumps(
        son_toplanti(),
        ensure_ascii=False
    ))
