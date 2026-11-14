"""KADO live status wrapper. Does not modify existing task runner or database."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'memory' / 'agent_live_state.json'
AGENTS = ('ARASTIRMACI', 'MIMAR', 'DENETCI', 'KADO_CEO')

def save(phase, agent='', completed=None, message='', task_id=0):
    """Durumu eszamanli yazimlarda guvenli kaydeder."""
    import tempfile

    STATE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'phase': phase,
        'agent': agent,
        'completed_agents': list(completed or []),
        'message': str(message)[:250],
        'task_id': task_id,
        'updated_at': time.time()
    }

    payload = json.dumps(data, ensure_ascii=False)
    last_error = None

    for attempt in range(6):
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=str(STATE.parent),
                prefix='agent_live_state_',
                suffix='.tmp',
                delete=False
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(payload)
                handle.flush()

            os.replace(str(temp_path), str(STATE))
            return

        except PermissionError as exc:
            last_error = exc
            time.sleep(0.05 * (attempt + 1))

        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    raise RuntimeError(
        f'Ajan durum dosyasi yazilamadi: {last_error}'
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task-id', type=int, required=True)
    args = parser.parse_args()
    if args.task_id < 1:
        parser.error('task-id pozitif olmali')
    if not os.environ.get('GEMINI_API_KEY'):
        print('HATA: GEMINI_API_KEY bu PowerShell oturumunda tanimli degil.', flush=True)
        return 2
    script = ROOT / 'kado_gorev_calistir.py'
    if not script.is_file():
        print('HATA: Gorev motoru bulunamadi:', script, flush=True)
        return 2
    save('running', message='Gorev motoru baslatiliyor', task_id=args.task_id)
    try:
        process = subprocess.Popen([sys.executable, '-u', str(script), '--task-id', str(args.task_id)],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1)
    except OSError as exc:
        save('failed', message=str(exc), task_id=args.task_id)
        print('Baslatma hatasi:', exc, flush=True)
        return 1
    current = ''
    completed = []
    last = 'Gorev motoru baslatildi'
    success_marker = False
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(2):
            save('running', current, completed, last, args.task_id)
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        for line in process.stdout:
            print(line, end='', flush=True)
            cleaned = line.strip()
            match = re.match(r'^(ARASTIRMACI|MIMAR|DENETCI|KADO_CEO)\s+dusunuyor', cleaned, re.I)
            if match:
                current = match.group(1).upper()
                last = current + ' dusunuyor'
            elif cleaned.startswith('====='):
                match = re.match(r'^=====\s*(ARASTIRMACI|MIMAR|DENETCI|KADO_CEO)\s*=====', cleaned, re.I)
                if match:
                    name = match.group(1).upper()
                    if name not in completed: completed.append(name)
                    last = name + ' yanit verdi'
            elif cleaned.startswith('ANALIZ TAMAMLANDI'):
                success_marker = True
                last = 'Analiz tamamlandi'
            elif cleaned.startswith('HATA:'):
                last = cleaned
            save('running', current, completed, last, args.task_id)
        rc = process.wait()
        if rc == 0 and success_marker and len(completed) == len(AGENTS):
            save('completed', '', completed, 'Tum ajanlar yanit verdi; toplantiyi panelden kontrol et', args.task_id)
        else:
            save('failed', current, completed, f'Gorev motoru cikis kodu: {rc}; son durum: {last}', args.task_id)
        return rc if rc else (0 if success_marker and len(completed) == len(AGENTS) else 1)
    except KeyboardInterrupt:
        process.terminate()
        save('failed', current, completed, 'Kullanici tarafindan durduruldu', args.task_id)
        return 130
    finally:
        stop.set()
        thread.join(timeout=3)

if __name__ == '__main__':
    sys.exit(main())
