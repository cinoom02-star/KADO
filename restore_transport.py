from pathlib import Path
import json,sys
folder=Path(sys.argv[1]).resolve()
backups=sorted(folder.glob('kado-transport-backup-*/manifest.json'))
if not backups:raise SystemExit('Bu pakete ait yedek bulunamadi.')
manifest=backups[-1];items=json.loads(manifest.read_text(encoding='utf-8'))
allowed={'node_modules/baileys-caller/dist/kado-native-wasm.mjs','node_modules/baileys-caller/dist/kado-native-index.mjs','node_modules/baileys-caller/dist/kado-pcm-normalizer.mjs','kado-native-call.mts'}
if any(i['path'] not in allowed for i in items):raise SystemExit('Yedek listesi uyusmuyor; dosya degistirilmedi.')
for item in items:
 if item['backup'] is not None and not (manifest.parent/item['backup']).is_file():raise SystemExit('Yedek eksik; dosya degistirilmedi.')
for item in reversed(items):
 p=folder/item['path']
 if item['backup'] is None:p.unlink(missing_ok=True)
 else:p.write_bytes((manifest.parent/item['backup']).read_bytes())
print('Son tasima duzeltmesinden onceki dosyalar geri yuklendi.')
