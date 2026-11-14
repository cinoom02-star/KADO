"""KADO owner approval queue. Separate local-only service; never executes actions."""
import datetime as dt
import html
import secrets
import sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'memory' / 'kado_approvals.db'
HOST, PORT = '127.0.0.1', 8767
TOKEN = secrets.token_urlsafe(32)


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute('PRAGMA busy_timeout=10000')
    con.execute('''CREATE TABLE IF NOT EXISTS approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        title TEXT NOT NULL,
        proposal TEXT NOT NULL,
        risk TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'bekliyor',
        created_at TEXT NOT NULL,
        decided_at TEXT
    )''')
    con.commit()
    return con


def e(s):
    return html.escape(str(s if s is not None else ''), quote=True)


class Handler(BaseHTTPRequestHandler):
    def reply(self, content, status=200):
        body = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != '/':
            return self.reply('Bulunamadi', 404)
        with connect() as con:
            items = con.execute('SELECT id,task_id,title,proposal,risk,status,created_at,decided_at FROM approvals ORDER BY id DESC LIMIT 100').fetchall()
        cards = []
        for i, tid, title, proposal, risk, status, created, decided in items:
            buttons = ''
            if status == 'bekliyor':
                buttons = ''.join(f'''<form method="post" action="/decide"><input type="hidden" name="token" value="{TOKEN}"><input type="hidden" name="id" value="{i}"><input type="hidden" name="decision" value="{choice}"><button class="{cls}">{label}</button></form>''' for choice, cls, label in [('onaylandi','yes','Onayla'),('reddedildi','no','Reddet')])
            cards.append(f'''<article><div class="top"><strong>#{i} · {e(title)}</strong><span class="status">{e(status)}</span></div><small>Gorev: {e(tid or '-')} · {e(created)}</small><h4>Oneri</h4><p>{e(proposal)}</p><h4>Risk / Etki</h4><p>{e(risk)}</p><div class="actions">{buttons}</div><small>{'Karar: '+e(decided) if decided else ''}</small></article>''')
        page = f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>KADO Patron Onay Merkezi</title><style>
        *{{box-sizing:border-box}}body{{margin:0;background:#0a1120;color:#eef5ff;font:15px/1.55 system-ui,sans-serif}}main{{max-width:1050px;margin:30px auto;padding:0 18px}}h1{{font-size:28px;margin-bottom:4px}}.muted,small{{color:#9fb1cc}}.notice{{border:1px solid #425b80;background:#15263f;padding:14px;border-radius:12px;margin:20px 0}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}section,article{{background:#142139;border:1px solid #293c5c;border-radius:15px;padding:19px;margin:16px 0}}label{{display:block;margin:11px 0 5px}}input,textarea{{display:block;width:100%;padding:11px;background:#0b1527;border:1px solid #566b88;border-radius:8px;color:#fff;font:inherit}}textarea{{min-height:80px}}button{{border:0;border-radius:8px;padding:10px 16px;background:#80afff;color:#081426;font-weight:bold;cursor:pointer}}.yes{{background:#6ed5b5}}.no{{background:#ff9ca7}}.actions{{display:flex;gap:10px}}.top{{display:flex;justify-content:space-between;gap:12px}}.status{{font-size:12px;color:#d1e1ff}}h4{{margin:13px 0 3px}}p{{white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0 10px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><main><h1>🛡️ KADO Patron Onay Merkezi</h1><div class="muted">Yerel sistem · Sadece sahibin kararları kaydedilir</div><div class="notice"><b>Guvenlik:</b> Onaylamak yalnizca bir karar kaydi olusturur. Dosya degistirme, kod calistirma, yayinlama, satin alma veya WhatsApp mesaji gonderme yapmaz. Ajanlar bu sayfadan otomatik islem baslatamaz.</div><div class="grid"><section><h2>Yeni onay talebi</h2><form method="post" action="/create"><input type="hidden" name="token" value="{TOKEN}"><label>Gorev ID (istege bagli)</label><input name="task_id" inputmode="numeric" maxlength="10" placeholder="1"><label>Baslik</label><input name="title" required maxlength="150" placeholder="Ornek: MVP gelistirme onayi"><label>Yapilmasi onerilen islem</label><textarea name="proposal" required maxlength="4000"></textarea><label>Riskler ve etkiler</label><textarea name="risk" required maxlength="2000"></textarea><button>Onaya gonder</button></form></section><section><h2>Onay kayitlari ({len(items)})</h2>{''.join(cards) or '<p>Henuz onay talebi yok.</p>'}</section></div></main></body></html>'''
        self.reply(page)

    def do_POST(self):
        if self.path not in ('/create', '/decide'):
            return self.reply('Bulunamadi', 404)
        if self.headers.get('Origin') not in (None, f'http://{HOST}:{PORT}'):
            return self.reply('Kaynak reddedildi', 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.reply('Gecersiz uzunluk', 400)
        if not 0 < length <= 12000:
            return self.reply('Istek boyutu gecersiz', 413)
        try:
            data = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True)
        except UnicodeDecodeError:
            return self.reply('Kodlama hatasi', 400)
        val = lambda key: data.get(key, [''])[0]
        if not secrets.compare_digest(val('token'), TOKEN):
            return self.reply('Yetkisiz', 403)
        with connect() as con:
            if self.path == '/create':
                title, proposal, risk, tid = (val(k).strip() for k in ('title','proposal','risk','task_id'))
                if not title or not proposal or not risk or len(title)>150 or len(proposal)>4000 or len(risk)>2000 or (tid and (not tid.isascii() or not tid.isdigit() or len(tid)>10)):
                    return self.reply('Alanlar gecersiz', 400)
                con.execute('INSERT INTO approvals(task_id,title,proposal,risk,created_at) VALUES (?,?,?,?,?)', (int(tid) if tid else None,title,proposal,risk,dt.datetime.now(dt.timezone.utc).isoformat()))
            else:
                idx, decision = val('id'), val('decision')
                if not idx.isascii() or not idx.isdigit() or decision not in ('onaylandi','reddedildi'):
                    return self.reply('Karar gecersiz', 400)
                con.execute("UPDATE approvals SET status=?, decided_at=? WHERE id=? AND status='bekliyor'", (decision,dt.datetime.now(dt.timezone.utc).isoformat(),int(idx)))
            con.commit()
        self.send_response(303)
        self.send_header('Location','/')
        self.send_header('Content-Length','0')
        self.end_headers()

if __name__ == '__main__':
    connect().close()
    print(f'KADO Patron Onay Merkezi: http://{HOST}:{PORT}', flush=True)
    try:
        ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt:
        print('Onay merkezi kapatildi.')
