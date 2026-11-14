# -*- coding: utf-8 -*-
"""KADO NOBETCI - projeler.json'daki her projeyi sirayla icerik -> kart -> video hattindan gecirir.
Hicbir seyi YAYINLAMAZ, onaylamaz. Mevcut kado_*.py dosyalarini degistirmez, sadece cagirir.

Kullanim:
  python kado_nobetci.py              # bugun henuz uretilmeyen projeleri calistirir
  python kado_nobetci.py --zorla      # bugun uretilmis olsa da tekrar calistirir
  python kado_nobetci.py --proje KADO # sadece bu proje
"""
import sys, os, re, json, time, shutil, subprocess, datetime, urllib.request, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJELER = ROOT / "projeler.json"
DURUM = ROOT / "memory" / "nobetci_durum.json"
LOCK = ROOT / "memory" / "nobetci.lock"
LOGDIR = ROOT / "raporlar"
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
ICERIK_TIMEOUT = 40 * 60   # yerel model yavas olabilir
KISA_TIMEOUT = 10 * 60

LOGDIR.mkdir(exist_ok=True)
(ROOT / "memory").mkdir(exist_ok=True)
log_f = LOGDIR / f"nobetci_{datetime.datetime.now():%Y%m%d}.log"

def log(s):
    line = f"[{datetime.datetime.now():%H:%M:%S}] {s}"
    print(line, flush=True)
    with open(log_f, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def calistir(args, timeout):
    try:
        r = subprocess.run([PY, *map(str, args)], cwd=ROOT, env=ENV, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "ZAMAN ASIMI"

def ollama_hazir(test_atla=False):
    if test_atla:
        return True
    def ping():
        try:
            urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3).read()
            return True
        except Exception:
            return False
    if ping():
        return True
    if shutil.which("ollama"):
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(15):
            time.sleep(2)
            if ping():
                return True
    return False

def sesli_metin(ozet, bekleyen):
    """Okunacak kisa ozet metni (saf fonksiyon, test edilebilir)."""
    yapilan = [x for x in ozet if x[2] and "bugun zaten" not in x[1]]
    hatali = [x[0] for x in ozet if "HATASI" in x[1]]
    parca = ["Nöbetçi bitti."]
    if yapilan:
        parca.append(", ".join(x[0] for x in yapilan) + " için paket hazırlandı.")
    elif not hatali:
        parca.append("Bugün yeni üretim yok.")
    if hatali:
        parca.append(", ".join(hatali) + " için üretim hata verdi.")
    parca.append(f"{bekleyen} paket onay bekliyor." if bekleyen else "Onay bekleyen paket yok.")
    parca.append("Hiçbir şey yayınlanmadı.")
    return " ".join(parca)

def konus(metin):
    """Windows sesiyle okur (Turkce ses varsa onu secer). Hata verirse sessizce loglar."""
    if sys.platform != "win32":
        return False
    import base64
    m = metin.replace("'", "")
    ps = ("Add-Type -AssemblyName System.Speech;"
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
          "$v=$s.GetInstalledVoices()|ForEach-Object{$_.VoiceInfo}|Where-Object{$_.Culture.Name -like 'tr*'}|Select-Object -First 1;"
          "if(-not $v){exit 3};$s.SelectVoice($v.Name);"
          f"$s.Speak('{m}')")
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc], timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 3:
            log("sesli ozet atlandi: bilgisayarda Turkce Windows sesi yok (Ayarlar > Zaman ve Dil > Konusma)")
            return False
        return True
    except Exception as ex:
        log(f"sesli ozet okunamadi: {ex}")
        return False

def durum_oku():
    try:
        return json.loads(DURUM.read_text(encoding="utf-8"))
    except Exception:
        return {}

def durum_yaz(d):
    DURUM.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zorla", action="store_true")
    ap.add_argument("--sesli", action="store_true", help="bitince ozeti sesli oku (ya da memory\\sesli_ac dosyasi olsun)")
    ap.add_argument("--proje")
    ap.add_argument("--test-ollama-atla", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()

    if not PROJELER.exists():
        log("DURDU: projeler.json yok")
        return 2
    # kilit: ayni anda iki nobetci calismasin (6 saatten eski kilit gecersiz)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 6 * 3600:
        log("DURDU: baska bir nobetci calisiyor olabilir (memory\\nobetci.lock)")
        return 3
    LOCK.write_text(str(os.getpid()))
    try:
        projeler = json.loads(PROJELER.read_text(encoding="utf-8-sig"))
        if a.proje:
            projeler = [p for p in projeler if p.get("ad", "").lower() == a.proje.lower()]
        if not ollama_hazir(a.test_ollama_atla):
            log("DURDU: Ollama acilamadi")
            return 4
        bugun = f"{datetime.date.today():%Y-%m-%d}"
        durum = durum_oku()
        ozet = []
        video_var = bool(shutil.which("ffmpeg"))
        for p in projeler:
            ad, hedef = p.get("ad", "").strip(), p.get("hedef", "").strip()
            plat = p.get("platform", "instagram")
            if not ad or not hedef:
                log(f"ATLANDI: ad/hedef eksik {p}")
                continue
            if not a.zorla and durum.get(ad, {}).get("tarih") == bugun:
                log(f"ATLANDI: {ad} bugun zaten uretildi ({durum[ad].get('gorev')})")
                ozet.append((ad, "bugun zaten var", durum[ad].get("gorev")))
                continue
            log(f"BASLADI: {ad}")
            hedef_son = hedef
            try:
                import kado_hafiza
                kado_hafiza.guncelle()
                ek = kado_hafiza.baglam(ad)
                if ek:
                    hedef_son = hedef + " | HAFIZA: " + ek
                    log(f"hafiza baglami eklendi ({len(ek)} karakter)")
            except Exception as ex:
                log(f"hafiza atlandi: {ex}")
            rc, out = calistir(["kado_icerik_hatti.py", ad, hedef_son, "--platform", plat], ICERIK_TIMEOUT)
            m = re.search(r"GOREV:\s*(\S+)", out)
            if rc != 0 or not m or "TAMAMLANDI" not in out:
                log(f"HATA icerik ({ad}) rc={rc}: {out.strip()[-300:]}")
                ozet.append((ad, "ICERIK HATASI", None))
                continue
            gorev = m.group(1)
            sonuc = ["icerik"]
            rc, out = calistir(["kado_gorsel_kart.py", gorev], KISA_TIMEOUT)
            if rc == 0 and "HAZIR" in out:
                sonuc.append("kart")
                if video_var:
                    rc, out = calistir(["kado_video.py", gorev, "--sure", "5"], KISA_TIMEOUT)
                    if rc == 0 and "HAZIR" in out:
                        sonuc.append("video")
                    else:
                        log(f"HATA video ({ad}): {out.strip()[-200:]}")
                else:
                    log("video atlandi: ffmpeg bulunamadi")
            else:
                log(f"HATA kart ({ad}): {out.strip()[-200:]}")
            durum[ad] = {"tarih": bugun, "gorev": gorev, "uretilen": sonuc}
            durum_yaz(durum)
            log(f"BITTI: {ad} -> {gorev} ({', '.join(sonuc)}) YAYINLANMADI, ONAY GEREKLI")
            ozet.append((ad, ", ".join(sonuc), gorev))
        # sabah raporu (varsa)
        if (ROOT / "kado_sabah_raporu.py").exists():
            calistir(["kado_sabah_raporu.py"], KISA_TIMEOUT)
            log("sabah raporu guncellendi")
        log("OZET: " + " | ".join(f"{x[0]}: {x[1]}" for x in ozet) if ozet else "OZET: is yok")
        if a.sesli or (ROOT / "memory" / "sesli_ac").exists():
            bekleyen = len(list((ROOT / "kado_agent_motor" / "kuyruk").glob("*.review")))
            metin = sesli_metin(ozet, bekleyen)
            log("sesli ozet: " + metin)
            konus(metin)
        return 0
    finally:
        try:
            LOCK.unlink()
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())
