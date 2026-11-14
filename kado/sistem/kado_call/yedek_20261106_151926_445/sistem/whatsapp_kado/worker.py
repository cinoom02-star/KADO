"""WhatsApp adapter: all answers come from the running desktop Kado."""
from __future__ import annotations
import base64
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_config import load_app_config


def speak(text,config):
    key=str(config.get('elevenlabs_api_key') or '').strip()
    voice=str(config.get('elevenlabs_voice_id') or '').strip()
    if not key or not voice: raise ValueError('ElevenLabs anahtari veya ses kimligi eksik.')
    url='https://api.elevenlabs.io/v1/text-to-speech/'+urllib.parse.quote(voice,safe='')+'?output_format=mp3_44100_128'
    request=urllib.request.Request(url,data=json.dumps({'text':text,'model_id':config.get('elevenlabs_model') or 'eleven_flash_v2_5'}).encode(),
                                   headers={'Content-Type':'application/json','xi-api-key':key})
    with urllib.request.urlopen(request,timeout=60) as result: data=result.read(12*1024*1024+1)
    if len(data)>12*1024*1024: raise ValueError('Ses yaniti fazla buyuk.')
    return base64.b64encode(data).decode('ascii')


def decode_audio(audio):
    binary=base64.b64decode(audio['data'],validate=True)
    if len(binary)>8*1024*1024 or not str(audio['mime']).startswith('audio/'):
        raise ValueError('Ses dosyasi uygun degil.')
    candidates=[ROOT/'whatsapp_kado'/'node_modules'/'ffmpeg-static'/'ffmpeg.exe',
                ROOT/'whatsapp_kado'/'node_modules'/'ffmpeg-static'/'ffmpeg']
    executable=next((str(p) for p in candidates if p.is_file()),None) or shutil.which('ffmpeg')
    if not executable: raise ValueError('Ses donusturucu bulunamadi.')
    result=subprocess.run([executable,'-nostdin','-v','error','-i','pipe:0','-t','60','-vn','-ac','1','-ar','16000','-f','s16le','pipe:1'],
                          input=binary,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode or not result.stdout: raise ValueError('Ses kaydi cozumlenemedi.')
    if len(result.stdout)>=1_920_000: raise ValueError('Lutfen 60 saniyeden kisa ses kaydi gonderin.')
    return base64.b64encode(result.stdout).decode('ascii')


def answer(payload):
    config=load_app_config()
    text=str(payload.get('text') or '')[:6000]
    if payload.get('action')=='voice_only':
        return {'text':text,'audio':speak(text,config)}
    try: state=json.loads((ROOT/'kado_call'/'link.json').read_text(encoding='utf-8'))
    except (OSError,ValueError): raise ValueError('ASIL KADO ACIK DEGIL. KADO_BIRLESIK_BASLAT.bat ile acin.')
    if state.get('ready') is False: raise ValueError('Asil Kado yeniden baglaniyor; hazir olunca tekrar deneyin.')
    port=state.get('port')
    if not isinstance(port,int) or not 1<=port<=65535: raise ValueError('Kado baglanti ayari gecersiz.')
    body={'chat':str(payload.get('chat','')),'text':text}
    if payload.get('audio'): body['pcm']=decode_audio(payload['audio'])
    request=urllib.request.Request(f'http://127.0.0.1:{port}/message',
        data=json.dumps(body).encode('utf-8'),headers={'Content-Type':'application/json','Authorization':'Bearer '+state['token']})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=100) as result: reply=json.load(result)
    except urllib.error.HTTPError as error:
        try: detail=json.loads(error.read(4096)).get('error','Kado yanit veremedi.')
        except Exception: detail='Kado yanit veremedi.'
        raise ValueError(detail)
    except urllib.error.URLError as error:
        raise ValueError('Yerel Kado baglanti hatasi: ' + str(error.reason))
    result={'text':str(reply.get('text','')).strip()[:3500]}
    if not result['text']: raise ValueError('Kado bos yanit dondurdu.')
    if payload.get('audio') or payload.get('voice'):
        try: result['audio']=speak(result['text'],config)
        except Exception: result['voice_failed']=True
    return result


def main():
    if '--check' in sys.argv:
        if not load_app_config().get('gemini_api_key'): raise SystemExit('Mevcut Kado Gemini anahtari eksik.')
        print('Mevcut Kado ayarlari okundu. Yanit kaynagi: ASIL MASAUSTU KADO.')
        return
    for line in sys.stdin:
        identifier=None
        try:
            payload=json.loads(line); identifier=payload.get('id')
            result=answer(payload);result.update(id=identifier,ok=True)
        except Exception as error:
            reason=str(error) if isinstance(error,ValueError) else 'Kado veya ses servisine baglanilamadi.'
            result={'id':identifier,'ok':False,'error':reason[:350]}
        print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
