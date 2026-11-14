import {readFileSync,writeFileSync,copyFileSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
const entry=fileURLToPath(import.meta.resolve('baileys-caller'));
const folder=dirname(entry);
let code=readFileSync(entry,'utf8');
const transforms=[
 ['import { AudioFeeder } from "./audio-feeder.mjs";', 'import { AudioFeeder } from "./audio-feeder.mjs";\nimport {LiveAudioFeeder} from "./kado-live-feeder.mjs";'],
 ['_audioSource = "silence";', `_audioSource = "silence";\n    _liveFeeder = null;\n    writePcm = (samples, rate) => { if (!this._liveFeeder) return false; this._liveFeeder.writePcm(samples, rate); return true; };\n    clearPcm = () => { this._liveFeeder?.clear(); };\n    flushPcm = () => { this._liveFeeder?.flush(); };`],
 ['this.#feeder = new AudioFeeder(', 'this.#feeder = new (audioSource === "kado-live" ? LiveAudioFeeder : AudioFeeder)('],
 ['this.#feeder.start();', 'if (this.#activeCall) this.#activeCall._liveFeeder = this.#feeder;\n        this.#feeder.start();'],
];
for(const [before,after] of transforms){if(!code.includes(before))throw Error('SDK surumu uyusmuyor: '+before);code=code.replace(before,after);}
// end() in this SDK otherwise prevents its own ended event from being emitted.
const start=code.indexOf('    end = () => {');
const end=code.indexOf('    mute = ',start);
if(start<0||end<0)throw Error('SDK end() bulunamadi');
code=code.slice(0,start)+`    end = () => {\n        if (this.#ended) return;\n        this._forceEnd("local_end");\n        try { this.engine.endCall(0, true); } catch {}\n    };\n`+code.slice(end);
copyFileSync(join(dirname(fileURLToPath(import.meta.url)),'live-feeder.mjs'),join(folder,'kado-live-feeder.mjs'));
writeFileSync(join(folder,'kado-native-index.mjs'),code);
console.log('Kado direct PCM adapter hazir. Orijinal SDK dosyasi korunuyor.');
