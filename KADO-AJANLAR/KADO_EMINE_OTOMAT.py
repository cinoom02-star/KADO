# -*- coding: utf-8 -*-
"""KADO Emine Otomat v1.0.  Runs locally; keeps CEO/Denetci/WhatsApp intact.

Commands: ilk_kur, uretim, durum, gunluk_kur, gunluk_kaldir,
          bagla, geri_al, sad_test
"""
import argparse
import ast
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.request
import wave

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'influencer_studio' / 'Emine_Uretim'
HOME = BASE / '06_OTOMATIK'
IMAGES = HOME / 'fotograflar'
SCRIPTS = HOME / 'senaryolar'
DELIVERIES = HOME / 'hazir_reels'
MODELS = HOME / 'ses_modelleri'
LOGS = HOME / 'kayitlar'
SETTINGS = HOME / 'ayarlar.json'
STATE = HOME / 'durum.json'
LOCK = HOME / 'uretim.lock'
BRIDGE_BACKUP = HOME / 'studyo_yedek.json'
STUDIO = ROOT / 'kado_studyo_31.py'
SCHED_NAME = 'KADO_EMINE_GUNLUK'
BMARK = '# EMINE_OTOMAT_V1_BASLANGIC'
EMARK = '# EMINE_OTOMAT_V1_BITIS'
DEFAULTS = {
    'saat': '11:00',
    'konusan_yuz': 'auto',  # sad installed: use it; else make motion-photo video
    'sad_talker_klasor': '',
    'sad_talker_python': '',
    'ollama_model': '',  # optional local model only; no paid API
    'ses_modeli': 'ilkiz',
    'otomatik_yayin': False,
    'reels_genislik': 720,
    'reels_yukseklik': 1280,
}
SCENES = [
    {
        'match': '01_istanbul', 'location': 'İstanbul sokakları', 'topic': 'Güne güzel bir başlangıç',
        'lines': [
            'Merhaba, ben Emine! Bugün İstanbul sokaklarında küçük bir mola verdim. Sizce bir günü güzelleştiren şey nedir?',
            'İstanbul’da yürürken yeni fikirler aklıma geliyor. Bugün sizinle güzel bir hikâye paylaşmak istedim!',
            'Bugün biraz şehir havası, biraz kahve ve bolca enerji. Siz gününüze nasıl başladınız?',
            'Her sokağın bir hikâyesi var. Benim bugünkü hikâyem de burada başladı. Hazır mısınız?',
        ],
    },
    {
        'match': '02_kafe', 'location': 'Sıcak bir kafe', 'topic': 'Kahve sohbeti',
        'lines': [
            'Selam! Kahvemi aldım, biraz sohbet etmeye geldim. Siz kahvenizi nasıl seversiniz?',
            'Bugün kendime küçücük bir kahve molası verdim. Bazen iyi hissetmek için bu kadarı yeterli!',
            'Bir kahve, güzel bir müzik ve tatlı bir sohbet. Sizce mükemmel mola nasıl olmalı?',
            'Burası çok huzurlu. Benimle böyle küçük molalara çıkmaya ne dersiniz?',
        ],
    },
    {
        'match': '03_oyuncak', 'location': 'Oyuncak mağazası', 'topic': 'Renkli mağaza turu',
        'lines': [
            'Merhaba! Bugün rengârenk bir oyuncak mağazasındayım. Çocukken en sevdiğiniz oyuncak neydi?',
            'Buradaki renkler insanın enerjisini yükseltiyor. Ben en çok yaratıcı oyunları seviyorum. Ya siz?',
            'Bugün küçük bir oyuncak turu yapıyorum. Sizce en eğlenceli oyun tek başına mı, arkadaşlarla mı?',
            'Oyuncakların dünyası gerçekten rengârenk. Bugün çocukluğumuzu hatırlayalım mı?',
        ],
    },
]


def say(msg):
    print(msg, flush=True)


def json_load(p, fallback):
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, UnicodeError):
        return fallback


def json_save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(t, p)


def setup_dirs():
    for d in (HOME, IMAGES, SCRIPTS, DELIVERIES, MODELS, LOGS):
        d.mkdir(parents=True, exist_ok=True)
    if not SETTINGS.exists():
        json_save(SETTINGS, DEFAULTS)
    return {**DEFAULTS, **json_load(SETTINGS, {})}


def find_ff(binname):
    found = shutil.which(binname)
    if found:
        return found
    for base in [Path('C:/ffmpeg/bin'), Path('C:/Program Files/ffmpeg/bin')]:
        p = base / (binname + '.exe')
        if p.is_file():
            return str(p)
    home = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft/WinGet/Packages'
    if home.is_dir():
        for p in home.glob('Gyan.FFmpeg*/ffmpeg-*/*/bin/' + binname + '.exe'):
            if p.is_file():
                return str(p)
        for p in home.rglob(binname + '.exe'):
            if p.is_file() and 'ffmpeg' in str(p).lower():
                return str(p)
    return None


def call(cmd, *, cwd=None, timeout=600, quiet=False):
    p = subprocess.run([str(x) for x in cmd], cwd=cwd, timeout=timeout,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        msg = ('\n'.join((p.stderr or p.stdout).splitlines()[-15:]))[-2200:]
        raise RuntimeError(f'Komut basarisiz ({p.returncode}): {msg}')
    if not quiet and p.stdout.strip():
        say(p.stdout.strip()[-800:])
    return p.stdout


def python_for_tasks():
    venv = ROOT / '.venv_emine' / 'Scripts' / 'python.exe'
    return venv if venv.is_file() else Path(sys.executable)


def choose_image():
    images = sorted(p for p in IMAGES.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'))
    if not images:
        fallback = ROOT / 'influencer_studio' / 'profiles' / 'Emine' / 'Emine_ANA_REFERANS.png'
        if not fallback.is_file():
            fallback = BASE / '01_REFERANS' / 'Emine_ANA_REFERANS.png'
        if not fallback.is_file():
            raise RuntimeError('Fotograf yok. 06_OTOMATIK\\fotograflar klasorune Emine fotograflari koy.')
        images = [fallback]
    state = json_load(STATE, {})
    count = int(state.get('sayac', 0))
    return images[count % len(images)]


def scene_for(image):
    return next((s for s in SCENES if s['match'] in image.stem.lower()), SCENES[0])


def fold(s):
    s = s.lower().replace('ı', 'i')
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def optional_ollama(scene, previous, settings):
    """Uses a model already installed by user; never calls a paid/cloud endpoint."""
    model = settings.get('ollama_model', '').strip()
    if not model:
        return None
    prompt = (
        f'Hayali sosyal medya karakteri Emine icin sadece Turkce, tek paragraflik, 25-45 kelimelik, '
        f'samimi Reels konusmasi yaz. Konum: {scene["location"]}. Konu: {scene["topic"]}. '
        f'Emine gercek bir insan oldugunu iddia etmesin. Tehlikeli/siyasi iddia, '
        f'uydurma guncel haber, izinsiz marka ismi olmasin. '+
        f'Onceki cumleyi tekrar etme: {previous}. Yalnizca konusma metni.')
    data = json.dumps({'model': model, 'prompt': prompt, 'stream': False,
                       'options': {'temperature': 0.85, 'num_predict': 140}}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=data,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=110) as response:
            output = json.loads(response.read().decode('utf-8')).get('response', '').strip()
            return output[:500] if 30 <= len(output) <= 500 else None
    except Exception as e:
        say('[BILGI] Yerel Ollama kullanilamadi, hazir senaryoya geciliyor: ' + str(e)[:120])
        return None


def choose_script(scene, settings):
    state = json_load(STATE, {})
    previous = state.get('son_metin', '')
    text = optional_ollama(scene, previous, settings)
    if text:
        return text, 'Ollama yerel model'
    options = scene['lines']
    shift = int(state.get('sayac', 0)) // len(SCENES)
    # A small deterministic library: no unfounded claim of AI-written unique scripts
    return options[shift % len(options)], 'Yerel senaryo havuzu'


def valid_piper_models():
    # All model files have matching ONNX + JSON. License is separately documented.
    choices = sorted(p for p in MODELS.rglob('*.onnx') if p.with_name(p.name + '.json').is_file())
    return choices


def install_female_voice():
    """Download the publicly MIT-described Turkish female Ilkiz model, only if both files exist."""
    setup_dirs()
    if valid_piper_models():
        say('[SES] Ses modeli zaten kurulu.')
        return valid_piper_models()[0]
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as e:
        raise RuntimeError('huggingface_hub kurulu degil; kurulumu tekrar calistir.') from e
    repo = 'ilkeraktuna/piper-tts-tr-ilkiz-medium'
    files = HfApi().list_repo_files(repo)
    onnx = [x for x in files if x.endswith('.onnx') and x + '.json' in files]
    if not onnx:
        raise RuntimeError('Ilkiz modelinde uyumlu ONNX + JSON bulunamadi. Kurulum durduruldu; '
                           'rastgele baska modele gecilmeyecek. Model: https://huggingface.co/' + repo)
    # prioritize medium model if multiple exist
    preferred = sorted(onnx, key=lambda x: ('medium' not in x.lower(), len(x)))[0]
    dest = MODELS / 'ilkiz'
    dest.mkdir(parents=True, exist_ok=True)
    for f in (preferred, preferred + '.json'):
        hf_hub_download(repo_id=repo, filename=f, local_dir=str(dest))
    full = dest / preferred
    if not (full.exists() and full.with_name(full.name + '.json').exists()):
        raise RuntimeError('Ilkiz indirilemedi veya eksik inmis.')
    say('[SES HAZIR] Türkçe kadın sesi: ' + str(full))
    say('[LISANS] Model sayfasi MIT diyor; gelir amacli kullanimdan once veri/lisans kaynagini teyit et.')
    return full


def synthesize(text, out):
    models = valid_piper_models()
    if not models:
        raise RuntimeError('Piper ses modeli yok. KUR_EMINE.bat ile ilk kurulumu yap.')
    # call stdlib Python Piper API; files already validated
    script = (
        'import sys,wave\n'
        'from piper import PiperVoice\n'
        'm,o,t=sys.argv[1:4]\n'
        'v=PiperVoice.load(m)\n'
        'with wave.open(o,"wb") as f:v.synthesize_wav(t,f)\n'
    )
    call([sys.executable, '-c', script, str(models[0]), str(out), text], timeout=240, quiet=True)
    if not out.is_file() or out.stat().st_size < 2000:
        raise RuntimeError('Ses uretilemedi.')
    with wave.open(str(out), 'rb') as f:
        if f.getnframes() <= 0:
            raise RuntimeError('Ses uretimi bos dondu.')
    return out


def seconds(audio):
    with wave.open(str(audio), 'rb') as w:
        return w.getnframes() / w.getframerate()


def save_motion_reels(image, audio, out, settings):
    ffmpeg = find_ff('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg bulunamadi. Bilgisayarinda mevcut FFmpeg PATH icinde gorunmeli.')
    w = int(settings.get('reels_genislik', 720)); h = int(settings.get('reels_yukseklik', 1280))
    if (w, h) != (720, 1280):
        raise RuntimeError('V1 icin render boyutu 720x1280 olmalidir.')
    # Small CPU-friendly slow zoom in vertical 9:16. No false lip-sync claim.
    vf = (f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=bilinear,'
          f'crop={w}:{h},'
          f"zoompan=z='min(zoom+0.00020,1.08)':d=1:s={w}x{h}:fps=20,"
          f'scale=1080:1920:flags=bilinear,format=yuv420p')
    dur = max(2, min(180, seconds(audio) + 0.3))
    call([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-i', image,
          '-i', audio, '-filter_complex', '[0:v]' + vf + '[v]',
          '-map', '[v]', '-map', '1:a:0', '-t', f'{dur:.3f}',
          '-r', '20', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '25',
          '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
          '-movflags', '+faststart', out], timeout=1200, quiet=True)
    return out



def technical_review(video):
    """Checks media format/audio, not identity or lip synchronization."""
    probe = find_ff('ffprobe')
    if not probe:
        return {'teknik_kontrol': 'ffprobe yok', 'uyarilar': ['ffprobe bulunamadi']}
    data = json.loads(call([probe, '-v', 'error', '-show_streams', '-show_format',
                            '-of', 'json', video], quiet=True))
    streams = data.get('streams', [])
    v = next((x for x in streams if x.get('codec_type') == 'video'), None)
    a = next((x for x in streams if x.get('codec_type') == 'audio'), None)
    duration = float(data.get('format', {}).get('duration') or 0)
    errors = []
    if not v:
        errors.append('Video akisi eksik')
    elif (v.get('width'), v.get('height')) != (1080, 1920):
        errors.append('Video cozunurlugu 1080x1920 degil')
    if not a:
        errors.append('Ses akisi eksik')
    if duration < 1.0:
        errors.append('Video suresi yetersiz')
    return {'teknik_kontrol': 'GECTI' if not errors else 'KALDI',
            'sure_saniye': round(duration, 2), 'uyarilar': errors,
            'dudak_senkronu_dogrulandi': False, 'yuz_tutarliligi_dogrulandi': False}


def sad_paths(settings):
    folder = Path(settings.get('sad_talker_klasor') or str(ROOT / 'SadTalker'))
    python = Path(settings.get('sad_talker_python') or str(folder / 'venv' / 'Scripts' / 'python.exe'))
    # Explicit separate SadTalker install; never pretend installed or launch incompatible core Python
    if folder.is_dir() and (folder / 'inference.py').is_file() and python.is_file():
        checkpoint = folder / 'checkpoints'
        if checkpoint.is_dir() and any(checkpoint.iterdir()):
            return folder, python
    return None


def save_sad_reels(image, audio, out, settings):
    found = sad_paths(settings)
    if not found:
        return False
    folder, python = found
    tmpdir = out.parent / 'sad_results'
    tmpdir.mkdir(exist_ok=True)
    before = set(tmpdir.rglob('*.mp4'))
    try:
        call([str(python), 'inference.py', '--source_image', image,
              '--driven_audio', audio, '--result_dir', str(tmpdir),
              '--cpu', '--still', '--preprocess', 'crop', '--size', '256'],
             cwd=str(folder), timeout=3600, quiet=True)
        new = sorted((p for p in tmpdir.rglob('*.mp4') if p not in before),
                     key=lambda p:p.stat().st_mtime, reverse=True)
        if not new:
            raise RuntimeError('SadTalker MP4 uretmedi.')
        ffmpeg = find_ff('ffmpeg')
        call([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', new[0],
              '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,'
                     'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
              '-map', '0:v:0', '-map', '0:a:0?',
              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
              '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', out],
             timeout=1200, quiet=True)
        return True
    except Exception as exc:
        say('[UYARI] SadTalker CPU hatasi: ' + str(exc)[:450])
        return False


@contextlib.contextmanager
def single_run():
    HOME.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
    except FileExistsError:
        if time.time() - LOCK.stat().st_mtime > 4 * 3600:
            LOCK.unlink(missing_ok=True)
            raise RuntimeError('Eski kilit temizlendi. Komutu yeniden calistir.')
        raise RuntimeError('KADO Emine zaten bir video hazirliyor; ikinci uretim baslatilmadi.')
    try:
        yield
    finally:
        LOCK.unlink(missing_ok=True)


def produce(*, force=False, topic=None):
    settings = setup_dirs()
    with single_run():
        today = dt.date.today().isoformat()
        state = json_load(STATE, {})
        if not force and state.get('son_gun') == today:
            say('[ZATEN HAZIR] Bugunun videosu daha once hazirlandi: ' + state.get('son_video', ''))
            return 0
        image = choose_image()
        scene = scene_for(image)
        script, generator = choose_script(scene, settings)
        if topic:
            # Topic can be passed from CEO command. Ollama is used if configured;
            # otherwise use a safe template rather than falsely claiming it understood any arbitrary topic.
            try:
                sc = dict(scene, topic=topic[:150])
                script = optional_ollama(sc, state.get('son_metin', ''), settings) or script
                generator = 'Ollama yerel model' if settings.get('ollama_model') else 'Yerel senaryo havuzu'
            except Exception:
                pass
        stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
        session = DELIVERIES / (stamp + '_' + image.stem)
        session.mkdir(parents=True, exist_ok=False)
        script_path = session / 'Emine_konusma.txt'
        script_path.write_text(script + '\n', encoding='utf-8')
        (session / 'Instagram_aciklama.txt').write_text(
            f'Bugün {scene["location"].lower()}! 🌸 Siz ne düşünüyorsunuz?\n'
            '#Emine #SanalInfluencer #DijitalKarakter #YapayZeka\n'
            'Not: Emine, yapay zekâ ile hazırlanmış sanal bir karakterdir.\n', encoding='utf-8')
        audio = session / 'Emine_ses.wav'
        out = session / 'Emine_REELS_HAZIR.mp4'
        report = {'tarih': dt.datetime.now().isoformat(timespec='seconds'),
                  'konum': scene['location'], 'konu': scene['topic'],
                  'gorsel': str(image), 'metin_kaynagi': generator,
                  'metin': script, 'instagram_otomatik_yayin': False,
                  'durum': 'BASLADI'}
        json_save(session / 'KADO_rapor.json', report)
        say('[KADO] Senaryo: ' + script)
        say('[KADO] Yerel Turkce ses hazirlaniyor...')
        try:
            synthesize(script, audio)
            say('[KADO] Ses hazir, video montajlaniyor...')
            engine = 'hareketli_fotograf'
            if settings.get('konusan_yuz') != 'kapali':
                if save_sad_reels(str(image), str(audio), str(out), settings):
                    engine = 'sadtalker_cpu'
                else:
                    say('[BILGI] Konusan yuz motoru mevcut degil; gercek dudak senkronu YOK.')
            if engine != 'sadtalker_cpu':
                save_motion_reels(str(image), str(audio), str(out), settings)
            if not out.is_file() or out.stat().st_size < 15_000:
                raise RuntimeError('MP4 eksik veya cok kucuk olustu.')
            verification = technical_review(str(out))
            report['teknik_denetim'] = verification
            if verification.get('teknik_kontrol') == 'KALDI':
                raise RuntimeError('KADO teknik denetim basarisiz: ' + str(verification['uyarilar']))
            report.update({'durum': 'YAYIN_ONAYI_BEKLIYOR', 'video': str(out),
                          'motor': engine, 'dudak_senkronu_uretildi': engine == 'sadtalker_cpu',
                          'insan_kontrolu_gerekli': True})
            json_save(session / 'KADO_rapor.json', report)
            json_save(STATE, {'sayac': int(state.get('sayac', 0)) + 1,
                              'son_gun': today, 'son_metin': script,
                              'son_video': str(out), 'motor': engine})
            say('[TAMAMLANDI] ' + str(out))
            say('[YAYIN] Instagram otomatik paylasilmadi. Son kontrol sende.')
            return 0
        except Exception as exc:
            report.update(durum='HATA', hata=str(exc)[:1000])
            json_save(session / 'KADO_rapor.json', report)
            raise


def daily_script():
    setup_dirs()
    # cmd script avoids schtasks quoting issues with python executable/args.
    cmd = HOME / 'KADO_EMINE_GUNLUK.cmd'
    py = python_for_tasks()
    # use cmd quotes around paths, no user-controlled command strings
    content = ('@echo off\r\nchcp 65001>nul\r\n'
               f'"{py}" "{ROOT / "KADO_EMINE_OTOMAT.py"}" uretim '
               f'>> "{LOGS / "gunluk.log"}" 2>&1\r\n')
    cmd.write_bytes(content.encode('utf-8'))
    return cmd


def schedule_create():
    s = setup_dirs()
    tm = s.get('saat', '11:00')
    try:
        dt.datetime.strptime(tm, '%H:%M')
    except ValueError as exc:
        raise RuntimeError('ayarlar.json saat degeri HH:MM olmali; ornek 11:00.') from exc
    if os.name != 'nt':
        say('[TEST] Windows disinda gorev zamanlayici kurulmaz.')
        return 0
    cmd = daily_script()
    # /TR string is the absolute path to the .cmd, quoted once.
    call(['schtasks', '/Create', '/F', '/SC', 'DAILY', '/ST', tm,
          '/TN', SCHED_NAME, '/TR', f'"{cmd}"'], quiet=False)
    say(f'[GUNLUK AKTIF] Windows acikken her gun {tm} - {SCHED_NAME}')
    return 0


def schedule_remove():
    if os.name != 'nt':
        say('[TEST] Windows disinda gorev kaldirilmaz.')
        return 0
    call(['schtasks', '/Delete', '/F', '/TN', SCHED_NAME], quiet=True)
    say('[DURDURULDU] Gunluk Emine uretimi kapatildi.')
    return 0


# Voice/studio connection appends one reversible wrapper only to kado_studyo_31.py.
# CEO -> kado_studyo_31 voice_route chain is already present on the user's PC.
STUDIO_WRAPPER = '''\n\n# EMINE_OTOMAT_V1_BASLANGIC
_emine_otomat_eski_voice_route = voice_route
def voice_route(request, project=None):
    try:
        from KADO_EMINE_OTOMAT import emine_kado_komutu
        _yanit = emine_kado_komutu(request)
        if _yanit is not None:
            return _yanit
    except Exception as _hata:
        return 'Emine otomat hatasi: ' + str(_hata)[:250]
    return _emine_otomat_eski_voice_route(request, project)
# EMINE_OTOMAT_V1_BITIS
'''


def connect_voice():
    setup_dirs()
    if not STUDIO.is_file():
        say('[UYARI] kado_studyo_31.py yok. Gunluk otomatik sistem bagimsiz calisir.')
        return 0
    src = STUDIO.read_bytes()
    txt = src.decode('utf-8-sig')
    if BMARK in txt:
        say('[ZATEN BAGLI] KADO ses/gorev yonlendirmesi mevcut.')
        return 0
    if 'def voice_route(' not in txt:
        say('[UYARI] Eski studyo ses arayuzu bulunamadi. Cekirdege dokunulmaz.')
        return 0
    ast.parse(txt)
    updated = txt.rstrip('\n') + STUDIO_WRAPPER
    ast.parse(updated)
    backup = HOME / ('kado_studyo_31_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S') + '.bak')
    shutil.copy2(STUDIO, backup)
    newline = '\r\n' if b'\r\n' in src else '\n'
    bom = src.startswith(b'\xef\xbb\xbf')
    new_bytes = updated.replace('\r\n', '\n').replace('\n', newline).encode('utf-8-sig' if bom else 'utf-8')
    temp = STUDIO.with_suffix('.emine_otomat.tmp')
    temp.write_bytes(new_bytes)
    os.replace(temp, STUDIO)
    json_save(BRIDGE_BACKUP, {'before': hashlib.sha256(src).hexdigest(),
                              'after': hashlib.sha256(new_bytes).hexdigest(),
                              'backup': str(backup)})
    say('[BAGLANDI] KADO Emine komutlari gercek video uretimini baslatir; stüdyo yedeklendi.')
    return 0


def disconnect_voice():
    m = json_load(BRIDGE_BACKUP, {})
    backup = Path(m.get('backup', '')) if m.get('backup') else None
    if not STUDIO.is_file() or not backup or not backup.is_file():
        raise RuntimeError('Geri alma yedegi bulunamadi; mevcut dosyaya dokunulmaz.')
    if hashlib.sha256(STUDIO.read_bytes()).hexdigest() != m.get('after'):
        raise RuntimeError('Stüdyo sonra degistirilmis; baska degisiklikleri silmemek icin geri alma durduruldu.')
    shutil.copy2(backup, STUDIO)
    BRIDGE_BACKUP.unlink(missing_ok=True)
    say('[GERI ALINDI] Eski kado_studyo_31.py aynen korundu.')
    return 0


def emine_kado_komutu(query):
    norm = fold(str(query))
    if 'emine' not in norm:
        return None
    if any(x in norm for x in ('durum', 'rapor', 'son video', 'ne yaptin')):
        st = json_load(STATE, {})
        return ('Emine son hazir video: ' + st.get('son_video', 'Henuz yok')
                + '. Instagram yayini senin onayini bekliyor.')
    if not any(x in norm for x in ('reels', 'video', 'icerik', 'hazirla', 'uret', 'olustur', 'yap')):
        return None
    if LOCK.exists():
        return 'Emine videosu su an hazirlaniyor. Bittiğinde hazir_reels klasorunde olacak.'
    import subprocess as sp
    # A detached worker keeps WhatsApp/CEO voice loop responsive. No paid service.
    flags = 0
    if os.name == 'nt':
        flags = sp.CREATE_NEW_PROCESS_GROUP | sp.DETACHED_PROCESS
    log = LOGS / ('kado_komut_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S') + '.log')
    LOGS.mkdir(parents=True, exist_ok=True)
    with log.open('ab') as output:
        sp.Popen([str(python_for_tasks()), str(ROOT / 'KADO_EMINE_OTOMAT.py'),
                  'uretim', '--zorla', '--konu', str(query)[:180]],
                 cwd=str(ROOT), stdout=output, stderr=sp.STDOUT,
                 stdin=sp.DEVNULL, creationflags=flags,
                 start_new_session=(os.name != 'nt'))
    return ('Emine icin konusmali sesli Reels gorevini otomatik baslattim. '
            'Hazir MP4 06_OTOMATIK/hazir_reels klasorune konacak. '
            'Konusan yuz modeli yoksa video hareketli fotograf olacaktir; Instagram yayini kapali.')


def status():
    s = setup_dirs()
    st = json_load(STATE, {})
    say('=== KADO EMINE OTOMAT DURUM ===')
    say('KADO kok: ' + str(ROOT))
    say('Fotograf sayisi: ' + str(len(list(IMAGES.glob('*.png'))) + len(list(IMAGES.glob('*.jpg')))))
    say('Piper ses modeli: ' + ('VAR' if valid_piper_models() else 'YOK'))
    say('SadTalker CPU: ' + ('HAZIR' if sad_paths(s) else 'HENUZ KURULMADI'))
    say('FFmpeg: ' + str(find_ff('ffmpeg') or 'YOK'))
    say('KADO studyo koprusu: ' + ('BAGLI' if STUDIO.is_file() and BMARK in STUDIO.read_text(encoding='utf-8-sig') else 'BAGLI DEGIL'))
    say('Bugun: ' + st.get('son_gun', 'Henuz uretilmedi'))
    say('Son video: ' + st.get('son_video', 'YOK'))
    say('Motor: ' + st.get('motor', 'YOK'))
    say('Windows gunluk saat (ayar): ' + s.get('saat', '11:00'))
    say('Instagram: MANUEL / ONAYLI')
    return 0


def main():
    parser = argparse.ArgumentParser(description='KADO Emine Yerel Otomasyon')
    parser.add_argument('komut', choices=['ilk_kur','uretim','durum','gunluk_kur',
                                         'gunluk_kaldir','bagla','geri_al','sad_test'])
    parser.add_argument('--zorla', action='store_true')
    parser.add_argument('--konu', default='')
    args = parser.parse_args()
    try:
        if args.komut == 'ilk_kur':
            setup_dirs(); install_female_voice(); return 0
        if args.komut == 'uretim':
            return produce(force=args.zorla, topic=args.konu)
        if args.komut == 'durum': return status()
        if args.komut == 'gunluk_kur': return schedule_create()
        if args.komut == 'gunluk_kaldir': return schedule_remove()
        if args.komut == 'bagla': return connect_voice()
        if args.komut == 'geri_al': return disconnect_voice()
        if args.komut == 'sad_test':
            say('[SADTALKER] ' + ('Hazir, CPU baglantisi bulundu.' if sad_paths(setup_dirs()) else 'Kurulu degil; mevcut Reels motoru hareketli fotograf.'))
            return 0
    except Exception as e:
        say('[HATA] ' + str(e))
        return 2
    return 1

if __name__ == '__main__':
    sys.exit(main())
