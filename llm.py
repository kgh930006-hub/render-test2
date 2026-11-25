"""Keyless LLM chain with fallback. Stdlib only (urllib)."""
import http.client
import json
import time
import urllib.error
import urllib.request

from config import PROVIDERS, SYSTEM_PROMPT


def _read_body(resp):
    try:
        return resp.read().decode("utf-8", "replace")
    except http.client.IncompleteRead as exc:
        # الشبكة تقطع الرد أحياناً — الجزء المقروء قد يحوي JSON كاملاً
        return (exc.partial or b"").decode("utf-8", "replace")


def _call_provider(provider, messages):
    payload = {
        "model": provider["model"],
        "messages": messages,
        "max_tokens": provider["max_tokens"],
        "temperature": 0.7,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        provider["url"],
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=provider["timeout"]) as resp:
        body = _read_body(resp)
    dt = round(time.time() - t0, 1)
    parsed = json.loads(body)
    msg = parsed["choices"][0]["message"]
    text = (msg.get("content") or "").strip()
    if not text:
        raise ValueError("empty content")
    return text, dt


def _call_with_retry(provider, messages):
    """محاولتان عند أخطاء الاتصال فقط (لا عند HTTP مثل 429)."""
    last_exc = None
    for attempt in (1, 2):
        try:
            return _call_provider(provider, messages)
        except urllib.error.HTTPError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == 1:
                time.sleep(1.5)
    raise last_exc


def chat(history, user_text, preferred_id=None, log=None):
    """history: list of {role, content}. Returns (text, provider_id, seconds).

    Tries preferred provider first, then enabled providers in order.
    Raises RuntimeError if all fail.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    enabled = [p for p in PROVIDERS if p.get("enabled")]
    if preferred_id:
        enabled.sort(key=lambda p: 0 if p["id"] == preferred_id else 1)

    errors = []
    for provider in enabled:
        try:
            text, dt = _call_with_retry(provider, messages)
            if log:
                log(f"llm ok provider={provider['id']} sec={dt}")
            return text, provider["id"], dt
        except Exception as exc:  # HTTPError, timeout, bad JSON, empty…
            errors.append(f"{provider['id']}: {type(exc).__name__}")
            if log:
                log(f"llm fail provider={provider['id']} err={type(exc).__name__}")
            continue
    raise RuntimeError("; ".join(errors) or "no enabled providers")


def enabled_providers():
    return [p for p in PROVIDERS if p.get("enabled")]
