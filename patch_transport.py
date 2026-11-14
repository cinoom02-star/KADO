from pathlib import Path
import datetime, json, subprocess, sys
folder=Path(sys.argv[1]).resolve(); dist=folder/'node_modules/baileys-caller/dist'
original=dist/'wasm-engine.mjs'; custom=dist/'kado-native-wasm.mjs'; entry=dist/'kado-native-index.mjs'; caller=folder/'kado-native-call.mts'
for p in (original,entry,caller):
    if not p.is_file():raise SystemExit('Gerekli arama dosyasi bulunamadi: '+p.name)
s=original.read_text(encoding='utf-8');index=entry.read_text(encoding='utf-8');call=caller.read_text(encoding='utf-8')
if "'./auth" not in call and 'authDir:' not in call:raise SystemExit('Arama dosyasi beklenen surumde degil.')
if "./kado-native-wasm.mjs" not in index and "./wasm-engine.mjs" not in index:raise SystemExit('SDK ses motoru baglantisi taninamadi.')
if 'kado-live' not in index:raise SystemExit('Mevcut Kado PCM adaptoru bulunamadi; islem durdu.')
old='    #isPlaybackActive = false;'
if s.count(old)!=1:raise SystemExit('Motor alanlari uyusmuyor; dosya degistirilmedi.')
s='import { PCMNormalizer } from "./kado-pcm-normalizer.mjs";\n'+s.replace(old,old+'''
    #kadoPlaybackRate = 16000;
    #kadoPlaybackChannels = 1;
    #kadoPlaybackFrames = 320;
    #kadoNormalizer = new PCMNormalizer();
    #kadoSetPlayback = (data) => {
        const rate = Number(data?.sample_rate ?? data?.sampleRate);
        const channels = Number(data?.channels ?? 1);
        const frames = Number(data?.frames_per_chunk ?? data?.framesPerChunk ?? Math.round(rate/50));
        if (!Number.isInteger(rate) || rate < 8000 || rate > 96000 || ![1,2].includes(channels)
            || !Number.isInteger(frames) || frames < 40 || frames > 4096) return;
        const restart = this.#isPlaybackActive;
        if (restart) this.#stopAudioPlaybackLoop();
        this.#kadoPlaybackRate = rate;
        this.#kadoPlaybackChannels = channels;
        this.#kadoPlaybackFrames = frames;
        this.#kadoNormalizer.reset();
        console.log('KADO PCM: motor='+rate+'Hz kanal='+channels+' parca='+frames+'; Kado girisi=16000Hz mono, sessizlik dahil.');
        if (restart) this.#startAudioPlaybackLoop();
    };
''',1)
# The original registers playback-format notifications only if an optional callback exists.
s=s.replace('        if (callbacks.onAudioPlaybackInit) {','        { // KADO: always consume playback-format metadata.',1)
s=s.replace('_a.registerGlobalCallbackListener("initPlaybackDriverJS", (data) => {','_a.registerGlobalCallbackListener("initPlaybackDriverJS", (data) => {\n                this.#kadoSetPlayback(data);',1)
s=s.replace('callbacks.onAudioPlaybackInit({','callbacks.onAudioPlaybackInit?.({',1)
s=s.replace('            initPlaybackDriverJS: (data) => {','            initPlaybackDriverJS: (data) => {\n                this.#kadoSetPlayback(data);',1)
a=s.index('    #startAudioPlaybackLoop = () => {');b=s.index('    #stopAudioPlaybackLoop',a)
s=s[:a]+'''    #startAudioPlaybackLoop = () => {
        if (this.#audioPlaybackLoopInterval) return;
        this.#ensureInitialized();
        this.#isPlaybackActive = true;
        if (typeof this.#instance.requestAudioDataFromWasmVoip !== 'function') return;
        const bufferSize = this.#kadoPlaybackFrames * this.#kadoPlaybackChannels * 4;
        const malloc = this.#instance._malloc ?? this.#instance.malloc;
        if (!malloc) return;
        this.#audioPlaybackBuffer = malloc(bufferSize);
        if (!this.#audioPlaybackBuffer || this.#audioPlaybackBuffer <= 0) return;
        const intervalMs = this.#kadoPlaybackFrames / this.#kadoPlaybackRate * 1000;
        let next = performance.now();
        const tick = () => {
            if (!this.#isPlaybackActive || !this.#instance || !this.#initialized) {
                this.#stopAudioPlaybackLoop(); return;
            }
            try {
                const before = this.#instance.GROWABLE_HEAP_F32?.();
                const start = Math.floor(this.#audioPlaybackBuffer/4);
                if (before && start >= 0 && start+bufferSize/4 <= before.length)
                    before.fill(0,start,start+bufferSize/4);
                this.#instance.requestAudioDataFromWasmVoip(this.#audioPlaybackBuffer,bufferSize);
                const heap = this.#instance.GROWABLE_HEAP_F32?.();
                if (heap && start >= 0 && start+bufferSize/4 <= heap.length) {
                    const frame = new Float32Array(heap.buffer,heap.byteOffset+start*4,bufferSize/4);
                    const mono = this.#kadoNormalizer.process(frame,this.#kadoPlaybackRate,this.#kadoPlaybackChannels);
                    if (mono.length) this.#config.callbacks?.onAudioPlaybackData?.(mono);
                }
            } catch {}
            if (!this.#isPlaybackActive) return;
            next += intervalMs;
            const now = performance.now();
            if (now-next > intervalMs) next = now+intervalMs;
            this.#audioPlaybackLoopInterval = setTimeout(tick,Math.max(1,next-now));
        };
        this.#audioPlaybackLoopInterval = setTimeout(tick,0);
    };
'''+s[b:]
index=index.replace('./wasm-engine.mjs','./kado-native-wasm.mjs',1)
# Keep account, number handling and signaling untouched. Disable only the old energy-cut hook.
call=call.replace(' checkPeerSpeech(f);'," if(!firstRemoteAudio){firstRemoteAudio=true;console.log('ILK KARSIDAN PCM: surekli 16kHz, sessizlik dahil.');}")
old_engine=entry.read_text(encoding='utf-8')
if './kado-native-wasm.mjs' in old_engine and custom.exists():old_engine=custom.read_text(encoding='utf-8')
else:old_engine=original.read_text(encoding='utf-8')
filtered='hasNonZero' in old_engine
fixed_clock='}, 16);' not in old_engine
print('ONCEKI MOTOR: sessizlik filtresi='+str(filtered)+'; sabit 16ms olmayan saat='+str(fixed_clock))
normalizer=Path(__file__).with_name('pcm-normalizer.mjs').read_text(encoding='utf-8')
changes=[(dist/'kado-pcm-normalizer.mjs',normalizer),(custom,s),(entry,index),(caller,call)]
for path,data in changes:
    check=path.with_name('.kado-check-'+path.name)
    if path.suffix=='.mjs':
        try:
            check.write_text(data,encoding='utf-8')
            subprocess.run(['node','--check',str(check)],check=True,capture_output=True,text=True)
        finally:check.unlink(missing_ok=True)
backup=folder/('kado-transport-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'));backup.mkdir()
manifest=[];written=[]
try:
    for i,(p,data) in enumerate(changes):
        existed=p.exists();before=p.read_bytes() if existed else None
        if existed:(backup/str(i)).write_bytes(before)
        manifest.append({'path':str(p.relative_to(folder)),'backup':str(i) if existed else None})
        p.write_text(data,encoding='utf-8');written.append((p,before))
    (backup/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
except BaseException:
    for p,before in reversed(written):
        if before is None:p.unlink(missing_ok=True)
        else:p.write_bytes(before)
    raise
print('TAMAM: surekli sessizlik, motor formatina uygun saat, bagimsiz PCM kopyasi ve 16kHz mono aktarim.')
print('YEDEK: '+backup.name)
print('WhatsApp hesabi, auth klasorleri, main.py ve mesajlasma dosyalari degistirilmedi.')
