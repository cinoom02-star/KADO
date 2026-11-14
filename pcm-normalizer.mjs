// Independent, stateful PCM downmix/resampling. SDK clients always receive 16 kHz mono.
export class PCMNormalizer {
 constructor(){this.reset();}
 reset(){this.tail=[];this.phase=0;this.rate=0;this.channels=0;}
 process(samples,rate,channels){
  if(!Number.isInteger(rate)||rate<8000||rate>96000||![1,2].includes(channels))throw Error('Unsupported playback PCM format');
  if(samples.length%channels)throw Error('Incomplete PCM channel frame');
  if(rate!==this.rate||channels!==this.channels){this.reset();this.rate=rate;this.channels=channels;}
  const mono=new Float32Array(samples.length/channels);
  for(let i=0;i<mono.length;i++){let sum=0;for(let c=0;c<channels;c++)sum+=samples[i*channels+c];mono[i]=sum/channels;}
  if(rate===16000)return mono; // also copies the WASM heap; silence is deliberately retained.
  const input=this.tail.concat(Array.from(mono)),out=[],ratio=rate/16000;
  while(this.phase+1<input.length){const k=Math.floor(this.phase),f=this.phase-k;out.push(input[k]*(1-f)+input[k+1]*f);this.phase+=ratio;}
  const used=Math.min(Math.floor(this.phase),input.length);this.tail=input.slice(used);this.phase-=used;
  return Float32Array.from(out);
 }
}
