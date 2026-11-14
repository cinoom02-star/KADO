# -*- coding: utf-8 -*-
"""KADO ENVANTER - sadece OKUR. Hicbir dosyayi/veritabanini degistirmez, anahtar okumaz.
Kullanim: python kado_envanter.py [KADO-AJANLAR klasoru]
"""
import re, sys, sqlite3, datetime
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
out = []
def p(s=""):
    out.append(s); print(s)

def db(name):
    f = root / "memory" / name
    if not f.exists():
        return None
    return sqlite3.connect(f"file:{f.as_posix()}?mode=ro", uri=True)

p(f"# KADO ENVANTER - {datetime.datetime.now():%d.%m.%Y %H:%M}")
p(f"Klasor: {root}\n")

# 1) 4 ana ajan
c = db("kado_company.db")
p("## 1) Ana ajanlar (toplantilarda konusan roller)")
if c:
    for role, n in c.execute("select role,count(*) from messages group by role order by 2 desc"):
        p(f"- {role}: {n} mesaj")
else:
    p("- kado_company.db bulunamadi")

# 2) 19 uzman
p("\n## 2) 19 uzman kadrosu (kado_19_uzman.py) - sadece tanimli kadro; gercekten calisip calismadigi ayri test ister")
f = root / "kado_19_uzman.py"
code_files = "\n".join(x.read_text(encoding="utf-8", errors="ignore")
                       for x in root.glob("kado_*.py") if x.name != "kado_19_uzman.py")
if f.exists():
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for uid, ad, rol, yet in re.findall(r'Uzman\("(U\d+)",\s*"([^"]+)",\s*"([^"]+)",\s*\(([^)]*)\)', txt):
        yets = re.findall(r'"([^"]+)"', yet)
        p(f"- {uid} {ad} [{rol}] yetenek={','.join(yets)}")
else:
    p("- kado_19_uzman.py bulunamadi")

# 3) toplantilar
p("\n## 3) Toplantilar")
if c:
    toplam = c.execute("select count(*) from meetings").fetchone()[0]
    p(f"Toplam: {toplam}")
    for st, n in c.execute("select status,count(*) from meetings group by status"):
        p(f"- {st}: {n}")
    p("\nSon 8 toplanti:")
    for i, t, st, top, n in c.execute(
        "select m.id,m.started_at,m.status,m.topic,(select count(*) from messages where meeting_id=m.id) "
        "from meetings m order by m.id desc limit 8"):
        p(f"- #{i} | {t[:16]} | {st} | {n} mesaj | {top[:70]}")
    p("\nGorevler (kado_company.db):")
    for i, t, st, ca in c.execute("select id,title,status,created_at from tasks"):
        p(f"- #{i} | {st} | {t}")

# 4) onay durumu (gercek kaynak: kuyruk dosya uzantilari + onaylar\\*.json)
import json
kq = root / "kado_agent_motor" / "kuyruk"
ko = root / "kado_agent_motor" / "onaylar"
def _j(pth):
    try:
        return json.loads(pth.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
p("\n## 4) Gorev kuyrugu ve kararlar (kado_agent_motor\\kuyruk, onaylar)")
if kq.exists():
    sayac = {}
    for x in kq.iterdir():
        sayac[x.suffix[1:]] = sayac.get(x.suffix[1:], 0) + 1
    p("Dosya durumlari: " + ", ".join(f"{k}={v}" for k, v in sorted(sayac.items())))
    p("\nOnay bekleyen (.review):")
    rv = sorted(kq.glob("*.review"))
    for x in rv:
        j = _j(x); p(f"- {x.stem} | {j.get('kind','?')} | {str(j.get('goal',''))[:60]}")
    if not rv:
        p("- yok")
else:
    p("- kuyruk klasoru bulunamadi")
p("\nVerilen kararlar (onaylar\\*.json):")
kl = sorted(ko.glob("*.json")) if ko.exists() else []
for x in kl:
    k = _j(x); p(f"- {k.get('zaman','')[:16]} | {k.get('karar')} | {k.get('id')} | {k.get('not','')}")
if not kl:
    p("- yok")

# 5) V4 veritabani (not: kado_onay.py kararlari buraya yazmaz, durum gecikmeli olabilir)
p("\n## 5) V4 gorev merkezi veritabani (kararlar dosyalardan okunur; bu tablo gecikmeli olabilir)")
v = db("kado_v4_gorevler.db")
if v:
    for i, k, g, st, u in v.execute("select id,kind,goal,state,updated from tasks order by updated desc limit 10"):
        p(f"- {i} | {k} | db durumu={st} | {(g or '')[:55]}")
else:
    p("- bulunamadi")

# 5b) eski CEO onerileri
p("\n## 5b) Eski CEO onerileri (kado_approvals.db, kado_onay_merkezi.py web sayfasi yonetir)")
a = db("kado_approvals.db")
if a:
    for st, n in a.execute("select status,count(*) from approvals group by status"):
        p(f"- {st}: {n}")
else:
    p("- bulunamadi")

# 6) dosyalar
p("\n## 6) Kod dosyalari")
py = sorted(x.name for x in root.glob("kado_*.py"))
p(f"{len(py)} adet kado_*.py. Son degisen 8:")
for x in sorted(root.glob("kado_*.py"), key=lambda x: x.stat().st_mtime, reverse=True)[:8]:
    p(f"- {x.name} ({datetime.datetime.fromtimestamp(x.stat().st_mtime):%d.%m %H:%M})")
for d in ("agents", "departments", "ceo", "dashboard", "evaluation", "approval"):
    dd = root / d
    if dd.exists():
        p(f"- klasor {d}/: {sum(1 for _ in dd.rglob('*') if _.is_file())} dosya")

# 7) icerik hatti ciktilari
p("\n## 7) Uretilen paketler (ciktilar)")
cd = root / "kado_agent_motor" / "ciktilar"
if cd.exists():
    for x in sorted((d for d in cd.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)[:12]:
        ek = [n for n in ("icerik_paketi.md", "gorseller", "video") if (x / n).exists()]
        p(f"- {x.name} | {', '.join(ek) if ek else 'kod/diger'}")

rp = root / "raporlar"
rp.mkdir(exist_ok=True)
dosya = rp / f"envanter_{datetime.datetime.now():%Y%m%d_%H%M}.md"
dosya.write_text("\n".join(out), encoding="utf-8")
p(f"\nKAYDEDILDI: {dosya}")
