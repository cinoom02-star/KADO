#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KADO Emine koprusu v1.0 — Stdlib + istege bagli ffmpeg.

Kullanim: python KADO_EMINE_KOPRU.py kontrol|hazirla|bagla|durum|geri_al
         python KADO_EMINE_KOPRU.py ses <indirilen_mp3_veya_wav>
         python KADO_EMINE_KOPRU.py video <buluttan_indirilen_mp4>
         python KADO_EMINE_KOPRU.py yeni "Konu"

KADO cekirdek / WhatsApp / CEO / denetci modullerini degistirmez.
Opsiyonel `bagla` SADECE kado_studyo_31.py sonuna geri alinabilir voice_route
sarmalayicisi ekler; otomatik yayin veya harici GPU baglantisi yapmaz.
"""
import argparse
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata
import uuid

ROOT = Path(__file__).resolve().parent
STUDIO = ROOT / 'influencer_studio'
ACTIVE = STUDIO / 'ACTIVE_INFLUENCER.json'
BASE = STUDIO / 'Emine_Uretim'
REF = BASE / '01_REFERANS'
AUDIO = BASE / '02_SES'
VIDEO = BASE / '03_KONUSAN_VIDEO'
REELS = BASE / '04_REELS_HAZIR'
TASKS = BASE / '05_GOREVLER'
BACKUPS = BASE / 'yedekler'
MANIFEST = BACKUPS / 'baglanti.json'
STUDIO_PY = ROOT / 'kado_studyo_31.py'
MARK_START = '# KADO_EMINE_BRIDGE_START v1'
MARK_END = '# KADO_EMINE_BRIDGE_END v1'
VIDEO_NAME = 'Emine_KONUSAN_ORIJINAL.mp4'
WAV_NAME = 'Emine_SES_16K.wav'
REF_NAME = 'Emine_ANA_REFERANS.png'

VOICE_WRAPPER = '''\n\n# KADO_EMINE_BRIDGE_START v1
# Bu blok yalnizca Emine isteklerini KADO_EMINE_KOPRU.py'ye yonlendirir.
_emine_voice_route_previous = voice_route
def voice_route(request, project=None):
    try:
        from KADO_EMINE_KOPRU import emine_voice_route as _emine_route
        _result = _emine_route(request, project)
        if _result is not None:
            return _result
    except Exception as _emine_exc:
        return 'Emine koprusu hatasi: ' + str(_emine_exc)[:180]
    return _emine_voice_route_previous(request, project)
# KADO_EMINE_BRIDGE_END v1
'''


def stamp():
    return dt.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, UnicodeError):
        return default


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex[:8] + '.tmp')
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def put_once(path, content):
    if not path.exists():
        path.write_text(content, encoding='utf-8-sig')
        print('[YAZILDI]', path)
    else:
        print('[KORUNDU]', path.name, '(var olan dosya degismedi)')


def fmt_size(path):
    return f'{path.stat().st_size / 1024:.0f} KB' if path.is_file() else 'yok'


def valid_profile():
    p = load_json(ACTIVE, {}) or {}
    if str(p.get('active_profile', '')).casefold() != 'emine':
        raise RuntimeError('ACTIVE_INFLUENCER.json icinde active_profile = Emine olmali. Yok veya farkli.')
    img = Path((p.get('files') or {}).get('reference_image') or '')
    if not img.is_file():
        fallback = STUDIO / 'profiles' / 'Emine' / REF_NAME
        if fallback.is_file():
            img = fallback
        else:
            raise RuntimeError('Emine referans fotografi bulunamadi: ' + str(img))
    return img


def ff_executable(name):
    found = shutil.which(name)
    if found:
        return found
    for candidate in (Path('C:/ffmpeg/bin') / (name + '.exe'),
                      Path('C:/Program Files/ffmpeg/bin') / (name + '.exe')):
        if candidate.is_file():
            return str(candidate)
    return None


def kontrol():
    print('=== KADO EMINE SISTEM KONTROLU ===')
    print('KADO klasoru:', ROOT)
    print('CEO:', 'BULUNDU' if (ROOT / 'kado_ceo.py').is_file() else 'YOK')
    print('Mevcut Denetci:', 'BULUNDU' if (ROOT / 'kado_denetci.py').is_file() else 'YOK')
    print('Studyo:', 'BULUNDU' if STUDIO_PY.is_file() else 'YOK')
    print('Aktif profil:', 'BULUNDU' if ACTIVE.is_file() else 'YOK')
    try:
        img = valid_profile()
        print('Emine referansi: TAMAM -', img, '(' + fmt_size(img) + ')')
    except RuntimeError as err:
        print('Emine referansi: HATA -', err)
    print('FFmpeg:', ff_executable('ffmpeg') or 'YOK - ses donusturme/montaj icin gerekli')
    print('FFprobe:', ff_executable('ffprobe') or 'YOK - ayrintili medya kontrolu icin istege bagli')
    print('Studyo baglantisi:', 'BAGLI' if STUDIO_PY.is_file() and MARK_START in STUDIO_PY.read_text(encoding='utf-8-sig') else 'HENUZ BAGLI DEGIL')
    print('GPU bulut modeli: BU DOSYA TARAFINDAN CALISTIRILMAZ; kullanici web demosunda uretir.')
    return 0


def hazirla():
    img = valid_profile()
    for folder in (REF, AUDIO, VIDEO, REELS, TASKS, BACKUPS):
        folder.mkdir(parents=True, exist_ok=True)
    ref_dst = REF / REF_NAME
    if not ref_dst.is_file():
        shutil.copy2(img, ref_dst)
        print('[KOPYALANDI] Emine ana fotografi:', ref_dst)
    else:
        print('[KORUNDU] Emine ana fotografi (var olan referans degistirilmedi)')
    put_once(BASE / '01_EMINE_TANISMA_METNI.txt',
             'Merhaba, ben Emine! Bugunden sonra burada bol bol gorusecegiz.\n'
             'Burası benim dijital dunyam; yeni hikayemize hos geldin!\n'
             '\nNot: Sesin 6-12 saniye olmasi ilk test icin idealdir.\n')
    put_once(BASE / '02_YENI_FOTOGRAF_PROMPT_EN.txt',
             'A realistic editorial portrait of the SAME fictional woman from the ID reference image, '
             'same facial proportions, same long wavy dark brown hair, same eye shape, same lips, '
             'same single tiny black beauty mark on the exact same cheek in the exact same position '
             'as the reference. She is outdoors in Istanbul in a stylish casual outfit, '
             'natural daylight, photorealistic, clean skin texture, 9:16 vertical composition. '
             'Do not shift, duplicate, erase or invent beauty marks. No face swap.\n')
    put_once(BASE / '03_KONUSAN_VIDEO_PROMPT_EN.txt',
             'One fictional young woman talking naturally to camera in Turkish. Identity must '
             'remain faithful to the uploaded reference portrait. Subtle head nods, natural '
             'facial expressions, accurate lip sync to the supplied speech audio. '
             'Single small cheek beauty mark stays in the same position, same outfit and '
             'background, no face morphing, no extra people, no text overlays.\n')
    put_once(BASE / '04_INSTAGRAM_CAPTION_TR.txt',
             'Merhaba, ben Emine! Dijital dunyama hos geldin. '
             'Yeni hikayelerimi burada paylasacagim. ✨\n'
             '#Emine #SanalInfluencer #DijitalKarakter #YapayZeka\n'
             'Not: Bu hesapta yapay zeka ile olusturulmus sanal bir karakter yer alir.\n')
    print('\n[HAZIR] Emine calisma merkezi:', BASE)
    print('Sonraki: Ses dosyasini indir, `ses` komutuyla WAV hazirla; bulutta video uret.')
    return 0


def run_cmd(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError('Komut hatasi (' + str(p.returncode) + '): ' + ('\n'.join(p.stderr.splitlines()[-6:]))[:800])
    return p.stdout.strip()


def ses_donustur(source):
    hazirla()
    src = Path(source).expanduser().resolve()
    if not src.is_file():
        raise RuntimeError('Ses dosyasi bulunamadi: ' + str(src))
    ff = ff_executable('ffmpeg')
    if not ff:
        raise RuntimeError('FFmpeg bulunamadi. PowerShell: winget install --id Gyan.FFmpeg -e')
    dst = AUDIO / WAV_NAME
    if src == dst:
        print('[TAMAM] Ses zaten standart WAV dosyasi:', dst)
        return 0
    temp = AUDIO / ('donusturme_' + uuid.uuid4().hex[:8] + '.wav')
    try:
        run_cmd([ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(src),
                 '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(temp)])
        if temp.stat().st_size < 1000:
            raise RuntimeError('Donusturulen dosya beklenenden cok kucuk.')
        os.replace(temp, dst)
    finally:
        if temp.exists():
            temp.unlink()
    print('[TAMAM] Buluta yuklenecek ses:', dst, '(' + fmt_size(dst) + ')')
    return 0


def audio_stream_exists(video_file):
    probe = ff_executable('ffprobe')
    if not probe:
        return None
    s = run_cmd([probe, '-v', 'error', '-select_streams', 'a:0',
                 '-show_entries', 'stream=index', '-of', 'csv=p=0', str(video_file)])
    return bool(s.strip())


def video_hazirla(source):
    hazirla()
    src = Path(source).expanduser().resolve()
    if not src.is_file():
        raise RuntimeError('Buluttan indirilen MP4 bulunamadi: ' + str(src))
    if src.suffix.lower() != '.mp4':
        raise RuntimeError('Video dosyasi MP4 olmali. Diger formatlari once MP4 yap.')
    ff = ff_executable('ffmpeg')
    if not ff:
        raise RuntimeError('FFmpeg bulunamadi. PowerShell: winget install --id Gyan.FFmpeg -e')
    raw_dst = VIDEO / ('Emine_BULUT_' + stamp() + '.mp4')
    shutil.copy2(src, raw_dst)
    wav = AUDIO / WAV_NAME
    has_audio = audio_stream_exists(raw_dst)
    out = REELS / ('Emine_REELS_' + stamp() + '.mp4')
    vf = ('scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,'
          'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=25')
    cmd = [ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(raw_dst)]
    if has_audio is False and wav.is_file():
        print('[BILGI] Video sessiz; hazir WAV eklenecek (senkron kontrolu yap).')
        cmd += ['-i', str(wav), '-map', '0:v:0', '-map', '1:a:0', '-shortest']
    else:
        cmd += ['-map', '0:v:0', '-map', '0:a:0?']
        if has_audio is None:
            print('[UYARI] ffprobe yok: ses akisi olup olmadigi dogrulanamadi.')
        elif not has_audio:
            print('[UYARI] Video sessiz ve ses WAV yok. Cikti sessiz olur.')
    cmd += ['-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-b:a', '128k',
            '-movflags', '+faststart', str(out)]
    try:
        run_cmd(cmd)
        if out.stat().st_size < 10000:
            raise RuntimeError('MP4 dosyasi cok kucuk veya hatali.')
    except Exception:
        if out.exists():
            out.unlink()
        raise
    write_json(TASKS / ('kontrol_' + stamp() + '.json'), {
        'karakter': 'Emine', 'kaynak': str(raw_dst), 'reels': str(out),
        'durum': 'INSAN_ONAYI_BEKLIYOR', 'yayinlandi': False,
        'denetci_entegrasyonu': False, 'yuz_tutarliligi_otomatik_dogrulandi': False,
        'not': 'Dudak senkronu ve benin yeri gozle kontrol edilmeli. Otomatik yayin yok.',
        'tarih': dt.datetime.now().isoformat(timespec='seconds')
    })
    print('[HAZIR] 1080x1920 Reels taslagi:', out)
    print('[DURUM] YAYINLANMADI - insan onayi gerekli; gozle yuz ve dudak senkronu kontrolu yap.')
    return 0


def new_job(topic='Emine tanisma reels'):
    hazirla()
    try:
        existing = load_json(STUDIO / 'profiles' / 'Emine' / 'drafts' / 'ilk_tanisma.json', {})
        if not isinstance(existing, dict):
            existing = {}
    except Exception:
        existing = {}
    data = {'id': stamp(), 'character': 'Emine', 'platform': 'instagram',
            'format': 'reels', 'topic': str(topic)[:300], 'status': 'taslak',
            'identity_reference': str(REF / REF_NAME),
            'speech_text': existing.get('script') or 'Merhaba, ben Emine. Yeni hikayem basliyor!',
            'generated_video': False, 'published': False, 'human_approval_required': True,
            'engine': 'Bulut web demosu (manuel): EchoMimic / SadTalker; otomatik API BAGLI DEGIL',
            'created_at': dt.datetime.now().isoformat(timespec='seconds')}
    path = TASKS / (data['id'] + '_gorev.json')
    write_json(path, data)
    print('[GOREV OLUSTU] ', path)
    print('[BILGI] Bu bir KADO görev TASLAGIDIR; bulutta gercek video kendiliginden uretilmez.')
    return path


def emine_voice_route(request, project=None):
    t = unicodedata.normalize('NFKD', str(request).lower())
    t = ''.join(c for c in t if not unicodedata.combining(c)).replace('ı', 'i')
    if 'emine' not in t:
        return None
    if any(x in t for x in ('durum', 'rapor', 'neler var', 'kac video')):
        return 'Emine AKTIF. Sonuc klasoru: ' + str(REELS) + '. Bulut modeli manuel; otomatik Instagram yayini KAPALI.'
    if any(x in t for x in ('hazirla', 'uret', 'olustur', 'yap', 'reels', 'video', 'icerik', 'gorev', 'post')):
        path = new_job(str(request)[:180])
        return ('Emine icin yeni Reels gorev taslagi olusturdum: ' + str(path) + '. '
                'Foto/ses ile video uretimi web GPU aracinda yapilir. Henüz MP4 uretilmedi, paylasilmadi.')
    return 'Emine profili aktif. "Emine icin Reels hazirla" diyebilirsin.'


def bagla():
    valid_profile()
    if not STUDIO_PY.is_file():
        raise RuntimeError('kado_studyo_31.py bulunamadi. Baglanti yapilmadi.')
    raw = STUDIO_PY.read_bytes()
    try:
        original = raw.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise RuntimeError('Studyo UTF-8 degil, degisiklik yapilmadi.') from e
    if MARK_START in original:
        print('[ZATEN BAGLI] Studyo icindeki Emine sarmalayicisi mevcut.')
        return 0
    if 'def voice_route(' not in original:
        raise RuntimeError('Studyo voice_route fonksiyonunu icermiyor; dokunulmadı.')
    ast.parse(original, filename=str(STUDIO_PY))
    patched = original.rstrip('\n') + VOICE_WRAPPER
    ast.parse(patched, filename=str(STUDIO_PY))
    # Once yedek kaydet; sonra orijinal encoding BOM ve CRLF stilini koru.
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / ('kado_studyo_31_' + stamp() + '.py.bak')
    shutil.copy2(STUDIO_PY, backup)
    had_bom = raw.startswith(b'\xef\xbb\xbf')
    newline = '\r\n' if b'\r\n' in raw else '\n'
    normalized = patched.replace('\r\n', '\n').replace('\n', newline)
    patched_bytes = normalized.encode('utf-8-sig' if had_bom else 'utf-8')
    tmp = STUDIO_PY.with_name(STUDIO_PY.name + '.emine.' + uuid.uuid4().hex[:6] + '.tmp')
    try:
        with tmp.open('xb') as f:
            f.write(patched_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STUDIO_PY)
        write_json(MANIFEST, {'backup': str(backup), 'target': str(STUDIO_PY),
                              'before_sha256': hashlib.sha256(raw).hexdigest(),
                              'after_sha256': hashlib.sha256(patched_bytes).hexdigest()})
    finally:
        if tmp.exists():
            tmp.unlink()
    print('[BAGLANDI] Yalnizca Emine komutlari kado_studyo_31.py uzerinden yonlendirilecek.')
    print('[YEDEK]', backup)
    print('[NOT] CEO, Denetci, WhatsApp veya baslatma dosyalari DEGISTIRILMEDI.')
    return 0


def geri_al():
    m = load_json(MANIFEST, {}) or {}
    backup = Path(m.get('backup') or '')
    if not backup.is_file():
        raise RuntimeError('Geri alma yedegi bulunamadi. Otomatik degisiklik yapilmadi.')
    if not STUDIO_PY.is_file():
        raise RuntimeError('Studyo dosyasi bulunamadi. Otomatik degisiklik yapilmadi.')
    if sha(STUDIO_PY) != m.get('after_sha256'):
        raise RuntimeError('Studyo sonradan degistirilmis! Uzerine yazilmadi. Manuel inceleme gerekli.')
    shutil.copy2(backup, STUDIO_PY)
    print('[GERI ALINDI] Eski stüdyo geri yuklendi:', STUDIO_PY)
    MANIFEST.unlink(missing_ok=True)
    return 0


def durum():
    kontrol()
    print('\n=== CALISMA KLASORLERI ===')
    for folder in (REF, AUDIO, VIDEO, REELS, TASKS):
        n = len([p for p in folder.iterdir() if p.is_file()]) if folder.exists() else 0
        print(f'{folder.name}: {n} dosya')
    print('Yayin:', 'MANUEL / Insan onayli, otomatik paylasim yok')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='KADO Emine sanal influencer is akis koprusu')
    sub = ap.add_subparsers(dest='command', required=True)
    for name in ('kontrol', 'hazirla', 'bagla', 'durum', 'geri_al'):
        sub.add_parser(name)
    s = sub.add_parser('ses'); s.add_argument('dosya')
    v = sub.add_parser('video'); v.add_argument('dosya')
    n = sub.add_parser('yeni'); n.add_argument('konu')
    args = ap.parse_args(argv)
    try:
        if args.command == 'kontrol': return kontrol()
        if args.command == 'hazirla': return hazirla()
        if args.command == 'bagla': return bagla()
        if args.command == 'durum': return durum()
        if args.command == 'geri_al': return geri_al()
        if args.command == 'ses': return ses_donustur(args.dosya)
        if args.command == 'video': return video_hazirla(args.dosya)
        if args.command == 'yeni': new_job(args.konu); return 0
    except (ValueError, RuntimeError, OSError, SyntaxError) as e:
        print('[HATA]', e, file=sys.stderr)
        return 2
    return 1

if __name__ == '__main__':
    sys.exit(main())
