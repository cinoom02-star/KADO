"""KADO AI Company V2 — read-only local dashboard. No third-party packages."""
from __future__ import annotations
import html
import json
import sqlite3
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'memory' / 'kado_company.db'
HOST, PORT = '127.0.0.1', 8766
STATE = ROOT / 'memory' / 'agent_live_state.json'

def live_state():
    try:
        data = json.loads(STATE.read_text(encoding='utf-8'))
        if not isinstance(data, dict): return {}
        if time.time() - float(data.get('updated_at', 0)) > 90 and data.get('phase') == 'running':
            data['phase'] = 'stale'
        return data
    except (OSError, ValueError, TypeError):
        return {}


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)

def fetch_data():
    if not DB.is_file():
        return {'error': 'Veritabani bulunamadi: ' + str(DB)}
    try:
        with sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True, timeout=3) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            tasks = [dict(x) for x in db.execute('SELECT id,title,details,status,created_at FROM tasks ORDER BY id DESC LIMIT 100')] if 'tasks' in tables else []
            meetings = [dict(x) for x in db.execute('SELECT id,topic,status,started_at FROM meetings ORDER BY id DESC LIMIT 30')] if 'meetings' in tables else []
            return {'tasks': tasks, 'meetings': meetings}
    except sqlite3.Error as e:
        return {'error': 'Veritabani okuma hatasi: ' + str(e)}

def fetch_meeting(mid):
    if not DB.is_file(): return None
    try:
        with sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True, timeout=3) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            meeting = db.execute('SELECT id,topic,status,started_at FROM meetings WHERE id=?', (mid,)).fetchone()
            if not meeting: return None
            messages = [dict(r) for r in db.execute('SELECT role,content,created_at FROM messages WHERE meeting_id=? ORDER BY id', (mid,))]
            return {'meeting': dict(meeting), 'messages': messages}
    except sqlite3.Error: return None

STYLE = r'''
:root{color-scheme:dark;--bg:#080e1c;--panel:#121d32;--line:#293a56;--muted:#9cafc9;--txt:#f2f7ff;--accent:#77b7ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#142440 0%,var(--bg) 60%);color:var(--txt);font:15px system-ui,-apple-system,'Segoe UI',sans-serif}
a{color:#a7cfff;text-decoration:none}a:hover{text-decoration:underline}.shell{max-width:1200px;margin:auto;padding:26px 18px 60px}
.top{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.brand{display:flex;align-items:center;gap:13px}.logo{width:51px;height:51px;border-radius:15px;background:linear-gradient(135deg,#3d7cf5,#65e3d1);display:grid;place-items:center;font-size:28px;box-shadow:0 0 25px #3b8fff55}
h1{font-size:25px;margin:0}h2{font-size:19px;margin:0 0 16px}.muted{color:var(--muted)}.sub{font-size:12px;margin-top:4px}.pill{border:1px solid #3c5c78;border-radius:999px;padding:8px 12px;font-size:12px;background:#14273a}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:23px 0}.stat,.panel,.agent{background:linear-gradient(160deg,#17253c,#10192b);border:1px solid var(--line);border-radius:18px;padding:18px}.stat strong{font-size:28px;display:block;margin-top:6px}
.agents{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.agent{text-align:center;position:relative;overflow:hidden;min-height:218px}.agent:before{content:'';position:absolute;inset:-50%;background:conic-gradient(transparent 75%,#5b8bff17);animation:spin 12s linear infinite;pointer-events:none}.agent>*{position:relative}.avatar{height:82px;width:82px;margin:8px auto 13px;border-radius:26px;display:grid;place-items:center;font-size:39px;background:linear-gradient(145deg,#293e62,#17223b);border:1px solid #47618b;box-shadow:0 0 24px #4e8fff26;animation:float 3.8s ease-in-out infinite}.agent:nth-child(2) .avatar{animation-delay:-.8s}.agent:nth-child(3) .avatar{animation-delay:-1.5s}.agent:nth-child(4) .avatar{animation-delay:-2.3s}.agent h3{margin:4px 0;font-size:17px}.agent .role{font-size:12px;color:var(--muted);min-height:20px}.state{display:inline-flex;align-items:center;gap:7px;color:#c2cde0;font-size:12px;margin-top:14px}.dot{height:7px;width:7px;border-radius:50%;background:#8192a9}.dot.live{background:#42e2b0;box-shadow:0 0 12px #42e2b0;animation:pulse 1.3s infinite}.agent.working{border-color:#42e2b0;box-shadow:0 0 24px #42e2b033}.agent.working .avatar{animation:float 1.2s ease-in-out infinite;box-shadow:0 0 25px #42e2b077}.agent.done .dot{background:#42e2b0}.agent.failed .dot{background:#ff778a}.live-info{margin:16px 0;padding:12px 16px;border:1px solid #345475;border-radius:12px;color:#c8dcfa}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}.panel{min-width:0}.item{display:block;border-top:1px solid var(--line);padding:13px 0;line-height:1.5}.item:first-of-type{border-top:0}.item .meta{font-size:12px;color:var(--muted);margin-top:5px}.tag{display:inline-block;padding:3px 8px;border:1px solid #4c6284;border-radius:8px;color:#cbdcff;font-size:11px;margin-left:6px}.notice{margin-top:20px;color:#adc0d9;font-size:12px}.back{display:inline-block;margin:12px 0 24px}.report{background:#0c1525;border:1px solid var(--line);border-radius:15px;padding:18px;margin:12px 0}.report pre{font:14px/1.7 system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;margin-bottom:0}.error{padding:18px;border:1px solid #b86d7a;background:#40202b;border-radius:12px}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}@keyframes pulse{50%{opacity:.4}}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:850px){.agents{grid-template-columns:repeat(2,1fr)}.stats{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}}@media(max-width:430px){.agents{gap:8px}.agent{padding:12px;min-height:198px}.avatar{height:65px;width:65px;font-size:30px}.shell{padding:18px 12px}}
@media(prefers-reduced-motion:reduce){*,*:before{animation:none!important}}
'''

def wrap(body, refresh=False):
    meta = '<meta http-equiv="refresh" content="3">' if refresh else ''
    return f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">{meta}<title>KADO | AI Sirketi V2</title><style>{STYLE}</style></head><body><div class="shell">{body}</div></body></html>'

def home():
    d = fetch_data()
    if 'error' in d: return wrap(f'<h1>KADO V2</h1><div class="error">{esc(d["error"])}</div>')
    tasks, meetings = d['tasks'], d['meetings']
    active = sum(t['status'] == 'devam' for t in tasks)
    completed = sum(t['status'] == 'tamam' for t in tasks)
    stats = [('Ajan profili','4'),('Toplanti',len(meetings)),('Gorev',len(tasks)),('Tamamlanan gorev',completed)]
    stat_html = ''.join(f'<div class="stat"><span class="muted">{esc(label)}</span><strong>{esc(value)}</strong></div>' for label,value in stats)
    agents = [('👑','KADO','CEO / Yonetici'),('🔎','Arastirmaci','Fikir ve pazar analizi'),('🧩','Mimar','Yazilim ve sistem'),('🛡️','Denetci','Kalite ve risk')]
    live = live_state()
    current = str(live.get('agent', '')).upper()
    phase = live.get('phase', '')
    completed_agents = set(live.get('completed_agents', [])) if isinstance(live.get('completed_agents'), list) else set()
    agent_keys = ['KADO_CEO', 'ARASTIRMACI', 'MIMAR', 'DENETCI']
    parts = []
    for (ico, name, role), key in zip(agents, agent_keys):
        working = phase == 'running' and current == key
        done = key in completed_agents
        failed = phase == 'failed' and current == key
        css = 'working' if working else 'failed' if failed else 'done' if done else ''
        label = 'Dusunuyor...' if working else 'Hata' if failed else 'Tamamladi' if done else 'Gorev bekliyor'
        dot = 'live' if working else ''
        parts.append(f'<article class="agent {css}"><div class="avatar" aria-hidden="true">{ico}</div><h3>{name}</h3><div class="role">{role}</div><div class="state"><span class="dot {dot}"></span> {label}</div></article>')
    agent_html = ''.join(parts)
    live_message = str(live.get('message', ''))[:250]
    live_note = f'<div class="live-info">Canli gorev #{esc(live.get("task_id", "?"))} · {esc(live_message)}</div>' if live and phase != 'stale' else '<div class="live-info">Canli gorev calismiyor veya son durum guncel degil.</div>'

    task_html = ''.join(f'<div class="item"><b>#{t["id"]} {esc(t["title"])}</b><span class="tag">{esc(t["status"])}</span><div class="meta">{esc(t["details"] or "Aciklama yok")}</div></div>' for t in tasks[:15]) or '<p class="muted">Henuz gorev yok.</p>'
    meeting_html = ''.join(f'<a class="item" href="/meeting?id={m["id"]}"><b>#{m["id"]} {esc(m["topic"])}</b><span class="tag">{esc(m["status"])}</span><div class="meta">{esc(m["started_at"] or "")}</div></a>' for m in meetings[:15]) or '<p class="muted">Toplanti yok.</p>'
    body = f'<header class="top"><div class="brand"><div class="logo">🤖</div><div><h1>KADO COMMAND CENTER</h1><div class="muted sub">AI Sirketi / Yonetim Merkezi V2</div></div></div><div class="pill">● Yerel sistem · Salt okunur</div></header><div class="stats">{stat_html}</div><h2>AI Ajan Kadrosu</h2><div class="agents">{agent_html}</div>{live_note}<div class="cols"><section class="panel"><h2>Gorev panosu <span class="tag">{active} devam ediyor</span></h2>{task_html}</section><section class="panel"><h2>Toplanti gecmisi</h2>{meeting_html}</section></div><p class="notice">3 saniyede bir yenilenir. Avatarlar dekoratif olarak hareket eder; calisma durumlari yeni baslaticinin canli kaydindan okunur. Gorev durumlari veritabanindan okunur. Bu surum islem baslatmaz, dosya degistirmez veya onay vermez.</p>'
    return wrap(body, refresh=True)

def detail(mid):
    d = fetch_meeting(mid)
    if not d: return wrap('<a class="back" href="/">← Ana panel</a><div class="error">Toplanti bulunamadi.</div>')
    m = d['meeting']
    sections = ''.join(f'<article class="report"><h2>{esc(msg["role"])}</h2><div class="muted sub">{esc(msg["created_at"])}</div><pre>{esc(msg["content"])}</pre></article>' for msg in d['messages']) or '<p>Kayitli mesaj yok.</p>'
    return wrap(f'<a class="back" href="/">← Ana panele don</a><h1>Toplanti #{mid}</h1><p>{esc(m["topic"])}</p><p class="muted">Durum: {esc(m["status"])}</p>{sections}<p class="notice">Raporlar veritabaninda kaydedildigi haliyle gosterilir. Eksik kaydedilen metinler burada tamamlanamaz.</p>')

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            page, status = home(), 200
        elif parsed.path == '/meeting':
            try:
                mid = int(parse_qs(parsed.query).get('id', [''])[0]); assert mid > 0
                page, status = detail(mid), 200
            except (ValueError, AssertionError):
                page, status = 'Gecersiz toplanti numarasi', 400
        else:
            page, status = 'Sayfa bulunamadi', 404
        data = page.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)
    def do_POST(self):
        self.send_error(405, 'Salt okunur panel')

if __name__ == '__main__':
    print('KADO V2 hazir: http://127.0.0.1:8766', flush=True)
    print('Kapatmak icin Ctrl+C. Mevcut V1 panel etkilenmez.', flush=True)
    try: ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt: print('\nKADO V2 kapatildi.')
    except OSError as exc: print('Panel baslatilamadi:', exc)
