"""KADO independent local job worker. No production integration, no posting."""
import argparse, ast, datetime, json, os, pathlib, re, time, urllib.request, uuid
BASE=pathlib.Path(__file__).resolve().parent
QUEUE=BASE/'kuyruk'; OUT=BASE/'ciktilar'; LOG=BASE/'gunluk.jsonl'
for p in (QUEUE,OUT): p.mkdir(parents=True,exist_ok=True)
def log(event,**kwargs):
    with LOG.open('a',encoding='utf-8') as f:f.write(json.dumps({'time':datetime.datetime.now().isoformat(timespec='seconds'),'event':event,**kwargs},ensure_ascii=False)+'\n')
def ask_model(prompt):
    endpoint=os.getenv('KADO_OLLAMA_URL','http://127.0.0.1:11434/api/generate')
    payload=json.dumps({'model':os.getenv('KADO_MODEL','qwen2.5:3b'),'prompt':prompt,'stream':False,'options':{'num_thread':2,'num_ctx':2048,'num_predict':650}}).encode()
    req=urllib.request.Request(endpoint,data=payload,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)['response'].strip()
def safe_filename(name):
    name=re.sub(r'[^a-zA-Z0-9_.-]','_',name).strip('._')
    return name[:70] or 'output'
def extract_code(text):
    match=re.search(r'```(?:python)?\s*\n(.*?)```',text,re.S|re.I)
    return match.group(1).strip() if match else text.strip()
class QualityRejected(Exception):
    pass

def text_issues(text):
    issues=[]
    if len(text.strip()) < 90: issues.append('Metin cok kisa')
    if re.search(r'[ÃÄÅ�]|\ufffd', text): issues.append('Karakter kodlama bozuklugu supheli')
    if re.search(r'(?i)\b(seviş\w*|sikiş\w*|porno\w*)\b',text):
        issues.append('Oyuncak markasi icin uygunsuz ifade')
    if re.search(r'(?i)\b(üzgünüm|bir yapay zeka|yapamam|şablon|örnek metin)\b',text):
        issues.append('Musteriye sunulamayacak model aciklamasi')
    if len(re.findall(r'#[\wçğıöşüÇĞİÖŞÜ]+',text)) < 3:
        issues.append('Yetersiz hashtag')
    if not re.search(r'(?i)han\s*toys|#hantoys',text):
        issues.append('Marka adi eksik')
    return issues

def code_issues(code):
    issues=[]
    try: tree=ast.parse(code)
    except SyntaxError as e: return ['Python sozdizimi: '+str(e)]
    blocked={'os','subprocess','socket','requests','urllib','shutil','ctypes','winreg','pickle','importlib'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in blocked: issues.append('Riskli import: '+alias.name)
        elif isinstance(node,ast.ImportFrom):
            if (node.module or '').split('.')[0] in blocked: issues.append('Riskli import: '+str(node.module))
        elif isinstance(node,ast.Call):
            fn=node.func
            if isinstance(fn,ast.Name) and fn.id in {'eval','exec','compile','__import__','open','input'} - {'input'}:
                issues.append('Riskli cagri: '+fn.id)
    if re.search(r'[ÃÄÅ�]|\ufffd',code): issues.append('Karakter kodlama bozuklugu supheli')
    return sorted(set(issues))

def execute(job):
    jid=job['id']; kind=job['kind']; goal=job['goal']; dest=OUT/jid;dest.mkdir(exist_ok=True)
    log('start',id=jid,kind=kind)
    if kind in ('kod','paylasim'):
        feedback=''
        for attempt in range(1,4):
            if kind=='kod':
                prompt=('Sen KADO kod yazari uzmansin. Tek bir Python 3 dosyasi yaz. '
                        'Harici kutuphane, os, subprocess, dosya okuma/yazma, ag ve gizli veri kullanma. '
                        'Turkce metinler dogru olsun. Yalnizca ```python kod blogu dondur. Gorev: '+goal)
            else:
                prompt=('Sen Han Toys oyuncak markasi icin Turkce Instagram metni yaziyorsun. '
                        'Baslik, aciklama, 5 ilgili hashtag ve gorsel briefi ver. '
                        'Argo, cinsel ifade, anlamsiz kelime, uydurma urun ozelligi, '
                        'model ozru veya sablon aciklamasi yazma. Yayinlama. Konu: '+goal)
            raw=ask_model(prompt+feedback)
            candidate=extract_code(raw) if kind=='kod' else raw
            issues=code_issues(candidate) if kind=='kod' else text_issues(candidate)
            (dest/f'deneme_{attempt}.txt').write_text(raw,encoding='utf-8')
            (dest/f'denetim_{attempt}.txt').write_text(
                'Kontrol: '+('RED\\n'+'\\n'.join(issues) if issues else 'ON KONTROLDEN GECTI')+
                '\\nBu otomatik kontrol tam guvenlik/dil dogrulamasi degildir.\\n',encoding='utf-8')
            log('quality_check',id=jid,attempt=attempt,issues=issues)
            if not issues: break
            feedback='\\nOnceki yanitin reddedildi. Su sorunlari gider: '+ '; '.join(issues)
        if issues:
            (dest/'INCELEME_GEREKLI.txt').write_text(
                '3 deneme otomatik kontrollerden gecemedi. Manuel inceleme gerekli.\\n'+
                '\\n'.join(issues),encoding='utf-8')
            raise QualityRejected('Kalite kontrolunden gecmedi: '+'; '.join(issues))
        if kind=='kod':
            (dest/'uygulama.py').write_text(candidate+'\\n',encoding='utf-8')
            (dest/'TEST_SONUCU.txt').write_text(
                'AST ve sinirli statik kontroller gecti. KOD CALISTIRILMADI; guvenlik ve davranis dogrulanmadi.',
                encoding='utf-8')
        else:
            (dest/'paylasim_taslagi.txt').write_text(candidate,encoding='utf-8')
            (dest/'YAYIN_ONAYI_GEREKLI.txt').write_text(
                'On kontrol gecti; insan incelemesi ve acik yayin onayi gerekli. Otomatik yayin YOK.',
                encoding='utf-8')
    elif kind=='arastirma':
        draft=ask_model('Yalnizca genel bilgi ve arastirma plani ver. Canli web taramasi yapmadigini belirt. Gorev: '+goal)
        (dest/'arastirma_taslagi.txt').write_text(draft,encoding='utf-8')
        (dest/'KAYNAK_UYARISI.txt').write_text('Canli web taramasi yapilmadi; olgular dogrulanmadi.',encoding='utf-8')
    else:raise ValueError('Desteklenmeyen gorev turu')
    (dest/'OZET.txt').write_text(f'KADO gorev {jid}\\nTur: {kind}\\nIstek: {goal}\\nCikti: {dest}\\n',encoding='utf-8')
    log('completed',id=jid,output=str(dest))
def submit(kind,goal):
    if kind not in ('kod','paylasim','arastirma'):raise ValueError('Tur: kod, paylasim veya arastirma')
    jid=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    p=QUEUE/(jid+'.json');p.write_text(json.dumps({'id':jid,'kind':kind,'goal':goal},ensure_ascii=False),encoding='utf-8');print('Gorev eklendi:',jid)
def tick():
    for p in sorted(QUEUE.glob('*.json')):
        working=p.with_suffix('.working')
        try:p.rename(working)
        except OSError:continue
        try:
            job=json.loads(working.read_text(encoding='utf-8'))
            execute(job)
            working.rename(working.with_suffix('.done'))
        except QualityRejected as e:
            log('review_required',file=working.name,error=str(e)[:250])
            print('Manuel inceleme gerekli:',str(e)[:200])
            working.rename(working.with_suffix('.review'))
        except Exception as e:
            log('failed',file=working.name,error=str(e)[:250])
            print('Gorev basarisiz:',str(e)[:200]);working.rename(working.with_suffix('.failed'))
        return True
    return False
def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('ekle');s.add_argument('kind',choices=['kod','paylasim','arastirma']);s.add_argument('goal')
    sub.add_parser('birkez');r=sub.add_parser('calis');r.add_argument('--bekleme',type=int,default=15)
    sub.add_parser('durum')
    a=ap.parse_args()
    if a.cmd=='ekle':submit(a.kind,a.goal)
    elif a.cmd=='birkez':print('Islendi' if tick() else 'Bekleyen gorev yok')
    elif a.cmd=='calis':
        print('KADO motor calisiyor. Durdurmak icin Ctrl+C. Yeni gorevler kuyruga eklenebilir.')
        try:
            while True:
                if not tick():time.sleep(max(3,a.bekleme))
        except KeyboardInterrupt:print('Motor durduruldu')
    else:
        for suffix in ('.json','.working','.done','.review','.failed'):
            print(suffix, len(list(QUEUE.glob('*'+suffix))))
        print('Ciktilar:',OUT)
if __name__=='__main__':main()
