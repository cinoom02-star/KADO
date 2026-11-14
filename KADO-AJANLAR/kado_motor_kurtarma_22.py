# -*- coding: utf-8 -*-
"""KADO 2.2 - one-file safe V4 recovery, diagnostics and optional Windows login startup.

Usage: python KADO_22_TEK_ADIM.py          (install and ensure once)
       python KADO_22_TEK_ADIM.py check    (read-only diagnosis)
       python KADO_22_TEK_ADIM.py ensure   (safely start if offline)
       python KADO_22_TEK_ADIM.py selftest
       python KADO_22_TEK_ADIM.py rollback (remove only 2.2 startup link)

Protects existing V3/V4 and KADO 2.1. Never retries failed jobs or deletes pending jobs.
"""
from __future__ import annotations
import argparse, csv, datetime, io, json, os, pathlib, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error, uuid

ROOT = pathlib.Path(os.environ.get('KADO_AGENTS_ROOT', r'C:\KADO\KADO-AJANLAR'))
NAME = 'kado_motor_kurtarma_22.py'
LOCK = 'kado_v4_motor.lock'
START = 'KADO_Motor_Guvenli_Baslat_22.cmd'
VERSION = '2.2.0'

def out(message):
    print(message, flush=True)

def py_exec(root):
    p = root / '.venv' / 'Scripts' / 'python.exe'
    return str(p if p.is_file() else sys.executable)

def startup_file():
    base=os.environ.get('APPDATA','')
    if not base: return None
    return pathlib.Path(base)/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'/START

def read_pid(path):
    try:
        txt=path.read_text(encoding='ascii').strip()
        if not txt.isdecimal() or not (0 < int(txt) < 4294967296):
            raise ValueError('invalid PID')
        return int(txt)
    except (OSError,UnicodeError,ValueError) as ex:
        raise RuntimeError('V4 kilidi okunamadi/bozuk; guvenlik icin degistirilmedi: '+str(ex)[:120])

def inspect_windows():
    """CIM distinguishes a dead PID from a reused PID; query errors are fatal."""
    if os.name!='nt':
        raise RuntimeError('Bu kurtarma yalnizca Windows icin; kilide dokunulmadi.')
    cmd=['powershell.exe','-NoProfile','-NonInteractive','-Command',
         '$ErrorActionPreference="Stop"; '
         '$p=Get-CimInstance Win32_Process -ErrorAction Stop | '
         'Where-Object { $_.Name -match "^(pythonw?|ollama)(\\.exe)?$" -or $_.CommandLine -match "kado_birlesik_motor_v[34]\\.py" }; '
         '@($p | Select-Object ProcessId,Name,CommandLine) | ConvertTo-Json -Compress -Depth 3']
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20,check=False)
    except (OSError,subprocess.TimeoutExpired) as ex:
        raise RuntimeError('Windows surec denetimi yapilamadi: '+str(ex)[:120])
    if p.returncode!=0:
        raise RuntimeError('Windows surec denetimi basarisiz; kilide dokunulmadi: '+p.stderr.strip()[:160])
    try:
        raw=json.loads(p.stdout.strip() or '[]')
        items=raw if isinstance(raw,list) else [raw] if isinstance(raw,dict) else []
        if not all(isinstance(x,dict) and 'ProcessId' in x for x in items):
            raise ValueError('beklenmeyen CIM cikti')
        return [{'pid':int(x['ProcessId']),'cmd':str(x.get('CommandLine') or ''),'name':str(x.get('Name') or '')} for x in items]
    except (ValueError,TypeError) as ex:
        raise RuntimeError('Surec listesi anlasilamadi; kilide dokunulmadi: '+str(ex)[:120])

def motor_processes(processes):
    r=[]
    for x in processes:
        cmd=x['cmd'].lower().replace('/','\\')
        if 'kado_birlesik_motor_v3.py' in cmd or 'kado_birlesik_motor_v4.py' in cmd:
            # Powershell process itself contains our CIM filter string; only Python can be motor.
            if x['name'].lower() in ('python.exe','pythonw.exe','py.exe'):
                r.append(x)
    return r

def lock_judgement(pid, processes):
    bypid={x['pid']:x for x in processes}
    motors=motor_processes(processes)
    live=bypid.get(pid)
    if live:
        if 'kado_birlesik_motor_v4.py' in live['cmd'].lower():
            return 'live_v4',motors
        return 'pid_reused',motors
    if motors:
        return 'another_motor',motors
    return 'stale',motors

def json_file(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError,UnicodeError):return default

def queue_snapshot(root):
    q=root/'kado_agent_motor'/'kuyruk'
    states={s:[] for s in ('.json','.working','.review','.done','.failed')}
    if not q.is_dir(): raise RuntimeError('Gorev kuyrugu bulunamadi: '+str(q))
    for p in q.iterdir():
        if p.is_file() and p.suffix in states:states[p.suffix].append(p)
    return states

def error_clues(root, limit=6):
    q=queue_snapshot(root)
    failed=sorted(q['.failed'],key=lambda x:x.stat().st_mtime,reverse=True)
    result=[]
    for p in failed[:limit]:
        base=root/'kado_agent_motor'/'ciktilar'/p.stem
        msgs=[]
        j=json_file(base/'SONUC.json',{})
        if isinstance(j,dict):
            for key in ('karar','hata','error','not','statik_karar'):
                v=j.get(key)
                if isinstance(v,str) and v.strip(): msgs.append(key+': '+v.strip().replace('\n',' ')[:120])
        for fname in ('INCELEME_GEREKLI.txt','DENETIM_HATASI.txt','denetim_3.txt','denetci_raporu.md'):
            f=base/fname
            if f.is_file():
                try:msgs.append(fname+': '+f.read_text(encoding='utf-8-sig',errors='replace')[:130].replace('\n',' '))
                except OSError:pass
        # Actual worker often writes the only error detail to gunluk.jsonl.
        logfile=root/'kado_agent_motor'/'gunluk.jsonl'
        if logfile.is_file() and not msgs:
            try:
                with logfile.open(encoding='utf-8-sig',errors='replace') as h:
                    for line in h:
                        if p.stem not in line:continue
                        e=json.loads(line)
                        if e.get('event') in ('failed','review_required') and e.get('error'):
                            msgs=[str(e['error'])[:240]]
            except (OSError,ValueError,TypeError):pass
        result.append((p.stem, ' | '.join(msgs)[:280] or 'Hata aciklamasi kaydedilmemis; kaynak belirlenemedi'))
    return result

def ollama_probe():
    url=os.environ.get('KADO_OLLAMA_URL','http://127.0.0.1:11434/api/generate')
    from urllib.parse import urlsplit
    u=urlsplit(url)
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1'):
        return False,'Ollama URL yerel degil; guvenlik icin otomatik baslatma yok.'
    endpoint=f'http://127.0.0.1:{u.port or 11434}/api/tags'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(endpoint,timeout=4) as h:
            if h.status!=200:return False,'Ollama yaniti basarisiz.'
            j=json.loads(h.read(2_000_000).decode('utf-8'))
    except Exception as e:
        return False,'Ollama yerel servisine baglanilamiyor: '+str(e)[:120]
    names=[str(x.get('name','')) for x in j.get('models',[]) if isinstance(x,dict)] if isinstance(j,dict) else []
    requested=os.environ.get('KADO_MODEL','qwen2.5:3b')
    ok=any(x==requested or x.split(':')[0]==requested and ':' not in requested for x in names)
    return (True, f'Ollama hazir, model: {requested}') if ok else (False, f'Ollama acik ama {requested!r} modeli kurulu degil. Mevcut modeller: {", ".join(names[:5]) or "yok"}.')

def process_state(root,processes):
    lock=root/LOCK
    if not lock.exists():
        return ('missing' if not motor_processes(processes) else 'unlocked_motor',None)
    pid=read_pid(lock)
    st,_=lock_judgement(pid,processes)
    return st,pid

def diagnose(root,processes=None):
    root=pathlib.Path(root)
    states=queue_snapshot(root)
    processes=inspect_windows() if processes is None else processes
    state,pid=process_state(root,processes)
    line=f'V4 motor: {state}'+(f' (PID {pid})' if pid else '')
    out(line)
    out('Gorevler: '+', '.join(f'{key[1:]}={len(value)}' for key,value in states.items()))
    for jid,msg in error_clues(root):out(f'GECMIS HATA {jid[-6:]}: {msg[:220]}')
    good,why=ollama_probe();out('Ollama: '+why)
    return state,good

def maybe_ollama(root):
    ok,msg=ollama_probe()
    if ok:return True,msg
    if 'acik ama' in msg:
        return False,msg  # Model missing: do not spawn another Ollama server.
    binary=shutil.which('ollama')
    if not binary:return False,msg+' Ollama komutu PATH icinde yok.'
    # Starting a local service does not download models, send messages, or execute queued jobs.
    log=root/'logs'/'kado22_ollama.log';log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('ab') as f:
        try:
            subprocess.Popen([binary,'serve'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,
                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
        except OSError as ex:return False,msg+' Ollama baslatilamadi: '+str(ex)[:100]
    for _ in range(12):
        time.sleep(1)
        ok,msg=ollama_probe()
        if ok:return True,msg
    return False,msg

def ensure(root=ROOT,allow_start_ollama=True):
    root=pathlib.Path(root)
    for f in ('kado_birlesik_motor_v3.py','kado_birlesik_motor_v4.py','kado_agent_motor/kado_motor.py'):
        if not (root/f).is_file():raise RuntimeError('Mevcut motor dosyasi eksik: '+f)
    states=queue_snapshot(root)
    processes=inspect_windows()  # fail closed if process inspection is unavailable
    state,pid=process_state(root,processes)
    if state=='live_v4':
        out(f'V4 zaten calisiyor (PID {pid}). Ikinci motor baslatilmadi.')
        return 0
    if state in ('pid_reused','another_motor','unlocked_motor'):
        out('GUVENLI DURDURULDU: '+state+'. Motor/kilit elle dogrulanmali, degisiklik yok.')
        return 3
    if len(states['.working']):
        out('GUVENLI DURDURULDU: .working gorev var; calisan/yarim kalmis gorev olabilir. Otomatik tekrar yok.')
        return 3
    if len(states['.json'])==0:
        out('Bekleyen gorev yok. Motorun calismasini saglamak icin baslatilabilir; ancak yeni is uretmiyoruz.')
    ready,msg=ollama_probe()
    if not ready and allow_start_ollama:ready,msg=maybe_ollama(root)
    if not ready:
        out('MOTOR BASLATILMADI: '+msg)
        out('Bekleyen gorev korundu; Ollama ve dogru yerel model hazir olmadan baslatmak hata uretebilir.')
        return 4
    out('Ollama: '+msg)
    lock=root/LOCK
    backup=None
    if state=='stale':
        # Recheck immediately before touching the lock; PID reuse is treated as unsafe.
        newproc=inspect_windows()
        cur,curpid=process_state(root,newproc)
        if cur!='stale' or curpid!=pid:
            out('GUVENLI DURDURULDU: kilit/surec durumu degisti; dokunulmadi.')
            return 3
        stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        folder=root/'yedekler'/'kado22_eski_kilit';folder.mkdir(parents=True,exist_ok=True)
        backup=folder/f'{stamp}_{uuid.uuid4().hex[:6]}_{LOCK}'
        os.replace(lock,backup)
        out('Eski kilit silinmedi, YEDEKLENDI: '+str(backup))
    # If process list or lock has changed, V4's own exclusive lock will refuse a second instance.
    python=py_exec(root)
    log=root/'logs'/('kado22_v4_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.log')
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('ab') as f:
        try:
            child=subprocess.Popen([python,'-u',str(root/'kado_birlesik_motor_v4.py'),'baslat'],
                cwd=str(root),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NO_WINDOW',0))
        except OSError as e:
            if backup and not lock.exists():os.replace(backup,lock)
            out('V4 baslatilamadi: '+str(e)[:150]);return 5
    for _ in range(7):
        time.sleep(1)
        if child.poll() is not None:break
    try:recorded=read_pid(lock) if lock.exists() else None
    except RuntimeError:recorded=None
    if child.poll() is None and recorded==child.pid:
        out(f'V4 BASLATILDI: PID {child.pid}. V3 alt motoru V4 tarafindan yonetiliyor.')
        out('LOG: '+str(log))
        out('Not: Gorevlerin tamamlanmasi ve kalitesi bu adimla garanti edilmez; 2.1 izleyici sonucunu raporlar.')
        return 0
    out('V4 saglik kontrolunu gecemedi; LOG: '+str(log))
    if backup and not lock.exists() and child.poll() is not None:
        os.replace(backup,lock)
        out('Onceki kilit geri yuklendi.')
    return 5

def install(root=ROOT):
    root=pathlib.Path(root)
    selftest()  # Non-mutating isolated tests before touching the installation.
    required=['kado_birlesik_motor_v3.py','kado_birlesik_motor_v4.py','kado_agent_motor/kado_motor.py','kado_izleme_21.py','kado_ceo.py']
    for name in required:
        if not (root/name).is_file():raise RuntimeError('Kurulum icin gerekli dosya yok: '+name)
    target=root/NAME
    source=pathlib.Path(__file__).resolve()
    if source!=target.resolve():
        if target.exists():
            folder=root/'yedekler'/'kado22_dosya';folder.mkdir(parents=True,exist_ok=True)
            bak=folder/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:5]+'.py')
            shutil.copy2(target,bak);out('ONCEKI KURTARMA ARACI YEDEGI: '+str(bak))
        tmp=target.with_name(target.name+'.'+uuid.uuid4().hex[:6]+'.tmp')
        shutil.copy2(source,tmp);os.replace(tmp,target)
    (root/'logs').mkdir(parents=True,exist_ok=True)
    s=startup_file()
    if s and s.parent.is_dir():
        exe=py_exec(root)
        line='@echo off\r\n"'+exe+'" "'+str(target)+'" ensure >>"'+str(root/'logs'/'kado22_baslangic.log')+'" 2>&1\r\n'
        if not s.exists() or s.read_text(encoding='utf-8',errors='replace')!=line:
            s.write_text(line,encoding='utf-8')
        out('WINDOWS BASLANGICI: '+str(s))
    out('KADO 2.2 kuruldu. V4, V3, CEO, ses, WhatsApp ve gorev dosyalari degistirilmedi.')
    return ensure(root)

def rollback(root=ROOT):
    s=startup_file()
    if s and s.is_file():
        content=s.read_text(encoding='utf-8',errors='replace')
        if NAME not in content:raise RuntimeError('Baslangic dosyasi baska amaca hizmet ediyor; silinmedi')
        s.unlink();out('2.2 Windows baslangici kaldirildi.')
    else:out('2.2 baslangic kaydi yok.')
    out('Gorevler, motor ve loglar korunuyor. Aktif V4 durdurulmadi.')
    return 0

def selftest():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t);q=root/'kado_agent_motor'/'kuyruk';q.mkdir(parents=True)
        job={'id':'a1','kind':'arastirma','goal':'Ara'}
        (q/'a1.json').write_text(json.dumps(job),encoding='utf-8')
        assert len(queue_snapshot(root)['.json'])==1
        l=root/LOCK;l.write_text('123',encoding='ascii');assert read_pid(l)==123
        assert lock_judgement(123,[])[0]=='stale'
        assert lock_judgement(123,[{'pid':123,'cmd':'python.exe something.py','name':'python.exe'}])[0]=='pid_reused'
        assert lock_judgement(123,[{'pid':123,'cmd':'python.exe C:\\KADO\\kado_birlesik_motor_v4.py baslat','name':'python.exe'}])[0]=='live_v4'
        assert lock_judgement(123,[{'pid':77,'cmd':'python.exe kado_birlesik_motor_v3.py','name':'python.exe'}])[0]=='another_motor'
        assert motor_processes([{'pid':4,'cmd':'powershell ...kado_birlesik_motor_v4.py','name':'powershell.exe'}])==[]
        assert process_state(root,[])[0]=='stale'
        l.unlink();assert process_state(root,[])[0]=='missing'
        (q/'a1.json').rename(q/'a1.failed')
        assert len(error_clues(root))==1
        (root/'kado_agent_motor'/'gunluk.jsonl').write_text(json.dumps({'id':'a1','event':'failed','error':'Ollama baglanti hatasi'})+'\n',encoding='utf-8')
        assert 'Ollama baglanti' in error_clues(root)[0][1]
    out('SELFTEST: 9/9 BASARILI (kilit, PID, baska motor, kuyruk, hata gunlugu).')
    return 0

def main():
    parser=argparse.ArgumentParser(description='KADO 2.2 tek dosya guvenli V4 motor kurtarma')
    parser.add_argument('command',nargs='?',default='install',choices=['install','check','ensure','selftest','rollback'])
    a=parser.parse_args()
    if a.command=='selftest':return selftest()
    if a.command=='check':diagnose(ROOT);return 0
    if a.command=='ensure':return ensure(ROOT)
    if a.command=='rollback':return rollback(ROOT)
    return install(ROOT)

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        out('GUVENLI DURDURULDU: '+str(e)[:300]);sys.exit(2)
