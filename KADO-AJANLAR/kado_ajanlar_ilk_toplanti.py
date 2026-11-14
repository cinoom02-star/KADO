import os, sqlite3, json, datetime, pathlib, sys
from google import genai

ROOT = pathlib.Path(__file__).resolve().parent
DB = ROOT / 'memory' / 'kado_company.db'
MODEL = os.getenv('KADO_AGENT_MODEL', 'gemini-2.5-flash')
ROLES = [
 ('arastirmaci', 'Pazar arastirmacisisin. Kanitlanmamis iddialari kesin bilgi gibi sunma. Firsat, hedef kitle, gelir modeli ve belirsizlikleri acikla.'),
 ('mimar', 'Yazilim mimarisin. Onceki arastirmaci gorusunu elestirel degerlendir. Teknik kapsam, MVP, risk ve uygulanabilirligi anlat.'),
 ('denetci', 'Bagimsiz denetcisin. Onceki iki ajanin varsayimlarini sorgula; guvenlik, butce, telif, cocuk uygulamalari ve gerceklik kontrollerini yap.'),
 ('kado_ceo', 'KADO CEO olarak onceki tum gorusleri degerlendir. Karar, gerekce, onay gerektiren isler ve sonraki 3 somut gorevi belirt. Hicbir dis eylemin yapildigini iddia etme.')
]

def setup_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute('CREATE TABLE IF NOT EXISTS meetings (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, topic TEXT NOT NULL, status TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)')
    con.commit()
    return con

def main():
    key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not key:
        print('HATA: GEMINI_API_KEY tanimli degil. Anahtari sohbete gonderme.', file=sys.stderr)
        return 2
    topic = 'KADO AI sirketinin ilk dusuk maliyetli ve ozgun dijital urunu ne olmali?'
    con = setup_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = con.execute('INSERT INTO meetings(started_at,topic,status) VALUES(?,?,?)', (now,topic,'running'))
    meeting_id = cur.lastrowid
    con.commit()
    client = genai.Client(api_key=key)
    history = []
    try:
        for role, instruction in ROLES:
            prompt = f'Gundem: {topic}\n\nOnceki gorusler:\n' + ('\n\n'.join(history) if history else 'Henuz yok.') + '\n\nEn fazla 250 kelime, Turkce, somut ve olculebilir yanit ver.'
            result = client.models.generate_content(model=MODEL, contents=prompt, config={'system_instruction': instruction, 'temperature': 0.4, 'max_output_tokens': 850})
            answer = (result.text or '').strip()
            if not answer:
                raise RuntimeError(f'{role} bos yanit verdi')
            history.append(f'{role}: {answer}')
            con.execute('INSERT INTO messages(meeting_id,role,content,created_at) VALUES(?,?,?,?)', (meeting_id,role,answer,datetime.datetime.now(datetime.timezone.utc).isoformat()))
            con.commit()
            print(f'\n===== {role.upper()} =====\n{answer}\n', flush=True)
        con.execute('UPDATE meetings SET status=? WHERE id=?', ('completed',meeting_id))
        con.commit()
        print(f'\nTOPLANTI TAMAMLANDI | ID: {meeting_id} | DB: {DB}')
        return 0
    except Exception as exc:
        con.execute('UPDATE meetings SET status=? WHERE id=?', ('failed',meeting_id))
        con.commit()
        print(f'TOPLANTI DURDU: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    finally:
        client.close()
        con.close()

if __name__ == '__main__':
    sys.exit(main())
