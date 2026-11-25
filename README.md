# 🗂️ بوت تخزين الذكريات — Memory Bot

بوت تليجرام متطور لحفظ كل ما يهمّك: نصوص، صور، فيديوهات، ملفات،
بصمات صوتية، أصوات، صور متحركة وملصقات — مع وسوم `#` وبحث واسترجاع وحذف.

Advanced Telegram bot to store everything that matters: text, photos,
videos, files, voice notes, audio, animations and stickers — with `#tags`,
search, retrieval and deletion.

---

## ✨ المميزات | Features

- **حفظ تلقائي:** أرسل أي شيء وسيُحفظ كذكرى مع نوعها وتاريخها.
  Auto-save any message as a memory with its type and date.
- **وسوم `#tag`:** تُستخرج تلقائياً من النص أو التعليق (عربي وإنجليزي).
  Tags are extracted automatically from text/caption (Arabic + Latin).
- **بحث:** `/search كلمة` يبحث في النصوص والوسوم.
  Search text, captions and tags.
- **قوائم وأزرار:** `/list` مع تصفح بالصفحات وأزرار «عرض» و«حذف» لكل ذكرى.
  Paginated lists with per-item View / Delete inline buttons.
- **إحصائيات:** `/stats` بعدد الذكريات حسب النوع.
- **نسخة احتياطية:** `/export` يرسل ملف `memories.db` كمستند.
- **حذف آمن:** `/clear` يطلب تأكيداً بزر قبل حذف الكل.
- **تخزين SQLite:** ملف واحد `memories.db`، بدون خادم خارجي.

## 📋 الأوامر | Commands

| الأمر | الوصف |
|---|---|
| `/start` | ترحيب وطريقة الاستخدام |
| `/help` | دليل الأوامر |
| `/stats` | إحصائيات حسب النوع والمجموع |
| `/list [نوع]` | عرض الذكريات مع أزرار التصفح |
| `/recent` | أحدث 5 ذكريات |
| `/search كلمة` | بحث في النصوص والوسوم |
| `/get رقم` | عرض ذكرى برقمها |
| `/delete رقم` | حذف ذكرى برقمها |
| `/export` | إرسال نسخة احتياطية من قاعدة البيانات |
| `/clear` | حذف كل الذكريات (بعد تأكيد) |

أنواع `/list`: `text, photo, video, document, voice, audio, animation, sticker`
مثال: `/list photo`

## 🧱 بنية المشروع | Structure

```
memory-bot/
├── bot.py              # المعالجات (Handlers) — python-telegram-bot v21
├── storage.py          # طبقة SQLite: CRUD + بحث + وسوم (بدون تليجرام)
├── config.py           # تحميل الإعدادات من البيئة / .env
├── requirements.txt    # python-telegram-bot>=21,<22
├── .env.example        # TELEGRAM_BOT_TOKEN=
├── .gitignore          # .env, memories.db, __pycache__
├── Dockerfile          # python:3.12-slim, polling
├── docker-compose.yml  # تشغيل مع مجلد بيانات دائم
├── tests/
│   └── test_storage.py # اختبارات طبقة التخزين (stdlib فقط)
└── README.md
```

قاعدة البيانات `memories.db` — جدول `memories`:
`id, user_id, chat_id, type, file_id, text, tags, created_at`

## 🚀 التشغيل محلياً | Run locally

```bash
cd memory-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# ضع توكن البوت من @BotFather في .env (TELEGRAM_BOT_TOKEN=...)
# Never paste the token in chat or commit .env.

python bot.py
```

التوكن لا يُخزَّن في الكود أبداً. بدونه يتوقف البوت برسالة واضحة.

## 🐳 Docker

```bash
cp .env.example .env   # ضع التوكن
docker compose up -d --build
docker compose logs -f
```

البيانات محفوظة في مجلد Docker المسمى `memory-data` (`/app/data/memories.db`)،
فتبقى الذكريات بعد إعادة التشغيل.

## ☁️ النشر | Deployment notes

البوت يعمل بالـ **polling**، لذا يحتاج عملية تعمل باستمرار (worker)،
وليس موقعاً ثابتاً (static site).

- **Render:** أنشئ Web Service أو Background Worker من هذا المستودع،
  أمر البدء `python bot.py`، وأضف متغير البيئة `TELEGRAM_BOT_TOKEN`.
  ملاحظة: Render يحتاج بطاقة على مساحة العمل لإنشاء خدمة.
- **Railway:** أنشئ مشروعاً من المستودع، أضف `TELEGRAM_BOT_TOKEN`
  كمتغير بيئة، وأمر البدء `python bot.py`، مع مجلد بيانات دائم
  (Volume) على `/app/data` إن أردت بقاء `memories.db`.
- **Vercel / Cloudflare Pages:** غير مناسبة — فهي للمواقع الثابتة
  والدوال قصيرة العمر، بينما هذا البوت يحتاج عملية polling مستمرة.
  استخدم Render أو Railway أو أي خادم VPS بدلاً منها.
- **VPS:** انسخ المشروع، ثبّت المتطلبات، ضع التوكن في `.env`،
  وشغّله عبر `systemd` أو `docker compose up -d`.

## ✅ الاختبارات | Tests

طبقة التخزين تُختبر بدون تليجرام، بالمكتبة القياسية فقط:

```bash
python -m unittest discover -s tests -v
# أو
python tests/test_storage.py
```

## 🔒 الأمان | Security

- لا يوجد أي توكن أو سرّ في ملفات المشروع — التوكن في `.env` فقط،
  وهو مستثنى في `.gitignore`.
- كل ذكرى مرتبطة بـ `user_id` صاحبها، ولا يمكن لمستخدم عرض أو حذف
  ذكريات مستخدم آخر.
- `/export` يرسل نسخة قاعدة البيانات إلى صاحبها فقط.
