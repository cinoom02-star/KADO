#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KADO 3.0 - Tek Adim Kurulum
Sanal Influencer Studyosu icin tek dosyali kurulum.
Guvenli: mevcut V3/V4, WhatsApp, ElevenLabs ve ses ayarlari degistirilmez.
Sadece yeni studyo dosyalari, planlar ve yardimci runtime olusturulur.
"""
from __future__ import annotations
import json, os, shutil, sys, textwrap, datetime as dt, tempfile, unittest
from pathlib import Path

ROOT = Path(r"C:\KADO\KADO-AJANLAR")
BACKUPS = ROOT / "yedekler"
STUDIO = ROOT / "influencer_studio"
RUNTIME = ROOT / "kado_influencer_studio.py"
SUMMARY = STUDIO / "state" / "studio_summary.json"
STARTUP = Path(os.environ.get("APPDATA", r"C:\Users\user\AppData\Roaming")) / Path("Microsoft") / "Windows" / "Start Menu" / "Programs" / "Startup" / "KADO_Influencer_Nobeti_30.cmd"
VERSION = "3.0.0"

def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(p: Path, data):
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def backup_paths(paths: list[Path]) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    target = ensure_dir(BACKUPS / f"kado_v30_{stamp}")
    for p in paths:
        if p.exists():
            dest = target / p.name
            if p.is_file():
                shutil.copy2(p, dest)
            elif p.is_dir():
                shutil.copytree(p, dest, dirs_exist_ok=True)
    return target

def runtime_code() -> str:
    return textwrap.dedent('''
    # -*- coding: utf-8 -*-
    """KADO Influencer Studio runtime - standart kutuphane."""
    from __future__ import annotations
    import json, datetime as dt
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent
    STUDIO = ROOT / "influencer_studio"

    def _read(path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def status():
        identity = _read(STUDIO / "identity" / "influencer_identity.json", {})
        calendar = _read(STUDIO / "calendar" / "30_gunluk_plan.json", {})
        drafts = sorted((STUDIO / "drafts").glob("*.json"))
        return {
            "ok": True,
            "identity_name": identity.get("stage_name", ""),
            "persona": identity.get("persona", ""),
            "days_planned": len(calendar.get("days", [])),
            "draft_count": len(drafts),
            "publish_mode": "KAPALI",
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        }

    def create_draft(project="KADO", topic="tanitim", platform="instagram"):
        identity = _read(STUDIO / "identity" / "influencer_identity.json", {})
        voice = identity.get("voice", {})
        hashtags = {
            "instagram": ["#kesfet", "#yenilik", "#ai", "#kado"],
            "tiktok": ["#fyp", "#kesfet", "#ai", "#kado"],
            "youtube": ["#shorts", "#ai", "#kado"]
        }.get(platform, ["#ai", "#kado"])
        slug = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        draft = {
            "id": slug,
            "project": project,
            "platform": platform,
            "topic": topic,
            "status": "taslak",
            "hook": f"Bugun {project} icin kisa bir fikir: {topic}.",
            "caption": f"{project} icin {topic} temali samimi ve sade bir paylasim taslagi.",
            "script": [
                f"Merhaba, ben {identity.get('stage_name', 'KADO Influencer')}.",
                f"Bugun {project} icin {topic} konusunu anlatiyorum.",
                "Yorumlara dusunceni yazmayi unutma."
            ],
            "visual_prompt": f"Ayni karakter, temiz isik, dikey kadraj, sosyal medya sunucusu tarzinda, konu: {topic}",
            "voice_style": voice.get("style", "samimi ve enerjik"),
            "hashtags": hashtags,
            "needs_human_approval": True,
            "publish_ready": False,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        }
        out = STUDIO / "drafts" / f"{slug}_{platform}_{topic}.json"
        _write(out, draft)
        return {"ok": True, "path": str(out), "draft": draft}

    def report_text():
        s = status()
        return (
            f"Sanal influencer durumu: isim={s['identity_name'] or '-'}, "
            f"planli gun={s['days_planned']}, taslak={s['draft_count']}, "
            f"yayin modu={s['publish_mode']}."
        )

    def main():
        print(report_text())
        return 0

    if __name__ == "__main__":
        raise SystemExit(main())
    ''').strip() + "\n"


def default_identity() -> dict:
    return {
        "version": VERSION,
        "stage_name": "KADO Nova",
        "persona": "samimi, guven veren, modern, Turkce konusan sanal influencer",
        "visual_consistency": {
            "same_face_required": True,
            "notes": [
                "Ayni yuz ve sac stili korunacak.",
                "Dikey sosyal medya kadraji tercih edilecek.",
                "Canli, temiz, modern bir gorunus korunacak."
            ]
        },
        "audience": ["genc yetiskinler", "girisimciler", "ebeveynler", "kucuk isletmeler"],
        "content_pillars": [
            "KADO yapay zeka asistani",
            "Han Toys tanitimlari",
            "arkaplan calismalari",
            "mikro egitici icerikler"
        ],
        "voice": {
            "style": "samimi, net, kisa, guven veren",
            "intro": "Selam, ben KADO Nova.",
            "language": "tr"
        },
        "safety": {
            "needs_human_approval_before_publish": True,
            "auto_account_creation": False,
            "auto_publish": False,
            "impersonation": False
        },
        "updated_at": utc_now()
    }


def default_calendar() -> dict:
    days = []
    themes = [
        ("instagram", "reel", "KADO tanitim"),
        ("tiktok", "kisa video", "Han Toys oyuncak fikri"),
        ("youtube", "short", "Yapay zeka ipucu"),
        ("instagram", "post", "arkaplan gunlugu"),
        ("tiktok", "kisa video", "mikro hikaye")
    ]
    for i in range(1, 31):
        platform, kind, topic = themes[(i - 1) % len(themes)]
        days.append({
            "day": i,
            "platform": platform,
            "type": kind,
            "topic": topic,
            "status": "planlandi",
            "needs_human_approval": True
        })
    return {
        "version": VERSION,
        "goal": "30 gunluk icerik ritmi ve influencer buyutme temeli",
        "days": days,
        "updated_at": utc_now()
    }


def platform_requirements_md() -> str:
    return textwrap.dedent("""
    # KADO 3.0 Platform Notlari

    Bu klasor, resmi platform kurallarina gore calismak icin hazirlanmistir.

    ## Instagram / Meta
    - Kisisel hesap degil, profesyonel hesap gerekir.
    - Yayin icin resmi erisim ve yetki gerekir.
    - Medya URL'leri yayin aninda genel erisilebilir olmalidir.

    ## TikTok
    - Content Posting API ile upload veya direct post yapilabilir.
    - Uygulama ve kapsam onayi gerekir.
    - Denetimsiz istemcilerde gorunurluk kisitlari olabilir.

    ## YouTube
    - YouTube Data API ile video yukleme OAuth ile yapilir.
    - Resumable upload ve retry desteklenir.

    ## KADO guvenlik ilkesi
    - Hesap acma otomatik DEGIL.
    - Yayin otomatik DEGIL.
    - Harcama otomatik DEGIL.
    - Insan onayi olmadan canliya cikis yok.
    """).strip() + "\n"


def sample_brand_book() -> str:
    return textwrap.dedent("""
    # KADO Nova Marka Kitabi

    ## Karakter cekirdegi
    - Isim: KADO Nova
    - Rol: KADO'nun sanal influencer ve sunucusu
    - Kimlik: samimi, zeki, rahat, guven verici

    ## Gorunus hedefi
    - Ayni yuz korunur
    - Temiz isik, sade arka plan, modern kiyafet
    - Dikey video ve mobil odakli kadraj

    ## Icerik tonu
    - Kisa giris
    - Tek ana fikir
    - Net kapanis ve cagrı

    ## Yasaklar
    - Baska gercek kisileri taklit etme
    - Onaysiz sponsorluk iddiasi
    - Onaysiz yayin
    """).strip() + "\n"


def sample_publish_templates() -> dict[str, dict]:
    return {
        "instagram_template.json": {
            "requires_professional_account": True,
            "media_public_url_required": True,
            "alt_text_supported": True,
            "auto_publish": False,
            "status": "baglanti_bekliyor"
        },
        "tiktok_template.json": {
            "direct_post_possible": True,
            "draft_upload_possible": True,
            "scope_examples": ["video.upload", "video.publish"],
            "auto_publish": False,
            "status": "baglanti_bekliyor"
        },
        "youtube_template.json": {
            "api": "videos.insert",
            "oauth_required": True,
            "auto_publish": False,
            "status": "baglanti_bekliyor"
        }
    }


def initial_summary() -> dict:
    return {
        "version": VERSION,
        "status": "hazir",
        "identity": "KADO Nova",
        "drafts": 0,
        "days_planned": 30,
        "publish_mode": "KAPALI",
        "notes": [
            "Sabit karakter altyapisi hazir.",
            "30 gunluk taslak takvim hazir.",
            "Resmi API baglantilari ayri asamada eklenecek.",
            "Onaysiz yayin kapali."
        ],
        "updated_at": utc_now()
    }


def install(root: Path = ROOT) -> dict:
    if not root.exists():
        raise RuntimeError(f"KADO-AJANLAR klasoru bulunamadi: {root}")
    files_to_backup = [STUDIO, RUNTIME]
    backup = backup_paths(files_to_backup)

    ensure_dir(STUDIO / "identity")
    ensure_dir(STUDIO / "calendar")
    ensure_dir(STUDIO / "drafts")
    ensure_dir(STUDIO / "exports")
    ensure_dir(STUDIO / "publish_queue")
    ensure_dir(STUDIO / "reports")
    ensure_dir(STUDIO / "configs")
    ensure_dir(STUDIO / "state")

    write_json(STUDIO / "identity" / "influencer_identity.json", default_identity())
    write_json(STUDIO / "calendar" / "30_gunluk_plan.json", default_calendar())
    (STUDIO / "reports" / "brand_book.md").write_text(sample_brand_book(), encoding="utf-8")
    (STUDIO / "reports" / "platform_notes.md").write_text(platform_requirements_md(), encoding="utf-8")

    for name, data in sample_publish_templates().items():
        write_json(STUDIO / "configs" / name, data)

    RUNTIME.write_text(runtime_code(), encoding="utf-8")
    write_json(SUMMARY, initial_summary())

    # sample draft
    ns = {}
    exec(RUNTIME.read_text(encoding="utf-8"), ns)
    ns["create_draft"]("KADO", "tanitim", "instagram")

    ensure_dir(STARTUP.parent)
    STARTUP.write_text(textwrap.dedent(f'''
        @echo off
        chcp 65001 >nul
        "{sys.executable}" "{RUNTIME}" >nul 2>nul
    ''').strip() + "\n", encoding="utf-8")

    return {
        "backup": str(backup),
        "runtime": str(RUNTIME),
        "identity": str(STUDIO / "identity" / "influencer_identity.json"),
        "calendar": str(STUDIO / "calendar" / "30_gunluk_plan.json"),
        "startup": str(STARTUP)
    }


class SelfTest(unittest.TestCase):
    def test_calendar_length(self):
        cal = default_calendar()
        self.assertEqual(len(cal["days"]), 30)

    def test_identity_flags(self):
        ident = default_identity()
        self.assertFalse(ident["safety"]["auto_publish"])
        self.assertFalse(ident["safety"]["auto_account_creation"])

    def test_runtime_contains_create_draft(self):
        code = runtime_code()
        self.assertIn("def create_draft", code)
        self.assertIn("needs_human_approval", code)

    def test_publish_templates(self):
        t = sample_publish_templates()
        self.assertIn("instagram_template.json", t)
        self.assertTrue(t["youtube_template.json"]["oauth_required"])

    def test_install_in_temp(self):
        with tempfile.TemporaryDirectory() as d:
            fake_root = Path(d)
            global ROOT, STUDIO, RUNTIME, SUMMARY, BACKUPS, STARTUP
            old = (ROOT, STUDIO, RUNTIME, SUMMARY, BACKUPS, STARTUP)
            try:
                ROOT = fake_root
                STUDIO = ROOT / "influencer_studio"
                RUNTIME = ROOT / "kado_influencer_studio.py"
                SUMMARY = STUDIO / "state" / "studio_summary.json"
                BACKUPS = ROOT / "yedekler"
                STARTUP = ROOT / "Startup" / "KADO_Influencer_Nobeti_30.cmd"
                result = install(ROOT)
                self.assertTrue(Path(result["runtime"]).exists())
                self.assertTrue(Path(result["identity"]).exists())
                self.assertTrue(Path(result["calendar"]).exists())
                self.assertTrue(any((STUDIO / "drafts").glob("*.json")))
            finally:
                ROOT, STUDIO, RUNTIME, SUMMARY, BACKUPS, STARTUP = old


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelfTest)
    res = unittest.TextTestRunner(verbosity=0).run(suite)
    if not res.wasSuccessful():
        print("SELFTEST: BASARISIZ")
        return 1
    print(f"Ran {res.testsRun} tests")
    print("OK")
    print("SELFTEST: BASARILI")
    try:
        result = install(ROOT)
    except Exception as exc:
        print(f"HATA: {exc}")
        return 2
    print(f"YEDEK: {result['backup']}")
    print("KURULUM BASARILI: KADO 3.0 Sanal Influencer Studyosu hazir.")
    print("MEVCUT CEO/V3/V4/SES/WHATSAPP AYARLARI DEGISTIRILMEDI.")
    print("YAYIN MODU: KAPALI. Resmi API baglantilari ve tokenlar bu surumde tutulmaz.")
    print("HESAP ACMA: OTOMATIK DEGIL. GERCEK HESAPLAR sonradan baglanir.")
    print(f"RUNTIME: {result['runtime']}")
    print(f"KIMLIK: {result['identity']}")
    print(f"TAKVIM: {result['calendar']}")
    print(f"BASLANGIC: {result['startup']}")
    print("HAZIR: sabit karakter kimligi, 30 gunluk takvim, ilk Instagram taslagi.")
    print("SONRA: KADO'yu yeniden baslat; 'KADO, sanal influencer durumunu anlat' ve 'KADO, KADO icin Instagram taslagi hazirla' de.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
