# ClawBot Lite — نسخة خفيفة بروح ClawBot Plus

بوت تيليجرام **io (@Tetris19730Bot)** يعمل بـ polling على هذه الـ VM عبر موصّل
`custom.telegram` (توكن مخزّن بأمان، لا يوجد أي توكن في الكود أو الملفات).

## ما يعمل
- محادثة عربية/إنجليزية بنماذج مجانية بدون مفتاح مع fallback تلقائي (انظر `MODEL_TESTS.md`).
- بحث عميق عند الطلب: `/search <سؤال>` — بحث Bing (DuckDuckGo محجوب بتحدّي بوت من هذه الـ VM) + جلب صفحات + تلخيص بالمصادر.
- ذاكرة محادثة قصيرة لكل chat في SQLite (`clawbot.db`)، و`/reset` لمسحها.
- أوامر: `/start` `/help` `/status` `/model` (أزرار اختيار نموذج) `/search` `/reset`.
- حدّ لطول الردود وسجلّات بلا أسرار (`bot.log`).

## ما لا يعمل (مقارنة بـ ClawBot Plus الكامل)
- لا تحكّم بالحاسوب: لا PyAutoGUI ولا نقر/كتابة ولا لقطات شاشة ولا فتح تطبيقات.
- لا تنفيذ shell ولا قراءة/كتابة ملفات نظام من رسائل تيليجرام (يُرفض صراحة).
- لا متصفح Playwright ولا صوت/ميكروفون ولا توليد PPT/فيديو.
- السبب: المشروع الكامل مصمم لـ Windows PC بواجهة رسومية وChrome ومفاتيح مدفوعة وذاكرة كبيرة؛
  هذه الـ VM ‏Linux headless بذاكرة متاحة ~520Mi. التفاصيل في `~/workspace/clawbot-research/feasibility.md`.

## التشغيل والإيقاف
- تشغيل: `cd ~/workspace/clawbot-lite && nohup python3 bot.py > bot.log 2>&1 & echo $! > bot.pid`
- إيقاف: `kill $(cat ~/workspace/clawbot-lite/bot.pid)`
- اختبار: أرسل `/start` إلى **@Tetris19730Bot** في تيليجرام، ثم جرّب سؤالاً عادياً و`/search طقس دمشق اليوم` و`/model`.
- يعمل فقط ما دامت الـ VM والعملية حية (ليس 24/7 مضموناً).

## النقل لاحقاً إلى Cloudflare Workers (للدوام 24/7)
1. انقل منطق `llm.py`/`search.py` إلى Worker (fetch بدل urllib، KV بدل SQLite).
2. أضف `TELEGRAM_BOT_TOKEN` كـ Worker secret يدوياً من لوحة Cloudflare (لا يمكن نسخ التوكن المخزّن تلقائياً).
3. اضبط webhook على `/webhook` بدل polling، وأعد ضبط الأوامر.
4. أوقف مشغّل الـ VM أولاً حتى لا يتنافس polling مع webhook.

## الملفات
- `bot.py` المشغّل · `config.py` قائمة النماذج (أضف dict لكل نموذج جديد) · `llm.py` سلسلة fallback · `search.py` البحث · `store.py` الذاكرة · `MODEL_TESTS.md` نتائج الاختبار.
