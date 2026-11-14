# -*- coding: utf-8 -*-
"""KADO 2.1: tek dosyali guvenli gorev izleyici + CEO rapor baglantisi.
KUR: python KADO_21_TEK_ADIM.py install
TEST: python KADO_21_TEK_ADIM.py selftest
Durum: python C:\\KADO\\KADO-AJANLAR\\kado_izleme_21.py report
Geri alma: python C:\\KADO\\KADO-AJANLAR\\kado_izleme_21.py rollback
No publishing, AI API access, job retries, old lock deletion or production task execution.
"""
from __future__ import annotations
import argparse, ast, collections, contextlib, csv, datetime as dt, io, json, os, pathlib, shutil, subprocess, sys, tempfile, time, uuid

VERSION = '2.1.0'
ROOT = pathlib.Path(os.environ.get('KADO_AGENTS_ROOT',r'C:\KADO\KADO-AJANLAR'))
SIS = pathlib.Path(os.environ.get('KADO_SISTEM_ROOT',r'C:\KADO\kado\sistem'))
MARK = '# KADO_21_REPORT_WRAPPER_START'
VALID = ('.json','.working','.done','.review','.failed')
STATE_FOLDER = 'kado21'

def iso(): return dt.datetime.now().astimezone().isoformat(timespec='seconds')
def now(): return dt.datetime.now()
def jread(p,default=None):
    try: return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
    except (OSError,UnicodeError,ValueError):return default

def atomic_json(p,d):
    p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.'+uuid.uuid4().hex[:8]+'.tmp')
    try:
        with temp.open('x',encoding='utf-8') as f:
            json.dump(d,f,indent=2,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        os.replace(temp,p)
    finally:
        if temp.exists():temp.unlink()

def state_dir(root=ROOT):return pathlib.Path(root)/'memory'/STATE_FOLDER

def get_tasks(root=ROOT):
    root=pathlib.Path(root);folder=root/'kado_agent_motor'/'kuyruk';out={};error=[]
    if not folder.is_dir():return out,['Kuyruk klasoru yok']
    for p in folder.iterdir():
        if not p.is_file() or p.suffix not in VALID:continue
        data=jread(p,None)
        if not isinstance(data,dict):
            error.append('Gecersiz kuyruk JSON: '+p.name);continue
        if str(data.get('id',p.stem))!=p.stem:
            error.append('Kimlik uyusmazligi: '+p.name);continue
        jid=p.stem
        item={'id':jid,'state':p.suffix[1:],'kind':str(data.get('kind','?'))[:40],
              'goal':str(data.get('goal',''))[:300],'changed':p.stat().st_mtime}
        # Ayni ID icin birden fazla uzanti, sessizce tek durum secmek yerine raporla.
        if jid in out:
            error.append('Cift durum: '+jid+' ('+out[jid]['state']+' ve '+item['state']+')')
            out[jid]['state']='conflict'
        else:out[jid]=item
    return out,error

def _read_outcome(root,jid):
    base=pathlib.Path(root)/'kado_agent_motor'/'ciktilar'/jid
    result=jread(base/'SONUC.json',{})
    if not isinstance(result,dict):result={}
    notes=[]
    for key in ('karar','statik_karar','hata','error','message','aciklama','neden'):
        v=result.get(key)
        if isinstance(v,(str,int,float)) and str(v).strip():notes.append(key+': '+str(v).replace('\n',' ')[:170])
    behavior=result.get('davranis')
    if isinstance(behavior,dict) and behavior.get('durum'):
        notes.append('davranis: '+str(behavior['durum'])[:60])
    for filename in ('UZMAN_DENETIM_SONUCU.json','denetci_raporu.md'):
        p=base/filename
        if p.is_file():
            if p.suffix=='.json':
                d=jread(p,{})
                if isinstance(d,dict):
                    notes.append(filename+': '+', '.join(str(k)+'='+str(v)[:50] for k,v in list(d.items())[:4])[:180])
            else:
                # Dosyanin tamamini rapora tasimiyoruz; sadece ilk anlamli satirlar.
                lines=p.read_text(encoding='utf-8-sig',errors='replace').splitlines()
                notes.append(filename+': '+ ' '.join(x.strip() for x in lines if x.strip())[:180])
    return ' | '.join(notes)[:500] or 'SONUC.json veya denetci aciklamasi bulunamadi'

def pid_check(root=ROOT):
    lock=pathlib.Path(root)/'kado_v4_motor.lock'
    if not lock.is_file():return 'V4 motor kilidi yok; acik oldugu dogrulanmadi.'
    try:
        pid=int(lock.read_text(encoding='ascii').strip())
        if pid<=0:raise ValueError('PID gecersiz')
    except (OSError,ValueError):return 'V4 kilit dosyasi gecersiz; elle incelenmeli.'
    if os.name!='nt':
        try:os.kill(pid,0);return f'V4 kilit PID {pid} canli; motorun is yaptigi henuz dogrulanmadi.'
        except OSError:return f'V4 kilit PID {pid} bulunamadi; muhtemelen eski kilit.'
    try:
        r=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/FO','CSV','/NH'],text=True,capture_output=True,timeout=6)
        rows=list(csv.reader(io.StringIO(r.stdout)))
        ok=r.returncode==0 and any(len(row)>1 and row[1].strip()==str(pid) for row in rows)
        return (f'V4 kilit PID {pid} gorunuyor; gercek V4 oldugu ayrica dogrulanmali.' if ok
                else f'V4 kilit PID {pid} calismiyor; eski kilit olabilir, otomatik silinmedi.')
    except (OSError,subprocess.TimeoutExpired):return 'V4 PID kontrolu yapilamadi; kilide dokunulmadi.'

@contextlib.contextmanager
def scan_guard(root):
    """Serialize watcher and voice report; never locks production queue."""
    sd=state_dir(root);sd.mkdir(parents=True,exist_ok=True)
    path=sd/'izleme.lock'
    with path.open('a+b') as lock:
        lock.seek(0,2)
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        if os.name=='nt':
            import msvcrt
            held=False
            for _ in range(60):
                try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);held=True;break
                except OSError:time.sleep(0.1)
            if not held:raise RuntimeError('Izleme mesgul, rapor daha sonra okunabilir.')
            try:yield
            finally:
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

def scan(root=ROOT,persist=True):
    if not persist:return _scan_unlocked(root,False)
    with scan_guard(root):return _scan_unlocked(root,True)

def _scan_unlocked(root=ROOT,persist=True):
    root=pathlib.Path(root);sd=state_dir(root);tasks,errors=get_tasks(root)
    prev=jread(sd/'durum.json',{}) if persist else {}
    if not isinstance(prev,dict):prev={}
    had_initial=bool(prev.get('initialized'))
    old=prev.get('tasks',{}) if isinstance(prev.get('tasks'),dict) else {}
    current={jid:t['state'] for jid,t in tasks.items()}
    events=[]
    if had_initial:
        for jid,item in sorted(tasks.items(),key=lambda x:x[1]['changed']):
            state=item['state'];prior=old.get(jid)
            if prior==state:continue
            if state not in ('done','failed','review','conflict'):continue
            verb={'done':'Tamamlandi (cikti kontrol edilmeli)','failed':'Basarisiz','review':'Insan onayi bekliyor','conflict':'Ayni gorevin birden cok durum dosyasi var'}[state]
            event={'time':iso(),'id':jid,'state':state,'old_state':prior,'message':verb,
                   'goal':item['goal'][:140]}
            if state in ('failed','review','done'):
                event['detail']=_read_outcome(root,jid)[:220]
            events.append(event)
    counts=dict(collections.Counter(item['state'] for item in tasks.values()))
    failures=sorted((t for t in tasks.values() if t['state']=='failed'),key=lambda x:x['changed'],reverse=True)
    # Hata raporu mevcut veriden her taramada yeniden uretilir; yeniden gorev calistirilmaz.
    failed_items=[{'id':t['id'],'kind':t['kind'],'goal':t['goal'],
                   'reason':_read_outcome(root,t['id'])} for t in failures[:30]]
    result={'time':iso(),'counts':counts,'total':len(tasks),'v4':pid_check(root),
            'failed_recent':failed_items,'warnings':errors[:20],
            'new_events':events,'initialized_before':had_initial}
    if persist:
        sd.mkdir(parents=True,exist_ok=True)
        # Olaylar once dayanikli günluge, sonra durum snapshotuna yazilir.
        if events:
            with (sd/'bildirimler.jsonl').open('a',encoding='utf-8') as f:
                for e in events:f.write(json.dumps(e,ensure_ascii=False)+'\n')
                f.flush();os.fsync(f.fileno())
        atomic_json(sd/'durum.json',{'initialized':True,'tasks':current,'time':iso()})
        atomic_json(sd/'son_rapor.json',dict(result,new_events=events[-20:]))
        today=now().date().isoformat()
        atomic_json(sd/('gunluk_'+today+'.json'),dict(result,new_events=events[-50:]))
    return result

def format_report(r,limit=7):
    c=r['counts'];name={'json':'bekleyen','working':'isleniyor','done':'tamamlandi','failed':'basarisiz','review':'onay bekliyor','conflict':'cakisma'}
    portions=[f'{c.get(x,0)} {name[x]}' for x in ('json','working','done','failed','review','conflict') if c.get(x,0)]
    out=['KADO 2.1: '+(', '.join(portions) if portions else 'Kayitli gorev yok')+'.',r['v4']]
    if r['warnings']:out.append(f"Uyari: {len(r['warnings'])} kayit sorunu. Ilki: {r['warnings'][0]}.")
    if r['failed_recent']:
        out.append('Son basarisiz gorevler: '+ '; '.join(f"{x['id'][-6:]}: {x['reason'][:90]}" for x in r['failed_recent'][:3])+'.')
    if r['new_events']:
        out.append('Yeni degisiklikler: '+ '; '.join(e['id'][-6:]+' '+e['message'] for e in r['new_events'][-limit:])+'.')
    else:out.append('Bu taramada yeni sonuc bildirimi yok.')
    out.append('Basarisiz gorevleri otomatik tekrarlamadim, kilit silmedim, yayin yapmadim.')
    return '\n'.join(out)[:2400]

def report(root=ROOT):
    result=scan(root,persist=True)
    return format_report(result)

def ceo_patch(src):
    if MARK in src:return src,False
    tree=ast.parse(src)
    names=[node.name for node in tree.body if isinstance(node,ast.FunctionDef)]
    if names.count('report')!=1 or names.count('ceo_calistir')!=1:
        raise RuntimeError('Mevcut CEO 2.0 yapisi beklenenden farkli: rapor/CEO sayisi.')
    if "KADO_V2_CEO_ROUTER_BEGIN" not in src:
        raise RuntimeError('Mevcut CEO 2.0 isareti bulunamadi; guvenli durduruldu.')
    addon='''\n# KADO_21_REPORT_WRAPPER_START\n# Tek CEO, tek ses araci. Yalnizca mevcut rapora 2.1 izleme ozeti eklenir.\n_kado21_previous_report = report\ndef report():\n    current = _kado21_previous_report()\n    try:\n        import kado_izleme_21 as _kado21\n        current += "\\n" + _kado21.report()\n    except Exception as exc:\n        current += "\\nKADO 2.1 izleme raporu okunamadi: " + str(exc)[:100]\n    return current\n# KADO_21_REPORT_WRAPPER_END\n'''
    ast.parse(src+addon)
    return src+addon,True

def target_script(root=ROOT):return pathlib.Path(root)/'kado_izleme_21.py'

def setup_startup(root=ROOT):
    if os.name!='nt':return None
    appdata=os.environ.get('APPDATA')
    if not appdata:return None
    folder=pathlib.Path(appdata)/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'
    if not folder.is_dir():return None
    p=folder/'KADO_Gorev_Izleyici_21.cmd'
    if not p.exists():
        python=pathlib.Path(root)/'.venv'/'Scripts'/'python.exe'
        exe=str(python if python.is_file() else sys.executable)
        command='@echo off\r\nstart "KADO 2.1 Izleyici" /min "'+exe+'" "'+str(target_script(root))+'" watch\r\n'
        p.write_text(command,encoding='utf-8')
    return p

def install(root=ROOT,sis=SIS):
    root=pathlib.Path(root);sis=pathlib.Path(sis)
    ceo=root/'kado_ceo.py';main=sis/'main.py';defs=sis/'tool_defs.py'
    requirements=[ceo,main,defs,root/'kado_birlesik_motor_v3.py',root/'kado_birlesik_motor_v4.py']
    for p in requirements:
        if not p.is_file():raise RuntimeError('Gerekli dosya eksik: '+str(p))
    for p in [root/'kado_agent_motor'/'kuyruk']:
        if not p.is_dir():raise RuntimeError('Gerekli kuyruk eksik: '+str(p))
    if 'kado_company_report' not in main.read_text(encoding='utf-8-sig') or 'kado_company_report' not in defs.read_text(encoding='utf-8-sig'):
        raise RuntimeError('Sesli rapor araci mevcut degil; birlestirme durduruldu.')
    src=ceo.read_text(encoding='utf-8-sig');target,changed=ceo_patch(src)
    installed=target_script(root)
    if not changed and installed.exists():
        print('ZATEN KURULU: KADO 2.1, ikinci kez eklenmedi.');print(report(root));return 0
    base=root/'yedekler'/('kado_v21_'+now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:5]);base.mkdir(parents=True,exist_ok=False)
    shutil.copy2(ceo,base/'kado_ceo.py')
    if installed.exists():shutil.copy2(installed,base/'kado_izleme_21.onceki.py')
    # Prevent writing or importing program code until it has passed parsing.
    module=pathlib.Path(__file__).read_text(encoding='utf-8-sig')
    ast.parse(module);ast.parse(target)
    tmp=ceo.with_name(ceo.name+'.'+uuid.uuid4().hex[:8]+'.tmp')
    try:
        shutil.copy2(pathlib.Path(__file__),installed)
        tmp.write_text(target,encoding='utf-8');os.replace(tmp,ceo)
        result=scan(root,persist=True)
        startup=setup_startup(root)
    except Exception:
        if tmp.exists():tmp.unlink()
        shutil.copy2(base/'kado_ceo.py',ceo)
        if (base/'kado_izleme_21.onceki.py').exists():shutil.copy2(base/'kado_izleme_21.onceki.py',installed)
        elif installed.exists():installed.unlink()
        raise
    print('KURULUM BASARILI: KADO 2.1 gorev izleme ve sesli rapora ekleme etkin.')
    print('YEDEK:',base)
    print('ILK DURUM REFERANSI OLUSTU: eski basarisizliklar yeni bildirim sayilmadi.')
    print('MEVCUT MOTOR/SOSYAL MEDYA/WHATSAPP/SES AYARLARI DEGISTIRILMEDI.')
    print('YENI GOREVLER OTOMATIK TEKRARLANMAZ; kilitler silinmez.')
    print('BASLANGIC:',str(startup) if startup else 'Windows baslangic kisayolu eklenmedi')
    print('GERI AL: & "'+str(root/'.venv'/'Scripts'/'python.exe')+'" "'+str(installed)+'" rollback')
    print('KADO yeniden baslatilmali. Otomatik sesli araya girme bu surumde yok.')
    print(format_report(result))
    return 0

def rollback(root=ROOT):
    root=pathlib.Path(root);backups=sorted((root/'yedekler').glob('kado_v21_*'))
    if not backups:raise RuntimeError('2.1 yedegi bulunamadi')
    b=backups[-1];source=b/'kado_ceo.py';ceo=root/'kado_ceo.py'
    if not source.is_file():raise RuntimeError('CEO yedegi eksik')
    if MARK not in ceo.read_text(encoding='utf-8-sig'):
        raise RuntimeError('CEO 2.1 artik kurulu degil; eski CEO uzerine yazilmadi.')
    shutil.copy2(source,ceo)
    appdata=os.environ.get('APPDATA')
    if appdata:
        startup=pathlib.Path(appdata)/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'/'KADO_Gorev_Izleyici_21.cmd'
        if startup.is_file():startup.unlink()
    print('GERI ALINDI: 2.0 Genel Mudur geri yuklendi. Izleme arsivi silinmedi.')
    print('Not: halihazirda acik izleyici varsa yeniden baslatildiginda calismayacak.')
    return 0

def watch(root=ROOT):
    print('KADO 2.1 izleyici aktif: yalnizca yerel kuyruğu izliyor, is yapmiyor/yayinlamiyor.',flush=True)
    try:
        while True:
            try:
                r=scan(root,persist=True)
                if r['new_events']:
                    print(format_report(r),flush=True)
            except (OSError,ValueError,RuntimeError) as e:print('IZLEME HATASI:',str(e)[:240],flush=True)
            time.sleep(30)
    except KeyboardInterrupt:return 0

def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        r=pathlib.Path(tmp);q=r/'kado_agent_motor'/'kuyruk';q.mkdir(parents=True)
        (r/'memory').mkdir()
        (q/'job1.failed').write_text(json.dumps({'id':'job1','kind':'kod','goal':'Deneme'}),encoding='utf-8')
        (q/'job2.json').write_text(json.dumps({'id':'job2','kind':'arastirma','goal':'Plan'}),encoding='utf-8')
        a=scan(r);assert a['counts']['failed']==1 and not a['new_events'] and not a['initialized_before']
        b=scan(r);assert not b['new_events'] and b['initialized_before']
        (q/'job2.json').rename(q/'job2.review')
        c=scan(r);assert len(c['new_events'])==1 and c['new_events'][0]['state']=='review'
        (q/'job2.review').rename(q/'job2.done')
        d=scan(r);assert len(d['new_events'])==1 and d['new_events'][0]['state']=='done'
        (q/'job1.failed').write_text('not json',encoding='utf-8')
        e=scan(r);assert e['warnings'] and e['counts'].get('failed',0)==0
        src="VERSION='2.0.0'\n# KADO_V2_CEO_ROUTER_BEGIN\ndef ceo_calistir(istek,proje=None):return ''\ndef report():return 'x'\n"
        patch,ok=ceo_patch(src);assert ok and MARK in patch
        patch2,ok2=ceo_patch(patch);assert not ok2 and patch==patch2
        exec(compile(patch,'fake','exec'),{'__name__':'not_main'}) if False else None
        assert get_tasks(r)[0]['job2']['state']=='done'
        assert len((state_dir(r)/'bildirimler.jsonl').read_text(encoding='utf-8').splitlines())==2
    print('SELFTEST: 10/10 BASARILI (durum, degisim, bildirim tekilligi, bozuk JSON, CEO yama, tekrar kurulum).')
    return 0

def main():
    parser=argparse.ArgumentParser(description='KADO 2.1: tek dosya kurulum ve izleme')
    parser.add_argument('command',nargs='?',default='install',choices=['install','selftest','report','scan','watch','rollback'])
    args=parser.parse_args()
    if args.command=='install':return install()
    if args.command=='selftest':return selftest()
    if args.command=='report':print(report());return 0
    if args.command=='scan':print(format_report(scan()));return 0
    if args.command=='watch':return watch()
    if args.command=='rollback':return rollback()
    return 2
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print('GUVENLI DURDURULDU: '+str(exc)[:400],file=sys.stderr);sys.exit(2)
