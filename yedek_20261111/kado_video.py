"""KADO kisa video (U11/U12, sablon tabanli): hikaye kartlarindan 1080x1920 dikey MP4 uretir
(yavas yakinlasma/uzaklasma + solma gecisi). ffmpeg gerekir. Hicbir yere yayin yapmaz.
Kullanim: python kado_video.py [son|GOREV_ID] [--sure 4] [--ses ses.mp3]
         python kado_video.py selftest
"""
import argparse, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "kado_agent_motor" / "ciktilar"
KUR = 'winget install --id Gyan.FFmpeg -e   (kurduktan sonra YENI bir PowerShell ac)'


def calistir(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg hatasi: " + " | ".join(r.stderr.strip().splitlines()[-4:]))


def klip(ff, img, dst, sure, ters, fps=25):
    d = int(sure * fps)
    z = "if(eq(on,1),1.12,max(zoom-0.0008,1.0))" if ters else "min(zoom+0.0008,1.12)"
    vf = (f"scale=1620:2880,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s=1080x1920:fps={fps},"
          f"fade=t=in:st=0:d=0.4,fade=t=out:st={sure - 0.4}:d=0.4,format=yuv420p")
    calistir([ff, "-y", "-i", str(img), "-vf", vf, "-t", str(sure), "-c:v", "libx264",
              "-preset", "veryfast", "-crf", "20", "-r", str(fps), str(dst)])


def video_uret(ff, resimler, hedef, sure=4, ses=None):
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t); liste = []
        for i, r in enumerate(resimler):
            c = t / f"c{i}.mp4"; klip(ff, r, c, sure, i % 2 == 1); liste.append(c)
        lf = t / "liste.txt"
        lf.write_text("\n".join(f"file '{c.as_posix()}'" for c in liste), encoding="utf-8")
        ham = t / "ham.mp4"
        calistir([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lf), "-c", "copy", str(ham)])
        if ses:
            calistir([ff, "-y", "-i", str(ham), "-i", str(ses), "-shortest", "-c:v", "copy", "-c:a", "aac", str(hedef)])
        else:
            shutil.copy2(ham, hedef)
    return hedef


def selftest():
    ff = shutil.which("ffmpeg")
    if not ff:
        print("SELFTEST ATLANDI: ffmpeg kurulu degil. Kur:", KUR); return 0
    from PIL import Image
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t); r = []
        for i, c in enumerate(((200, 30, 30), (30, 200, 30), (30, 30, 200))):
            p = t / f"k{i}.png"; Image.new("RGB", (1080, 1920), c).save(p); r.append(p)
        v = video_uret(ff, r, t / "video" / "reel.mp4", sure=2)
        assert v.exists() and v.stat().st_size > 5000
        pr = shutil.which("ffprobe")
        if pr:
            import subprocess as sp
            s = sp.run([pr, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)], capture_output=True, text=True).stdout.strip()
            assert 5.0 <= float(s) <= 7.0, s
    print("SELFTEST 2/2 BASARILI: 3 kartlik klip uretimi, sure kontrolu")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    ff = shutil.which("ffmpeg")
    if not ff:
        print("FFMPEG YOK. Kur:", KUR); return 3
    ap = argparse.ArgumentParser()
    ap.add_argument("gorev", nargs="?", default="son"); ap.add_argument("--sure", type=int, default=4); ap.add_argument("--ses")
    a = ap.parse_args()
    if a.gorev == "son":
        ad = sorted(OUT.glob("*/gorseller/kart_1_hikaye.png"), key=lambda p: p.stat().st_mtime)
        if not ad:
            print("Kart bulunamadi. Once: python kado_gorsel_kart.py"); return 1
        klasor = ad[-1].parent
    else:
        klasor = OUT / a.gorev / "gorseller"
    resimler = sorted(klasor.glob("kart_*_hikaye.png"))
    if not resimler:
        print("Hikaye kartlari bulunamadi:", klasor); return 1
    hedef = klasor.parent / "video" / "reel.mp4"
    v = video_uret(ff, resimler, hedef, a.sure, a.ses)
    print("KART SAYISI:", len(resimler), "| SURE (sn):", len(resimler) * a.sure)
    print("VIDEO:", v)
    print("DURUM: HAZIR - SESSIZ TASLAK" if not a.ses else "DURUM: HAZIR", "- YAYINLANMADI, ONAY GEREKLI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
