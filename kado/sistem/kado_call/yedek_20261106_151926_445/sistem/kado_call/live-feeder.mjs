// Direct PCM transport for the existing baileys-caller SDK (no FIFO / FFmpeg).
export class LiveAudioFeeder {
    constructor(rate, channels, frames, onChunk) {
        this.rate=rate; this.channels=channels; this.frames=frames; this.onChunk=onChunk;
        this.queue=[]; this.partial=[]; this.tail=[]; this.phase=0; this.running=false;
    }
    start() {
        if(this.running)return;
        this.running=true; this.next=performance.now();
        const tick=()=>{
            if(!this.running)return;
            this.onChunk(this.queue.shift() || new Float32Array(this.frames*this.channels));
            // Do not burst old silence frames after the event loop has been delayed.
            this.next=Math.max(this.next+this.frames/this.rate*1000,performance.now());
            this.timer=setTimeout(tick,Math.max(1,this.next-performance.now()));
        }; this.timer=setTimeout(tick, 0);
    }
    writePcm(pcm,rate) {
        if(!Number.isFinite(rate)||rate<8000||rate>96000)throw Error('Unsupported PCM rate');
        if(this.inputRate && this.inputRate!==rate)this.clear();
        this.inputRate=rate;
        const input=this.tail.concat(Array.from(pcm));
        const ratio=rate/this.rate;
        while(this.phase+1<input.length) {
            const index=Math.floor(this.phase), fraction=this.phase-index;
            const value=input[index]*(1-fraction)+input[index+1]*fraction;
            for(let c=0;c<this.channels;c++)this.partial.push(Math.max(-1,Math.min(1,value)));
            if(this.partial.length===this.frames*this.channels) {
                if(this.queue.length>=Math.ceil(20*this.rate/this.frames))throw Error('PCM queue exceeds 20 seconds');
                this.queue.push(Float32Array.from(this.partial));this.partial=[];
            }
            this.phase+=ratio;
        }
        const used=Math.min(Math.floor(this.phase),input.length);
        this.tail=input.slice(used);this.phase-=used;
    }
    flush() {
        if(this.tail.length)this.writePcm(Float32Array.from([this.tail.at(-1),this.tail.at(-1)]),this.inputRate);
        if(this.partial.length){
            const frame=new Float32Array(this.frames*this.channels);frame.set(this.partial);
            this.queue.push(frame);this.partial=[];
        }
        this.tail=[];this.phase=0;
    }
    clear() {this.queue=[];this.partial=[];this.tail=[];this.phase=0;}
    stop(){this.running=false;clearTimeout(this.timer);this.clear();}
}
