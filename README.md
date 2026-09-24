# Instagram Auto Reply

Instagram doğrudan mesajlarını alan, yanıt üreten ve geri gönderen bir otomasyon.

Gelen mesaj bir webhook ile gelir. Metin bir dil modeline gider. Üretilen yanıt ya Instagram’a yazılır ya da, hesap bağlı değilse, yerel bir kutuda saklanır. Aynı mesaj iki kez işlenmez. Konuşma geçmişi saklanır, böylece yanıt bir önceki mesajlara bakabilir.

Yanıtın ne söyleyeceği `prompts/system.txt` dosyasındadır. Bu dosya değiştirilerek başka bir hesap veya başka bir konu için kullanılabilir.

## Nasıl çalışır

İki parça vardır. Python mesajı ve modeli yönetir. n8n adımları birbirine bağlar.

```
Instagram
   │
   ▼
Python  GET/POST /webhook
   │
   ▼
n8n     gelen mesajı alır
   │
   ├─► POST /v1/reply   yanıt üret
   │
   └─► POST /v1/send    yanıtı gönder
              │
              ├─ Instagram API   hesap bağlıysa
              └─ yerel kutu      hesap bağlı değilse
```

Python, webhook’a gelen olayı ayıklar. Kendi gönderdiği mesajları, silinen mesajları, metinsiz olayları ve daha önce gördüğü mesaj kimliklerini atlar. n8n adresi tanımlıysa temiz mesajı n8n’e bırakır. Tanımlı değilse yanıtı kendisi üretir ve göndermeyi dener.

n8n akışı `workflows/instagram_auto_reply.json` içindedir. Üç düğümü vardır: webhook, yanıt isteği, gönderim isteği.

## Teknolojiler

| Parça | Ne için |
| --- | --- |
| Python | Uygulama |
| FastAPI | HTTP API |
| Uvicorn | Sunucu |
| OpenAI API | Yanıt üretimi (`gpt-4o-mini`) |
| SQLite | Konuşma geçmişi, işlenen mesajlar, yerel kutu |
| n8n | Akışın sırası |
| Instagram API | Mesaj alma ve gönderme (`graph.instagram.com`) |
| pytest | Webhook ve gönderim testleri |

Ayarlar `.env` dosyasından okunur. Örnek alanlar `.env.example` içindedir. `.env` depoya girmez.

## Çalıştırma

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m app
```

API `http://127.0.0.1:8000` adresinde dinler. `OPENAI_API_KEY` doluysa model yanıt üretir. Boşsa sabit bir test cümlesi döner.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

n8n akışını yüklemek için:

```powershell
n8n import:workflow --input=workflows/instagram_auto_reply.json
n8n publish:workflow --id=instagramAutoReply
n8n start
```

Webhook adresi `http://127.0.0.1:5678/webhook/instagram-inbound` olur. Python’un olayı bu adrese iletmesi için `N8N_WEBHOOK_URL` aynı değeri almalıdır.

## HTTP uçları

| Yol | İş |
| --- | --- |
| `GET /health` | Model, n8n ve Instagram ayarlarının dolu olup olmadığı |
| `GET /webhook` | Meta doğrulaması (`hub.challenge`) |
| `POST /webhook` | Gelen mesaj olayı |
| `POST /v1/reply` | Metinden yanıt |
| `POST /v1/send` | Yanıtı Instagram’a veya yerel kutuya yazar |
| `GET /v1/outbox` | Yerel kutudaki son yanıtlar |
| `GET /v1/conversations/{sender_id}` | Bir gönderenin son mesajları |

`IG_ACCESS_TOKEN` ve `IG_USER_ID` boşken gönderim Instagram’a gitmez. `POST /v1/send` bu durumda `200` döner ve `mode` alanı `local` olur. `META_APP_SECRET` doluysa gelen webhook imzası kontrol edilir.
