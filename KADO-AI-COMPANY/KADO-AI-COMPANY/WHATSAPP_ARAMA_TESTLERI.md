# WhatsApp mesaj, ses ve arama saha testleri

**Başlangıç durumu: YAPILMADI.** Bu ortamda Windows KADO, mevcut WhatsApp taşıması ve gerçek hesap yoktur. Adaptör birim / sözleşme testi bu saha testlerinden hiçbirini tamamlamaz. Aşağıdaki kontroller mevcut kurulumda kullanıcı tarafından yetkilendirilmiş gerçek kişilerle yapılır.

Ön koşullar: KADO ve mevcut köprü yedekli, oturum korunmuş, taşıyıcı sürümü kaydedilmiş, izinli sahip ve kişi kimlikleri açık, test kişisi görüşmeden haberdar olmalıdır. KADO açılışta "Merhaba, ben KADO, yapay zekâ asistanıyım" demelidir. Görüşmeyi kaydetmek ayrı açık izin gerektirir. Varsayılan kanıt, içeriksiz durum ve zamanlama kayıtlarıdır.

## Metin ve sesli mesaj

| Kimlik | Uygulama | Geçme ölçütü | İlk durum |
| --- | --- | --- | --- |
| M01 | İzinli sahip, komut önekli denetim mesajı gönderir | Gerçek mesaj kimliği bir merkezî görev açar; KADO sonucu geri yollar | YAPILMADI |
| M02 | Aynı mesaj olayı iki defa teslim edilir; süreç yeniden başlatılıp tekrar denenir | Aynı görev kimliği korunur; ikinci cevap gönderilmez | YAPILMADI |
| M03 | İzinli olmayan kişi ve öneksiz mesaj denenir | Görev / kritik işlem başlatılamaz | YAPILMADI |
| M04 | Ağ kopması, 429 ve belirsiz gönderim oluşur | Sınırlı tekrar, hata kaydı; belirsiz teslim uzlaştırılmadan ikinci gönderim yok | YAPILMADI |
| V01 | Gerçek sesli mesaj gönderilir | Çözümleme ve STT metni doğru; görev sonucu doğru kanala bağlı | YAPILMADI |
| V02 | KADO mevcut ses kimliğiyle sesli cevap yollar | Alıcı gerçekten oynatır; sesli mesaj türü ve süre doğrulanır | YAPILMADI |
| V03 | Birincil STT / TTS sağlayıcısı kesilir | Yalnızca yapılandırılmış yedek denenir; yoksa açık hata, süreç çökmez | YAPILMADI |

## Giden arama

1. Mevcut taşımanın `outgoing_call` yeteneği için sürüm ve gerçek kanıt bulun. Desteklenmiyorsa sonuç **DESTEKLENMİYOR** olur; sonraki adımlar başarılı işaretlenmez.
2. Yetkisiz gönderenin "ara" komutunu deneyin; reddedilmelidir. İzinli sahipte rehberde olmayan ve aynı adla iki farklı kişi için arama başlatılmamalı; açıklama istenmelidir.
3. Sahip, izinli bir kişiyi aramayı açıkça onaylar. Gerçek arama kimliği ve `start_requested` zamanı kaydedilir.
4. Karşı cihazın çaldığını ayrı doğrulayın. İsteğin başarılı dönmesi veya "calling" olayı karşı tarafın cevap verdiği anlamına gelmez.
5. Karşı taraf açar; gerçek `connected/answered` olayı ve zamanı kaydedilir. Karşı taraf açmazsa doğru zaman aşımı / meşgul durumu raporlanmalıdır.
6. KADO yapay zekâ tanıtımını gönderir. Taşımanın ses paketini kabul etmesi ve karşı tarafın tanıtımı gerçekten duyması ayrı kanıtlardır.
7. Karşı taraf önceden seçilen kısa bir cümle söyler. KADO tarafında gelen PCM ve doğru STT çıktısı doğrulanır. Böylece ses alma ayrıca kanıtlanır.
8. KADO bağlama uygun yanıt verir. En az üç karşılıklı konuşma turu denenir; yanlış bağlam, sessizlik döngüsü veya tek yönlü ses varsa test geçmez.
9. KADO konuşurken karşı taraf araya girer. Barge-in varsa TTS duruşu ve yeni konuşmanın işlenmesi ölçülür; yoksa özellik desteklenmiyor olarak kaydedilir.
10. Her iki taraftan kapatma denenir. Gerçek kapanma olayı, temizlenen tampon / kaynaklar ve KADO'nun sahip için kısa özeti kontrol edilir.

## Gelen arama

1. Mevcut taşımanın `incoming_call` ve cevaplama giriş noktası gerçek koddan doğrulanır. Desteklenmiyorsa açıkça **DESTEKLENMİYOR** yazılır.
2. İzinli olmayan kişiden gelen arama politika gereği reddedilir veya kullanıcıya bırakılır; otomatik kabul edilmez.
3. İzinli test kişisi arar. Gelen çağrı kimliği, arayan kimliği, politika kararı ve gerçek cevaplanma olayı ayrı kaydedilir.
4. KADO'nun yapay zekâ tanıtımı, karşı tarafın duyduğu ses, KADO'nun aldığı PCM, en az üç karşılıklı tur ve kapatma, giden testteki ölçütlerle ayrı doğrulanır.

## Gecikme ve ses formatı

Taşımanın beklediği format mevcut koddan ölçülür. 16 kHz mono PCM16 kullanılıyorsa Float32 değerleri [-1, 1] aralığına sınırlandırılıp ayrı Int16 tamponuna çevrilmeli; paylaşılan tamponun daha sonra değişmesi sesi bozmamalıdır. Paket süresi, örnek sayısı ve sessizlik zamanlaması kayıt altına alınır.

Her tur için `kullanıcı konuşma bitişi → STT son metni → model ilk sonuç → TTS ilk örnek → taşıma gönderimi → alıcının ilk duyduğu ses` zamanlarını ölçün. Son adımı ölçmeden yalnızca sunucu logundan uçtan uca gecikme iddia etmeyin. En az 10 turda ortanca ve p95 gecikme raporlanır. 2–3 saniye **hedeftir**, doğrulanmış sonuç değildir.

## Kanıt formu

| Test | Windows / köprü sürümü | Görev / arama kimliği | Başlatma | Cevaplanma | Ses TX | Ses RX | Çift yön | Gecikme | Sonuç / hata |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Giden | Doldurulacak | Doldurulacak | Doğrulanmadı | Doğrulanmadı | Doğrulanmadı | Doğrulanmadı | Doğrulanmadı | Ölçülmedi | YAPILMADI |
| Gelen | Doldurulacak | Doldurulacak | Doğrulanmadı | Doğrulanmadı | Doğrulanmadı | Doğrulanmadı | Doğrulanmadı | Ölçülmedi | YAPILMADI |

Sadece arama başlatma geçerse yalnızca o adım başarılıdır. Gerçek çift yönlü konuşma ve sahip raporu doğrulanmadan "WhatsApp araması çalışıyor" sonucu yazılmaz.
