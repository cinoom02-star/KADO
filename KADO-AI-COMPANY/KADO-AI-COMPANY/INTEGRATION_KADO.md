# KADO entegrasyonu

Adım adım Türkçe kurulum ve SDK örneği: [KADO_ENTEGRASYON_REHBERI.md](KADO_ENTEGRASYON_REHBERI.md).

Kısa sözleşme: mevcut KADO komutu doğrular ve CEO kararını verir; bu servis gerçek merkezî görev kimliği döndürür. KADO, görev olaylarını izler ve son raporu kendi ses / WhatsApp kanalıyla kullanıcıya iletir. Bu servis KADO'nun hafızasını veya mevcut konuşma motorunu değiştirmez.

REST, Python SDK, CLI ve WebSocket olay akışı uygulanır. Yerel olay otobüsü aynı Python sürecindeki tüketiciler içindir; ayrı süreçler arasında kalıcı mesaj kuyruğu yerine geçmez. MCP araç sunucusu henüz uygulanmamıştır. CEO'nun doğal dil planlayıcısı için mevcut KADO giriş noktası kaynak incelendikten sonra bağlanır.
