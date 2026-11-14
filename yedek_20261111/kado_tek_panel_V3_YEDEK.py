"""KADO V3 unified local dashboard. Standard library; no agent execution."""
import datetime as dt
import html
import json
import secrets
import sqlite3
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / 'memory' / 'kado_company.db'
APPROVAL = ROOT / 'memory' / 'kado_approvals.db'
LIVE = ROOT / 'memory' / 'agent_live_state.json'
HOST, PORT = '127.0.0.1', 8768
TOKEN = secrets.token_urlsafe(32)

def e(v): return html.escape(str(v if v is not None else ''), quote=True)
def conn(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=10)
    c.execute('PRAGMA busy_timeout=10000')
    c.row_factory = sqlite3.Row
    return c

def init():
    with conn(MAIN) as c:
        c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, details TEXT NOT NULL DEFAULT "", status TEXT NOT NULL DEFAULT "bekliyor", created_at TEXT NOT NULL)')
    with conn(APPROVAL) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, title TEXT NOT NULL, proposal TEXT NOT NULL, risk TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'bekliyor', created_at TEXT NOT NULL, decided_at TEXT)''')

def state():
    try:
        d = json.loads(LIVE.read_text(encoding='utf-8'))
        if not isinstance(d, dict): return {}
        if d.get('phase') == 'running' and time.time()-float(d.get('updated_at',0)) > 90: d['phase']='stale'
        return d
    except (OSError, ValueError, TypeError): return {}

CSS = '''
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#080e1c;color:#edf4ff;font:15px/1.5 system-ui,'Segoe UI',sans-serif}a{color:#a8ccff;text-decoration:none}a:hover{text-decoration:underline}main{max-width:1250px;margin:auto;padding:24px 18px 65px}header{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}h1{font-size:26px;margin:0}h2{font-size:19px;margin:0 0 15px}h3{font-size:16px;margin:5px 0}nav{display:flex;flex-wrap:wrap;gap:8px;margin:23px 0}nav a{border:1px solid #354b6b;background:#17263e;padding:9px 13px;border-radius:10px}.muted,small{color:#9eafc9}.card,.agent{background:linear-gradient(155deg,#17253d,#10192a);border:1px solid #2b3d59;border-radius:16px;padding:18px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:18px}.stat strong{font-size:28px;display:block}.agent{text-align:center;overflow:hidden;position:relative}.avatar{font-size:38px;display:grid;place-items:center;width:80px;height:80px;margin:8px auto 12px;border-radius:25px;background:#273b5d;animation:float 3s ease-in-out infinite}.agent:nth-child(2) .avatar{animation-delay:-.7s}.agent:nth-child(3) .avatar{animation-delay:-1.4s}.agent:nth-child(4) .avatar{animation-delay:-2s}.agent.working{border-color:#54e6b9;box-shadow:0 0 22px #37dcb52c}.agent.working .avatar{animation:float 1s ease-in-out infinite;box-shadow:0 0 22px #42e5b555}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#8495ae;margin-right:7px}.working .dot{background:#4ce7b8;animation:pulse 1s infinite}.done .dot{background:#4ce7b8}.failed .dot{background:#ff7c92}.item{display:block;border-top:1px solid #2e405b;padding:13px 0}.item:first-of-type{border-top:0}.tag{font-size:12px;color:#c3d7f6;border:1px solid #4c6080;padding:3px 8px;border-radius:8px;margin-left:7px}.notice{border:1px solid #425b80;background:#15243a;border-radius:12px;padding:12px;margin:18px 0}.report{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.65 system-ui,sans-serif}input,textarea,select{display:block;width:100%;background:#0c1627;color:white;border:1px solid #526581;border-radius:8px;padding:10px;font:inherit;margin:5px 0 12px}textarea{min-height:80px}label{display:block;margin-top:8px}button{border:0;border-radius:8px;background:#86b4ff;color:#08152a;padding:10px 14px;font-weight:700;cursor:pointer}.yes{background:#72d6b3}.no{background:#ffa1aa}.actions{display:flex;gap:8px;flex-wrap:wrap}.actions form{margin:0}.approval{border-top:1px solid #34435a;padding:15px 0}.approval p{white-space:pre-wrap;overflow-wrap:anywhere}.error{color:#ffb5bf}.scroll{overflow:auto}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #34435a;text-align:left;vertical-align:top}section{margin-bottom:18px}@keyframes float{50%{transform:translateY(-8px)}}@keyframes pulse{50%{opacity:.3}}@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}}@media(max-width:430px){main{padding:14px}.grid{gap:8px}.agent{padding:10px}.avatar{width:65px;height:65px;font-size:30px}}@media(prefers-reduced-motion:reduce){*{animation:none!important}}
'''

def page(body, refresh=False):
    meta='<meta http-equiv="refresh" content="5">' if refresh else ''
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">{meta}<title>KADO V3 | Tek Merkez</title><style>{CSS}</style></head><body><main><header><div><h1>🤖 KADO — AI Şirket Merkezi V3</h1><small>Tek panel · Yerel bilgisayar · Patron kontrolünde</small></div><span class="tag">● Yerel sistem</span></header><nav><a href="/">🏠 Ana Panel</a><a href="/tasks">📋 Görevler</a><a href="/meetings">💬 Toplantılar</a><a href="/approvals">🛡️ Patron Onayları</a></nav>{body}<p class="muted">KADO V3: Onaylar yalnızca karar kaydıdır; kod çalıştırma, satın alma, yayınlama veya mesaj gönderme yapılmaz. Ajan avatarlarının boşta hareket etmesi dekoratiftir.</p></main></body></html>'''

def agents_html():
    d=state(); phase=d.get('phase',''); current=str(d.get('agent','')).upper(); done=d.get('completed_agents',[]); done=done if isinstance(done,list) else []
    agents=[('👑','KADO CEO','KADO_CEO'),('🔎','Araştırmacı','ARASTIRMACI'),('🧩','Mimar','MIMAR'),('🛡️','Denetçi','DENETCI')]
    out=[]
    for ico,name,key in agents:
        working=phase=='running' and current==key
        failed=phase=='failed' and current==key
        completed=key in done and phase!='stale'
        css='working' if working else 'failed' if failed else 'done' if completed else ''
        label='Düşünüyor...' if working else 'Hata' if failed else 'Tamamladı' if completed else 'Görev bekliyor'
        out.append(f'<div class="agent {css}"><div class="avatar">{ico}</div><h3>{name}</h3><small><span class="dot"></span>{label}</small></div>')
    info=f'Görev #{e(d.get("task_id","?"))}: {e(str(d.get("message",""))[:220])}' if d and phase not in ('stale','') else 'Şu anda canlı görev yok.'
    return '<div class="grid">'+''.join(out)+'</div><div class="notice">'+info+'</div>'

def home():
    with conn(MAIN) as c:
        tasks=[dict(r) for r in c.execute('SELECT id,title,status FROM tasks ORDER BY id DESC LIMIT 8')]
        try: meetings=[dict(r) for r in c.execute('SELECT id,topic,status FROM meetings ORDER BY id DESC LIMIT 8')]
        except sqlite3.OperationalError: meetings=[]
    with conn(APPROVAL) as c:
        pending=c.execute("SELECT COUNT(*) FROM approvals WHERE status='bekliyor'").fetchone()[0]
    stats=[('Ajan','4'),('Görev',len(tasks)),('Son toplantı',meetings[0]['id'] if meetings else '—'),('Onay bekleyen',pending)]
    cards=''.join(f'<div class="card stat"><small>{e(n)}</small><strong>{e(v)}</strong></div>' for n,v in stats)
    task_html=''.join(f'<div class="item">#{t["id"]} {e(t["title"])} <span class="tag">{e(t["status"])}</span></div>' for t in tasks) or 'Henüz görev yok.'
    meet_html=''.join(f'<a class="item" href="/meeting?id={m["id"]}">#{m["id"]} {e(m["topic"])} <span class="tag">{e(m["status"])}</span></a>' for m in meetings) or 'Henüz toplantı yok.'
    return page(f'<div class="grid">{cards}</div><h2 style="margin-top:24px">Canlı ajan kadrosu</h2>{agents_html()}<div class="cols"><section class="card"><h2>Son görevler</h2>{task_html}<a href="/tasks">Tüm görevler</a></section><section class="card"><h2>Son toplantılar</h2>{meet_html}<a href="/meetings">Tüm toplantılar</a></section></div>',True)

def tasks_page():
    with conn(MAIN) as c: tasks=[dict(r) for r in c.execute('SELECT id,title,details,status,created_at FROM tasks ORDER BY id DESC LIMIT 100')]
    form=f'''<section class="card"><h2>Yeni görev</h2><form method="post" action="/task"><input type="hidden" name="token" value="{TOKEN}"><label>Görev başlığı</label><input name="title" maxlength="150" required><label>Açıklama</label><textarea name="details" maxlength="2000"></textarea><button>Görevi kaydet</button></form></section>'''
    rows=''.join(f'''<tr><td>#{t['id']}</td><td><b>{e(t['title'])}</b><br><small>{e(t['details'])}</small></td><td>{e(t['status'])}</td><td><form method="post" action="/task-status"><input type="hidden" name="token" value="{TOKEN}"><input type="hidden" name="id" value="{t['id']}"><select name="status">{''.join(f'<option value="{v}" {"selected" if v==t['status'] else ""}>{label}</option>' for v,label in [('bekliyor','Bekliyor'),('devam','Devam'),('tamam','Tamam')])}</select><button>Kaydet</button></form></td></tr>''' for t in tasks)
    return page(form+f'<section class="card scroll"><h2>Görev listesi</h2><table><tr><th>ID</th><th>Görev</th><th>Durum</th><th>İşlem</th></tr>{rows}</table></section><div class="notice">Görev oluşturmak veya durumunu değiştirmek Gemini çalıştırmaz. Ajan motoru ayrı başlatılır.</div>')

def meetings_page():
    with conn(MAIN) as c:
        try: items=[dict(r) for r in c.execute('SELECT id,topic,status,started_at FROM meetings ORDER BY id DESC LIMIT 100')]
        except sqlite3.OperationalError: items=[]
    rows=''.join(f'<a class="item" href="/meeting?id={m["id"]}"><b>#{m["id"]} {e(m["topic"])}</b> <span class="tag">{e(m["status"])}</span><br><small>{e(m["started_at"])}</small></a>' for m in items)
    return page('<section class="card"><h2>Toplantı geçmişi</h2>'+ (rows or 'Henüz toplantı yok.') +'</section>')

def meeting_detail(mid):
    with conn(MAIN) as c:
        try:
            m=c.execute('SELECT id,topic,status FROM meetings WHERE id=?',(mid,)).fetchone()
            if not m: return page('<div class="error">Toplantı bulunamadı.</div>')
            msgs=c.execute('SELECT role,content,created_at FROM messages WHERE meeting_id=? ORDER BY id',(mid,)).fetchall()
        except sqlite3.OperationalError: return page('<div class="error">Toplantı tablosu henüz hazır değil.</div>')
    blocks=''.join(f'<section class="card"><h2>{e(x["role"])}</h2><small>{e(x["created_at"])}</small><pre class="report">{e(x["content"])}</pre></section>' for x in msgs)
    return page(f'<h2>Toplantı #{mid} — {e(m["topic"])}</h2><p class="muted">Durum: {e(m["status"])}</p>{blocks}')

def approvals_page():
    with conn(APPROVAL) as c: items=[dict(r) for r in c.execute('SELECT * FROM approvals ORDER BY id DESC LIMIT 100')]
    form=f'''<section class="card"><h2>Yeni onay talebi</h2><form method="post" action="/approval-create"><input type="hidden" name="token" value="{TOKEN}"><label>Görev ID (isteğe bağlı)</label><input name="task_id" maxlength="10" inputmode="numeric"><label>Başlık</label><input name="title" maxlength="150" required><label>Önerilen işlem</label><textarea name="proposal" maxlength="4000" required></textarea><label>Risk ve etkiler</label><textarea name="risk" maxlength="2000" required></textarea><button>Onaya gönder</button></form></section>'''
    blocks=[]
    for x in items:
        actions=''
        if x['status']=='bekliyor':
            actions='<div class="actions">'+''.join(f'<form method="post" action="/approval-decide"><input type="hidden" name="token" value="{TOKEN}"><input type="hidden" name="id" value="{x["id"]}"><input type="hidden" name="decision" value="{v}"><button class="{css}">{label}</button></form>' for v,css,label in [('onaylandi','yes','Onayla'),('reddedildi','no','Reddet')])+'</div>'
        blocks.append(f'<div class="approval"><h3>#{x["id"]} {e(x["title"])} <span class="tag">{e(x["status"])}</span></h3><small>Görev: {e(x["task_id"] or "—")} · {e(x["created_at"])}</small><h3>Öneri</h3><p>{e(x["proposal"])}</p><h3>Risk</h3><p>{e(x["risk"])}</p>{actions}</div>')
    return page('<div class="notice"><b>Güvenlik:</b> Onay yalnızca karar kaydeder. Gerçek işlem başlatılmaz.</div><div class="cols">'+form+'<section class="card"><h2>Onay kayıtları ('+str(len(items))+')</h2>'+(''.join(blocks) or 'Henüz onay talebi yok.')+'</section></div>')

class Handler(BaseHTTPRequestHandler):
    def respond(self, content, status=200):
        data=content.encode('utf-8'); self.send_response(status)
        for k,v in [('Content-Type','text/html; charset=utf-8'),('Content-Length',str(len(data))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),('Referrer-Policy','no-referrer'),('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")]: self.send_header(k,v)
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        p=urlparse(self.path)
        try:
            if p.path=='/': return self.respond(home())
            if p.path=='/tasks': return self.respond(tasks_page())
            if p.path=='/meetings': return self.respond(meetings_page())
            if p.path=='/approvals': return self.respond(approvals_page())
            if p.path=='/meeting':
                mid=int(parse_qs(p.query).get('id',['0'])[0]); assert mid>0
                return self.respond(meeting_detail(mid))
            return self.respond('Sayfa bulunamadı',404)
        except (ValueError,AssertionError): return self.respond('Geçersiz parametre',400)
        except sqlite3.Error as ex: return self.respond(page('<p class="error">Veritabanı hatası: '+e(ex)+'</p>'),500)
    def do_POST(self):
        if self.path not in ('/task','/task-status','/approval-create','/approval-decide'): return self.respond('Bulunamadı',404)
        origin=self.headers.get('Origin')
        if origin not in (None,f'http://{HOST}:{PORT}'): return self.respond('Kaynak reddedildi',403)
        if self.headers.get('Content-Type','').split(';')[0].strip()!='application/x-www-form-urlencoded': return self.respond('Form bekleniyor',415)
        try: n=int(self.headers.get('Content-Length','0'))
        except ValueError: return self.respond('Geçersiz uzunluk',400)
        if n<=0 or n>12000: return self.respond('İstek boyutu geçersiz',413)
        try: d=parse_qs(self.rfile.read(n).decode('utf-8'),keep_blank_values=True)
        except UnicodeDecodeError: return self.respond('Kodlama hatası',400)
        v=lambda k:d.get(k,[''])[0].strip()
        if not secrets.compare_digest(v('token'),TOKEN): return self.respond('Yetkisiz istek',403)
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            if self.path=='/task':
                title,details=v('title'),v('details')
                if not title or len(title)>150 or len(details)>2000: return self.respond('Görev alanları geçersiz',400)
                with conn(MAIN) as c: c.execute('INSERT INTO tasks(title,details,status,created_at) VALUES(?,?,?,?)',(title,details,'bekliyor',now))
                dest='/tasks'
            elif self.path=='/task-status':
                if not v('id').isascii() or not v('id').isdigit() or v('status') not in ('bekliyor','devam','tamam'): return self.respond('Geçersiz görev durumu',400)
                with conn(MAIN) as c: c.execute('UPDATE tasks SET status=? WHERE id=?',(v('status'),int(v('id'))))
                dest='/tasks'
            elif self.path=='/approval-create':
                title,proposal,risk,tid=(v(k) for k in ('title','proposal','risk','task_id'))
                if not title or not proposal or not risk or len(title)>150 or len(proposal)>4000 or len(risk)>2000 or (tid and (not tid.isascii() or not tid.isdigit() or len(tid)>10)): return self.respond('Onay alanları geçersiz',400)
                with conn(APPROVAL) as c: c.execute('INSERT INTO approvals(task_id,title,proposal,risk,created_at) VALUES(?,?,?,?,?)',(int(tid) if tid else None,title,proposal,risk,now))
                dest='/approvals'
            else:
                idx,decision=v('id'),v('decision')
                if not idx.isascii() or not idx.isdigit() or decision not in ('onaylandi','reddedildi'): return self.respond('Geçersiz karar',400)
                with conn(APPROVAL) as c: c.execute("UPDATE approvals SET status=?,decided_at=? WHERE id=? AND status='bekliyor'",(decision,now,int(idx)))
                dest='/approvals'
        except sqlite3.Error as ex: return self.respond('Veritabanı hatası: '+e(ex),500)
        self.send_response(303); self.send_header('Location',dest); self.send_header('Content-Length','0'); self.end_headers()

if __name__=='__main__':
    init()
    print(f'KADO V3 Tek Panel: http://{HOST}:{PORT}',flush=True)
    print('V1/V2 ve WhatsApp dosyalari degistirilmez. Kapatmak icin Ctrl+C.',flush=True)
    try: ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt: print('KADO V3 kapatildi.')
    except OSError as ex: print('Panel baslatilamadi:',ex)
