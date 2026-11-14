from pathlib import Path
import sys, datetime
folder=Path(sys.argv[1])
p=folder/'kado-native-call.mts'
s=p.read_text(encoding='utf-8')
old=' checkPeerSpeech(f);'
new=" if(!firstRemoteAudio){firstRemoteAudio=true;console.log('ILK KARSIDAN PCM ALINDI. Sade acilis V3.');}"
if old not in s and new not in s:
    raise SystemExit('Arama dosyasi surumu uyusmuyor; dosya degistirilmedi.')
s=s.replace(old,new)
p.with_name(p.name+'.sade-oncesi-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S')).write_bytes(p.read_bytes())
p.write_text(s,encoding='utf-8')
print('Yerel enerjiye gore ses kesme kaldirildi. Arayan hesap ve oturum korunuyor.')
