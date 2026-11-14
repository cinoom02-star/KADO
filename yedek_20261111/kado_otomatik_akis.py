"""KADO V3: run an owner-selected task, verify stored meeting, import CEO approvals.
No automatic execution of approved actions. Existing programs are not modified.
"""
import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'memory' / 'kado_company.db'
ROLES = {'arastirmaci', 'mimar', 'denetci', 'kado_ceo'}


def latest_id():
    with sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True) as db:
        return db.execute('SELECT COALESCE(MAX(id),0) FROM meetings').fetchone()[0]


def verify(meeting_id, task_id):
    with sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True) as db:
        meeting = db.execute('SELECT topic,status FROM meetings WHERE id=?', (meeting_id,)).fetchone()
        if not meeting or meeting[1] != 'completed' or not meeting[0].startswith(f'Panel gorevi #{task_id}:'):
            return False, 'Toplanti tamamlanmamis veya gorev eslesmiyor.'
        messages = db.execute('SELECT role,content FROM messages WHERE meeting_id=?', (meeting_id,)).fetchall()
        if len(messages) != 4 or {role.lower() for role, _ in messages} != ROLES:
            return False, 'Dort ajanin kaydi eksik veya tekrarlanmis.'
        if any(not content or len(content.strip()) < 30 for _, content in messages):
            return False, 'En az bir rapor bos veya cok kisa.'
        return True, 'Dort ajan kaydi mevcut.'


def main():
    parser = argparse.ArgumentParser(description='Gorevi calistir ve CEO onaylarini otomatik kuyruga aktar.')
    parser.add_argument('--task-id', required=True, type=int)
    args = parser.parse_args()
    if args.task_id < 1 or not DB.is_file():
        parser.error('Gecerli gorev ID veya veritabani bulunamadi.')
    if not os.environ.get('GEMINI_API_KEY') and not os.environ.get('GOOGLE_API_KEY'):
        print('HATA: API anahtari bu PowerShell oturumunda tanimli degil. Anahtari paylasmayin.')
        return 2
    runner = ROOT / 'kado_canli_gorev.py'
    importer = ROOT / 'kado_ceo_onay_aktar.py'
    if not runner.is_file() or not importer.is_file():
        print('HATA: Canli gorev motoru veya onay aktarim modulu eksik.')
        return 2
    before = latest_id()
    print('KADO otomatik akis basladi. Onaylar yalnizca kaydedilecek.', flush=True)
    result = subprocess.run([sys.executable, '-u', str(runner), '--task-id', str(args.task_id)], cwd=ROOT, check=False)
    if result.returncode:
        print('HATA: Ajan analizi basarisiz. Onay aktarilmadi.', flush=True)
        return result.returncode
    after = latest_id()
    if after != before + 1:
        print('HATA: Toplanti sayisi beklenmedik bicimde degisti; guvenlik icin aktarim durduruldu.')
        return 1
    ok, reason = verify(after, args.task_id)
    print('Kayit kontrolu:', reason, flush=True)
    if not ok:
        return 1
    print('Not: Gemini finish_reason henuz dogrulanmiyor; kayit kontrolu tek basina kesilmeyi dislamaz.', flush=True)
    imported = subprocess.run([sys.executable, str(importer), '--meeting-id', str(after), '--task-id', str(args.task_id), '--apply'], cwd=ROOT, check=False)
    if imported.returncode:
        print('HATA: Toplanti tamamlandi ancak onay aktarimi basarisiz.')
        return imported.returncode
    print(f'AKIS TAMAMLANDI | Toplanti #{after} | Gercek eylem uygulanmadi.', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
