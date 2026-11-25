"""ClawBot Lite config — keyless OpenAI-compatible providers.

To add a model: append one dict to PROVIDERS. Only enabled=True entries
are tried, in list order (per-chat preferred provider goes first).
No API keys anywhere: all endpoints are keyless. Never put a token here.

Verified live 2026-11-25 (EN+AR, curl-confirmed): 10 distinct keyless
models + 2 routers/aliases. See ~/workspace/clawbot-research/free-models.md
and MODEL_TESTS.md. Kilo free models rotate (~200 req/h/IP) — re-check
GET https://api.kilo.ai/api/gateway/models periodically.
"""

# timeout: per-provider seconds (short, so fallback stays fast)
# max_tokens: Kilo needs 800-1200 for Arabic (empty replies below that)
PROVIDERS = [
    {
        "id": "freeai-qwen7b",
        "label": "FreeAI Qwen (الأسرع)",
        "url": "https://api.free.ai/v1/chat/completions",
        "model": "qwen7b",
        "max_tokens": 800,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "kilo-auto",
        "label": "Kilo Auto (مجاني)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "kilo-auto/free",
        "max_tokens": 1200,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "pollinations-openai",
        "label": "Pollinations OpenAI",
        "url": "https://text.pollinations.ai/openai/chat/completions",
        "model": "openai",
        "max_tokens": 800,
        "timeout": 30,
        "enabled": True,
    },
    {
        "id": "kilo-nemotron-ultra",
        "label": "Kilo Nemotron Ultra (مجاني)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "max_tokens": 1000,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "kilo-ernie",
        "label": "Kilo ERNIE Flash (مجاني)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "baidu/ernie-5.5-flash-preview:free",
        "max_tokens": 1000,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "kilo-nemotron-lightning",
        "label": "Kilo Nemotron Lightning (مجاني)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "nvidia/nemotron-3.5-lightning:free",
        "max_tokens": 1000,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "kilo-nemotron-super-vl",
        "label": "Kilo Nemotron Super-VL (مجاني)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "nvidia/nemotron-3.5-super-vl:free",
        "max_tokens": 1000,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "kilo-nemotron-nano-omni",
        "label": "Kilo Nemotron Nano-Omni (مجاني)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "max_tokens": 1000,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "kilo-beam",
        "label": "Kilo Beam (مجاني)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "reflection/beam-free",
        "max_tokens": 1000,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "kilo-flint",
        "label": "Kilo Flint (مجاني، بطيء)",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "recursive/flint-v1.0:free",
        "max_tokens": 1000,
        "timeout": 35,
        "enabled": True,
    },
    {
        "id": "freeai-qwen-coder",
        "label": "FreeAI Qwen Coder",
        "url": "https://api.free.ai/v1/chat/completions",
        "model": "qwen-coder",
        "max_tokens": 800,
        "timeout": 25,
        "enabled": True,
    },
    {
        "id": "chat-gpt4o",
        "label": "ch.at GPT-4o (أخير)",
        "url": "https://ch.at/v1/chat/completions",
        "model": "gpt-4o",
        "max_tokens": 800,
        "timeout": 35,
        "enabled": True,  # بلا أدوات — يبقى أخيراً دائماً
    },
    # --- معطّل: فشل الاختبار المباشر 2026-11-25 ---
    {
        "id": "kilo-openrouter-free",
        "label": "Kilo OpenRouter Free",
        "url": "https://api.kilo.ai/api/gateway/chat/completions",
        "model": "openrouter/free",
        "max_tokens": 1000,
        "timeout": 25,
        "enabled": False,  # إعادة اختبار: content فارغ (finish=length)
    },
    {
        "id": "pollinations-deepseek",
        "label": "Pollinations DeepSeek",
        "url": "https://text.pollinations.ai/openai/chat/completions",
        "model": "deepseek",
        "max_tokens": 800,
        "timeout": 30,
        "enabled": False,  # 404 — غير متاح على Classic API
    },
    {
        "id": "ovh-qwen36",
        "label": "OVH Qwen3.6-27B",
        "url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions",
        "model": "Qwen3.6-27B",
        "max_tokens": 800,
        "timeout": 25,
        "enabled": False,  # 429 rate limit بدون مفتاح
    },
    {
        "id": "ovh-llama70b",
        "label": "OVH Llama-3.3-70B",
        "url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions",
        "model": "Meta-Llama-3_3-70B-Instruct",
        "max_tokens": 800,
        "timeout": 25,
        "enabled": False,
    },
    {
        "id": "keylessai-gpt4o",
        "label": "KeylessAI GPT-4o",
        "url": "https://keylessai.thryx.workers.dev/v1/chat/completions",
        "model": "gpt-4o",
        "max_tokens": 800,
        "timeout": 25,
        "enabled": False,
    },
]

SYSTEM_PROMPT = (
    "أنت مساعد ذكي ودود داخل بوت تيليجرام. أجب بلغة المستخدم (العربية غالباً) "
    "باختصار ووضوح. لا تنفّذ أوامر نظام ولا تتحكم بالحاسوب أبداً؛ إذا طُلب منك "
    "ذلك ارفض بلطف واعرض المساعدة بالشرح فقط. عند تلخيص نتائج بحث، اذكر المصادر."
)

MAX_REPLY_CHARS = 3500
HISTORY_LIMIT = 12  # رسائل محفوظة لكل محادثة في السياق
POLL_TIMEOUT = 25  # ثواني long-polling
