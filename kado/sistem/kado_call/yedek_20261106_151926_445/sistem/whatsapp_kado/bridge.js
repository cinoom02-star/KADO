'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const {spawn, execFile} = require('child_process');
const readline = require('readline');
const {promisify} = require('util');
const {eligible, acceptOnce} = require('./policy');
const {Client, LocalAuth, MessageMedia} = require('whatsapp-web.js');
const qr = require('qrcode-terminal');
const ffmpeg = require('ffmpeg-static');
const run = promisify(execFile);
const start = Math.floor(Date.now() / 1000);
let enabled = true, pendingCount = 0, nextId = 0, ready = false;
let mode = 'test', testNumber = '';
const testIds = new Set();
const paused = new Map(), sending = new Set(), sent = new Set(), seen = new Set();
const requests = new Map();
let queue = Promise.resolve();

const cli = readline.createInterface({input: process.stdin, output: process.stdout});
const ask = q => new Promise(resolve => cli.question(q, resolve));
const worker = spawn(process.env.KADO_PY || 'python', ['-u', path.join(__dirname, 'worker.py')],
    {cwd: __dirname, stdio: ['pipe', 'pipe', 'inherit'], windowsHide: true});
function failPending(reason) {
    for (const request of requests.values()) { clearTimeout(request.timer); request.reject(new Error(reason)); }
    requests.clear();
}
readline.createInterface({input: worker.stdout}).on('line', line => {
    try {
        const result = JSON.parse(line), request = requests.get(result.id);
        if (!request) return;
        clearTimeout(request.timer); requests.delete(result.id);
        result.ok ? request.resolve(result) : request.reject(new Error(result.error));
    } catch { console.error('Kado cevap aktarim hatasi.'); }
});
worker.on('error', () => { enabled = false; failPending('Python baslatilamadi.'); });
worker.stdin.on('error', () => failPending('Python baglantisi kapandi.'));
worker.on('exit', () => { enabled = false; failPending('Python kapandi; yeniden baslatin.'); });
function think(payload) {
    return new Promise((resolve, reject) => {
        const id = ++nextId;
        const timer = setTimeout(() => {
            requests.delete(id); reject(new Error('Kado zaman asimina ugradi.'));
            // A stalled serial worker must not retain pending customer messages.
            enabled = false; worker.kill();
        }, 180000);
        requests.set(id, {resolve, reject, timer});
        worker.stdin.write(JSON.stringify({...payload, id}) + '\n');
    });
}
const client = new Client({authStrategy: new LocalAuth({dataPath: path.join(__dirname, '.session')}),
    puppeteer: {headless: true}});
client.on('qr', value => {
    console.log('\nWhatsApp Business > Bagli cihazlar > Cihaz bagla: bu QR kodunu okutun.');
    qr.generate(value, {small: true});
});
client.on('ready', async () => {
    if (mode !== 'all') {
        testIds.add(testNumber + '@c.us');
        try {
            const records = await client.getContactLidAndPhone([testNumber + '@c.us']);
            for (const record of records) {
                if (record.lid) testIds.add(record.lid);
                if (record.pn) testIds.add(record.pn);
            }
        } catch { console.log('Test numarasi LID eslemesi alinamadi; telefon kimligiyle denenecek.'); }
    }
    ready = true;
    console.log('\nKADO WHATSAPP BAGLANDI. Mod: ' + (mode === 'all' ? 'TUM BIREYSEL SOHBETLER' : 'TEST NUMARASI'));
    console.log('Komutlar: dur = cevaplari durdur, ac = yeniden ac, cik = kapat.');
});
client.on('auth_failure', () => console.error('Oturum dogrulanamadi; telefondan bagli cihazlari kontrol edin.'));
client.on('disconnected', () => {
    ready = false; enabled = false;
    console.error('WhatsApp baglantisi kesildi. Pencereyi kapatip yeniden baslatin.');
});
// Replies no longer pause a conversation automatically. Use dur/ac in this window.
async function send(to, content, opts = {}) {
    sending.add(to);
    try {
        const result = await client.sendMessage(to, content, {...opts, sendSeen: false});
        if (result?.id?._serialized) sent.add(result.id._serialized);
        if (sent.size > 3000) sent.delete(sent.values().next().value);
        return result;
    } finally { sending.delete(to); }
}
async function voiceMedia(b64) {
    const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'kado-wa-'));
    try {
        const input = path.join(folder, 'reply.mp3'), output = path.join(folder, 'reply.ogg');
        fs.writeFileSync(input, Buffer.from(b64, 'base64'));
        await run(ffmpeg, ['-nostdin', '-y', '-i', input, '-vn', '-c:a', 'libopus', '-b:a', '32k', output],
            {timeout: 30000, windowsHide: true});
        return MessageMedia.fromFilePath(output);
    } finally { fs.rmSync(folder, {recursive: true, force: true}); }
}
let receivedCount = 0;
const rejectedTestIds = new Set();
async function onIncoming(msg) {
    if (msg.fromMe || msg.isStatus) return;
    if (!eligible(msg, start, 'all', testNumber)) return;
    if (mode !== 'all' && !testIds.has(msg.from)) {
        try {
            const records = await client.getContactLidAndPhone([msg.from]);
            if (records.some(r => r.pn === testNumber + '@c.us')) testIds.add(msg.from);
        } catch { /* Fail closed: never answer an unverified test sender. */ }
        if (!testIds.has(msg.from)) {
            if (!rejectedTestIds.has(msg.from)) {
                console.log('Bir mesaj TEST NUMARASI eslesmedigi icin atlandi.');
                rejectedTestIds.add(msg.from);
            }
            return;
        }
    }
    if (!enabled || !ready) { console.log('Mesaj alindi fakat otomatik cevap kapali.'); return; }
    if (pendingCount >= 10) { console.log('Mesaj sirasi dolu; bu mesaj islenmedi.'); return; }
    if (!acceptOnce(seen, msg)) return;
    const number = ++receivedCount;
    console.log('Mesaj #' + number + ' alindi; cevap sirasina eklendi.');
    pendingCount++;
    queue = queue.then(async () => {
        if (!enabled || !ready || (paused.get(msg.from) || 0) > Date.now()) return;
        let stage = 'mesaji hazirlama';
        try {
            const payload = {chat: msg.from, text: msg.body || ''};
            if (msg.type === 'ptt' || msg.type === 'audio') {
                // Refuse large attachments before and after downloading.
                if (Number(msg._data?.size) > 8 * 1024 * 1024) {
                    await send(msg.from, 'Ses kaydi cok buyuk. Daha kisa bir kayit gonderebilir misiniz?'); return;
                }
                const media = await msg.downloadMedia();
                if (!media || !media.mimetype.startsWith('audio/') ||
                    Buffer.byteLength(media.data, 'base64') > 8 * 1024 * 1024) {
                    await send(msg.from, 'Bu ses kaydini okuyamadim. Yazarak veya kisa bir ses kaydiyla deneyin.'); return;
                }
                payload.audio = {mime: media.mimetype, data: media.data};
            }
            if (/^sesli\s*:/i.test(payload.text)) {
                payload.voice = true; payload.text = payload.text.replace(/^sesli\s*:/i, '');
            }
            stage = 'Gemini cevabi';
            const result = await think(payload);
            // Stop/pause can happen while the model is generating.
            if (!enabled || !ready || (paused.get(msg.from) || 0) > Date.now()) return;
            stage = 'WhatsApp cevabini gonderme';
            let delivered = false;
            if (result.audio) {
                try {
                    const media = await voiceMedia(result.audio);
                    if (!enabled || !ready || (paused.get(msg.from) || 0) > Date.now()) return;
                    await send(msg.from, media, {sendAudioAsVoice: true}); delivered = true;
                } catch { console.log('Ses gonderilemedi; metin olarak denenecek.'); }
            }
            if (!delivered) await send(msg.from, result.text);
            if (result.voice_failed) console.log('ElevenLabs yaniti alinamadi; metin gonderildi.');
            console.log('Mesaj #' + number + ' icin gonderim tamamlandi.');
        } catch (error) {
            // Customer content and secrets are never written to logs.
            console.error('Mesaj #' + number + ' HATA [' + stage + ']:', String(error.stack || error.message || error).replace(/https?:\/\/\S+/g, '[adres]').replace(/AIza[\w-]+/g, '[anahtar]').slice(0, 1600));
        }
    }).catch(() => console.error('Mesaj isleme hatasi.')).finally(() => pendingCount--);
}
client.on('message', msg => { onIncoming(msg).catch(() => console.error('Gelen mesaj islenemedi.')); });
// Test-mode fallback: some Web sessions deliver the first event but miss later ones.
// Fetch only the verified test conversation, and deduplicate shared event/poll messages.
let polling = false, pollErrorLogged = false;
setInterval(async () => {
    if (mode === 'all' || !ready || !enabled || polling) return;
    polling = true;
    try {
        let messages = null;
        for (const id of testIds) {
            try {
                const chat = await client.getChatById(id);
                messages = await chat.fetchMessages({limit: 8});
                if (messages?.length) break;
            } catch { /* Try the verified alternative phone/LID identity. */ }
        }
        if (!messages) throw new Error('Test sohbeti okunamadi.');
        for (const message of messages) await onIncoming(message);
    } catch {
        if (!pollErrorLogged) {
            console.log('Test sohbetinin ek kontrolu kullanilamadi; yeni mesaj olaylari dinleniyor.');
            pollErrorLogged = true;
        }
    } finally { polling = false; }
}, 10000).unref();
// Local commands issued by the desktop Kado, never by an incoming contact.
const ipc = path.join(__dirname,'.ipc');
fs.mkdirSync(ipc,{recursive:true});
let commandBusy=false;
setInterval(async()=>{
    if(!ready)return;
    fs.writeFileSync(path.join(ipc,'heartbeat.json'),JSON.stringify({time:Date.now()/1000}));
    if(commandBusy)return;
    const names=fs.readdirSync(ipc).filter(n=>/^[a-f0-9]{32}\.request\.json$/.test(n));
    if(!names.length)return;
    commandBusy=true;
    const name=names[0], file=path.join(ipc,name);
    let item;
    try{
        item=JSON.parse(fs.readFileSync(file,'utf8'));
        if(item.id !== name.slice(0,32))throw Error('Gecersiz komut kimligi');
        fs.renameSync(file,file+'.processing');
        if(!/^[0-9]{10,15}$/.test(item.phone)||typeof item.text!=='string'||!item.text.trim())throw Error('Gecersiz mesaj');
        const target=item.phone+'@c.us';
        if(item.voice){
            const audio=await think({action:'voice_only',text:item.text.slice(0,3500)});
            await send(target,await voiceMedia(audio.audio),{sendAudioAsVoice:true});
        }else await send(target,item.text.slice(0,3500));
        fs.writeFileSync(path.join(ipc,item.id+'.result.json'),JSON.stringify({message:'WhatsApp gonderim cagrisi tamamlandi; teslim durumu sohbetten kontrol edilebilir.'}));
    }catch{
        if(item?.id && /^[a-f0-9]{32}$/.test(item.id))fs.writeFileSync(path.join(ipc,item.id+'.result.json'),JSON.stringify({message:'WhatsApp mesaji gonderilemedi.'}));
    }finally{
        try{fs.unlinkSync(file+'.processing');}catch{}
        commandBusy=false;
    }
},1000).unref();
client.on('call', () => console.log('WhatsApp aramasi geldi. Bu surum aramayi ACMAZ; telefondan cevaplayin.'));
async function stop() {
    enabled = false; worker.kill();
    await Promise.race([client.destroy().catch(() => {}), new Promise(r => setTimeout(r, 3000))]);
    process.exit(0);
}
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
async function main() {
    console.log('ASIL KADO WHATSAPP - Yazi ve ses kaydi, cevaplar masaustundeki Kado tarafindan.');
    console.log('Resmi olmayan baglanti: kopma / hesap kisitlamasi riski vardir.');
    console.log('Gelen mesajlar ASIL KADO oturumuna aktarilir; ses kayitlari ElevenLabs ile uretilir.');
    console.log('Normal Kado becerileri korunur. Dis kisiler bilgisayar komutu calistiramaz.\n');
    const choice = (await ask('Sadece test numarasi: 1 (onerilir) / Tum bireysel sohbetler: 2 : ')).trim();
    if (choice === '2') {
        const confirm = await ask('Gelen tum bireysel mesajlara otomatik cevap acilsin mi? EVET yazin: ');
        if (confirm.trim().toUpperCase() !== 'EVET') return stop();
        mode = 'all';
    } else {
        testNumber = (await ask('Test mesaji gonderecek DIGER telefonun numarasi (905xxxxxxxxx): ')).replace(/\D/g, '');
        if (!/^\d{10,15}$/.test(testNumber)) { console.log('Numara gecersiz. Yeniden baslatin.'); return stop(); }
    }
    cli.on('line', value => {
        const command = value.trim().toLowerCase();
        if (command === 'dur') { enabled = false; console.log('Otomatik cevap DURDU.'); }
        if (command === 'ac' && ready && worker.exitCode === null && !worker.killed) { enabled = true; console.log('Otomatik cevap ACIK.'); }
        if (command === 'cik') stop();
    });
    await client.initialize();
}
main().catch(error => { console.error('BASLATMA HATASI:', String(error.stack || error.message || error).replace(/https?:\/\/\S+/g, '[adres]').slice(0, 1600)); stop(); });

// KADO_BAGLANTI_TAKIP
console.log('Baglanti asama kaydi acik.');
client.on('loading_screen', (yuzde) => console.log('WhatsApp yukleniyor: %' + yuzde));
client.on('authenticated', () => console.log('WhatsApp oturumu dogrulandi; hazirlaniyor.'));
client.on('change_state', (durum) => console.log('WhatsApp durumu:', durum));