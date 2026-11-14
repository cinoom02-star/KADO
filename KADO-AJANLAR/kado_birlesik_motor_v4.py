"""KADO V4: V3 worker + read-only centralized SQLite task registry and watchdog.
Does not modify KADO production, WhatsApp, or execute generated code.
"""
import argparse, contextlib, datetime, json, os, pathlib, sqlite3, subprocess, sys, time
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT/'kado_agent_motor'; QUEUE=BASE/'kuyruk'; OUT=BASE/'ciktilar'
REPORT=ROOT/'entegrasyon_raporlari'; DB=ROOT/'memory'/'kado_v4_gorevler.db'
LOCK=ROOT/'kado_v4_motor.lock'
SUFFIXES=('.json','.working','.done','.review','.failed')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=10)
    c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, kind TEXT, goal TEXT, state TEXT, updated TEXT, static_decision TEXT, behavior TEXT, outcome TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, task_id TEXT, old_state TEXT, new_state TEXT)')
    c.commit();return c
def scan(c):
    count=0
    if not QUEUE.exists():return 0
    for p in sorted(QUEUE.iterdir()):
        if p.suffix not in SUFFIXES or not p.is_file():continue
        try:
            job=json.loads(p.read_text(encoding='utf-8-sig'))
            if not isinstance(job,dict):continue
            jid=str(job.get('id') or p.stem)
            if jid!=p.stem:continue
            kind=str(job.get('kind',''));goal=str(job.get('goal',''))[:2000]
            state=p.suffix[1:]
            result=OUT/jid/'SONUC.json'
            data=json.loads(result.read_text(encoding='utf-8')) if result.exists() else {}
            static=str(data.get('statik_karar',''))
            behavior=str(data.get('davranis',{}).get('durum','')) if isinstance(data.get('davranis'),dict) else ''
            old=c.execute('SELECT state FROM tasks WHERE id=?',(jid,)).fetchone()
            if not old or old[0]!=state:
                c.execute('INSERT INTO events(time,task_id,old_state,new_state) VALUES(?,?,?,?)',(utc(),jid,old[0] if old else '',state))
            c.execute('INSERT INTO tasks(id,kind,goal,state,updated,static_decision,behavior,outcome) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,updated=excluded.updated,static_decision=excluded.static_decision,behavior=excluded.behavior,outcome=excluded.outcome',
                      (jid,kind,goal,state,utc(),static,behavior,str(result) if result.exists() else ''))
            count+=1
        except (OSError,ValueError,TypeError,sqlite3.Error) as exc:
            print('Kayit atlandi:',p.name,str(exc)[:120],flush=True)
    c.commit();return count
def status(c):
    scan(c)
    for state,n in c.execute('SELECT state,count(*) FROM tasks GROUP BY state ORDER BY state'):
        print(f'{state}: {n}')
    print('\nSON 8 GOREV')
    for row in c.execute('SELECT id,kind,state,static_decision,behavior FROM tasks ORDER BY id DESC LIMIT 8'):
        print(' | '.join(str(x or '-') for x in row))
    print('Veritabani:',DB)
def pid_alive(pid):
    if os.name!='nt':
        try:os.kill(pid,0);return True
        except OSError:return False
    # tasklist is a fixed system command; never contains generated/user code.
    try:
        r=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/FO','CSV','/NH'],capture_output=True,text=True,timeout=8)
        return r.returncode==0 and f'"{pid}"' in r.stdout
    except (OSError,subprocess.TimeoutExpired):return True # fail closed

def acquire():
    if LOCK.exists():
        try:
            old=int(LOCK.read_text(encoding='ascii').strip())
            if pid_alive(old):raise RuntimeError(f'V4 zaten calisiyor: PID {old}')
        except ValueError:raise RuntimeError('Kilit dosyasi bozuk; elle kontrol edin: '+str(LOCK))
        LOCK.unlink()
    fd=os.open(LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(fd,'w',encoding='ascii') as f:f.write(str(os.getpid()))
def release():
    try:
        if LOCK.exists() and LOCK.read_text(encoding='ascii').strip()==str(os.getpid()):LOCK.unlink()
    except OSError:pass

def serve(interval):
    v3=ROOT/'kado_birlesik_motor_v3.py'
    if not v3.is_file():raise RuntimeError('V3 dosyasi yok: '+str(v3))
    acquire();child=None
    try:
        with contextlib.closing(connect()) as c:
            scan(c)
            print('KADO V4 gorev merkezi aktif. V3 uretim motoru baslatiliyor.',flush=True)
            child=subprocess.Popen([sys.executable,'-u',str(v3)],cwd=str(ROOT))
            while True:
                scan(c)
                rc=child.poll()
                if rc is not None:
                    print(f'V3 motoru durdu (kod {rc}). Otomatik yeniden baslatilmadi.',flush=True)
                    return rc or 1
                time.sleep(interval)
    except KeyboardInterrupt:
        print('KADO V4 durduruluyor...',flush=True)
        return 0
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                print('Alt motor kapanmadi; PID:',child.pid,'manuel kontrol edin.',flush=True)
        release()
def selftest():
    import tempfile
    global DB,QUEUE,OUT
    old=(DB,QUEUE,OUT)
    try:
        with tempfile.TemporaryDirectory() as t:
            t=pathlib.Path(t);DB=t/'test.db';QUEUE=t/'q';OUT=t/'o';QUEUE.mkdir();OUT.mkdir()
            jid='test_001';(QUEUE/(jid+'.json')).write_text(json.dumps({'id':jid,'kind':'kod','goal':'topla'}),encoding='utf-8')
            with contextlib.closing(connect()) as c:
                assert scan(c)==1
                assert c.execute('SELECT state FROM tasks').fetchone()[0]=='json'
                (QUEUE/(jid+'.json')).rename(QUEUE/(jid+'.review'))
                d=OUT/jid;d.mkdir();(d/'SONUC.json').write_text(json.dumps({'statik_karar':'GECTI','davranis':{'durum':'GECTI'}}),encoding='utf-8')
                scan(c)
                assert c.execute('SELECT state,behavior FROM tasks').fetchone()==('review','GECTI')
                assert c.execute('SELECT count(*) FROM events').fetchone()[0]==2
        print('V4 SELFTEST 3/3 BASARILI: kayit, durum gecisi, sonuc aktarimi')
    finally:DB,QUEUE,OUT=old

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['baslat','durum','selftest']);ap.add_argument('--aralik',type=int,default=5)
    args=ap.parse_args()
    if args.command=='selftest':selftest()
    elif args.command=='durum':
        with contextlib.closing(connect()) as c:status(c)
    else:return serve(max(2,args.aralik))
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:print('HATA:',e,file=sys.stderr);sys.exit(1)
