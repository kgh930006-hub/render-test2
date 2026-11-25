"""PATCH P-FALLBACK v2 / TURBO: keyless multi-provider LLM, parallel race + fallback.

Interface unchanged (agent.py _ask_llm: astream/ainvoke -> .content/.completion).
v2 adds:
- Race: first 3 healthy providers in parallel threads, 10s per-provider cap,
  first valid reply wins (tail-latency killer when provider #1 is slow/broken).
- Circuit breaker: 3 consecutive failures -> 120s cooldown.
- EWMA latency ordering + persistent stats in turbo_stats.json.
- Sequential fallback over the remaining providers if the race fails.
No Authorization header (Kilo keyless rejects SDK dummy-key with 401).
No keys anywhere. Logs provider id + seconds + error type only.
Tool-calling: NOT supported (same as v1).
"""
import asyncio
import concurrent.futures
import http.client
import json
import logging
import pathlib
import threading
import time
import urllib.error
import urllib.request

logger = logging.getLogger("clawbot.fallback_llm")

STATS_FILE = pathlib.Path(__file__).with_name("turbo_stats.json")
RACE_N = 3
RACE_TIMEOUT = 10
COOLDOWN_SEC = 120
FAIL_THRESHOLD = 3

PROVIDERS = [
    {"id": "freeai-qwen7b", "url": "https://api.free.ai/v1/chat/completions",
     "model": "qwen7b", "max_tokens": 800, "timeout": 25, "enabled": True},
    {"id": "kilo-auto", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "kilo-auto/free", "max_tokens": 1200, "timeout": 25, "enabled": True},
    {"id": "pollinations-openai", "url": "https://text.pollinations.ai/openai/chat/completions",
     "model": "openai", "max_tokens": 800, "timeout": 30, "enabled": True},
    {"id": "kilo-nemotron-ultra", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "nvidia/nemotron-3-ultra-550b-a55b:free", "max_tokens": 1000, "timeout": 25, "enabled": True},
    {"id": "kilo-ernie", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "baidu/ernie-5.5-flash-preview:free", "max_tokens": 1000, "timeout": 25, "enabled": True},
    {"id": "kilo-nemotron-lightning", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "nvidia/nemotron-3.5-lightning:free", "max_tokens": 1000, "timeout": 25, "enabled": True},
    {"id": "kilo-nemotron-super-vl", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "nvidia/nemotron-3.5-super-vl:free", "max_tokens": 1000, "timeout": 25, "enabled": True},
    {"id": "kilo-nemotron-nano-omni", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "max_tokens": 1000, "timeout": 25,
     "enabled": False},  # 2026-11-25 retest: AR OK, EN HTTP 200 0-byte body consistently
    {"id": "kilo-beam", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "reflection/beam-free", "max_tokens": 1000, "timeout": 25, "enabled": True},
    {"id": "kilo-flint", "url": "https://api.kilo.ai/api/gateway/chat/completions",
     "model": "recursive/flint-v1.0:free", "max_tokens": 1000, "timeout": 35, "enabled": True},
    {"id": "freeai-qwen-coder", "url": "https://api.free.ai/v1/chat/completions",
     "model": "qwen-coder", "max_tokens": 800, "timeout": 25, "enabled": True},
    {"id": "chat-gpt4o", "url": "https://ch.at/v1/chat/completions",
     "model": "gpt-4o", "max_tokens": 800, "timeout": 35, "enabled": True},  # no tools, always last
]

_lock = threading.Lock()
_stats = None


def _load_stats():
    global _stats
    if _stats is not None:
        return _stats
    try:
        _stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except Exception:
        _stats = {}
    return _stats


def _save_stats():
    try:
        tmp = STATS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_stats, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(STATS_FILE)
    except Exception:
        pass


def _record(pid, success, dt=None):
    with _lock:
        s = _load_stats().setdefault(pid, {"ewma": None, "ok": 0, "fail": 0, "consec_fail": 0, "cooldown_until": 0})
        if success:
            s["ok"] += 1
            s["consec_fail"] = 0
            s["ewma"] = dt if s["ewma"] is None else round(0.7 * s["ewma"] + 0.3 * dt, 2)
        else:
            s["fail"] += 1
            s["consec_fail"] += 1
            if s["consec_fail"] >= FAIL_THRESHOLD:
                s["cooldown_until"] = time.time() + COOLDOWN_SEC
                s["consec_fail"] = 0
                logger.info(f"circuit open provider={pid} cooldown={COOLDOWN_SEC}s")
        _save_stats()


def provider_health():
    """For /model and /turbo: list of dicts sorted by EWMA (unknown last, config order)."""
    now = time.time()
    out = []
    with _lock:
        stats = dict(_load_stats())
    for i, p in enumerate([x for x in PROVIDERS if x.get("enabled")]):
        s = stats.get(p["id"], {})
        cd = max(0, int(s.get("cooldown_until", 0) - now))
        out.append({"id": p["id"], "model": p["model"], "ewma": s.get("ewma"),
                    "ok": s.get("ok", 0), "fail": s.get("fail", 0),
                    "cooldown_sec": cd, "order": i})
    out.sort(key=lambda d: (d["cooldown_sec"] > 0, d["ewma"] is None, d["ewma"] or 0, d["order"]))
    return out


def _healthy_sorted(providers):
    now = time.time()
    with _lock:
        stats = dict(_load_stats())
    def key(item):
        i, p = item
        s = stats.get(p["id"], {})
        cooling = s.get("cooldown_until", 0) > now
        ewma = s.get("ewma")
        return (cooling, ewma is None, ewma or 0, i)
    return [p for _, p in sorted(enumerate(providers), key=key)]


def _read_body(resp):
    try:
        return resp.read().decode("utf-8", "replace")
    except http.client.IncompleteRead as exc:
        return (exc.partial or b"").decode("utf-8", "replace")


def _role_of(msg):
    role = getattr(msg, "role", None)
    if role:
        return str(role)
    name = type(msg).__name__.lower()
    if "system" in name:
        return "system"
    if "assistant" in name:
        return "assistant"
    return "user"


def _convert_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for item in content:
            if isinstance(item, dict):
                out.append(item)
            elif hasattr(item, "text"):
                out.append({"type": "text", "text": str(item.text)})
            else:
                out.append({"type": "text", "text": str(item)})
        return out
    return str(content)


def _convert_messages(messages):
    converted, has_image = [], False
    for msg in messages:
        if isinstance(msg, dict):
            role, content = msg.get("role", "user"), _convert_content(msg.get("content", ""))
        else:
            role, content = _role_of(msg), _convert_content(getattr(msg, "content", str(msg)))
        if isinstance(content, list) and any(isinstance(i, dict) and i.get("type") == "image_url" for i in content):
            has_image = True
        converted.append({"role": role, "content": content})
    return converted, has_image


class _Resp:
    def __init__(self, text, completion=None):
        self.content = text
        self.completion = text if completion is None else completion
        self.usage = None
        self.usage_metadata = None
        self.thinking = None
        self.stop_reason = None


class FallbackLLM:
    model = "fallback-chain"
    model_name = "fallback-chain (keyless, turbo race+fallback)"

    def __init__(self, providers=None):
        self.providers = [p for p in (providers or PROVIDERS) if p.get("enabled")]
        self.last_provider = None

    def _call_provider(self, provider, messages, timeout_override=None):
        payload = {"model": provider["model"], "messages": messages,
                   "max_tokens": provider["max_tokens"], "temperature": 0.7}
        req = urllib.request.Request(
            provider["url"], data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout_override or provider["timeout"]) as resp:
            body = _read_body(resp)
        dt = round(time.time() - t0, 1)
        parsed = json.loads(body)
        text = (parsed["choices"][0]["message"].get("content") or "").strip()
        if not text:
            raise ValueError("empty content")
        return text, dt

    def _call_with_retry(self, provider, messages):
        last_exc = None
        for attempt in (1, 2):
            try:
                return self._call_provider(provider, messages)
            except urllib.error.HTTPError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt == 1:
                    time.sleep(1.5)
        raise last_exc

    def _try_one(self, provider, converted, race=False):
        """Returns (text, dt) or raises. Records stats + logs."""
        try:
            if race:
                text, dt = self._call_provider(provider, converted, timeout_override=RACE_TIMEOUT)
            else:
                text, dt = self._call_with_retry(provider, converted)
            _record(provider["id"], True, dt)
            logger.info(f"fallback ok provider={provider['id']} sec={dt}{' race' if race else ''}")
            return text, dt
        except Exception as exc:
            _record(provider["id"], False)
            logger.info(f"fallback fail provider={provider['id']} err={type(exc).__name__}")
            raise

    def _run_chain(self, messages):
        converted, has_image = _convert_messages(messages)
        ordered = _healthy_sorted(self.providers)
        errors = []
        # --- Race first RACE_N healthy providers ---
        race_set = ordered[:RACE_N]
        if len(race_set) > 1:
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=RACE_N)
            futs = {ex.submit(self._try_one, p, converted, True): p for p in race_set}
            try:
                for fut in concurrent.futures.as_completed(futs, timeout=RACE_TIMEOUT + 5):
                    p = futs[fut]
                    try:
                        text, _dt = fut.result()
                        self.last_provider = p["id"]
                        ex.shutdown(wait=False)  # TURBO: don't wait for losers
                        return text
                    except Exception as exc:
                        errors.append(f"{p['id']}: {type(exc).__name__}")
            except concurrent.futures.TimeoutError:
                errors.append("race: TimeoutError")
            ex.shutdown(wait=False)
        # --- Sequential fallback over the rest (then raced ones, full timeout) ---
        rest = ordered[RACE_N:] + race_set
        for provider in rest:
            try:
                text, _dt = self._try_one(provider, converted, race=False)
                self.last_provider = provider["id"]
                return text
            except Exception as exc:
                errors.append(f"{provider['id']}: {type(exc).__name__}")
                continue
        detail = "; ".join(errors) or "no enabled providers"
        if has_image:
            raise Exception(f"400 image multimodal: all providers failed ({detail})")
        raise RuntimeError(f"all providers failed ({detail})")

    def invoke(self, messages, output_format=None, **kwargs):
        text = self._run_chain(messages)
        return _Resp(text, self._parse_output(text, output_format))

    async def ainvoke(self, messages, output_format=None, **kwargs):
        text = await asyncio.to_thread(self._run_chain, messages)
        return _Resp(text, self._parse_output(text, output_format))

    async def astream(self, messages, **kwargs):
        result = await self.ainvoke(messages)
        yield result

    @staticmethod
    def _parse_output(text, output_format):
        if output_format is None:
            return text
        try:
            raw = text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].removeprefix("json").strip()
            s, e = raw.find("{"), raw.rfind("}")
            if s != -1 and e != -1:
                raw = raw[s:e + 1]
            obj = json.loads(raw)
            if hasattr(output_format, "model_validate"):
                return output_format.model_validate(obj)
            return output_format(**obj)
        except Exception:
            return text


def create_fallback_llm():
    llm = FallbackLLM()
    logger.info("fallback chain ready: %d slots (%s)", len(llm.providers),
                ",".join(p["id"] for p in llm.providers))
    return llm
