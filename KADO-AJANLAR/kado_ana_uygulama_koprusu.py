"""KADO ana uygulama gorevleri -> V4 kuyrugu. Standart kutuphane.
Yalnizca 'KOD:', 'PAYLASIM:', 'ARASTIRMA:' ile baslayan gorevler aktarilir.
Ana KADO veritabanina ve WhatsApp'a yazmaz. Yayin veya kod calistirma yapmaz.
"""
import argparse, datetime, json, pathlib, sqlite3, time, uuid, tempfile
from contextlib import closing
ROOT=pathlib.Path(__file__).resolve().parent
MAIN=ROOT/'memory'/'kado_company.db'
MAP=ROOT/'memory'/'kado_gorev_koprusu.db'
QUEUE=ROOT/'kado_agent_motor'/'kuyruk'
PREFIXES={'KOD:':'kod','PAYLASIM:':'paylasim','ARASTIRMA:':'arastirma'}
def connect_map(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=10)
    c.execute('CREATE TABLE IF NOT EXISTS transfers (source_id INTEGER PRIMARY KEY, queue_id TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL)')
    c.commit()
    return c
def read_tasks(path):
    if not path.is_file(): raise RuntimeError('Ana KADO gorev veritabani bulunamadi: '+str(path))
    c=sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True,timeout=5)
    try:
        cols={r[1] for r in c.execute('PRAGMA table_info(tasks)')}
        if not {'id','title','details'}.issubset(cols):
            raise RuntimeError('Ana KADO tasks semasi beklenenden farkli: '+str(cols))
        return c.execute('SELECT id,title,details FROM tasks ORDER BY id').fetchall()
    finally:c.close()
def once(main=MAIN, mapping=MAP, queue=QUEUE):
    rows=read_tasks(main)
    queue.mkdir(parents=True,exist_ok=True)
    transferred=[]
    with closing(connect_map(mapping)) as c:
        for source_id,title,details in rows:
            title=str(title or '').strip()
            match=next(((prefix,kind) for prefix,kind in PREFIXES.items() if title.upper().startswith(prefix)),None)
            if not match:continue
            prefix,kind=match
            goal=(title[len(prefix):].strip()+' '+str(details or '').strip()).strip()
            if not goal or len(goal)>4000:continue
            if c.execute('SELECT 1 FROM transfers WHERE source_id=?',(source_id,)).fetchone():continue
            jid=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
            target=queue/(jid+'.json')
            job={'id':jid,'kind':kind,'goal':goal}
            # Atomic creation; never overwrite a queue job.
            try:
                with target.open('x',encoding='utf-8') as f:
                    json.dump(job,f,ensure_ascii=False)
                c.execute('INSERT INTO transfers VALUES(?,?,?,?)',(source_id,jid,kind,datetime.datetime.now(datetime.timezone.utc).isoformat()))
                c.commit()
                transferred.append((source_id,jid,kind))
            except Exception:
                # If mapping fails, preserve job to avoid duplicate execution.
                raise
    return transferred
def selftest():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d);main=root/'main.db';mapping=root/'map.db';queue=root/'q'
        with closing(sqlite3.connect(main)) as c:
            c.execute('CREATE TABLE tasks (id INTEGER PRIMARY KEY,title TEXT,details TEXT)')
            c.executemany('INSERT INTO tasks VALUES(?,?,?)',[(1,'KOD: topla','iki sayi'),(2,'Normal gorev','dokunma'),(3,'PAYLASIM: Han Toys','taslak')])
            c.commit()
        a=once(main,mapping,queue)
        assert len(a)==2 and len(once(main,mapping,queue))==0
        assert len(list(queue.glob('*.json')))==2
        print('KOPRU SELFTEST 3/3 BASARILI (filtre, kuyruk, tekrar engelleme)')
def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['selftest','birkez','izle'])
    p.add_argument('--interval',type=int,default=10)
    a=p.parse_args()
    if a.mode=='selftest':return selftest()
    if a.mode=='birkez':
        for item in once():print('AKTARILDI:',*item)
        return
    print('KADO KOPRU AKTIF. Ana uygulamada yeni gorev basligi KOD: ... ile baslamali.',flush=True)
    try:
        while True:
            try:
                for item in once():print('AKTARILDI:',*item,flush=True)
            except (OSError,sqlite3.Error,RuntimeError) as e:
                print('KOPRU UYARI:',str(e)[:250],flush=True)
            time.sleep(max(3,a.interval))
    except KeyboardInterrupt:print('KOPRU DURDU')
if __name__=='__main__':main()
