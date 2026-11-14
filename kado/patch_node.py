from pathlib import Path
import sys,datetime
p=Path(sys.argv[1])/'kado-native-call.mts'
s=p.read_text(encoding='utf-8')
if '// KADO_CALL_START_LATENCY_V2' in s:
    print('Arama ses baslangic duzeltmesi zaten kurulu.');raise SystemExit(0)
anchor="call.on('audio',(f:Float32Array)=>{"
if anchor not in s or 'if(!connected||!prepared)return;' not in s:
    raise SystemExit('Arama kodu surumu uyusmuyor. Dosya degistirilmedi.')
helper='''// KADO_CALL_START_LATENCY_V2
let speechMs=0,quietMs=0,voiceLatched=false,firstRemoteAudio=false;
const speechThreshold=0.035;
function checkPeerSpeech(samples:Float32Array){
 if(!samples.length)return;
 if(!firstRemoteAudio){firstRemoteAudio=true;console.log('ILK KARSIDAN PCM ALINDI.');}
 let energy=0;for(const sample of samples)energy+=sample*sample;
 const rms=Math.sqrt(energy/samples.length);
 const ms=samples.length/16000*1000;
 if(rms>=speechThreshold){
  quietMs=0;speechMs+=ms;
  if(speechMs>=120&&!voiceLatched){
   voiceLatched=true;transmit({type:'peer_speaking'});
   console.log('KARSI TARAF KONUSUYOR: bekleyen ses kesiliyor.');
  }
 }else{
  quietMs+=ms;
  if(quietMs>=180){speechMs=0;voiceLatched=false;}
 }
}
'''
s=s.replace(anchor,helper+anchor,1)
s=s.replace('const prepareDeadline=Date.now()+15000;','const prepareDeadline=Date.now()+30000;')
s=s.replace('if(!connected||!prepared)return;','if(!connected||!prepared)return;\n checkPeerSpeech(f);',1)
backup=p.with_name(p.name+'.acilis-oncesi-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
backup.write_text(p.read_text(encoding='utf-8'),encoding='utf-8')
p.write_text(s,encoding='utf-8')
print('Arama basinda gelen ses ve soz kesme algilamasi eklendi. Arayan hesap ayari korundu.')
