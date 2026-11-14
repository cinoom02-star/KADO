# -*- coding: utf-8 -*-
"""KADO Birlesik Merkez 1.0 - tek dosyali, stdlib-only Windows kurulumu.
Kullanim: py -3 KADO_TEK_KURULUM.py install
             py -3 KADO_TEK_KURULUM.py selftest
Kurulum sonrasinda ayni kod C:/KADO/KADO-AJANLAR/kado_ceo.py olarak kullanilir.
Sinir: Sosyal medyaya otomatik yayin veya hesap acma YOK; resmi API yetkileri gerekir.
"""
from __future__ import annotations
import argparse, ast, datetime as dt, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile, time, uuid

DEFAULT_ROOT = pathlib.Path(r'C:\KADO\KADO-AJANLAR')
DEFAULT_SISTEM = pathlib.Path(r'C:\KADO\kado\sistem')
VERSION='2.0.0'
TOOL_MARKER='KADO_UNIFIED_20261111_V1'
KINDS=('arastirma','kod','paylasim')

def root():return pathlib.Path(os.environ.get('KADO_AGENTS_ROOT',str(DEFAULT_ROOT)))
def sistem():return pathlib.Path(os.environ.get('KADO_SISTEM_ROOT',str(DEFAULT_SISTEM)))
def qdir():return root()/'kado_agent_motor'/'kuyruk'
def state_dir():return root()/'memory'/'kado_growth'
def iso():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def today():return dt.datetime.now().date().isoformat()
def json_read(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError,UnicodeError):return default

def atomic_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex[:8]+'.tmp')
    try:
        with tmp.open('x',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def project_names():
    d=json_read(root()/'projeler.json',[])
    if isinstance(d,dict):d=d.get('projeler',[])
    return [str(x['ad']) for x in d if isinstance(x,dict) and x.get('ad')] if isinstance(d,list) else []

def resolve_project(text,explicit=None):
    names=project_names()
    if explicit:
        m=[x for x in names if x.casefold()==str(explicit).strip().casefold()]
        if len(m)==1:return m[0]
        raise ValueError('Proje kayitli degil: '+str(explicit))
    m=[x for x in names if x.casefold() in text.casefold()]
    if len(m)==1:return m[0]
    if len(m)>1:raise ValueError('Birden cok proje bulundu; proje adini acik belirt.')
    raise ValueError('Proje adi gerekli. Kayitli projeler: '+', '.join(names))

def kind_for(text):
    s=text.casefold()
    if any(w in s for w in ('instagram','tiktok','youtube','threads','influencer','reels','sosyal medya','paylasim','gonderi','içerik','icerik','video','tanitim','tanıtım')):return 'paylasim'
    if any(w in s for w in ('kod','python','yazilim','yazılım','hata duzelt','hata düzelt','uygulama geliştir','uygulama gelistir','fonksiyon')):return 'kod'
    if any(w in s for w in ('araştır','arastir','incele','analiz','rakip','pazar','fikir','araştırma')):return 'arastirma'
    raise ValueError('Gorev turu acik degil. Arastirma, kod ya da sosyal medya uretimi iste.')

def ensure_queue():
    for name in ('kado_birlesik_motor_v3.py','kado_birlesik_motor_v4.py','kado_agent_motor/kado_motor.py'):
        if not (root()/name).is_file():raise RuntimeError('Mevcut motor dosyasi eksik: '+name)
    if not qdir().is_dir():raise RuntimeError('Mevcut kuyruk klasoru bulunamadi. Yeni motor olusturulmaz.')

def queue_task(kind,goal,deterministic=None):
    if kind not in KINDS:raise ValueError('Mevcut motor bu gorevi desteklemiyor: '+kind)
    goal=' '.join(str(goal).split())
    if not 8<=len(goal)<=2000:raise ValueError('Gorev 8-2000 karakter olmali')
    ensure_queue()
    jid=deterministic or dt.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    if not jid.replace('_','').isalnum():raise ValueError('Gecersiz gorev kimligi')
    if deterministic:
        if any((qdir()/(jid+ext)).exists() for ext in ('.json','.working','.done','.review','.failed')):
            return jid,False
    p=qdir()/(jid+'.json')
    with p.open('x',encoding='utf-8') as f:
        json.dump({'id':jid,'kind':kind,'goal':goal},f,ensure_ascii=False)
        f.flush();os.fsync(f.fileno())
    return jid,True


# KADO_V2_CEO_ROUTER_BEGIN
# Tek CEO: sesli araclarin kullandigi ceo_calistir burada guvenli sekilde yenilenir.
import re as _v2re
import urllib.request as _v2url

def _v2_norm(text):
    return str(text or '').casefold().translate(str.maketrans('çğıöşü','cgiosu'))

def _v2_route(request):
    s=_v2_norm(request)
    # Arastirma/kod niyeti, metinde sosyal ag gecse bile once gelir.
    if any(x in s for x in ('arastir','rakip','pazar analizi','trend analizi','incele','karsilastir','rekabet')):
        return 'arastirma'
    if any(x in s for x in ('kod yaz','python kod','fonksiyon yaz','yazilim gelistir','hata duzelt','bug duzelt','uygulama gelistir')):
        return 'kod'
    if any(x in s for x in ('onay bekleyen','bekleyen paket','paketleri say')):return 'paketler'
    if any(x in s for x in ('genel durum','sirket durum','gorev durum','gorev rapor','rapor ver','neler yapildi','ne yaptik')):
        return 'rapor'
    if any(x in s for x in ('takvim olustur','icerik takvimi','influencer takvimi')):return 'takvim'
    if any(x in s for x in ('sanal influencer baslat','influencer projesini baslat','karakter kimligini olustur')):return 'karakter'
    if any(x in s for x in ('tanitim paket','reklam metni','magaza aciklama','influencer mesaj','lansman metni')):
        return 'tanitim'
    if any(x in s for x in ('video','reels','shorts','icerik','gonderi','paylasim','instagram','tiktok','youtube','animasyon')):
        return 'icerik'
    if 'rapor' in s or 'durum' in s:return 'rapor'
    return None

def _v2_bridge():
    import importlib as _imp
    return _imp.import_module('kado_ses_icerik_koprusu')

def _v2_motor_state():
    lock=root()/'kado_v4_motor.lock'
    if not lock.is_file():return 'V4 motorunun acik oldugu dogrulanmadi (kilit yok).'
    try:
        pid=int(lock.read_text(encoding='ascii').strip())
        if pid<=0:return 'V4 kilit kaydi gecersiz.'
        if os.name=='nt':
            r=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/FO','CSV','/NH'],capture_output=True,text=True,timeout=5)
            ok=r.returncode==0 and f'"{pid}"' in r.stdout
        else:
            try:os.kill(pid,0);ok=True
            except OSError:ok=False
        return (f'V4 kilit PID {pid} calisiyor (motor sagligi ayri test ister).' if ok
                else f'V4 kilit PID {pid} calismiyor; kuyruktaki islerin islendigi dogrulanmadi.')
    except (ValueError,OSError,subprocess.TimeoutExpired) as exc:
        return 'V4 canlilik kontrolu yapilamadi: '+str(exc)[:75]

def _v2_ollama():
    try:
        with _v2url.urlopen('http://127.0.0.1:11434/api/tags',timeout=2) as r:
            return r.status==200
    except Exception:return False

def _v2_tanitim(project):
    exe=root()/ 'kado_tanitim_paketi.py'
    if not exe.is_file():return 'Tanitim modulu bulunamadi; gorev baslatilmadi.'
    if not _v2_ollama():return 'Ollama yerel model servisi acik degil. Tanitim baslatilmadi, tamamlandi denmedi.'
    project_info=next((p for p in (json_read(root()/'projeler.json',[]) or []) if isinstance(p,dict) and p.get('ad')==project),{})
    target=str(project_info.get('hedef','')).strip()
    if len(target)<12:return 'Proje hedefi eksik. Tanitim baslatilmadi.'
    logdir=root()/'logs';logdir.mkdir(exist_ok=True)
    stamp=dt.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]
    logfile=logdir/('ceo_tanitim_'+stamp+'.log')
    try:
        with logfile.open('ab') as out:
            child=subprocess.Popen([default_python(),str(exe),project,target,'--asama','cikis-oncesi'],
                cwd=str(root()),stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,ValueError) as e:return 'Tanitim baslatilamadi: '+str(e)[:120]
    return (f'{project} icin tanitim uretim sureci baslatildi (PID {child.pid}). '
            'Henuz tamamlanmadi. Denetci ve insan onayi kontrol edilmeli, otomatik yayin yok. '
            'Islem gunlugu: '+str(logfile))

def ceo_calistir(istek,proje=None):
    try:
        text=' '.join(str(istek or '').split())
        if not text:return 'Hangi gorevi yapmami istedigini soyle.'
        task=_v2_route(text)
        if task is None:return 'Gorevi netlestir: arastirma, kod, icerik, tanitim veya rapor iste.'
        if task=='rapor':
            output=report()+'\n'+_v2_motor_state()
            try:output+='\nIcerik: '+_v2_bridge().durum()
            except (ImportError,AttributeError,RuntimeError) as exc:output+='\nIcerik durumu okunamadi: '+str(exc)[:80]
            return output[:3300]
        if task=='paketler':
            bridge=_v2_bridge()
            return bridge.paketler(bridge.bekleyenler())
        if task=='karakter':return influencer_init()
        if task=='takvim':return influencer_plan(14)
        project=resolve_project(text,proje)
        if task=='icerik':
            bridge=_v2_bridge()
            return bridge.baslat(project, bool('yeniden' in _v2_norm(text) or 'tekrar' in _v2_norm(text)))
        if task=='tanitim':return _v2_tanitim(project)
        # Arastirma/kod: mevcut V3/V4 kuyruğu. Kayit, basari degildir.
        jid,created=queue_task(task,project+': '+text)
        return (f'{project} icin {task} gorevi mevcut kuyruga '+('kaydedildi' if created else 'zaten kayitli')+
            f'. Gorev numarasi {jid}. '+_v2_motor_state()+' Isin tamamlandigi dogrulanmadi. '
            'Arastirma motoru tek basina canli web taramasi yapmaz; kaynak dogrulamasi gerekir. Yayin yok.')
    except (ImportError,AttributeError,ValueError,RuntimeError,OSError) as exc:
        return 'Gorev guvenli sekilde baslatilamadi: '+str(exc)[:180]
# KADO_V2_CEO_ROUTER_END


PERSONA={
 'schema':1,'name':'KADO Dijital Karakter','identity':'Tamamen kurgusal, 18 yas ustu dijital karakter',
 'transparency':'Bu hesapta yapay zeka ile olusturulmus sanal karakter bulunur.',
 'purpose':'Teknoloji, yaraticilik ve gundelik yasam hakkinda bilgilendirici ve eglenceli icerikler',
 'voice':'Kendine ozgu veya lisansli ses; gercek kisinin izinsiz ses klonu kullanilmaz',
 'reference_image':'','character_lora':'','trigger_word':'kado_virtual_character',
 'visual_anchors':{'age':'yetiskin','face':'Tek referans kimlige bagli sabit yuz','hair':'Sabit sac rengi ve uzunlugu',
                   'style':'Cagdas ve temiz stil','palette':'lacivert, beyaz, turkuaz','accessory':'minimal gumus kolye'},
 'rules':['Her paylasimda AI/sanal karakter aciklamasi','Gercek kisi oldugunu iddia etme',
          'Yasamis gibi sahte urun deneyimi anlatma','Gercek bir kisinin yuzunu/sesini izinsiz kopyalama',
          'Takipci/yorum satin alma ve spam yok','Gercek urunun fiziksel ozelliklerini degistirme',
          'Yayin icin insandan onay ve resmi platform API yetkisi']}
RESEARCH={
 'researched_at':'2026-11-11',
 'scope':'Public project documentation, developer policies and community accounts; no private Instagram account accessed.',
 'projects':[
  {'name':'LangGraph','url':'https://github.com/langchain-ai/langgraph','decision':'later_optional',
   'why':'Durable execution and human approval useful; no migration before existing V3/V4 verified.'},
  {'name':'ComfyUI','url':'https://github.com/Comfy-Org/ComfyUI','decision':'recommended_optional',
   'why':'Visual generation pipeline; requires local GPU/runtime, workflow and vetted checkpoints.'},
  {'name':'InstantID','url':'https://github.com/instantX-research/InstantID','decision':'evaluate_license_and_model',
   'why':'Identity from reference photo for a fictional adult character; not a substitute for full-body consistency.'},
  {'name':'IP Helper (CN)','url':'https://github.com/hpsh0rk/ip_helper','decision':'architecture_reference_only',
   'why':'Visual anchors, character reference and consistency management; code/license not imported.'},
  {'name':'Threads automation (JP)','url':'https://github.com/Tohoso/threads-automation','decision':'architecture_reference_only',
   'why':'Draft -> audit -> owner approval -> post -> measure. Repository says all rights reserved.'},
  {'name':'browser-use','url':'https://github.com/browser-use/browser-use','decision':'not_installed',
   'why':'Browser agents need separate consent, isolation, maintenance and platform-compliant actions.'},
  {'name':'OpenClaw','url':'https://github.com/openclaw/openclaw','decision':'do_not_merge',
   'why':'Security and operational risk of a second always-on system; keep existing KADO.'},
  {'name':'Microsoft AutoGen','url':'https://github.com/microsoft/autogen','decision':'do_not_use',
   'why':'Archived project, not recommended for new production use.'}],
 'platforms':[
  {'name':'Meta Instagram','url':'https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api',
   'requirement':'Professional account, OAuth permissions and eligible publish API; publishing not integrated.'},
  {'name':'TikTok','url':'https://developers.tiktok.com/docs/en/content-posting-api-get-started',
   'requirement':'Creator authorization, approved video.publish scope and app audit for public posting.'},
  {'name':'YouTube','url':'https://developers.google.com/youtube/data/guides/authentication',
   'requirement':'OAuth2 owner consent and per-endpoint quotas; uploading not integrated.'}],
 'rules':['Identity is explicitly fictional and AI-generated','Do not pretend to be a real person or fake testimony',
          'No fake followers or spam','No unattended publishing or credentials embedded in scripts',
          'Product claims and sponsored status reviewed before publishing']}

TOPICS=[
 ('Teknolojide 1 dakikalik yararli bilgi','Reels/Shorts','Bir somut fayda, kaynak kontrolu, 20-35 sn'),
 ('Sanal karakterin yaratici gunlugu','Gorsel carousel','Kurgu oldugunu acikca anlat, ayni yuz kimligi'),
 ('Yapay zeka ile neler yapilabilir?','Reels','Gercek uygulama ornegi, abartisiz'),
 ('Takipciden gelen genel sorular','Gorsel + aciklama','Kisisel bilgileri paylasma'),
 ('Haftalik en guzel fikir','Shorts/Reels','Kendi uretimini ozgun sun'),
 ('Sanal influencer nasil yapiliyor?','Carousel','Seffaf backstage, referans gorsel kaydi'),
 ('Haftalik degerlendirme','Reels','Dogrulanmis metrik yoksa basari iddiasi yok')]

def influencer_init(name=None):
    path=state_dir()/'persona.json'
    if path.exists():return 'Sanal karakter kimligi zaten var: '+str(path)+'. Uzerine yazilmadi.'
    p=dict(PERSONA)
    if name:p['name']=name.strip()[:100]
    p['created_at']=iso();atomic_json(path,p)
    return 'Sanal karakter kimligi olusturuldu: '+str(path)+'. Referans gorsel ve LoRA henüz bagli degil.'

def influencer_plan(days=14):
    if not (state_dir()/'persona.json').is_file():influencer_init()
    if not 1<=days<=90:raise ValueError('Gun sayisi 1-90 olmali')
    start=dt.date.today();entries=[]
    for i in range(days):
        title,format_,brief=TOPICS[i%len(TOPICS)]
        entries.append({'date':(start+dt.timedelta(days=i)).isoformat(),'platforms':['instagram','youtube_shorts'],
                        'topic':title,'format':format_,'brief':brief,'status':'planned','task_id':None,
                        'posting_requires_approval':True})
    dest=state_dir()/('takvim_'+start.isoformat()+'.json')
    if dest.exists():return 'Takvim mevcut, uzerine yazilmadi: '+str(dest)
    atomic_json(dest,{'created_at':iso(),'days':days,'entries':entries})
    return f'{days} gunluk taslak takvim olusturuldu: {dest}. Otomatik yayin KAPALI.'

def calendar_tick():
    """Current date's approved-for-drafting slot: queue once; publication never."""
    names=project_names()
    if not names:return 'Takvim isleyemedi: kayitli proje yok.'
    preferred=next((n for n in names if 'KADO' in n.upper()),names[0])
    files=sorted(state_dir().glob('takvim_*.json'),reverse=True) if state_dir().exists() else []
    if not files:return 'Takvim yok. influencer-plan komutu gerekiyor.'
    selected=None
    for f in files:
        d=json_read(f,{}) or {}
        for e in d.get('entries',[]):
            if isinstance(e,dict) and e.get('date')==today() and e.get('status')=='planned':
                selected=(f,d,e);break
        if selected:break
    if selected is None:return 'Bugun icin bekleyen yeni takvim taslagi yok.'
    path,d,e=selected
    entryid=e['date'].replace('-','')+'_'+hashlib.sha256((str(path)+e['topic']).encode()).hexdigest()[:6]
    goal=(f'{preferred}: Kurgusal KADO sanal influencer gonderi TASLAGI. Baslik: {e["topic"]}. '
          f'Format: {e["format"]}. Brif: {e["brief"]}. Instagram/YouTube icin senaryo, '
          'storyboard, altyazi, gorsel promptlari ve seffaf AI karakter aciklamasi. '
          'Gercek kisi taklidi yok, gercekte yasanmamis deneyim iddiasi yok, otomatik yayin yok.')
    jid,created=queue_task('paylasim',goal,deterministic=entryid)
    e['task_id']=jid;e['status']='draft_queued';e['queued_at']=iso()
    atomic_json(path,d)
    return ('Taslak kuyruga alindi: ' if created else 'Mevcut taslak kaydi: ')+jid+'. Yayin yok.'

def watch():
    """Keeps a daily draft queue active while this process runs; no posting or account actions."""
    print('KADO taslak nobeti basladi. Yalnizca yerel taslak; otomatik yayin yok.',flush=True)
    last=None
    try:
        while True:
            day=today()
            if day!=last:
                try:print(calendar_tick(),flush=True)
                except (OSError,ValueError,RuntimeError) as exc:print('NOBET UYARI:',str(exc)[:200],flush=True)
                last=day
            time.sleep(60)
    except KeyboardInterrupt:return 0

def install_startup():
    """Opt-in user-level Windows logon task. Can be disabled by deleting the cmd file."""
    if os.name!='nt':raise RuntimeError('Baslangic kisayolu yalnizca Windows icin')
    appdata=os.environ.get('APPDATA')
    if not appdata:raise RuntimeError('APPDATA bulunamadi')
    startup=pathlib.Path(appdata)/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'
    if not startup.is_dir():raise RuntimeError('Windows Baslangic klasoru bulunamadi')
    py=default_python();script=str(root()/'kado_ceo.py')
    target=startup/'KADO_Taslak_Nobeti.cmd'
    # Windows START runs minimized; it does not launch KADO voice or V4 worker.
    content='@echo off\r\nstart "KADO Taslak Nobeti" /min "'+py+'" "'+script+'" watch\r\n'
    if not target.exists():target.write_text(content,encoding='utf-8')
    return str(target)

def social_draft(proje,topic):
    project=resolve_project('',proje)
    name=(json_read(state_dir()/'persona.json',{}) or {}).get('name','KADO Dijital Karakter')
    if not str(topic).strip():raise ValueError('Icerik konusu gerekli')
    goal=(f'{project}: {name} sanal influencer icin Instagram ve YouTube Shorts icerik TASLAGI. '
          f'Konu: {topic}. 20-35 saniyelik video senaryosu, 3 saniye giris, 5 sahne storyboard, '
          'gorsel uretim promptlari, altyazi, 3 baslik, 2 aciklama, 5 ilgili etiket, kaynak gerektiren '
          'iddialari isaretle. Karakter tutarliligi, gercek kisiyi taklit etmeme, "AI ile olusturulmus '
          'sanal karakter" aciklamasi zorunlu. Otomatik yayinlama yapma.')
    jid,_=queue_task('paylasim',goal)
    return f'Sanal influencer icerik taslagi gorevi kuyruga eklendi: {jid}. Medya dosyasi henuz uretilmedi; yayin yok.'

def report():
    queue=qdir(); counts={x:0 for x in ('.json','.working','.done','.review','.failed')};recent=[]
    if queue.exists():
        paths=[p for p in queue.iterdir() if p.is_file() and p.suffix in counts]
        for p in paths:counts[p.suffix]+=1
        for p in sorted(paths,key=lambda x:x.stat().st_mtime,reverse=True)[:5]:
            data=json_read(p,{}) or {}
            recent.append(f"{p.stem}: {p.suffix[1:]} / {str(data.get('kind','?'))} / {str(data.get('goal',''))[:100]}")
    lock=root()/'kado_v4_motor.lock';pid=lock.read_text(encoding='ascii',errors='replace').strip() if lock.exists() else ''
    try:
        backup_count=len(list((root()/'yedekler').glob('kado_unified_*')))
    except OSError:backup_count=0
    lines=[f'KADO Merkez {VERSION} - {iso()}',f'Kayitli projeler: {", ".join(project_names()) or "yok"}',
           'Mevcut kuyruk: '+str(queue), 'Gorev sayilari: '+', '.join(f'{k[1:]}={v}' for k,v in counts.items()),
           'V4 kilit PID (calistigi dogrulanmadi): '+(pid or 'yok'),
           'Sanal influencer: '+('Kimlik hazir, gorsel/hesap ayrica gerekir' if (state_dir()/'persona.json').exists() else 'Henuz kurulmamıs'),
           'Otomatik yayin: KAPALI; platform API tokenlari bu modulde tutulmaz.',f'Kurulum yedek sayisi: {backup_count}']
    lines+=['Son 5 kuyruk kaydi:']+recent
    return '\n'.join(lines)

TOOLS={
 'kado_assign_task':('task',[('request','Sesle verilen tam gorev, proje adiyla birlikte')], 'KADO CEO ile mevcut ajan kuyruguna gorev kaydet. Tamamlandi iddia etme.'),
 'kado_company_overview':('status',[],'KADO ajanlarinin mevcut durumunu, bekleyen ve tamamlanan gorevleri acikla.'),
 'kado_influencer_start':('influencer-init',[('name','Kurgusal sanal karakter adi')],'Tutarlı ve açıkça yapay olarak tanitilan sanal influencer kimligi olustur.'),
 'kado_influencer_calendar':('influencer-plan',[],'Sanal influencer icin 14 gunluk icerik takvimi olustur, otomatik yayinlama yok.'),
 'kado_influencer_content':('social-draft',[('project','Kayitli proje adi'),('topic','Uretilecek icerigin konusu')],
                            'Yapay influencer icin video senaryosu ve paylasim taslagi uretme gorevi kaydet.'),
 'kado_company_report':('report',[],'KADO gorev sirasi, uretim ve onay durumunu sesli ozetle.')}

def decl(name,entry):
    command,fields,description=entry
    return {'name':name,'description':description,'parameters':{'type':'OBJECT','properties':{key:{'type':'STRING','description':desc} for key,desc in fields},'required':[key for key,_ in fields]}}

def patch_main(src,to_add,python_path, installed):
    anchor='            elif name == "shell_run":'
    if not to_add:return src
    if src.count(anchor)!=1:raise RuntimeError('main.py arac yapisi taninmadi. Hicbir degisiklik yapilmadi.')
    lines=[]
    for n in to_add:
        cmd,fields,_=TOOLS[n]
        argv=['_py','_center',repr(cmd)]+[f'str(args.get({key!r}, ""))' for key,_ in fields]
        if cmd=='influencer-init' and fields: pass
        lines.extend([f'            elif name == "{n}":\n',
                      '                import subprocess as _ksp\n',
                      '                def _kado_center_call():\n',
                      f'                    _py = {python_path!r}\n',
                      f'                    _center = {str(installed)!r}\n',
                      f'                    _r = _ksp.run([{", ".join(argv)}], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45, check=False)\n',
                      '                    return (_r.stdout or _r.stderr or "KADO yanit vermedi").strip()[:3500]\n',
                      '                result = await loop.run_in_executor(None, _kado_center_call)\n\n'])
    return src.replace(anchor,''.join(lines)+anchor,1)

def patch_defs(src,to_add):
    if not to_add:return src
    anchor='TOOL_DECLARATIONS = ['
    if src.count(anchor)!=1:raise RuntimeError('tool_defs.py yapisi taninmadi; mevcut dosya korunuyor')
    block='\n'.join('    '+repr(decl(n,TOOLS[n]))+',' for n in to_add)+'\n'
    return src.replace(anchor,anchor+'\n'+block,1)

def default_python():
    v=root()/'.venv'/'Scripts'/'python.exe'
    return str(v if v.is_file() else pathlib.Path(sys.executable))

def install(startup=False):
    R=root();S=sistem();src=pathlib.Path(__file__).resolve()
    expected=[R/'kado_birlesik_motor_v3.py',R/'kado_birlesik_motor_v4.py',
              R/'kado_agent_motor'/'kado_motor.py',R/'kado_ses_icerik_koprusu.py',
              S/'main.py',S/'tool_defs.py']
    missing=[str(p) for p in expected if not p.is_file()]
    if missing:raise RuntimeError('Kurulum guvenli durdu, eksik dosyalar: '+'; '.join(missing))
    ensure_queue()
    m=S/'main.py';t=S/'tool_defs.py';c=R/'kado_ceo.py'
    originals={p:p.read_bytes() for p in (m,t)}
    origc=c.read_bytes() if c.exists() else None
    main=originals[m].decode('utf-8-sig');defs=originals[t].decode('utf-8-sig')
    # Eski araç varsa işleyen mevcut yol korunur; yeni declaration/handler oluşturulmaz.
    # Uygunsuz yarim entegrasyon varsa otomatik tamir yerine dur.
    newnames=[]
    for n in TOOLS:
        in_main=('elif name == "'+n+'"' in main or "elif name == '"+n+"'" in main)
        in_defs=("'name': '"+n+"'" in defs or '"name": "'+n+'"' in defs)
        if in_main!=in_defs:raise RuntimeError(f'{n}: kismi eski baglanti bulundu, degisiklik yapilmadi.')
        if not in_main:newnames.append(n)
    updated_main=patch_main(main,newnames,default_python(),c)
    updated_defs=patch_defs(defs,newnames)
    ast.parse(updated_main);ast.parse(updated_defs);ast.parse(src.read_text(encoding='utf-8-sig'))
    backup=R/'yedekler'/('kado_unified_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4])
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(m,backup/'main.py');shutil.copy2(t,backup/'tool_defs.py')
    if c.exists():shutil.copy2(c,backup/'kado_ceo.py')
    atomic_json(backup/'manifest.json',{'version':VERSION,'installed_at':iso(),
                    'ceo_preexisted':origc is not None,'source_path':str(src),'patched_tools':newnames})
    print('YEDEK:',backup,flush=True)
    try:
        # replace atomic, no partial content; roll back on failure
        for p,content in [(c,src.read_bytes()),(m,updated_main.encode('utf-8')),(t,updated_defs.encode('utf-8'))]:
            tmp=p.with_name(p.name+'.kado-tmp')
            tmp.write_bytes(content);os.replace(tmp,p)
        ast.parse(m.read_text(encoding='utf-8-sig'));ast.parse(t.read_text(encoding='utf-8-sig'))
    except Exception:
        m.write_bytes(originals[m]);t.write_bytes(originals[t])
        if origc is None:
            if c.exists():c.unlink()
        else:c.write_bytes(origc)
        raise
    try:
        if not (state_dir()/'arastirma_kaynaklari.json').exists():
            atomic_json(state_dir()/'arastirma_kaynaklari.json',RESEARCH)
        if not (state_dir()/'persona.json').exists():influencer_init()
        if not list(state_dir().glob('takvim_*.json')):influencer_plan(14)
    except (OSError,ValueError) as exc:
        print('UYARI: sosyal icerik hazirligi tamamlanamadi:',str(exc)[:150])
    print('KURULUM TAMAMLANDI: mevcut V3/V4 motoru korunuyor; yeni motor/veritabani yok.')
    print('Sesli araclar eklendi:',', '.join(newnames) if newnames else 'Zaten bagli olan araclar korundu.')
    print('KADO yeniden baslatilmali. WhatsApp/ElevenLabs/API anahtarlari degistirilmedi.')
    print('UYARI: Hesap acma, gercek goruntu/video uretme ve otomatik yayin etkin DEGIL.')
    if startup:
        try:print('Windows oturum acilisinda taslak nobeti:',install_startup())
        except (OSError,RuntimeError) as exc:print('UYARI: otomatik baslangic ayarlanamadi:',str(exc)[:150])
    else:
        print('Taslak nobeti otomatik baslamaz; install --startup ile acilabilir.')
    print('GERI AL: py -3 "'+str(c)+'" rollback "'+str(backup)+'"')
    return 0

def rollback(folder):
    b=pathlib.Path(folder).resolve();root_back=(root()/'yedekler').resolve()
    if root_back not in b.parents or not b.name.startswith('kado_unified_'):raise ValueError('Gecersiz yedek dizini')
    manifest=json_read(b/'manifest.json')
    if not manifest:raise ValueError('Yedek manifest yok')
    for f,where in [('main.py',sistem()/'main.py'),('tool_defs.py',sistem()/'tool_defs.py')]:
        src=b/f
        if not src.is_file():raise RuntimeError('Eksik yedek: '+f)
        ast.parse(src.read_text(encoding='utf-8-sig'))
    shutil.copy2(b/'main.py',sistem()/'main.py');shutil.copy2(b/'tool_defs.py',sistem()/'tool_defs.py')
    if manifest.get('ceo_preexisted'):
        shutil.copy2(b/'kado_ceo.py',root()/'kado_ceo.py')
    else:
        (root()/'kado_ceo.py').unlink(missing_ok=True)
    print('Geri alma tamamlandi. KADO yeniden baslatilmali.')

def selftest():
    import unittest
    class T(unittest.TestCase):
        def test_schema(self):
            for n,e in TOOLS.items():
                d=decl(n,e);self.assertEqual(d['name'],n)
        def test_classification(self):
            self.assertEqual(kind_for('Instagram reels uret'),'paylasim')
            self.assertEqual(kind_for('Python kod yaz'),'kod')
            self.assertEqual(kind_for('pazar arastir'),'arastirma')
        def test_main_patch(self):
            m='def f():\n    if name == "foo":\n        pass\n            elif name == "shell_run":\n                pass\n'
            # sample text strictly checks syntax marker insertion, not valid artificial surrounding Python
            self.assertIn('kado_company_report',patch_main(m,['kado_company_report'],'python','center'))
        def test_defs_patch(self):
            t='TOOL_DECLARATIONS = []\n'
            self.assertIn('kado_company_overview',patch_defs(t,['kado_company_overview']))
        def test_safe_ids(self):
            self.assertEqual(len(PERSONA['rules']),7)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(T)
    r=unittest.TextTestRunner(verbosity=1).run(suite)
    print('SELFTEST:', 'BASARILI' if r.wasSuccessful() else 'BASARISIZ')
    return 0 if r.wasSuccessful() else 1

def main(argv=None):
    p=argparse.ArgumentParser(description='KADO Birlesik Merkez, sesli CEO ve sosyal medya taslak merkezi')
    sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('install');i.add_argument('--startup',action='store_true');sub.add_parser('selftest');sub.add_parser('status');sub.add_parser('report');sub.add_parser('research');sub.add_parser('tick');sub.add_parser('watch')
    a=sub.add_parser('task');a.add_argument('request');a.add_argument('--project')
    a=sub.add_parser('influencer-init');a.add_argument('name',nargs='?')
    a=sub.add_parser('influencer-plan');a.add_argument('--days',type=int,default=14)
    a=sub.add_parser('social-draft');a.add_argument('project');a.add_argument('topic')
    a=sub.add_parser('rollback');a.add_argument('folder')
    args=p.parse_args(argv)
    try:
        if args.command=='install':return install(args.startup)
        if args.command=='selftest':return selftest()
        if args.command in ('status','report'):print(report());return 0
        if args.command=='research':print(json.dumps(RESEARCH,ensure_ascii=False,indent=2));return 0
        if args.command=='tick':print(calendar_tick());return 0
        if args.command=='watch':return watch()
        if args.command=='task':print(ceo_calistir(args.request,args.project));return 0
        if args.command=='influencer-init':print(influencer_init(args.name));return 0
        if args.command=='influencer-plan':print(influencer_plan(args.days));return 0
        if args.command=='social-draft':print(social_draft(args.project,args.topic));return 0
        if args.command=='rollback':rollback(args.folder);return 0
    except (OSError,ValueError,RuntimeError,SyntaxError) as e:
        print('GUVENLI DURDURULDU:',str(e)[:500],file=sys.stderr);return 2
    return 1


# KADO_21_REPORT_WRAPPER_START
# Tek CEO, tek ses araci. Yalnizca mevcut rapora 2.1 izleme ozeti eklenir.
_kado21_previous_report = report
def report():
    current = _kado21_previous_report()
    try:
        import kado_izleme_21 as _kado21
        current += "\n" + _kado21.report()
    except Exception as exc:
        current += "\nKADO 2.1 izleme raporu okunamadi: " + str(exc)[:100]
    return current
# KADO_21_REPORT_WRAPPER_END


# KADO_31_STUDIO_VOICE_START
# KADO 3.1: mevcut ses araclari ve ana CEO korunur, sadece Influencer Studio yoluna yonlendirme.
_kado31_previous_ceo = ceo_calistir
_kado31_previous_social_draft = social_draft
_kado31_previous_influencer_init = influencer_init
_kado31_previous_influencer_plan = influencer_plan
_kado31_previous_report = report

def ceo_calistir(istek,proje=None):
    try:
        import kado_studyo_31 as studio
        result=studio.voice_route(istek,proje)
        if result is not None:return result
    except Exception as exc:
        return 'Influencer Studyosu baglantisi okunamadi: '+str(exc)[:130]
    return _kado31_previous_ceo(istek,proje)

def social_draft(proje,topic):
    try:
        import kado_studyo_31 as studio
        return studio.make_drafts(studio.project_of(topic,proje),str(topic).strip()[:180],studio.platform_of(topic),studio.number_in(topic))
    except Exception as exc:
        return 'Sanal influencer taslagi olusturulamadi: '+str(exc)[:130]

def influencer_init(name=None):
    try:
        import kado_studyo_31 as studio
        return studio.status()
    except Exception as exc:return 'KADO 3.0 kimligi okunamadi: '+str(exc)[:130]

def influencer_plan(days=14):
    try:
        import kado_studyo_31 as studio
        return studio.calendar_report()
    except Exception as exc:return 'Stüdyo takvimi okunamadi: '+str(exc)[:130]

def report():
    base=_kado31_previous_report()
    try:
        import kado_studyo_31 as studio
        return base+'\n'+studio.status()
    except Exception as exc:return base+'\nStüdyo okunamadi: '+str(exc)[:90]
# KADO_31_STUDIO_VOICE_END

if __name__=='__main__':sys.exit(main())
