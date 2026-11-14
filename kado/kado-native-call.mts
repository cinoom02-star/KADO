import {dirname,join} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {readFileSync,existsSync} from 'node:fs';
import WebSocket,{WebSocketServer} from 'ws';
const number=process.argv[2];
if(!/^\d{10,15}$/.test(number||''))throw Error('Aranacak ulke kodlu numara gerekli.');
const linkPath=process.env.KADO_LINK_FILE||'/mnt/c/KADO/kado/sistem/kado_call/link.json';
if(!existsSync(linkPath))throw Error('Once Windows tarafinda KADO_BIRLESIK_BASLAT.bat acilmali.');
const link=JSON.parse(readFileSync(linkPath,'utf8'));
const entry=join(dirname(fileURLToPath(import.meta.resolve('baileys-caller'))),'kado-native-index.mjs');
const {VoipClient}=await import(pathToFileURL(entry).href);
// Diagnostic stage logs: never dump Signal/WhatsApp key objects.
for (const method of ['log','info','warn','error'] as const) {
 const original=console[method].bind(console);
 console[method]=(...args:any[])=>{
  const text=typeof args[0]==='string'?args[0]:'';
  const secret=args.some(value=>value && typeof value==='object' &&
   ('currentRatchet' in value || 'privKey' in value || 'rootKey' in value));
  if(secret || /^(Closing session|Removing old closed session|Session already closed)/i.test(text)) {
   original('WhatsApp sifreli oturumu guncellendi.'); return;
  }
  original(...args);
 };
}
async function stage<T>(label:string, action:()=>Promise<T>, ms=45000):Promise<T> {
 console.log('ASAMA:',label);
 let timer:ReturnType<typeof setTimeout>|undefined;
 try {
  const result=await Promise.race([action(),new Promise<never>((_,reject)=>{
   timer=setTimeout(()=>reject(new Error(label+' - '+ms/1000+' saniyede tamamlanamadi.')),ms);
  })]);
  console.log('TAMAM:',label);return result;
 }finally{clearTimeout(timer);}
}
const client=new VoipClient({authDir:'./auth'});
let peer:any,call:any,closing=false,connected=false,prepared=false;
const pending:{pcm:Float32Array,rate:number}[]=[];
function transmit(value:any){if(peer?.readyState===WebSocket.OPEN)peer.send(JSON.stringify(value));}
const server=new WebSocketServer({host:'127.0.0.1',port:8769,maxPayload:2*1024*1024,
 verifyClient:({req}:any)=>req.headers['x-kado-token']===link.token});
server.on('error',e=>{console.error('Arama kanali acilamadi:',e.message);shutdown();});
server.on('connection',(socket:any)=>{
 if(peer){socket.close(1008,'Only one Kado');return;}peer=socket;
 socket.on('message',(raw:any)=>{
  try{
   const m=JSON.parse(raw.toString());
   if(m.type==='call_ready'){prepared=true;}
   else if(m.type==='audio_out'){
    const b=Buffer.from(m.data,'base64');if(b.length%2)throw Error('Invalid PCM length');
    const f=new Float32Array(b.length/2);for(let i=0;i<f.length;i++)f[i]=b.readInt16LE(i*2)/32768;
    if(pending.length>=100)throw Error('Audio engine buffer full');
    pending.push({pcm:f,rate:m.rate});
    drain();
   }else if(m.type==='tts_end'){drain();call?.flushPcm();}
   else if(m.type==='clear_audio'){pending.length=0;call?.clearPcm();}
   else if(m.type==='hangup'){if(call)call.end();else shutdown();}
  }catch(e:any){console.error('Ses aktarim hatasi:',e.message);call?.end();}
 });
 socket.on('close',()=>{peer=undefined;if(!closing)shutdown();});
 socket.on('error',()=>shutdown());
});
function drain(){
 while(pending.length && call){
  const item=pending[0];
  if(!call.writePcm(item.pcm,item.rate))return;
  pending.shift();
 }
}
const drainTimer=setInterval(()=>{try{drain();}catch{call?.end();}},20);
async function shutdown(){
 if(closing)return;closing=true;clearInterval(drainTimer);
 transmit({type:'call_ended'});
 try{call?.end();}catch{}
 try{client.disconnect();}catch{}
 try{peer?.close();server.close();}catch{}
 setTimeout(()=>process.exit(0),300).unref();
}
process.on('unhandledRejection',(error:any)=>{console.error('Arama baslatilamadi:',error?.message||'Baglanti hatasi');shutdown();});
process.on('SIGINT',shutdown);process.on('SIGTERM',shutdown);
console.log('Asil Kado baglantisi bekleniyor...');
const deadline=Date.now()+30000;
while(!peer){if(Date.now()>deadline)throw Error('Asil Kado baglanmadi. Birlesik baslaticiyi kontrol edin.');await new Promise(r=>setTimeout(r,100));}
console.log('TAMAM: Masaustundeki asil Kado ile baglanti.');
await stage('1 WhatsApp oturumu ve WASM ses motoru',()=>client.connect(),45000);
console.log('ASAMA: 2 Kado aramaya hazirlaniyor.');
transmit({type:'call_prepare',number});
const prepareDeadline=Date.now()+15000;
while(!prepared){if(Date.now()>prepareDeadline)throw Error('Kado aramaya hazir degil.');await new Promise(r=>setTimeout(r,100));}
console.log('TAMAM: 2 Kado aramaya hazir.');
call=await stage('3 WhatsApp arama istegi',()=>client.call(number,{audioSource:'kado-live',durationMs:180000}),45000);
console.log('ASAMA: 4 Karsinin calmasi veya acmasi bekleniyor.');
call.on('ringing',()=>console.log('Caliyor...'));
call.on('connected',()=>{connected=true;console.log('Arama acildi: asil Kado konusuyor.');transmit({type:'call_started',number});});
call.on('audio',(f:Float32Array)=>{
 if(!connected||!prepared)return;
 const b=Buffer.alloc(f.length*2);for(let i=0;i<f.length;i++)b.writeInt16LE(Math.round(Math.max(-1,Math.min(1,f[i]))*(f[i]<0?32768:32767)),i*2);
 transmit({type:'audio_in',data:b.toString('base64'),rate:16000});
});
call.on('error',(e:any)=>{console.error('Arama hatasi:',e.message);shutdown();});
call.on('ended',(reason:string)=>{console.log('Arama bitti:',reason);shutdown();});
await call.waitForEnd();await shutdown();
