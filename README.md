# Instagram Auto Reply

Luminova Instagram hesabına gelen doğrudan mesajları yanıtlayan bir otomasyon. Python mesajı alır, konuşmayı hatırlar ve yanıtı üretir. n8n bu adımları sıraya koyar.

Canlı Instagram bağlantısı olmadan da çalışır. Erişim anahtarı boşken yanıt üretilir ve yerel bir kutuya yazılır. Böylece akış, Meta hesabı bağlanmadan denenebilir.

## Ne yapar

Müşteri bir mesaj gönderir. Sistem kısa Türkçe bir yanıt yazar, fiyat söylemez ve görüşme için bir temsilciye yönlendirir. Çalışma saatleri her gün 08:00–18:00 olarak kabul edilir. Hizmetler mobil uygulama tasarımı, web sitesi tasarımı ve n8n otomasyonudur. Bu kurallar `prompts/system.txt` içindedir.

## Akış

1. Instagram, gelen mesajı Python’daki `/webhook` adresine yollar.
2. Python mesajı temizler. Kendi mesajlarını, silinenleri ve tekrar gelenleri eler.
3. n8n adresi tanımlıysa temiz mesaj oraya gider. Değilse Python yanıtı kendisi üretir.
4. n8n, `POST /v1/reply` ile yanıt ister.
5. n8n, `POST /v1/send` ile yanıtı gönderir.
6. Instagram anahtarı yoksa yanıt yerel kutuya yazılır. Anahtar varsa Instagram’a gider.

n8n akışı `workflows/instagram_auto_reply.json` dosyasındadır.

## Çalıştırma

Python 3.11 veya üzeri gerekir.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m app
```

Servis `http://127.0.0.1:8000` adresinde açılır. `.env` içine OpenAI anahtarını yaz. Anahtar `sk-` ile başlar. Model varsayılan olarak `gpt-4o-mini` kullanılır.

Sağlık kontrolü:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Testler:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## n8n

n8n kuruluysa akışı içe aktar:

```powershell
n8n import:workflow --input=workflows/instagram_auto_reply.json
n8n publish:workflow --id=instagramAutoReply
n8n start
```

Üretim webhook adresi `http://127.0.0.1:5678/webhook/instagram-inbound` olur. Python’un mesajı n8n’e iletmesi için `.env` içinde `N8N_WEBHOOK_URL` bu adres olmalıdır. Deneme için mesajı doğrudan bu webhook’a da gönderebilirsin.

n8n’in kendi Assistant kurulumu bu projeye ait değildir. Oraya anahtar veya sandbox girmen gerekmez.

## Uçlar

| Yol | İş |
| --- | --- |
| `GET /health` | Model, n8n ve Instagram ayarının dolu olup olmadığını söyler |
| `GET /webhook` | Meta doğrulama isteğine `hub.challenge` döner |
| `POST /webhook` | Gelen Instagram olayını işler |
| `POST /v1/reply` | Metne göre yanıt üretir |
| `POST /v1/send` | Yanıtı Instagram’a veya yerel kutuya yazar |
| `GET /v1/outbox` | Son yerel yanıtları listeler |
| `GET /v1/conversations/{sender_id}` | Bir kişinin son mesajlarını döner |

## Ayarlar

`.env.example` dosyasını kopyala. Gerçek değerleri `.env` içine yaz. Bu dosya git’e girmez.

Instagram’a gerçekten göndermek için `IG_ACCESS_TOKEN` ve `IG_USER_ID` gerekir. İkisi boşken `POST /v1/send` yine 200 döner, `mode` alanı `local` olur ve metin `GET /v1/outbox` ile okunur.

Webhook imzası için `META_APP_SECRET` doldurulursa gelen istekler doğrulanır. Boşsa imza kontrolü atlanır. Bu yalnızca yerel deneme içindir.
