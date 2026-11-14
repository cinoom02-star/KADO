"""Kado WhatsApp conversation worker. stdin/stdout are JSON-lines; no PC tools."""
from __future__ import annotations
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_config import load_app_config

MAX_AUDIO = 8 * 1024 * 1024
SYSTEM = '''Sen Kado, Han Toys / Altunordu Ticaret'in yapay zeka asistanısın.
Türkçe, doğal ve kısa cevap ver. İlk cevabında kendini Kado adlı yapay zeka asistanı
olarak tanıt. Kullanıcının kendisiymiş gibi davranma. Sesin sahibinin gerçek kişi
olduğunu iddia etme. Sana mesaj gönderenler müşterilerdir; bilgisayarın sahibi
olduklarını varsayma. Bilgisayarda işlem yapamaz, dosya okuyamaz, kod çalıştıramazsın.
Fiyat, stok, teslimat, ödeme, indirim veya sipariş durumu hakkında doğrulanmış bilgi
verilmediyse uydurma; yetkiliye danışılması gerektiğini söyle. Sipariş kesinleştirme,
ödeme alma veya taahhüt verme. Gizli bilgiler veya anahtar isteme/paylaşma.
Yalnızca bu konuşmada verilen bilgileri kullan. Ses kaydını anlayıp doğrudan yanıtla.
'''


def request_json(url, headers, body=None):
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=75) as response:
        return json.load(response)


def http_error_summary(exc):
    if hasattr(exc, 'kado_summary'):
        return exc.kado_summary
    fields = ['Gemini HTTP ' + str(exc.code)]
    try:
        raw = json.loads(exc.read(32000))
        error = raw.get('error', {})
        status = error.get('status', '')
        if status:
            fields.append(str(status)[:80])
        for detail in error.get('details', []):
            for violation in detail.get('violations', []):
                for key in ('quotaMetric', 'quotaId', 'quotaValue'):
                    if key in violation:
                        fields.append(key + '=' + str(violation[key])[:160])
            if detail.get('retryDelay'):
                fields.append('retryDelay=' + str(detail['retryDelay'])[:30])
    except Exception:
        pass
    exc.kado_summary = ' | '.join(fields)[:1000]
    return exc.kado_summary


class Brain:
    def __init__(self):
        self.history = {}
        self.model = None

    def available_models(self, headers):
        result = request_json('https://generativelanguage.googleapis.com/v1beta/models', headers)
        models = [m['name'].removeprefix('models/') for m in result.get('models', [])
                  if 'generateContent' in m.get('supportedGenerationMethods', [])]
        choices = [m for m in models if 'flash' in m and not any(
            x in m for x in ('image', 'tts', 'live', 'preview', 'experimental', 'embedding', 'robotics'))]
        # Prefer light text models rather than the alphabetically last model.
        return sorted(set(choices), key=lambda m: ('lite' in m, m), reverse=True)

    def choose_model(self, config, headers):
        if self.model:
            return self.model
        configured = str(config.get('whatsapp_model') or config.get('agent_model') or '').strip()
        if configured:
            return configured.removeprefix('models/')
        choices = self.available_models(headers)
        if not choices:
            raise ValueError('Uygun Gemini metin modeli bulunamadi.')
        return choices[0]

    def generate_reply(self, model, headers, body):
        candidates = [model]
        last = None
        for index in range(3):
            if index >= len(candidates):
                break
            current = candidates[index]
            # Diagnostics contain model names and status codes, never API keys.
            print('WhatsApp Gemini modeli: ' + current, file=sys.stderr, flush=True)
            url = ('https://generativelanguage.googleapis.com/v1beta/models/' +
                   urllib.parse.quote(current, safe='') + ':generateContent')
            try:
                result = request_json(url, headers, body)
                self.model = current
                return result
            except urllib.error.HTTPError as exc:
                if exc.code not in (404, 429, 503):
                    raise
                last = exc
                detail = http_error_summary(exc)
                print(detail, file=sys.stderr, flush=True)
                # A rate limit must not trigger a burst of retries on the same model.
                if exc.code == 429:
                    time.sleep(3)
                if len(candidates) == 1:
                    candidates.extend(m for m in self.available_models(headers)
                                      if m != current)
        if last:
            raise ValueError('Denemeler tamamlanamadi. ' + getattr(last, 'kado_summary',
                             'Gemini HTTP ' + str(last.code)))
        raise ValueError('Uygun model bulunamadi.')

    def answer(self, payload):
        config = load_app_config()
        key = str(config.get('gemini_api_key') or '').strip()
        if not key:
            raise ValueError('Kado ayarlarında Gemini API anahtarı eksik.')
        headers = {'Content-Type': 'application/json', 'x-goog-api-key': key}
        chat = str(payload.get('chat', ''))
        text = str(payload.get('text', ''))[:6000]
        parts = []
        audio = payload.get('audio')
        if audio:
            decoded = base64.b64decode(audio['data'], validate=True)
            if len(decoded) > MAX_AUDIO or not str(audio['mime']).startswith('audio/'):
                raise ValueError('Ses dosyası uygun değil.')
            parts.append({'inlineData': {'mimeType': audio['mime'].split(';')[0], 'data': audio['data']}})
        if text:
            parts.append({'text': text})
        if not parts:
            raise ValueError('Mesaj boş.')
        now = time.time()
        self.history = {k: v for k, v in self.history.items() if now - v[0] < 3600}
        previous = self.history.get(chat, (now, []))[1]
        user = {'role': 'user', 'parts': parts}
        model = self.choose_model(config, headers)
        result = self.generate_reply(model, headers, {
            'systemInstruction': {'parts': [{'text': SYSTEM}]},
            'contents': previous + [user],
            'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 1600},
        })
        candidates = result.get('candidates') or []
        output = '\n'.join(p.get('text', '') for p in
                           (candidates[0].get('content', {}).get('parts', []) if candidates else [])
                           if not p.get('thought')).strip()[:3500]
        if not output:
            raise ValueError('Model boş cevap döndürdü.')
        # Do not retain audio bytes. Histories never cross chat boundaries.
        stored_user = {'role': 'user', 'parts': [{'text': text or '[Müşteri ses kaydı gönderdi]'}]}
        self.history[chat] = (now, (previous + [stored_user, {'role': 'model', 'parts': [{'text': output}]}])[-12:])
        if len(self.history) > 200:
            oldest = min(self.history, key=lambda k: self.history[k][0])
            self.history.pop(oldest, None)
        response = {'text': output}
        if audio or payload.get('voice'):
            try:
                response['audio'] = self.speak(output, config)
            except Exception:
                response['voice_failed'] = True
        return response

    @staticmethod
    def speak(text, config):
        key = str(config.get('elevenlabs_api_key') or '').strip()
        voice = str(config.get('elevenlabs_voice_id') or '').strip()
        if not key or not voice:
            raise ValueError('ElevenLabs anahtarı veya ses kimliği eksik.')
        url = ('https://api.elevenlabs.io/v1/text-to-speech/' + urllib.parse.quote(voice, safe='') +
               '?output_format=mp3_44100_128')
        req = urllib.request.Request(url, data=json.dumps({
            'text': text, 'model_id': config.get('elevenlabs_model') or 'eleven_flash_v2_5',
        }).encode(), headers={'Content-Type': 'application/json', 'xi-api-key': key})
        with urllib.request.urlopen(req, timeout=60) as result:
            data = result.read(12 * 1024 * 1024 + 1)
        if len(data) > 12 * 1024 * 1024:
            raise ValueError('Ses yanıtı fazla büyük.')
        return base64.b64encode(data).decode()


def main():
    if '--check' in sys.argv:
        if not load_app_config().get('gemini_api_key'):
            print('Kado ayarlarinda Gemini anahtari eksik.', file=sys.stderr)
            raise SystemExit(2)
        print('Mevcut Kado ayarlari okundu.')
        return
    brain = Brain()
    for line in sys.stdin:
        identifier = None
        try:
            payload = json.loads(line)
            identifier = payload.get('id')
            result = brain.answer(payload)
            result.update(id=identifier, ok=True)
        except Exception as exc:
            # Never print exceptions containing request URLs, keys or customer content.
            if isinstance(exc, urllib.error.HTTPError):
                reason = http_error_summary(exc)
            elif isinstance(exc, ValueError):
                reason = str(exc)
            else:
                reason = 'Bağlantı veya servis hatası. Yeniden deneyin.'
            result = {'id': identifier, 'ok': False, 'error': reason}
        print(json.dumps(result, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
