import datetime
import pathlib
import sys

folder=pathlib.Path(sys.argv[1])
link=pathlib.Path(sys.argv[2])
stamp=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
feeder=folder/'node_modules/baileys-caller/dist/kado-live-feeder.mjs'
source=link.parent/'live-feeder.mjs'
index=folder/'node_modules/baileys-caller/dist/kado-native-index.mjs'
for path in (feeder,index):
    if not path.is_file():raise SystemExit('Beklenen dosya bulunamadi: '+str(path))
changes=[]
for path in (feeder,source):
    if not path.is_file():continue
    text=path.read_text(encoding='utf-8')
    if '}; tick();' in text:
        changes.append((path,text,text.replace('}; tick();','}; this.timer=setTimeout(tick, 0);')))
    elif '}; this.timer=setTimeout(tick, 0);' not in text:
        raise SystemExit('Ses adaptoru surumu uyusmuyor. Degisiklik yapilmadi.')
text=index.read_text(encoding='utf-8')
patched=text
if 'KADO_NUMARA_KONTROLU' not in patched:
    anchor='const targetNumber = phoneNumber.replace(/\\D/g, "");'
    if anchor not in patched:raise SystemExit('SDK numara bolumu bulunamadi. Degisiklik yapilmadi.')
    patched=patched.replace(anchor,anchor+'''
        // KADO_NUMARA_KONTROLU: never log session keys.
        const ownNumber = String(this.#sock.authState.creds.me?.id || '').split('@')[0].split(':')[0];
        console.log('ARAYAN SON 4:', ownNumber.slice(-4), '| ARANAN SON 4:', targetNumber.slice(-4));
        if (ownNumber && ownNumber === targetNumber) throw new Error('Ayni WhatsApp hatti kendisini arayamaz. Diger telefonun numarasini kullanin.');
''',1)
if 'kadoStartResult' not in patched:
    anchor='this.#engine.startCall({'
    if anchor not in patched:raise SystemExit('SDK baslatma bolumu bulunamadi. Degisiklik yapilmadi.')
    patched=patched.replace(anchor,'const kadoStartResult = this.#engine.startCall({',1)
    anchor='        return call;'
    if anchor not in patched:raise SystemExit('SDK donus bolumu bulunamadi. Degisiklik yapilmadi.')
    patched=patched.replace(anchor,"        console.log('VOIP BASLATMA SONUCU:', typeof kadoStartResult === 'number' || typeof kadoStartResult === 'string' ? kadoStartResult : typeof kadoStartResult);\n"+anchor,1)
if text!=patched:changes.append((index,text,patched))
written=[]
try:
    for path,before,after in changes:
        backup=path.with_name(path.name+'.yedek-'+stamp)
        backup.write_text(before,encoding='utf-8')
        path.write_text(after,encoding='utf-8')
        written.append((path,before))
except Exception:
    for path,before in written:path.write_text(before,encoding='utf-8')
    raise
print('Canli ses ilk paket zamanlamasi duzeltildi. Numara ve VoIP sonuc kontrolu eklendi.')
print('Mesajlasma, asil Kado, anahtarlar ve auth oturumu degistirilmedi.')
