from pathlib import Path
import sys
folder=Path(sys.argv[1]);dist=folder/'node_modules/baileys-caller/dist'
entry=(dist/'kado-native-index.mjs').read_text(encoding='utf-8')
custom='./kado-native-wasm.mjs' in entry
engine=(dist/('kado-native-wasm.mjs' if custom else 'wasm-engine.mjs')).read_text(encoding='utf-8')
caller=(folder/'kado-native-call.mts').read_text(encoding='utf-8')
print('=== KADO ARAMA TASIMA KONTROLU ===')
print('Kullanilan motor: '+('Kado adaptoru' if custom else 'orijinal motor'))
print('Sessizligi atan eski filtre: '+('VAR' if 'hasNonZero' in engine else 'YOK'))
print('Sabit 16ms eski ses saati: '+('VAR' if '}, 16);' in engine else 'YOK'))
print('Motor hizini okuyup 16kHz monoya donusturme: '+('VAR' if '#kadoSetPlayback' in engine and 'kadoNormalizer.process' in engine else 'YOK'))
print('Eski yerel enerjiyle ses kesme cagrisi: '+('VAR' if ' checkPeerSpeech(f);' in caller else 'YOK'))
print('Bu kontrol anahtarlari, sohbetleri ve auth dosyalarini okumaz.')
