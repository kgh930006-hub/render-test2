#!/usr/bin/env python3
"""ClawBot Lite — lightweight Telegram assistant (polling, keyless LLMs).

Uses the custom.telegram helper (surrogate credential). No token in code.
No shell execution, no computer control, no system file access from chats.
"""
import importlib.util
import json
import os
import sys
import time
import traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from config import HISTORY_LIMIT, MAX_REPLY_CHARS, POLL_TIMEOUT
import llm
import search as websearch
import store

_HELPER = "/home/hatch/workspace/custom-connectors/custom.telegram/bin/telegram.py"
_spec = importlib.util.spec_from_file_location("tg_helper", _HELPER)
tg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tg)

STARTED_AT = time.time()
LAST_PROVIDER = {}  # chat_id -> (provider_id, seconds)


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def tg_call(method, payload=None, timeout=30):
    return tg.call(method, payload, timeout=timeout)


def send(chat_id, text, reply_markup=None):
    text = (text or "").strip() or "…"
    if len(text) > MAX_REPLY_CHARS:
        text = text[: MAX_REPLY_CHARS - 20] + "\n…(تم الاختصار)"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    res = tg_call("sendMessage", payload)
    if not res.get("ok"):
        log(f"sendMessage fail chat={chat_id} desc={res.get('description')}")
    return res


def typing(chat_id):
    try:
        tg_call("sendChatAction", {"chat_id": chat_id, "action": "typing"}, timeout=10)
    except Exception:
        pass


SHELL_HINTS = [
    "نفذ أمر", "نفّذ أمر", "نفذ الامر", "شغل أمر", "run command", "execute command",
    "shell command", "sudo ", "rm -rf", "chmod ", "افتح التيرمينال", "terminal command",
]


def looks_like_shell_request(text):
    low = text.lower()
    return any(h in low for h in SHELL_HINTS)


HELP_TEXT = (
    "أهلاً! أنا نسخة خفيفة بروح ClawBot Plus — مساعد محادثة وبحث، بدون تحكم بالحاسوب.\n\n"
    "الأوامر:\n"
    "/start — البدء\n"
    "/help — هذه المساعدة\n"
    "/status — حالة البوت والنموذج الحالي\n"
    "/model — اختيار النموذج\n"
    "/search <سؤال> — بحث عميق في الويب مع تلخيص\n"
    "/reset — مسح ذاكرة المحادثة\n\n"
    "أو اكتب أي سؤال مباشرة وسأجيب."
)


def model_keyboard():
    rows = []
    for p in llm.enabled_providers():
        rows.append([{"text": p["label"], "callback_data": f"model:{p['id']}"}])
    rows.append([{"text": "تلقائي (الأسرع المتاح)", "callback_data": "model:auto"}])
    return {"inline_keyboard": rows}


def handle_command(chat_id, text):
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/start", "/help"):
        send(chat_id, HELP_TEXT)
        return True
    if cmd == "/status":
        up = int(time.time() - STARTED_AT)
        pref = store.get_provider(chat_id) or "تلقائي"
        last = LAST_PROVIDER.get(chat_id)
        last_txt = f"{last[0]} ({last[1]}ث)" if last else "لا يوجد بعد"
        names = ", ".join(p["id"] for p in llm.enabled_providers())
        send(
            chat_id,
            f"البوت يعمل (polling) منذ {up} ثانية.\n"
            f"النموذج المفضل: {pref}\nآخر نموذج أجاب: {last_txt}\n"
            f"النماذج المفعّلة: {names}",
        )
        return True
    if cmd == "/model":
        send(chat_id, "اختر النموذج المفضل لهذه المحادثة:", reply_markup=model_keyboard())
        return True
    if cmd == "/reset":
        store.reset_chat(chat_id)
        send(chat_id, "تم مسح ذاكرة هذه المحادثة. ابدأ من جديد.")
        return True
    if cmd == "/search":
        if not arg:
            send(chat_id, "استخدم: /search ثم سؤالك. مثال: /search طقس دمشق اليوم")
            return True
        do_search(chat_id, arg)
        return True
    return False


def do_search(chat_id, query):
    typing(chat_id)
    try:
        context, sources = websearch.deep_search(query)
    except Exception as exc:
        log(f"search fail chat={chat_id} err={type(exc).__name__}")
        send(chat_id, "تعذر البحث الآن. حاول مجدداً بعد قليل.")
        return
    if not context:
        send(chat_id, "لم أجد نتائج لهذا البحث.")
        return
    prompt = (
        f"لخّص وأجب عن السؤال التالي اعتماداً على نتائج البحث فقط، بالعربية، "
        f"مع ذكر المصادر في النهاية.\n\nالسؤال: {query}\n\nنتائج البحث:\n{context}"
    )
    try:
        typing(chat_id)
        text, pid, sec = llm.chat([], prompt, store.get_provider(chat_id), log=log)
        LAST_PROVIDER[chat_id] = (pid, sec)
        src = "\n".join(f"- {s}" for s in sources[:5])
        send(chat_id, f"{text}\n\nالمصادر:\n{src}")
    except Exception:
        # fallback: raw snippets without LLM
        send(chat_id, "نتائج البحث:\n\n" + context[:2500])


def handle_text(chat_id, text):
    if looks_like_shell_request(text):
        send(
            chat_id,
            "لا أنفّذ أوامر نظام ولا أتحكم بالحاسوب في هذه النسخة الخفيفة. "
            "أقدر أشرح لك الأمر أو أساعدك بالبحث والمحادثة فقط.",
        )
        return
    typing(chat_id)
    hist = store.history(chat_id, HISTORY_LIMIT)
    try:
        answer, pid, sec = llm.chat(hist, text, store.get_provider(chat_id), log=log)
    except Exception as exc:
        log(f"chat fail chat={chat_id} err={exc}")
        send(chat_id, "كل النماذج المجانية مشغولة الآن. حاول بعد دقيقة.")
        return
    LAST_PROVIDER[chat_id] = (pid, sec)
    store.add_message(chat_id, "user", text)
    store.add_message(chat_id, "assistant", answer)
    send(chat_id, answer)


def handle_callback(cq):
    cq_id = cq.get("id")
    data = cq.get("data") or ""
    chat_id = (cq.get("message") or {}).get("chat", {}).get("id")
    if data.startswith("model:") and chat_id:
        choice = data.split(":", 1)[1]
        if choice == "auto":
            store.set_provider(chat_id, "")
            msg = "تم: النموذج التلقائي."
        else:
            store.set_provider(chat_id, choice)
            msg = f"تم اختيار النموذج: {choice}"
        tg_call("answerCallbackQuery", {"callback_query_id": cq_id, "text": msg})
        send(chat_id, msg)
    else:
        tg_call("answerCallbackQuery", {"callback_query_id": cq_id})


def main():
    me = tg_call("getMe")
    if not me.get("ok"):
        log(f"getMe failed: {me.get('description')}")
        return 1
    bot = me["result"]
    log(f"started bot id={bot.get('id')} username=@{bot.get('username')}")
    offset = store.get_offset()
    log(f"offset={offset}")
    while True:
        try:
            res = tg_call(
                "getUpdates",
                {"offset": offset, "timeout": POLL_TIMEOUT, "limit": 10,
                 "allowed_updates": ["message", "callback_query"]},
                timeout=POLL_TIMEOUT + 10,
            )
            if not res.get("ok"):
                log(f"getUpdates not ok: {res.get('description')}")
                time.sleep(5)
                continue
            for upd in res.get("result") or []:
                offset = max(offset, int(upd["update_id"]) + 1)
                store.set_offset(offset)
                try:
                    if "callback_query" in upd:
                        handle_callback(upd["callback_query"])
                    elif "message" in upd:
                        msg = upd["message"]
                        chat_id = msg["chat"]["id"]
                        text = (msg.get("text") or "").strip()
                        log(f"update chat={chat_id} len={len(text)}")
                        if not text:
                            send(chat_id, "أتعامل مع النصوص والأوامر حالياً. اكتب سؤالك.")
                        elif text.startswith("/"):
                            if not handle_command(chat_id, text):
                                send(chat_id, "أمر غير معروف. جرّب /help")
                        else:
                            handle_text(chat_id, text)
                except Exception:
                    log("handle error:\n" + traceback.format_exc(limit=3))
        except KeyboardInterrupt:
            log("stopped by keyboard")
            return 0
        except Exception:
            log("poll error:\n" + traceback.format_exc(limit=3))
            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
