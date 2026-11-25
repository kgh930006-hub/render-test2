"""TURBO x100 patch (2026-11-25 20:15 Damascus): race LLM already in fallback_llm v2.
This patch wires telegram_bot.py: direct tools, memory+cache, fast shell, typing,
split replies, /model /turbo /weather /time /calc /shell /remember /memory /forget
/remind, photo handler with VL, computer loop capped at 5 steps.
Backs up original, writes unified diff. Idempotent-ish (asserts anchors)."""
import difflib
import pathlib
import shutil
import sys

V = pathlib.Path("/home/hatch/workspace/clawbot-plus-actual/venv/lib/python3.12/site-packages/clawbot/computer/telegram_bot.py")
LOGS = pathlib.Path("/home/hatch/workspace/clawbot-plus-actual/logs")
src = V.read_text(encoding="utf-8")
orig = src
shutil.copy(V, LOGS / "telegram_bot.py.pre-turbo.bak")

def rep(old, new, name):
    global src
    assert old in src, f"anchor missing: {name}"
    src = src.replace(old, new, 1)

# 1) sys.path for turbo modules
rep('COMPUTER_DIR = Path(__file__).parent.parent / "computer"\nif str(COMPUTER_DIR) not in sys.path:\n    sys.path.insert(0, str(COMPUTER_DIR))',
    'COMPUTER_DIR = Path(__file__).parent.parent / "computer"\nif str(COMPUTER_DIR) not in sys.path:\n    sys.path.insert(0, str(COMPUTER_DIR))\n# TURBO: project dir for turbo_tools/turbo_store/fallback_llm\nsys.path.insert(0, "/home/hatch/workspace/clawbot-plus-actual")',
    "sys.path")

# 2) flush: split instead of truncate
rep('''        try:
            # Truncate if too long (Telegram limit is 4096)
            if len(text) > 3900:
                text = text[:3900] + "\\n... (truncated)"
            
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=None  # Plain text to avoid markdown issues
                )
            except (TimedOut, NetworkError) as _e1:  # PATCH P-FIX-2002: retry once
                logger.warning(f"Telegram flush retry after {type(_e1).__name__}")
                await asyncio.sleep(2)
                await self.bot.send_message(
                    chat_id=self.chat_id, text=text, parse_mode=None
                )''',
    '''        try:
            # TURBO: split long replies into <=3900-char messages (no truncation)
            chunks = [text[i:i+3900] for i in range(0, len(text), 3900)] or [text]
            for chunk in chunks:
                try:
                    await self.bot.send_message(chat_id=self.chat_id, text=chunk, parse_mode=None)
                except (TimedOut, NetworkError) as _e1:  # PATCH P-FIX-2002: retry once
                    logger.warning(f"Telegram flush retry after {type(_e1).__name__}")
                    await asyncio.sleep(2)
                    await self.bot.send_message(chat_id=self.chat_id, text=chunk, parse_mode=None)''',
    "flush split")

# 3) computer loop cap 5 steps
rep("    for step in range(1, 41):",
    "    for step in range(1, 6):  # TURBO: max 5 steps (was 40)",
    "loop cap")

# 4) cmd_start help text
rep('"Normal text messages will just chat with the AI!"',
    '"⚡ TURBO:\\n"\n        f"  /weather [مدينة] — طقس مباشر | /time — الوقت | /calc <تعبير>\\n"\n        f"  /shell <أمر> — تنفيذ مباشر سريع | /model — صحة النماذج | /turbo — الحالة\\n"\n        f"  /remember <نص> /memory /forget — ذاكرة دائمة | /remind <دقائق> <نص>\\n"\n        f"  أرسل صورة لتحليلها | اكتب (نفّذ: <أمر>) للتنفيذ المباشر\\n\\n"\n        f"Normal text messages will just chat with the AI!"',
    "start help")

# 5) run_chat_task: cache check before live-data fetch
rep("    # ── Auto-fetch live data for weather queries ──",
    '''    # TURBO: answer cache (1h) for identical questions
    try:
        import turbo_store as _ts_cache
        _cached = _ts_cache.cache_get(text)
        if _cached:
            await tg_output.send(_cached)
            await tg_output.flush()
            return
    except Exception:
        pass

    # ── Auto-fetch live data for weather queries ──''',
    "cache check")

# 6) run_chat_task: persistent history + memories injection
rep('''    if CHAT_HISTORY:
        chat_context += "[Previous Conversation History]\\n" + "\\n".join(CHAT_HISTORY[-8:]) + "\\n\\n"''',
    '''    if CHAT_HISTORY:
        chat_context += "[Previous Conversation History]\\n" + "\\n".join(CHAT_HISTORY[-8:]) + "\\n\\n"
    try:  # TURBO: persistent history (30) + saved memories
        import turbo_store as _ts_hist
        _hist = _ts_hist.get_history(tg_output.chat_id, 30)
        if _hist:
            chat_context += "[Turbo Persistent History]\\n" + "\\n".join(_hist) + "\\n\\n"
        _mems = _ts_hist.list_memories(tg_output.chat_id)
        if _mems:
            chat_context += "[User Saved Memories]\\n" + "\\n".join(f"- {m}" for m in _mems) + "\\n\\n"
    except Exception:
        pass''',
    "history inject")

# 7) run_chat_task: persist + cache after reply
rep('''        CHAT_HISTORY.append(f"User: {text}")
        CHAT_HISTORY.append(f"ClawBot: {reply}")''',
    '''        CHAT_HISTORY.append(f"User: {text}")
        CHAT_HISTORY.append(f"ClawBot: {reply}")
        try:  # TURBO: persist history + cache answer
            import turbo_store as _ts_save
            _ts_save.add_message(tg_output.chat_id, "User", text)
            _ts_save.add_message(tg_output.chat_id, "ClawBot", reply)
            _ts_save.cache_set(text, reply)
        except Exception:
            pass''',
    "persist")

# 8) handle_message: typing + direct intents in chat-first else-branch
rep('''        else:
            await run_chat_task(task, tg_output)''',
    '''        else:
            try:  # TURBO: typing indicator
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            except Exception:
                pass
            _direct = None
            try:  # TURBO: direct tools without LLM (weather/time/calc/shell)
                import turbo_tools as _tt, turbo_store as _ts
                if task.startswith(("نفّذ:", "نفذ:", "shell:")):
                    _direct = await asyncio.to_thread(_tt.shell_direct, task.split(":", 1)[1])
                elif task.startswith(("احسب:", "احسب ")):
                    _direct = _tt.calc(task.split(":", 1)[1] if ":" in task else task[5:])
                elif _tt.is_weather_intent(task):
                    _direct = await asyncio.to_thread(_tt.weather, _tt.extract_city(task))
                elif any(k in task for k in ("كم الساعة", "الساعة الآن", "الوقت الآن", "what time")):
                    _direct = _tt.time_now()
                if _direct is not None:
                    await _reply_retry(update, _direct[:3900])
                    try:
                        _ts.add_message(update.effective_chat.id, "User", task)
                        _ts.add_message(update.effective_chat.id, "ClawBot", _direct)
                    except Exception:
                        pass
            except Exception as _e:
                logger.warning(f"TURBO direct intent failed: {type(_e).__name__}")
                _direct = None
            if _direct is None:
                await run_chat_task(task, tg_output)''',
    "direct intents")

# 9) new commands + photo handler before def main()
NEW_FUNCS = '''
# ════════════════════════════════════════════════════════
# ⚡ TURBO COMMANDS (2026-11-25)
# ════════════════════════════════════════════════════════

async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    import turbo_tools as _tt
    city = " ".join(context.args).strip() or "دمشق"
    await _reply_retry(update, await asyncio.to_thread(_tt.weather, city))

async def cmd_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    import turbo_tools as _tt
    await _reply_retry(update, _tt.time_now())

async def cmd_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    import turbo_tools as _tt
    await _reply_retry(update, _tt.calc(" ".join(context.args)))

async def cmd_shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    import turbo_tools as _tt
    await _reply_retry(update, await asyncio.to_thread(_tt.shell_direct, " ".join(context.args)))

async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    import turbo_store as _ts
    txt = " ".join(context.args).strip()
    if not txt:
        await _reply_retry(update, "الاستخدام: /remember <نص تريد حفظه>"); return
    _ts.remember(update.effective_chat.id, txt)
    await _reply_retry(update, f"💾 حُفظ في الذاكرة: {txt}")

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    import turbo_store as _ts
    mems = _ts.list_memories(update.effective_chat.id)
    await _reply_retry(update, "💾 ذاكرتك المحفوظة:\\n" + ("\\n".join(f"- {m}" for m in mems) if mems else "(فارغة — استخدم /remember)"))

async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    import turbo_store as _ts
    n = _ts.forget_all(update.effective_chat.id)
    await _reply_retry(update, f"🗑️ مُسحت الذاكرة وسجل المحادثة ({n} ذكرى).")

async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    try:
        from fallback_llm import provider_health
        lines = ["🤖 النماذج المجانية (سباق Turbo — أول رد صالح يفوز):"]
        for h in provider_health():
            ew = f"{h['ewma']}ث" if h["ewma"] is not None else "—"
            cd = f" ⏸️ تبريد {h['cooldown_sec']}ث" if h["cooldown_sec"] else ""
            lines.append(f"• {h['id']}: متوسط {ew} | نجاح {h['ok']} | فشل {h['fail']}{cd}")
        await _reply_retry(update, "\\n".join(lines)[:3900])
    except Exception as e:
        await _reply_retry(update, f"تعذّر عرض النماذج: {type(e).__name__}")

async def cmd_turbo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    try:
        import turbo_store as _ts
        from fallback_llm import provider_health
        st = _ts.stats()
        healthy = sum(1 for h in provider_health() if not h["cooldown_sec"])
        await _reply_retry(update,
            f"⚡ حالة Turbo:\\n• مزوّدون أصحّاء: {healthy}\\n• رسائل محفوظة: {st['messages']}\\n"
            f"• ذكريات: {st['memories']} | كاش حي: {st['cache_live']} | قاعدة: {st['db_kb']}KB\\n"
            f"• أوامر: /weather /time /calc /shell /model /remember /memory /forget /remind")
    except Exception as e:
        await _reply_retry(update, f"تعذّر عرض حالة Turbo: {type(e).__name__}")

async def _remind_callback(context):
    try:
        await context.bot.send_message(chat_id=context.job.chat_id, text=f"⏰ تذكير: {context.job.data}")
    except Exception:
        pass

async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    if not context.job_queue:
        await _reply_retry(update, "⏰ JobQueue غير متاحة في هذه النسخة — التذكيرات لا تعمل."); return
    if len(context.args) < 2 or not context.args[0].isdigit():
        await _reply_retry(update, "الاستخدام: /remind <دقائق> <نص> — مثال: /remind 10 اشرب ماء"); return
    mins = int(context.args[0]); txt = " ".join(context.args[1:])
    context.job_queue.run_once(_remind_callback, when=mins * 60, chat_id=update.effective_chat.id, data=txt)
    await _reply_retry(update, f"⏰ سأذكّرك بعد {mins} دقيقة: {txt}")

def _describe_image_vl(path, caption=""):
    """TURBO photo analysis via Kilo VL models (keyless). Returns Arabic text or honest failure."""
    import base64 as _b64, io as _io, json as _json, urllib.request as _rq
    from PIL import Image as _Img
    img = _Img.open(path); img.thumbnail((1024, 1024))
    buf = _io.BytesIO(); img.convert("RGB").save(buf, "JPEG", quality=80)
    small = _b64.b64encode(buf.getvalue()).decode()
    q = caption.strip() or "Describe this image briefly."
    prompt = q + " Answer in Arabic."
    for model in ("nvidia/nemotron-3.5-super-vl:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"):
        try:
            payload = {"model": model, "max_tokens": 800, "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{small}"}}]}]}
            req = _rq.Request("https://api.kilo.ai/api/gateway/chat/completions",
                              data=_json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json", "Accept": "application/json"})
            with _rq.urlopen(req, timeout=35) as r:
                d = _json.loads(r.read().decode("utf-8", "replace"))
            content = ((d.get("choices") or [{}])[0].get("message") or {}).get("content")
            if content and content.strip():
                return "🖼️ تحليل الصورة:\\n" + content.strip()
        except Exception:
            continue
    return "🖼️ حُفظت الصورة لكن نماذج الرؤية لم ترد الآن — جرّب مجدداً بعد قليل."

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update): return
    try:
        import pathlib as _pl, time as _t
        photo = update.message.photo[-1]
        f = await context.bot.get_file(photo.file_id)
        d = _pl.Path("/home/hatch/workspace/clawbot-plus-actual/photos"); d.mkdir(exist_ok=True)
        path = d / f"photo_{int(_t.time())}.jpg"
        await f.download_to_drive(str(path))
        await _reply_retry(update, f"📷 استلمت الصورة ({photo.width}x{photo.height}) وحفظتها. جارٍ تحليلها...")
        desc = await asyncio.to_thread(_describe_image_vl, str(path), update.message.caption or "")
        await _reply_retry(update, desc[:3900])
    except Exception as e:
        await _reply_retry(update, f"خطأ معالجة الصورة: {type(e).__name__}")

'''
rep("\ndef main():", NEW_FUNCS + "\ndef main():", "new funcs")

# 10) registration
rep('    app.add_handler(CommandHandler("search", cmd_search))  # PATCH P-SEARCH',
    '''    app.add_handler(CommandHandler("search", cmd_search))  # PATCH P-SEARCH
    # TURBO commands
    app.add_handler(CommandHandler("weather", cmd_weather))
    app.add_handler(CommandHandler("time", cmd_time))
    app.add_handler(CommandHandler("calc", cmd_calc))
    app.add_handler(CommandHandler("shell", cmd_shell))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("turbo", cmd_turbo))
    app.add_handler(CommandHandler("remind", cmd_remind))''',
    "registration")
rep("    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))",
    "    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))\n    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))  # TURBO",
    "photo handler")

V.write_text(src, encoding="utf-8")
diff = "\n".join(difflib.unified_diff(orig.splitlines(), src.splitlines(), "telegram_bot.py.orig", "telegram_bot.py", lineterm=""))
(LOGS / "telegram_bot.turbo.diff").write_text(diff, encoding="utf-8")
print(f"TURBO_PATCH_OK diff_lines={len(diff.splitlines())} new_lines={len(src.splitlines())}")
