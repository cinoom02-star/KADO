"""


KADO — Gemini Live araç (tool) tanımları


Masaüstü (main.py) ve web sunucusu (kado_web/server.py) ortak kullanır.


"""





TOOL_DECLARATIONS = [
    # KADO_CLAUDE_12_BAGLANTI
    {'name': 'computer_knowledge', 'description': 'KADO bilgisayardaki dosya, uygulama, onay bekleyen islemler, otonom cekirdek ve sistem durumu hakkinda soruldugunda kullan. Dosya arama ve durum icin bu araci sec.', 'parameters': {'type': 'OBJECT', 'properties': {'query': {'type': 'STRING', 'description': 'Kullanicinin tam sorusu'}}, 'required': ['query']}},
    {'name': 'kado_company_overview', 'description': 'KADO ajanlarinin mevcut durumunu, bekleyen ve tamamlanan gorevleri acikla.', 'parameters': {'type': 'OBJECT', 'properties': {}, 'required': []}},
    {'name': 'kado_influencer_start', 'description': 'Tutarlı ve açıkça yapay olarak tanitilan sanal influencer kimligi olustur.', 'parameters': {'type': 'OBJECT', 'properties': {'name': {'type': 'STRING', 'description': 'Kurgusal sanal karakter adi'}}, 'required': ['name']}},
    {'name': 'kado_influencer_calendar', 'description': 'Sanal influencer icin 14 gunluk icerik takvimi olustur, otomatik yayinlama yok.', 'parameters': {'type': 'OBJECT', 'properties': {}, 'required': []}},
    {'name': 'kado_influencer_content', 'description': 'Yapay influencer icin video senaryosu ve paylasim taslagi uretme gorevi kaydet.', 'parameters': {'type': 'OBJECT', 'properties': {'project': {'type': 'STRING', 'description': 'Kayitli proje adi'}, 'topic': {'type': 'STRING', 'description': 'Uretilecek icerigin konusu'}}, 'required': ['project', 'topic']}},
    {'name': 'kado_company_report', 'description': 'KADO gorev sirasi, uretim ve onay durumunu sesli ozetle.', 'parameters': {'type': 'OBJECT', 'properties': {}, 'required': []}},

    {'name': 'kado_assign_task', 'description': 'Kullanici bir projeye arastirma, kod veya sosyal medya gorevi verirse mevcut ajan kuyruguna kaydet. Tamamlandi deme. Proje adini istek cumlesinde acikca belirt.', 'parameters': {'type': 'OBJECT', 'properties': {'request': {'type': 'STRING', 'description': 'Proje adi ve tam gorev cumlesi'}}, 'required': ['request']}},
    {'name': 'kado_project_add', 'description': 'Yeni proje kaydet; ad ve ayrintili hedef gereklidir.', 'parameters': {'type': 'OBJECT', 'properties': {'name': {'type': 'STRING', 'description': 'name'}, 'goal': {'type': 'STRING', 'description': 'goal'}}, 'required': ['name', 'goal']}},
    {'name': 'kado_project_list', 'description': 'Kayitli projeleri listele.', 'parameters': {'type': 'OBJECT', 'properties': {}, 'required': []}},
    {'name': 'kado_pending_packages', 'description': 'Onay bekleyen paketleri listele.', 'parameters': {'type': 'OBJECT', 'properties': {}, 'required': []}},
    {'name': 'kado_read_package', 'description': 'Paketi sesli ozetle; hedef son veya paket kimligi olabilir.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},
    {'name': 'kado_approval_request', 'description': 'Onay icin kullanicidan ayrica evet iste; sadece taslak, yayin yok.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},
    {'name': 'kado_rejection_request', 'description': 'Ret icin sebep al, ayrica evet iste; sadece taslak.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}, 'reason': {'type': 'STRING', 'description': 'reason'}}, 'required': ['target', 'reason']}},
    {'name': 'kado_approval_confirm', 'description': 'Yalnizca kullanici onceki onay sorusuna acikca evet dediginde kullan.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},
    {'name': 'kado_rejection_confirm', 'description': 'Yalnizca kullanici onceki ret sorusuna acikca evet dediginde kullan.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},
    {'name': 'kado_undo_decision', 'description': 'Son paket kararini geri al; yayin geri alinamaz.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},


    {'name': 'kado_project_add', 'description': 'Yeni proje kaydet; ad ve ayrintili hedef gereklidir.', 'parameters': {'type': 'OBJECT', 'properties': {'name': {'type': 'STRING', 'description': 'name'}, 'goal': {'type': 'STRING', 'description': 'goal'}}, 'required': ['name', 'goal']}},

    {'name': 'kado_project_list', 'description': 'Kayitli projeleri listele.', 'parameters': {'type': 'OBJECT', 'properties': {}, 'required': []}},

    {'name': 'kado_pending_packages', 'description': 'Onay bekleyen paketleri listele.', 'parameters': {'type': 'OBJECT', 'properties': {}, 'required': []}},

    {'name': 'kado_read_package', 'description': 'Paketi sesli ozetle; hedef son veya paket kimligi olabilir.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},

    {'name': 'kado_approval_request', 'description': 'Onay icin kullanicidan ayrica evet iste; sadece taslak, yayin yok.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},

    {'name': 'kado_rejection_request', 'description': 'Ret icin sebep al, ayrica evet iste; sadece taslak.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}, 'reason': {'type': 'STRING', 'description': 'reason'}}, 'required': ['target', 'reason']}},

    {'name': 'kado_approval_confirm', 'description': 'Yalnizca kullanici onceki onay sorusuna acikca evet dediginde kullan.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},

    {'name': 'kado_rejection_confirm', 'description': 'Yalnizca kullanici onceki ret sorusuna acikca evet dediginde kullan.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},

    {'name': 'kado_undo_decision', 'description': 'Son paket kararini geri al; yayin geri alinamaz.', 'parameters': {'type': 'OBJECT', 'properties': {'target': {'type': 'STRING', 'description': 'target'}}, 'required': ['target']}},







    {


        "name": "create_agent_task",


        "description": (


            "Kullanici KADO ajan ekibine yeni bir gorev "


            "vermek istediginde kullan. Gorev olusturur "


            "ama ajanlari baslatmaz. Baslatmak icin "


            "kullanicidan ayrica acik onay iste."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "title": {


                    "type": "STRING",


                    "description": "Gorevin kisa basligi"


                },


                "details": {


                    "type": "STRING",


                    "description": "Arastirilacak konu ve istenen sonuc"


                }


            },


            "required": ["title", "details"]


        }


    },





    {


        "name": "start_agent_task",


        "description": (


            "Kullanici acikca mevcut bir gorev numarasi icin "


            "ajan ekibini baslatmani istediginde kullan. "


            "Ornek: '2 numarali gorev icin ekibi calistir'. "


            "Durum sorgusunda veya rapor isteginde kullanma. "


            "Bu arac yalnizca baslatma istegi gonderir; "


            "toplantinin tamamlandigini iddia etme."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "task_id": {


                    "type": "INTEGER",


                    "description": "Calistirilacak mevcut gorevin numarasi"


                }


            },


            "required": ["task_id"]


        }


    },








    {


        "name": "get_agent_status",


        "description": (


            "Kullanici ajan ekibinin durumunu, hangi ajanin "


            "calistigini veya gorevin ilerlemesini sordugunda "


            "son kaydedilen durumu oku. Anlik oldugunu iddia etme."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {}


        }


    },





    {


        "name": "get_agent_report",


        "description": (


            "KADO AI ajan ekibinin son tamamlanan toplantisini "


            "ve gercek ajan raporlarini okur. Kullanici ekibin "


            "ne yaptigini, son toplantiyi veya ajan kararlarini "


            "sordugunda kullan. Raporu kisa ve dogal Turkceyle anlat."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {}


        }


    },





    {


        "name": "start_content_task",


        "description": (


            "Kullanici bir proje icin gonderi, gorsel kart ve video "


            "hazirlanmasini istediginde kullan. Ornek: 'Han Toys icin "


            "icerik hazirla'. Sadece kayitli projeler calisir. "


            "Hicbir sey yayinlanmaz, sonuc onay bekler. Bittigini "


            "iddia etme; baslatma istegi gonderilir."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "project": {


                    "type": "STRING",


                    "description": "Proje adi (ornek: Han Toys, KADO)"


                },


                "again": {


                    "type": "BOOLEAN",


                    "description": "Bugun zaten uretildiyse yeniden uret"


                }


            },


            "required": ["project"]


        }


    },





    {


        "name": "get_content_status",


        "description": (


            "Kullanici icerik hattinin durumunu, onay bekleyen "


            "paketleri veya bugun ne uretildigini sordugunda kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {}


        }


    },





    {


        "name": "prepare_publish_package",


        "description": (


            "Kullanici onayladigi icerik paketlerinin telefonla elle "


            "paylasilmak uzere klasor ve zip olarak hazirlanmasini "


            "istediginde kullan. Ornek: 'onayli paketi yayina hazirla'. "


            "Sadece ONAYLI paketler hazirlanir. Hicbir sey yayinlanmaz."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {}


        }


    },





    {


        "name": "open_app",


        "description": "Windows'ta herhangi bir uygulamayı açar. Spotify, Safari, Terminal, Finder, VS Code vb.",


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "app_name": {


                    "type": "STRING",


                    "description": "Uygulama adı (örn. 'Spotify', 'Safari', 'Terminal')"


                }


            },


            "required": ["app_name"]


        }


    },


    {


        "name": "sys_info",


        "description": "Sistem bilgisi alır: pil durumu, CPU, RAM, disk, saat, tarih, ağ bağlantısı.",


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "query": {


                    "type": "STRING",


                    "description": "battery | cpu | ram | disk | time | date | network | all"


                }


            },


            "required": ["query"]


        }


    },


    {


        "name": "get_weather",


        "description": (


            "Anlik hava durumunu ozetler. Konum verilmezse kullanicinin "


            "BULUNDUGU sehir otomatik tespit edilir. "


            "Kullanici hava durumunu, sicakligi veya yagmur durumunu sordugunda kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "location": {


                    "type": "STRING",


                    "description": "Sehir veya konum. Bos birakilirsa Istanbul kullanilir."


                }


            }


        }


    },


    {


        "name": "get_calendar_events",


        "description": (


            "Apple Calendar takvimini okur. "


            "Bugun, yarin, siradaki etkinlik veya yaklasan ajandayi ozetler. "


            "Kullanici toplanti, takvim, ajanda, etkinlik veya gunluk programini sordugunda kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "query": {


                    "type": "STRING",


                    "description": (


                        "today | tomorrow | next | agenda | week veya dogal dilde "


                        "'onumuzdeki 30 gun', '2 hafta', 'bu ay', 'gelecek ay'"


                    )


                },


                "limit": {


                    "type": "NUMBER",


                    "description": "Maksimum etkinlik sayisi"


                }


            },


            "required": ["query"]


        }


    },


    {


        "name": "add_calendar_event",


        "description": (


            "Apple Calendar takvimine yeni etkinlik ekler. "


            "Kullanici toplanti, randevu, takvime ekleme veya etkinlik olusturma isterse kullan. "


            "Baslangic tarihini gercek tarih/saat olarak ver; bitis verilmezse varsayilan sure kullanilir."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "title": {


                    "type": "STRING",


                    "description": "Etkinlik basligi. Ornek: 'Disci Randevusu'"


                },


                "start_iso": {


                    "type": "STRING",


                    "description": "Baslangic tarih/saat. ISO veya yyyy-MM-dd HH:mm formatinda."


                },


                "end_iso": {


                    "type": "STRING",


                    "description": "Bitis tarih/saat. Opsiyonel."


                },


                "location": {


                    "type": "STRING",


                    "description": "Etkinlik konumu. Opsiyonel."


                },


                "notes": {


                    "type": "STRING",


                    "description": "Etkinlik notlari. Opsiyonel."


                },


                "calendar_name": {


                    "type": "STRING",


                    "description": "Eklenecek takvim adi. Opsiyonel."


                },


                "all_day": {


                    "type": "BOOLEAN",


                    "description": "true ise tum gun etkinligi olusturur."


                }


            },


            "required": ["title", "start_iso"]


        }


    },


    {


        "name": "delete_calendar_event",


        "description": (


            "Apple Calendar takviminden etkinlik siler. "


            "Kullanici bir toplantiyi, randevuyu veya takvim kaydini silmek istediginde kullan. "


            "Ayni ada birden fazla etkinlik varsa dogru kaydi bulmak icin baslangic tarihini gercek tarih/saat olarak ver."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "title": {


                    "type": "STRING",


                    "description": "Silinecek etkinlik basligi. Ornek: 'Disci Randevusu'"


                },


                "start_iso": {


                    "type": "STRING",


                    "description": "Opsiyonel tarih/saat. Ayni isimli birden fazla etkinligi ayirt etmek icin kullan."


                },


                "calendar_name": {


                    "type": "STRING",


                    "description": "Opsiyonel takvim adi"


                },


                "delete_all_matches": {


                    "type": "BOOLEAN",


                    "description": "true ise eslesen tum etkinlikleri siler"


                }


            },


            "required": ["title"]


        }


    },


    {


        "name": "get_reminders",


        "description": (


            "Apple Animsaticilar listesini okur. "


            "Bugunku, yaklasan, geciken veya tum acik animsaticilari ozetler. "


            "Kullanici hatirlatma, animsatici, reminder veya yapilacaklar listesini sordugunda kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "query": {


                    "type": "STRING",


                    "description": "today | upcoming | overdue | all | next"


                },


                "limit": {


                    "type": "NUMBER",


                    "description": "Maksimum animsatici sayisi"


                },


                "list_name": {


                    "type": "STRING",


                    "description": "Istenirse belirli bir animsatici listesi adi"


                }


            },


            "required": ["query"]


        }


    },


    {


        "name": "add_reminder",


        "description": (


            "Apple Animsaticilar uygulamasina yeni bir animsatici ekler. "


            "Kullanici 'hatirlat', 'animsatici ekle', 'reminder kur' dediginde kullan. "


            "Goreli zaman ifadelerini bugunku tarih baglamina gore due_iso alanina ISO formatinda cevir."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "title": {


                    "type": "STRING",


                    "description": "Animsatici basligi"


                },


                "due_iso": {


                    "type": "STRING",


                    "description": "Opsiyonel tarih/saat. Ornek: 2026-04-13T09:00 veya tum gun icin 2026-04-13"


                },


                "notes": {


                    "type": "STRING",


                    "description": "Opsiyonel not"


                },


                "list_name": {


                    "type": "STRING",


                    "description": "Opsiyonel animsatici listesi"


                },


                "priority": {


                    "type": "STRING",


                    "description": "low | medium | high"


                },


                "all_day": {


                    "type": "BOOLEAN",


                    "description": "Tum gun animsatici ise true"


                }


            },


            "required": ["title"]


        }


    },


    {


        "name": "browser_control",


        "description": "Tarayıcıda URL açar, Google'da arama yapar veya YouTube'da ilk sonucu doğrudan oynatır.",


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "action": {"type": "STRING", "description": "open_url | search | play_youtube"},


                "url":    {"type": "STRING", "description": "Açılacak URL (open_url için)"},


                "query":  {"type": "STRING", "description": "Arama sorgusu (search veya play_youtube için)"}


            },


            "required": ["action"]


        }


    },


    {


        "name": "shell_run",


        "description": "Windows PowerShell komutu çalıştırır. Dosya işlemleri, sistem yönetimi.",


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "command": {


                    "type": "STRING",


                    "description": "Çalıştırılacak PowerShell komutu"


                }


            },


            "required": ["command"]


        }


    },


    {


        "name": "toggle_webcam",


        "description": (


            "Gerçek zamanlı webcam akışını başlatır veya durdurur. "


            "Akış aktifken model sürekli kamera görüntüsü alır — 'bak', 'gör', 'göster', "


            "'kameraya bak', 'önümdekileri anlat', 'ne görüyorsun' gibi komutlarda 'start' kullan. "


            "'kamerayı kapat', 'artık bakma' gibi durumlarda 'stop' kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "action": {


                    "type": "STRING",


                    "description": "start — akışı başlat  |  stop — akışı durdur"


                }


            },


            "required": ["action"]


        }


    },


    {


        "name": "play_media",


        "description": (


            "YouTube, Spotify veya Apple Music/Music uygulamasında şarkı, müzik veya video açar. "


            "Kullanıcı belirli bir platform söylerse onu kullan. "


            "Belirtmezse uygun olanı dene. "


            "Kullanıcı 'çal', 'oynat', 'aç' diyorsa autoplay=true kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "query": {


                    "type": "STRING",


                    "description": "Şarkı, sanatçı, albüm veya video arama ifadesi"


                },


                "provider": {


                    "type": "STRING",


                    "description": "auto | youtube | spotify | apple_music"


                },


                "autoplay": {


                    "type": "BOOLEAN",


                    "description": "true ise mümkünse doğrudan oynatır"


                }


            },


            "required": ["query"]


        }


    },


    {


        "name": "control_media",


        "description": (


            "Halihazirda calan medyayi kontrol eder: durdurur, devam ettirir, "


            "sonraki/onceki parcaya gecer. Spotify, YouTube veya hangi oynatici "


            "caliyorsa ona gider. "


            "Kullanici 'durdur', 'duraklat', 'sustur', 'muzigi kapat', 'devam et', "


            "'sonraki sarki', 'gec', 'onceki' gibi bir sey soyledigINDE bunu kullan. "


            "Yeni bir sarki BASLATMAK icin bu araci degil play_media'yi kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "action": {


                    "type": "STRING",


                    "description": (


                        "pause (durdur/duraklat) | resume (devam et) | stop (tamamen durdur) | "


                        "next (sonraki parca) | previous (onceki parca)"


                    )


                }


            },


            "required": ["action"]


        }


    },


    {


        "name": "get_youtube_channel_report",


        "description": (


            "YouTube kanalinin public istatistiklerini ve son videolarin performansini raporlar. "


            "Kullanici kanal istatistiklerini, abone sayisini, son videolarini, buyume hizini "


            "veya YouTube analizini sordugunda kullan. Bu arac Studio yerine public YouTube Data API verisini kullanir."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "query": {


                    "type": "STRING",


                    "description": (


                        "Dogal dilde analiz istegi. Ornek: "


                        "'YouTube istatistiklerim nasil', 'son videolarimi analiz et', "


                        "'kanal buyumemi ozetle'"


                    )


                },


                "handle": {


                    "type": "STRING",


                    "description": (


                        "Opsiyonel kanal handle'i, kanal linki veya kanal ID'si. "


                        "Bos birakilirsa ayarlardaki youtube_channel_handle kullanilir."


                    )


                },


                "video_limit": {


                    "type": "NUMBER",


                    "description": "Analize dahil edilecek son video sayisi. Varsayilan 6."


                }


            },


            "required": ["query"]


        }


    },


    {


        "name": "sing",


        "description": (


            "Enstrümansız, sesle ŞARKI SÖYLER (ritimli, uzatmalı, ezgili). Kullanıcı 'şarkı söyle', 'bana bir şarkı yap', "


            "'… hakkında şarkı/rap', 'ninni söyle' derse kullan. Sözleri bu araç ORİJİNAL yazar; sen söz yazma/okuma. "


            "Mevcut/telifli şarkıların sözlerini ASLA verme; kullanıcı gerçek bir şarkı isterse onu play_media ile çaldır "


            "ya da 'o tarzda yeni, orijinal bir şarkı' öner. 'lyrics' alanını SADECE kullanıcı kendi yazdığı sözleri "


            "söylediyse ya da telifsiz/anonim halk türküsü içinse doldur. Araç dönünce HİÇBİR ŞEY SÖYLEME."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "request": {"type": "STRING", "description": "Şarkının konusu/isteği (örn. 'yağmurlu bir İstanbul akşamı', 'arkadaşıma doğum günü')"},


                "style": {"type": "STRING", "description": "Tarz/ruh hali (örn. 'duygulu pop', 'sert rap', 'neşeli türkü havası', 'ninni')"},


                "lyrics": {"type": "STRING", "description": "Opsiyonel: kullanıcının kendi yazdığı / telifsiz sözler"}


            },


            "required": ["request"]


        }


    },


    {


        "name": "message_me",


        "description": (


            "Kullanıcının KENDİ telefonuna WhatsApp'tan mesaj yazar (not, hatırlatma, özet, link, 'bana yaz'). "


            "'Telefonuma mesaj at', 'bana WhatsApp'tan yaz', 'bunu telefonuma gönder' denince kullan. "


            "Başkasına mesaj için send_whatsapp_message kullanılır, bu değil."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {"text": {"type": "STRING", "description": "Telefona gidecek mesaj metni (kısa ve net)"}},


            "required": ["text"]


        }


    },


    {


        "name": "quick_research",


        "description": (


            "HIZLI internet araştırması (birkaç saniye): güncel fiyat, haber, bilgi, karşılaştırma, 'şunu araştır', "


            "'… var mı bak', 'indirim var mı' gibi her bilgi sorusu için KULLAN. Ekranda gezmez, kullanıcının "


            "fare/klavyesine dokunmaz. Kaynaklı kısa cevap döner. Tarayıcıda gezmek (computer_task) yerine hep bunu tercih et."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {"query": {"type": "STRING", "description": "Araştırılacak konu/soru, net ve tam"}},


            "required": ["query"]


        }


    },


    {


        "name": "start_job",


        "description": (


            "ARKA PLAN İŞİ başlatır; kullanıcı bilgisayarda başka şey yaparken Kado fare/klavyeye DOKUNMADAN çalışır. "


            "Şunlar için kullan: kod yazma/çalıştırma, uygulama fikrini bilgisayarda yapma (python ortamı kurar), "


            "dosyaları okuyup rapor/özet çıkarma, uzun/derin araştırma, dosya düzenleme/oluşturma. "


            "Araç hemen döner; iş bitince sesli haber verilir. Hedefi net ve tam yaz."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {"goal": {"type": "STRING", "description": "İşin tam tarifi (ne yapılacak, beklenen sonuç)"}},


            "required": ["goal"]


        }


    },


    {


        "name": "index_folder",


        "description": (


            "Bir klasördeki dosyaları (txt, kod, docx, pptx, pdf…) ÖĞRENİR ve yerel olarak indeksler; sonra "


            "search_my_files ile aranabilir. Kullanıcı 'belgelerimi öğren', 'şu klasörü tara' derse kullan. "


            "Şifre/gizli görünen dosyaları atlar. Arka planda çalışır."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {"path": {"type": "STRING", "description": "Klasör yolu, örn: C:\\Users\\Ad\\Documents veya 'Masaüstü'"}},


            "required": ["path"]


        }


    },


    {


        "name": "search_my_files",


        "description": (


            "Kullanıcının daha önce öğretilmiş dosyalarında anında arama yapar ('şu rapor nerede', "


            "'… hakkında yazdığım dosya', 'geçen ay ne yazmıştım'). Dosya yolları + ilgili parçalar döner."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {"query": {"type": "STRING", "description": "Aranacak kelime/konu"}},


            "required": ["query"]


        }


    },


    {


        "name": "computer_task",


        "description": (


            "Bilgisayarı KENDİSİ KULLANIR: ekrana bakar, fareyle tıklar, klavyeyle yazar, sitelere girer, "


            "arama yapar, formları doldurur. Kullanıcı 'şunu bilgisayarda yap', 'şu siteye gir ve ...', "


            "'bana ... bul', 'şuraya tıkla' gibi bir iş istediğinde kullan. Görev ARKA PLANDA yürür, "


            "araç hemen döner; bitince ya da onay gerekince sesli haber verilir. "


            "Basit işler için önce open_app/browser_control'ü tercih et; çok adımlı veya tıklama gerektiren "


            "işler için bunu kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "goal": {


                    "type": "STRING",


                    "description": "Yapılacak işin net, tam tarifi. Örn: 'Trendyol'a gir, siyah spor ayakkabı ara, ilk 3 fiyatı söyle'"


                }


            },


            "required": ["goal"]


        }


    },


    {


        "name": "computer_task_control",


        "description": (


            "Çalışan bilgisayar görevini VE arka plan işlerini yönetir. action: 'stop' (kullanıcı dur/iptal/vazgeç derse), "


            "'status' (ne durumda), 'reply' (KADO görev sırasında 'Onaylıyor musun?' gibi bir soru sorduysa "


            "kullanıcının cevabını ilet; answer alanına kullanıcının sözünü yaz)."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "action": {"type": "STRING", "description": "stop | status | reply"},


                "answer": {"type": "STRING", "description": "reply için kullanıcının cevabı (örn. 'evet yap' / 'hayır')"}


            },


            "required": ["action"]


        }


    },


    {


        "name": "analyze_screen",


        "description": (


            "Aktif pencerenin ekran goruntusunu alip Gemini vision ile analiz eder. "


            "Kullanici ekranda ne oldugunu, bir hatayi, gorunen metni, butonlari veya pencere icerigini sordugunda kullan. "


            "Bu surum yalnizca aktif pencereyi destekler."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "query": {


                    "type": "STRING",


                    "description": "Kullanicinin ekranla ilgili sorusu. Ornek: 'Bu hatayi oku', 'Ekranda ne var?'"


                },


                "target": {


                    "type": "STRING",


                    "description": "Su an sadece active_window desteklenir."


                }


            },


            "required": ["query"]


        }


    },


    {


        "name": "save_memory",


        "description": "Kullanıcı hakkında önemli bilgiyi kalıcı belleğe kaydeder. İsim, tercihler, projeler vb. duyunca sessizce çağır.",


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "category": {


                    "type": "STRING",


                    "description": "identity | preferences | projects | notes"


                },


                "key":   {"type": "STRING", "description": "Kısa anahtar (örn. 'name')"},


                "value": {"type": "STRING", "description": "Değer (İngilizce)"}


            },


            "required": ["category", "key", "value"]


        }


    },


    {


        "name": "delete_memory",


        "description": (


            "Kalici hafizadaki bir kaydi siler. "


            "Kullanici 'bunu hafizandan kaldir', 'unut', 'sil' gibi bir sey derse kullan. "


            "Mumkunse category ve key ile sil; emin degilsen match_text ile ilgili kaydi bulup kaldir."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "category": {


                    "type": "STRING",


                    "description": "Kaydin kategorisi. Ornek: notes | identity | preferences | projects"


                },


                "key": {


                    "type": "STRING",


                    "description": "Silinecek anahtar. Ornek: claude_limit_refresh"


                },


                "match_text": {


                    "type": "STRING",


                    "description": "Kaydi bulmak icin kullanilacak dogal dil parcasi. Ornek: 'claude ai limit yenilenmesi'"


                }


            }


        }


    },


    {


        "name": "send_whatsapp_message",


        "description": (


            "WhatsApp Desktop veya WhatsApp Web üzerinden mesaj taslağı açar veya mesajı gönderir. "


            "Kişi adı veya telefon numarasıyla çalışabilir. "


            "Telefon numarası verilmemişse kişi adını önce kayıtlı WhatsApp kişileri ve içe aktarılan telefon rehberinde ara. "


            "Kullanıcı 'gönder', 'yolla', 'ile', 'hemen gönder' gibi açık bir gönderme niyeti söylüyorsa "


            "ekstra onay istemeden send_now=true kullan. "


            "Yalnızca 'hazırla', 'taslak aç', 'yaz ama gönderme' diyorsa send_now=false kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "recipient_name": {


                    "type": "STRING",


                    "description": "Kişi adı. Örn: 'Anne', 'Ahmet', 'Ece'"


                },


                "phone_number": {


                    "type": "STRING",


                    "description": "Uluslararası telefon numarası. Örn: +905551112233"


                },


                "message": {


                    "type": "STRING",


                    "description": "Gönderilecek mesaj içeriği"


                },


                "app_target": {


                    "type": "STRING",


                    "description": "desktop | web | auto. Varsayılan auto, tercihen desktop."


                },


                "send_now": {


                    "type": "BOOLEAN",


                    "description": "true ise sohbet açıldıktan sonra mesajı otomatik gönderir"


                }


            },


            "required": ["message"]


        }


    },


    {


        "name": "save_whatsapp_contact",


        "description": (


            "Sık kullanılan bir WhatsApp kişisini adı ve telefon numarasıyla kalıcı belleğe kaydeder. "


            "Kullanıcı bir kişiyi 'annem', 'Ahmet', 'iş ortağım' gibi tekrar kullanılacak şekilde tanımladığında kullan."


        ),


        "parameters": {


            "type": "OBJECT",


            "properties": {


                "display_name": {


                    "type": "STRING",


                    "description": "Kaydedilecek kişi adı. Örn: 'Annem', 'Ahmet'"


                },


                "phone_number": {


                    "type": "STRING",


                    "description": "Uluslararası telefon numarası. Örn: +905551112233"


                },


                "aliases": {


                    "type": "STRING",


                    "description": "Virgülle ayrılmış alternatif hitaplar. Örn: 'anne, annem, mom'"


                }


            },


            "required": ["display_name", "phone_number"]


        }


    }


]


