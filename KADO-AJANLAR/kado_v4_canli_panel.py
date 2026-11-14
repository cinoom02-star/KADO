"""Read-only KADO V4 task dashboard. Does not start workers or execute generated code."""
import argparse, html, json, sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/'memory'/'kado_v4_gorevler.db'
HOST='127.0.0.1'
def snapshot():
    if not DB.is_file(): return [],[], 'Veritabani henuz yok'
    try:
        uri=DB.resolve().as_uri()+'?mode=ro'
        with sqlite3.connect(uri,uri=True,timeout=3) as c:
            c.execute('PRAGMA query_only=ON')
            rows=c.execute('SELECT id,kind,goal,state,updated,static_decision,behavior FROM tasks ORDER BY id DESC LIMIT 100').fetchall()
            events=c.execute('SELECT time,task_id,old_state,new_state FROM events ORDER BY id DESC LIMIT 20').fetchall()
        return rows,events,''
    except (sqlite3.Error,OSError) as ex:return [],[],str(ex)
def esc(x):return html.escape(str(x if x is not None else ''),quote=True)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?')[0] not in ('/','/health'):
            self.send_error(404);return
        if self.path.startswith('/health'):
            body=json.dumps({'db_exists':DB.is_file()}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        rows,events,error=snapshot()
        counts={k:sum(r[3]==k for r in rows) for k in ('json','working','done','review','failed')}
        trs=''.join('<tr>'+''.join(f'<td>{esc(x)}</td>' for x in r)+'</tr>' for r in rows)
        ers=''.join('<tr>'+''.join(f'<td>{esc(x)}</td>' for x in r)+'</tr>' for r in events)
        cards=''.join(f'<div class="card"><b>{esc(k)}</b><strong>{v}</strong></div>' for k,v in counts.items())
        page=f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta http-equiv="refresh" content="8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KADO V4 Canlı Görevler</title><style>body{{background:#0d1424;color:#eef3ff;font:15px system-ui;margin:0;padding:25px}}main{{max-width:1200px;margin:auto}}h1{{font-size:25px}}.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:#192640;border:1px solid #36496b;border-radius:12px;padding:15px;min-width:110px}}strong{{display:block;font-size:27px;margin-top:8px}}.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{text-align:left;border-bottom:1px solid #34435a;padding:9px;overflow-wrap:anywhere;max-width:320px}}section{{margin:26px 0}}small{{color:#aabbd4}}.warn{{color:#ffb5b5}}</style></head><body><main><h1>🤖 KADO — V4 Canlı Görev Takibi</h1><small>Yalnızca yerel görüntüleme · 8 saniyede yenilenir · Kod çalıştırmaz · Onay vermez</small><p class="warn">{esc(error)}</p><div class="cards">{cards}</div><section><h2>Son 100 görev</h2><div class="scroll"><table><thead><tr><th>Kimlik</th><th>Tür</th><th>Görev</th><th>Durum</th><th>Güncelleme</th><th>Statik</th><th>Davranış</th></tr></thead><tbody>{trs}</tbody></table></div></section><section><h2>Son 20 durum değişikliği</h2><div class="scroll"><table><thead><tr><th>Zaman</th><th>Görev</th><th>Önce</th><th>Sonra</th></tr></thead><tbody>{ers}</tbody></table></div></section></main></body></html>'''
        data=page.encode('utf-8');self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8771);p.add_argument('--selftest',action='store_true');a=p.parse_args()
    if a.selftest:
        assert esc('<script>')=='&lt;script&gt;'; assert snapshot()[2]=='' or not DB.exists();print('PANEL SELFTEST BASARILI');return
    server=ThreadingHTTPServer((HOST,a.port),Handler)
    print(f'KADO CANLI PANEL: http://{HOST}:{a.port}  | Ctrl+C ile durdur',flush=True)
    server.serve_forever()
if __name__=='__main__':main()
