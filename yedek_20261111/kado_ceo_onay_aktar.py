"""KADO V3: preview/import CEO approval recommendations; never executes actions."""
import argparse
import datetime as dt
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / 'memory' / 'kado_company.db'
APPROVAL = ROOT / 'memory' / 'kado_approvals.db'

def proposals(content):
    # Require an explicit owner-approval section, not arbitrary CEO suggestions.
    section = re.search(r'(?im)^\s*\*{0,2}(?:Sahibinden|Patrondan|Kullanıcıdan)\s+Onay\s+Gerektiren\s+Adımlar\s*:?\*{0,2}\s*$', content)
    if not section:
        return []
    lines = content[section.end():].splitlines()
    result = []
    for line in lines:
        m = re.match(r'^\s*(?:\d+[.)]|[-*])\s+(.*\S)\s*$', line)
        if m:
            item = re.sub(r'\*+', '', m.group(1)).strip()
            if item:
                result.append(item)
        elif result and line.strip() and not line.startswith((' ', '\t')):
            break
    return result[:12]

def main():
    p = argparse.ArgumentParser(description='KADO CEO onay önerilerini incele ve kuyruğa al')
    p.add_argument('--meeting-id', type=int, required=True)
    p.add_argument('--task-id', type=int)
    p.add_argument('--apply', action='store_true', help='Onay kuyruğuna kaydet; işlem yürütmez')
    args = p.parse_args()
    if args.meeting_id < 1 or (args.task_id is not None and args.task_id < 1):
        p.error('ID pozitif olmalı')
    if not MAIN.is_file():
        p.error('Ana veritabanı bulunamadı')
    with sqlite3.connect(f'file:{MAIN.as_posix()}?mode=ro', uri=True) as c:
        meeting = c.execute('SELECT topic,status FROM meetings WHERE id=?', (args.meeting_id,)).fetchone()
        if not meeting or meeting[1] != 'completed':
            p.error('Tamamlanmış toplantı bulunamadı')
        row = c.execute("SELECT content FROM messages WHERE meeting_id=? AND lower(role)='kado_ceo' ORDER BY id DESC LIMIT 1", (args.meeting_id,)).fetchone()
    if not row:
        p.error('KADO CEO raporu bulunamadı')
    items = proposals(row[0])
    print(f'Toplantı #{args.meeting_id}: {meeting[0]}')
    if not items:
        print('Açık bir patron onay maddesi bulunamadı. Otomatik talep oluşturulmadı.')
        return
    for i, item in enumerate(items, 1):
        print(f'{i}. {item}')
    if not args.apply:
        print('\nSADECE ÖNİZLEME. Kaydetmek için --apply ekle.')
        return
    APPROVAL.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(APPROVAL, timeout=10) as c:
        c.execute('PRAGMA busy_timeout=10000')
        c.execute('''CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, title TEXT NOT NULL, proposal TEXT NOT NULL, risk TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'bekliyor', created_at TEXT NOT NULL, decided_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS approval_imports (meeting_id INTEGER NOT NULL, item_no INTEGER NOT NULL, approval_id INTEGER NOT NULL, PRIMARY KEY(meeting_id,item_no))''')
        count = 0
        for i, item in enumerate(items, 1):
            if c.execute('SELECT 1 FROM approval_imports WHERE meeting_id=? AND item_no=?', (args.meeting_id,i)).fetchone():
                continue
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            cur = c.execute('INSERT INTO approvals(task_id,title,proposal,risk,created_at) VALUES(?,?,?,?,?)', (
                args.task_id, f'KADO CEO · Toplantı #{args.meeting_id} · Madde {i}', item[:4000],
                'AI tarafından önerilmiştir; maliyet, hukuki uyum, güvenlik ve uygulanabilirlik insan tarafından doğrulanmalıdır. Onay yalnızca karar kaydıdır.', now))
            c.execute('INSERT INTO approval_imports(meeting_id,item_no,approval_id) VALUES(?,?,?)', (args.meeting_id,i,cur.lastrowid))
            count += 1
    print(f'Onay kuyruğuna eklenen yeni talep: {count}. Gerçek işlem yapılmadı.')

if __name__ == '__main__':
    main()
