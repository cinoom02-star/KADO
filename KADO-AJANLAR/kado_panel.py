"""KADO-AJANLAR local, owner-controlled MVP dashboard. Standard library only."""
import datetime as dt
import html
import os
from pathlib import Path
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'memory' / 'kado_company.db'
HOST, PORT = '127.0.0.1', 8765
TOKEN = secrets.token_urlsafe(24)


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute('PRAGMA busy_timeout=10000')
    conn.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, details TEXT NOT NULL DEFAULT "", status TEXT NOT NULL DEFAULT "bekliyor", created_at TEXT NOT NULL)')
    conn.commit()
    return conn


def esc(value):
    return html.escape(str(value), quote=True)


class Handler(BaseHTTPRequestHandler):
    def respond(self, body, status=200):
        data = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != '/':
            return self.respond('Sayfa bulunamadi', 404)
        with connect() as db:
            tasks = db.execute('SELECT id,title,details,status,created_at FROM tasks ORDER BY id DESC LIMIT 100').fetchall()
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            meetings = db.execute('SELECT id,topic,status,started_at FROM meetings ORDER BY id DESC LIMIT 10').fetchall() if 'meetings' in tables else []
        rows = ''.join(f'<tr><td>#{t[0]}</td><td><b>{esc(t[1])}</b><small>{esc(t[2])}</small></td><td>{esc(t[3])}</td><td><form method="post" action="/status"><input type="hidden" name="token" value="{TOKEN}"><input type="hidden" name="id" value="{t[0]}"><select name="status"><option value="bekliyor">Bekliyor</option><option value="devam">Devam</option><option value="tamam">Tamam</option></select><button>Guncelle</button></form></td></tr>' for t in tasks)
        history = ''.join(f'<tr><td>#{m[0]}</td><td>{esc(m[1])}</td><td>{esc(m[2])}</td><td>{esc(m[3][:19])}</td></tr>' for m in meetings)
        page = f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>KADO Yonetim Paneli</title><style>body{{background:#0b1220;color:#edf2f7;font:16px system-ui,sans-serif;max-width:1080px;margin:35px auto;padding:0 18px}}h1{{font-size:30px}}.sub,small{{color:#9eacc0}}small{{display:block;margin-top:5px}}section{{background:#172235;padding:22px;border-radius:16px;margin:22px 0}}input,textarea,select{{background:#0b1220;color:white;border:1px solid #52647e;border-radius:7px;padding:10px;max-width:100%;box-sizing:border-box}}input,textarea{{width:100%;margin:7px 0 14px}}button{{background:#6b8fff;color:#081020;border:0;border-radius:7px;padding:10px 13px;font-weight:bold;cursor:pointer}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #354258;padding:12px;text-align:left;vertical-align:top}}.scroll{{overflow-x:auto}}form{{margin:0}}.notice{{color:#b9d7ff}}</style></head><body><h1>KADO / Yonetim Paneli</h1><p class="sub">Yerel prototip · Sadece bu bilgisayarda · Ajanlar otomatik islem yapmaz</p><section><h2>Yeni gorev olustur</h2><form method="post" action="/task"><input type="hidden" name="token" value="{TOKEN}"><label>Gorev adi</label><input name="title" maxlength="150" required placeholder="Ornek: Urun aciklamasi MVP tasarla"><label>Aciklama</label><textarea name="details" maxlength="2000" rows="3" placeholder="Hedef, sinirlar, teslim kriterleri"></textarea><button>Gorevi kaydet</button></form></section><section><h2>Gorevler ({len(tasks)})</h2><div class="scroll"><table><tr><th>ID</th><th>Gorev</th><th>Durum</th><th>Islem</th></tr>{rows or '<tr><td colspan="4">Henuz gorev yok.</td></tr>'}</table></div></section><section><h2>Son toplantilar</h2><div class="scroll"><table><tr><th>ID</th><th>Gundem</th><th>Durum</th><th>Tarih (UTC)</th></tr>{history or '<tr><td colspan="4">Toplanti kaydi yok.</td></tr>'}</table></div></section><p class="notice">Bu panel, mevcut KADO ile baglantili degildir. API anahtari kullanmaz. Otomatik gorev calistirma kapali.</p></body></html>'''
        self.respond(page)

    def do_POST(self):
        if self.path not in ('/task', '/status'):
            return self.respond('Bulunamadi', 404)
        if self.headers.get('Origin') not in (None, f'http://{HOST}:{PORT}'):
            return self.respond('Kaynak reddedildi', 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.respond('Gecersiz istek', 400)
        if not 0 < length <= 8192:
            return self.respond('Istek boyutu gecersiz', 413)
        data = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True)
        get = lambda name: data.get(name, [''])[0]
        if not secrets.compare_digest(get('token'), TOKEN):
            return self.respond('Yetkisiz istek', 403)
        with connect() as db:
            if self.path == '/task':
                title, details = get('title').strip(), get('details').strip()
                if not title or len(title) > 150 or len(details) > 2000:
                    return self.respond('Gorev alanlari gecersiz', 400)
                db.execute('INSERT INTO tasks(title,details,status,created_at) VALUES(?,?,?,?)', (title, details, 'bekliyor', dt.datetime.now(dt.timezone.utc).isoformat()))
            else:
                if get('status') not in ('bekliyor', 'devam', 'tamam') or not get('id').isdigit():
                    return self.respond('Gecersiz durum', 400)
                db.execute('UPDATE tasks SET status=? WHERE id=?', (get('status'), int(get('id'))))
            db.commit()
        self.send_response(303)
        self.send_header('Location', '/')
        self.send_header('Content-Length', '0')
        self.end_headers()


if __name__ == '__main__':
    print(f'KADO panel hazir: http://{HOST}:{PORT}', flush=True)
    print('Kapatmak icin Ctrl+C. Sadece yerel bilgisayarda acilir.', flush=True)
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nPanel kapatildi.')
    except OSError as exc:
        print(f'Panel baslatilamadi: {exc}')
