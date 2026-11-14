#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║   K.A.D.O — TELEFONDAN BAĞLAN (bu Mac sunucu olur)    ║
# ║   Çift tıkla → telefon için adres + QR kod çıkar.        ║
# ╚══════════════════════════════════════════════════════════╝
#
# Bilgisayarını telefondan kontrol etmeni sağlar. Bu Mac açık ve bu pencere
# açık kaldığı sürece, telefondan (her yerden) bağlanabilirsin.

DIR="$(cd "$(dirname "$0")" && pwd)"

# kado_web klasörünü bul (paylaşım düzeni: sistem/kado_web, dev: kado_web)
for w in "$DIR/sistem/kado_web" "$DIR/kado_web"; do
    if [ -f "$w/WEB_BASLAT.command" ]; then
        exec bash "$w/WEB_BASLAT.command"
    fi
done

echo ""
echo "❌ Telefon sunucusu dosyaları bulunamadı."
echo "   Önce BASLAT.command'a çift tıklayıp kurulumu tamamla."
echo ""
read -p "Kapatmak için Enter'a bas..."
exit 1
