# Kado ilk konusma gecikmesi: arastirma ve duzeltme

Tarih: 6 Kasim 2026. Hedef: arama acilinca, ilk sozu kim soylerse soylesin, aranan kisi
konusmasini bitirdikten sonra Kado'nun ilk anlamli cevabinin 2-3 saniyede duyulmasi.

## Bizim yapi

WhatsApp Opus/RTP -> baileys-caller WASM -> Float32 PCM -> Node -> yerel WebSocket ->
Windows'ta asil Kado Gemini Live oturumu -> cevap transkripsiyonu -> cumle biriktirme ->
ElevenLabs HTTP PCM akisi -> yerel WebSocket -> 24kHz/16kHz donusumu -> WhatsApp.

Arastirmada calisan V3 hostu, ana Kado _build_config / _receive_audio / _el_flush,
Node arama koprusu, orijinal SDK'nin kaynak ve dist dosyalari, ozel PCM feeder ve
onceki paketlerin kurulum kodlari okundu. API anahtarlari veya auth klasorleri okunmadi.
GitHub'dan orijinal ve optimize edilmis WASM kaynaklari da yeniden getirildi.

## Dogrulanan kod bulgulari

1. Orijinal SDK, sifira yakin gelen PCM parcalarini hasNonZero filtresiyle atiyor.
   Bu sesin zaman eksenindeki sessizligi yok eder. Server-side VAD kullanan Gemini'ye
   konusma bittikten sonraki sessizlik ulasmazsa sirayi bitirme gecikebilir.
2. Orijinal SDK 320 ornek okuyup sabit 16ms saat kullaniyor. README'nin bildirdigi
   16kHz mono icin 320 ornegin suresi 20ms'dir. Ayrica orijinal motor gelen sesin
   initPlaybackDriverJS format bilgisini ancak opsiyonel callback verilirse kaydediyor;
   bizim temel index callback vermiyor. Duzeltme bu format bilgisini her iki callback
   yolunda okuyup saati ve tamponu ona gore ayarliyor, Kado'ya 16kHz mono veriyor.
3. Orijinal gelen PCM, WASM heap'inin gorunumudur; kopya degildir. Sonraki native
   okuma ayni bellegi degistirebilir. Duzeltme bagimsiz PCM olusturur; okunacak bolgeyi
   sifirlayarak yeni veri gelmeyen turda eski konusmanin tekrarini da onler.
4. V3 kurucusu hostu ve Node ses-kesme cagrisini degistiriyor, ama alttaki motor
   sessizlik duzeltmesini zorunlu kilmiyor. Onceki paketlerden hangilerinin gercekten
   kuruldugu uzaktan belli degil. Bu nedenle yeni kurucu once aktif motoru denetler.
   Bilgisayarinda bu filtre zaten kaldirildiysa bulgu 1 tek basina neden aciklamaz.
5. _el_flush tamamlanan cumleyi veya belli bir ilk parca kosulunu bekliyor. Bu ek
   gecikme olusturabilir, fakat 10-30 saniyelik ilk tur gecikmesini tek basina bu
   koda baglayamayiz. Bu paket V4'teki erken ifade degisikligini uygulamaz.

## Kayitlari nasil yorumlamaliyiz?

'Arama olcumu: ilk karsi taraf metni' kisinin konusmayi bitirdigi an degildir.
Google'in aciklamasina gore transkripsiyonlar model turunden bagimsiz gelebilir.
Bu nedenle iki metin zamanini cikarmak kesin 'dusunme suresi' vermez. Ilk yanit
metninden ilk yerel ses parcasina kadar olan fark da cumle tamponu + TTS + yerel
aktarim karisimidir; aranan telefonda sesi duyma suresinin tamami degildir.
V3'te ilk ses bazen 1.8s, bazen 15s; V4'te tek denemede 28.7s goruldu. Bu tek
karsilastirma V4'un tum farki yarattigini kanitlamaz. Aramalar farkli girdilerle yapildi.

## Diger yollardan ne ogrendik?

- LuxyTeam optimize SDK'nin guncel kaynagi sessizligi atlamiyor, PCM'yi kopyaliyor,
  playback formatindan zamanlama hesapliyor. Bu, tasima duzeltmesini destekliyor;
  tum projeyi farkli bir fork'a tasimak yerine mevcut SDK icin sinirli adapter yazildi.
- Google Live belgeleri 20-40ms kucuk PCM parcalari, kisa giris tamponu, kesilmede
  eski sesin temizlenmesi ve dogru VAD/sessizlik ayarlarini oneriyor.
- Vapi belgeleri endpointing, model, TTS ve son beklemeyi ayri asamalar olarak ele
  aliyor. 2.3s ornekleri bizim sistem icin olculmus bir sonuc veya garanti degildir.
- ElevenLabs, gercek zamanli LLM metni icin WebSocket oneriyor; buffer esigi/flush
  ayarlarini acikliyor. Bizde HTTP zaten streaming; WebSocket'a gecmek buyuk ek
  degisikliktir ve Gemini ilk tur gecikmesini otomatik cozmez. Bu pakette uygulanmadi.
- Reddit ve Google SDK issue'larinda benzer 3-6s veya daha uzun ilk yanit/kesilme
  sikayetleri var. Bunlar kullanici bildirimidir; ayni hata bizde var demek degildir.
- Pipecat'in WebRTC tavsiyesi internet uzerindeki istemci-sunucu yolu icindir.
  Bizde WhatsApp zaten RTP/WebRTC kullaniyor; Windows-WSL yerel WebSocket'i
  korlemesine degistirmek ilk tercih degildir.

## Bu paketin kapsam ve siniri

Yalnizca mevcut aramanin tasima motorunu ve eski enerji-kesme cagrisini duzeltir.
Ilk selami onceden calmaz, baska bir ajan kurmaz, yapay 'hmm' sesiyle sureyi gizlemez.
Gemini modelini/anahtarini, ElevenLabs sesini, masaustu araclarini ve mesajlasmayi
 degistirmez. Motor orijinali korunur; yeni adaptor dogrulanip tarihli yedekle kurulur.

Yerel testler: 16/48kHz mono-stereo ile 8kHz PCM surekliligi; sessiz kareler; heap
kopyasi; eski kare sifirlama; 20ms saat; tekrarlanan kurulum; hesap/auth korunmasi;
geri alma; cikis PCM testleri; gercek yerel WebSocket iki yonlu PCM testi; 21 mevcut
Python testi. Bunlar gercek WhatsApp aramasi veya bulut yanit suresi testi degildir.

Basari olcutu: en az 5 aramada ilk 'alo'nun bitisinden Kado'nun anlamli cevabinin
telefon hoparlorunden duyulmasina kadar sure; sonraki 3 tur da olculmeli. 2-3s hedef,
5s ustu beklemeler ve ust yuzdelik de raporlanmali. Tasima duzelmisken uzun kuyruk
suruyorsa bir sonraki neden Gemini VAD/ilk tur ve provider gecikmesi olarak ayristirilir;
bunun canli kaydi olmadan 'kokten kesin cozuldu' denemez.

## Birincil kaynaklar

- https://github.com/SheIITear/baileys-caller/blob/main/src/wasm-engine.mts
- https://github.com/SheIITear/baileys-caller
- https://github.com/LuxyTeam/baileys-caller-optimized/blob/main/src/wasm-engine.mts
- https://ai.google.dev/gemini-api/docs/live-api/best-practices
- https://ai.google.dev/gemini-api/docs/live-api/capabilities
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/live-api
- https://elevenlabs.io/docs/eleven-api/guides/how-to/best-practices/latency-optimization
- https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts
- https://docs.vapi.ai/customization/voice-pipeline-configuration
- https://docs.pipecat.ai/client/concepts/choosing-a-transport

## Topluluk bildirimleri (nedenin kaniti degil)

- https://github.com/googleapis/python-genai/issues/2333
- https://github.com/googleapis/python-genai/issues/1859
- https://www.reddit.com/r/AI_Agents/comments/1p7bxl9/gemini_live_latency_issue_3000ms_in_voice_chat/
