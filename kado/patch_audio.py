from pathlib import Path
import sys,datetime
folder=Path(sys.argv[1]);dist=folder/'node_modules/baileys-caller/dist'
entry=dist/'kado-native-index.mjs';original=dist/'wasm-engine.mjs';custom=dist/'kado-native-wasm.mjs'
caller=folder/'kado-native-call.mts'
for path in (entry,original,caller):
    if not path.is_file():raise SystemExit('Dosya bulunamadi: '+str(path))
stamp=datetime.datetime.now().strftime('%Y%m%d%H%M%S')
wasm=original.read_text(encoding='utf-8')
old='''                const hasNonZero = audioData.some((s) => Math.abs(s) > 0.0001);
                if (hasNonZero)
                    this.#config.callbacks?.onAudioPlaybackData?.(audioData);'''
new='''                // KADO_PCM_SILENCE: silence must reach the speech endpoint detector.
                this.#config.callbacks?.onAudioPlaybackData?.(Float32Array.from(audioData));'''
if old not in wasm or '        }, 16);' not in wasm:
    raise SystemExit('Ses motoru surumu uyusmuyor. Degisiklik yapilmadi.')
wasm=wasm.replace(old,new,1).replace('        }, 16);','        }, 20);',1)
# Clear only the allocated PCM output region before requesting the next frame.
anchor='            this.#instance.requestAudioDataFromWasmVoip(this.#audioPlaybackBuffer, bufferSize);'
# Preserve indentation-independent matching across the exact distributed SDK.
anchor='this.#instance.requestAudioDataFromWasmVoip(this.#audioPlaybackBuffer, bufferSize);'
if anchor not in wasm:raise SystemExit('PCM okuma bolumu bulunamadi. Degisiklik yapilmadi.')
wasm=wasm.replace(anchor,'''const clearHeap = this.#instance.GROWABLE_HEAP_F32?.();
                const clearIndex = Math.floor(this.#audioPlaybackBuffer / 4);
                if (clearHeap && clearIndex >= 0 && clearIndex + bufferSize/4 <= clearHeap.length)
                    clearHeap.fill(0, clearIndex, clearIndex + bufferSize/4);
                '''+anchor,1)
index=entry.read_text(encoding='utf-8')
if './kado-native-wasm.mjs' not in index:
    if './wasm-engine.mjs' not in index:raise SystemExit('Ses motoru baglantisi bulunamadi.')
    index=index.replace('./wasm-engine.mjs','./kado-native-wasm.mjs',1)
text=caller.read_text(encoding='utf-8')
if '// KADO_VAD_PLAYBACK_ONLY' not in text:
    if 'function checkPeerSpeech(samples:Float32Array){' not in text:
        raise SystemExit('Onceki soz kesme duzeltmesi bulunamadi. Degisiklik yapilmadi.')
    text=text.replace('const speechThreshold=0.035;','const speechThreshold=0.06;',1)
    text=text.replace('if(speechMs>=120&&!voiceLatched)', 'if(speechMs>=240&&!voiceLatched)',1)
    text=text.replace('if(quietMs>=180)', 'if(quietMs>=300)',1)
    anchor='function checkPeerSpeech(samples:Float32Array){'
    text=text.replace(anchor,anchor+'''
 // KADO_VAD_PLAYBACK_ONLY: do not cancel a reply while Kado is just listening.
 const playing = (call?._liveFeeder?.queue?.length || 0) > 0 || pending.length > 0;
 if(!playing){speechMs=0;quietMs=0;voiceLatched=false;return;}
''',1)
    text=text.replace("KARSI TARAF KONUSUYOR: bekleyen ses kesiliyor.","SOZ KESME: Kado konusurken yeterli ses algilandi.")
changes=[(custom,wasm),(entry,index),(caller,text)]
written=[]
try:
    for path,data in changes:
        existed=path.exists();before=path.read_text(encoding='utf-8') if existed else None
        if existed:path.with_name(path.name+'.ses-oncesi-'+stamp).write_text(before,encoding='utf-8')
        path.write_text(data,encoding='utf-8');written.append((path,before))
except Exception:
    for path,before in written:
        if before is None:path.unlink(missing_ok=True)
        else:path.write_text(before,encoding='utf-8')
    raise
print('Sessizlik PCM aktarimi, 20ms ses saati ve yalnizca konusurken soz kesme duzeltildi.')
print('Arayan hesap ve QR oturumlari korunuyor. Orijinal wasm-engine.mjs degistirilmedi.')
