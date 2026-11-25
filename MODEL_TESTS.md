# نتائج اختبار النماذج المباشر — 2026-11-25

الطريقة: طلب EN وطلب AR لكل مرشّح (انظر `~/workspace/clawbot-research/test_models.py`
و`enar_results.jsonl` — 18 مرشّحاً)، ثم إعادة اختبار حدّية وسلسلة كاملة من `llm.py`.

## يعمل بالعربية (مفعّل في config.py)
- Kilo `kilo-auto/free` — متقلّب (فارغ/انقطاع أحياناً) لكن السلسلة نجحت به في 1.6ث بعد إعادة المحاولة؛ يحتاج max_tokens=1200.
- Pollinations `openai` (Classic) — AR ناجح 5.5ث.
- FreeAI `qwen7b` — AR ناجح 0.7ث.
- Kilo `nvidia/nemotron-3-ultra-550b-a55b:free` — AR ناجح 2.1ث.
- Kilo `nvidia/nemotron-3.5-lightning:free` — AR ناجح 5.0ث.
- ch.at `gpt-4o` — AR ناجح 1.0ث في هذا الاختبار (تاريخياً أبطأ، يبقى أخيراً).

المجموع المفعّل الآن: 6 نماذج. القائمة في `config.py` فيها 10 خانات رئيسية + احتياطي،
وتُوسَّع بإضافة dict واحد لكل نموذج جديد بعد اختباره.

## لا يعمل بدون مفتاح الآن (معطّل)
- OVH (Qwen3.6-27B / Llama-3.3-70B / DeepSeek-V4.1-Flash / gpt-oss-120b): كلها 429 rate limit.
- Pollinations `deepseek`: 404 — غير متاح على Classic API. و`gen.pollinations.ai`: 401 يحتاج مفتاحاً.
- Kilo `openrouter/free`: انقطاعات متكررة. Kilo `ling-3.2-flash:free`: 429. Kilo `ernie-5.5-flash:free`: EN ناجح ثم AR انقطاع/429 عند الإعادة.
- FreeAI `qwen-coder`: EN ناجح، AR فشل عند الإعادة (IncompleteRead/انقطاع) — يبقى معطّلاً حتى ينجح اختبار AR.
- KeylessAI `gpt-4o`: انقطاع فوري. ApiLlmFree `free-ai`: timeout ‏45ث.

ملاحظة: أخطاء IncompleteRead/RemoteDisconnected متكررة من هذه الـ VM؛ لذلك `llm.py`
يقرأ الجزء المتاح عند IncompleteRead ويعيد المحاولة مرة عند أخطاء الاتصال قبل الانتقال للمزوّد التالي.
