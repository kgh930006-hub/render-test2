"""SILENT FAST MODE patch (2026-11-25 20:30 Damascus).
- TelegramOutput.silent: steps -> log only; one final result message.
- run_fast_task: shell intent direct (no LLM); one planning LLM call ->
  sequential step execution; replan on failure (max 2); GUI tasks fall back
  to the existing loop (silent). Total cap 120s, per-step 20s.
- agent.get_system_context cached 5 minutes.
Backups + diffs written. Chat-first and /search untouched."""
import difflib
import pathlib
import shutil

BASE = pathlib.Path("/home/hatch/workspace/clawbot-plus-actual")
V = BASE / "venv/lib/python3.12/site-packages/clawbot/computer/telegram_bot.py"
A = BASE / "venv/lib/python3.12/site-packages/clawbot/computer/agent.py"
LOGS = BASE / "logs"

src = V.read_text(encoding="utf-8"); orig = src
shutil.copy(V, LOGS / "telegram_bot.py.pre-silent.bak")

def rep(old, new, name):
    global src
    assert old in src, f"anchor missing: {name}"
    src = src.replace(old, new, 1)

# 1) TelegramOutput silent mode
rep('''    def __init__(self, bot: Bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self.buffer: list[str] = []
        self.last_flush = time.time()
        self.message_id = None  # For editing existing message
        self.step_count = 0''',
    '''    def __init__(self, bot: Bot, chat_id: str):
        self.bot = bot
        self.chat_id = chat_id
        self.buffer: list[str] = []
        self.last_flush = time.time()
        self.message_id = None  # For editing existing message
        self.step_count = 0
        self.silent = False  # SILENT FAST: steps -> log only, one final message
        self.silent_log: list[str] = []''',
    "silent init")

rep('''    async def send(self, text: str):
        """Send a message to Telegram."""
        try:
            # Clean rich markup
            clean = self._clean_markup(text)
            if not clean.strip():
                return
            ''',
    '''    async def send(self, text: str):
        """Send a message to Telegram."""
        try:
            # Clean rich markup
            clean = self._clean_markup(text)
            if not clean.strip():
                return
            if self.silent:  # SILENT FAST: log only, never to user
                self.silent_log.append(clean)
                logger.info(f"SILENT-STEP: {clean[:160]}")
                return
            ''',
    "silent send")

rep('''    async def flush(self):
        """Flush buffer to Telegram."""
        if not self.buffer:
            return
        ''',
    '''    async def flush(self):
        """Flush buffer to Telegram."""
        if self.silent:  # SILENT FAST: buffer -> log only
            if self.buffer:
                self.silent_log.extend(self.buffer)
                self.buffer = []
            return
        if not self.buffer:
            return
        ''',
    "silent flush")

rep('''    async def send_photo(self, image_bytes: bytes, caption: str = ""):
        """Send a screenshot to Telegram."""
        try:''',
    '''    async def send_photo(self, image_bytes: bytes, caption: str = ""):
        """Send a screenshot to Telegram."""
        if self.silent:  # SILENT FAST: no step photos to user
            logger.info(f"SILENT-PHOTO skipped: {caption[:80]}")
            return
        try:''',
    "silent photo")

# final-result helpers appended to class (after send_photo body end anchor)
rep('''        except Exception as e:
            logger.error(f"Telegram photo error: {e}")''',
    '''        except Exception as e:
            logger.error(f"Telegram photo error: {e}")

    def final_result(self) -> str:  # SILENT FAST
        for line in reversed(self.silent_log):
            if "Task Complete" in line:
                txt = line.split("Task Complete!", 1)[-1].strip().lstrip("—- ").strip()
                return txt or line
        meaningful = [l for l in self.silent_log
                      if not l.startswith(("📍 Step", "🔄 Loop", "🤖 ClawBot — Task Started", "⚠️ Task finished"))]
        if meaningful:
            return meaningful[-1][:1500]
        return "تم التنفيذ."

    async def send_final(self, text: str):  # SILENT FAST: the ONE user message
        text = (text or "تم التنفيذ.").strip()
        for chunk in [text[i:i+3900] for i in range(0, len(text), 3900)]:
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=chunk, parse_mode=None)
            except (TimedOut, NetworkError):
                await asyncio.sleep(2)
                await self.bot.send_message(chat_id=self.chat_id, text=chunk, parse_mode=None)''',
    "final helpers")

# 2) run_fast_task + typing keeper, inserted before run_ClawBot_task
FAST = '''
# ════════════════════════════════════════════════════════
# 🔇 SILENT FAST TASK (2026-11-25): direct shell / one-plan execution
# ════════════════════════════════════════════════════════

_SHELL_CMDS = {"echo", "ls", "cat", "pwd", "whoami", "date", "df", "free", "ps", "uname",
               "mkdir", "touch", "cp", "mv", "head", "tail", "wc", "grep", "find", "python3",
               "python", "pip", "curl", "wget", "tar", "zip", "unzip", "chmod", "hostname",
               "uptime", "id", "env", "printenv", "tee", "sed", "awk", "sort", "du", "stat"}
_GUI_WORDS = ("screenshot", "لقطة", "افتح", "open app", "click", "انقر", "المتصفح",
              "browser", "نافذة", "window", "اكتب في", "type into", "gui")

def _shell_intent(task: str):
    t = task.strip()
    for p in ("نفّذ:", "نفذ:", "shell:", "run:", "execute:"):
        if t.startswith(p):
            return t.split(":", 1)[1].strip()
    first = t.split()[0].strip("`") if t.split() else ""
    if first in _SHELL_CMDS:
        return t.strip("`")
    low = t.lower()
    for marker in ("run shell command:", "run command:", "execute command:", "shell command:"):
        if marker in low:
            return t[low.index(marker) + len(marker):].strip().strip("`'\\"")
    return None

async def run_fast_task(task: str, tg_output: TelegramOutput):
    """Returns final result text, or None to fall back to the GUI loop."""
    global cancel_task
    import json as _json, subprocess as _sp
    import turbo_tools as _tt
    cmd = _shell_intent(task)
    if cmd:
        out = await asyncio.to_thread(_tt.shell_direct, cmd)
        return f"✅ النتيجة:\\n{out}"
    if any(w in task.lower() for w in _GUI_WORDS):
        return None  # GUI task -> silent loop
    from agent import _ask_llm, get_system_context
    llm = create_default_llm()
    plan_prompt = (
        "You are a Linux task planner. Convert the task into a JSON array of steps. "
        "Each step: {\\"type\\": \\"shell\\" or \\"python\\", \\"command\\": \\"...\\"} for shell, "
        "or {\\"type\\": \\"python\\", \\"code\\": \\"...\\"} for python. Max 8 steps. "
        "Use absolute paths under /home/hatch when creating files. Output ONLY the JSON array.\\n"
        f"{get_system_context()}\\nTask: {task}")
    outputs, error_ctx = [], ""
    for attempt in range(3):  # initial plan + up to 2 replans
        try:
            raw = await _ask_llm(llm, plan_prompt + error_ctx)
            s, e = raw.find("["), raw.rfind("]")
            steps = _json.loads(raw[s:e + 1]) if s != -1 and e != -1 else []
        except Exception as exc:
            steps = []
            error_ctx = f"\\nPrevious planning failed: {type(exc).__name__}. Output ONLY a JSON array."
        if not steps:
            continue
        failed = None
        for st in steps[:8]:
            if cancel_task:
                return "🛑 أُوقف التنفيذ بطلبك."
            try:
                if st.get("type") == "python":
                    def _runpy(code=st.get("code", "")):
                        p = _sp.run(["python3", "-c", code], capture_output=True, text=True, timeout=20)
                        return ((p.stdout or "") + (p.stderr or "")).strip() or f"(exit {p.returncode})"
                    out = await asyncio.to_thread(_runpy)
                else:
                    out = await asyncio.to_thread(_tt.shell_direct, st.get("command", ""))
            except Exception as exc:
                out = f"ERROR: {type(exc).__name__}"
            outputs.append(out[:1200])
            if out.startswith(("ERROR", "⛔", "⏱️")) or "Traceback" in out:
                failed = out
                break
        if failed is None:
            body = "\\n".join(o for o in outputs if o and o != "(done)") or "تم التنفيذ بنجاح."
            return f"✅ النتيجة:\\n{body[:3500]}"
        error_ctx = f"\\nA step failed with: {failed[:300]}\\nOutputs so far: {outputs}\\nProduce a corrected JSON array for the REMAINING work only."
        outputs = []
    return None  # planning failed -> silent loop fallback

async def _typing_keeper(bot, chat_id, stop_event):
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass

'''
rep("async def run_ClawBot_task(task: str, tg_output: TelegramOutput):",
    FAST + "async def run_ClawBot_task(task: str, tg_output: TelegramOutput):",
    "fast task funcs")

# 3) handle_message computer branch: silent + fast + one final message
rep('''        if is_computer_mode:
            await _reply_retry(update, f"🤖 PC Task samajh aaya!\\n⚡ Executing: {task[:80]}")''',
    '''        if is_computer_mode:
            tg_output.silent = True  # SILENT FAST: no step messages to user
            _stop_typing = asyncio.Event()
            _typing_task = asyncio.create_task(_typing_keeper(context.bot, update.effective_chat.id, _stop_typing))''',
    "silent computer start")

rep('''            try:
                await run_ClawBot_task(task_with_context, tg_output)
            except Exception as _ce:  # PATCH P-FIX-2002: never silence on PC-task failure
                logger.error(f"Computer task failed, falling back to chat LLM: {_ce}", exc_info=True)
                try:
                    await run_chat_task(task, tg_output)
                except Exception as _fe:
                    logger.error(f"Chat fallback also failed: {_fe}", exc_info=True)
                    await _reply_retry(update, "❌ تعذّر تنفيذ المهمة والرد. حاول مرة أخرى أو استخدم /search.")''',
    '''            try:  # SILENT FAST: fast path first, silent loop fallback, ONE final message
                _result = await asyncio.wait_for(run_fast_task(task, tg_output), timeout=120)
                if _result is None:
                    await asyncio.wait_for(run_ClawBot_task(task_with_context, tg_output), timeout=120)
                    _result = "✅ النتيجة:\\n" + tg_output.final_result()
                await tg_output.send_final(_result)
            except asyncio.TimeoutError:
                await tg_output.send_final("⏱️ تجاوز التنفيذ 120 ثانية وأُوقف. جرّب مهمة أصغر أو /shell مباشرة.")
            except Exception as _ce:  # PATCH P-FIX-2002: never silence on PC-task failure
                logger.error(f"Computer task failed, falling back to chat LLM: {_ce}", exc_info=True)
                try:
                    tg_output.silent = False
                    await run_chat_task(task, tg_output)
                except Exception as _fe:
                    logger.error(f"Chat fallback also failed: {_fe}", exc_info=True)
                    await tg_output.send_final("❌ تعذّر تنفيذ المهمة والرد. حاول مرة أخرى أو استخدم /search.")
            finally:
                _stop_typing.set()
                _typing_task.cancel()''',
    "silent computer run")

V.write_text(src, encoding="utf-8")
diff = "\n".join(difflib.unified_diff(orig.splitlines(), src.splitlines(), "telegram_bot.py.orig", "telegram_bot.py", lineterm=""))
(LOGS / "telegram_bot.silent.diff").write_text(diff, encoding="utf-8")
print(f"telegram_bot silent patch ok diff_lines={len(diff.splitlines())}")

# 4) agent.py: get_system_context 5-min cache
asrc = A.read_text(encoding="utf-8"); aorig = asrc
shutil.copy(A, LOGS / "agent.py.pre-silent.bak")
old = "def get_system_context() -> str:\n    import getpass, socket, platform"
new = ("_SYSCTX_CACHE = {\"ts\": 0.0, \"val\": \"\"}  # SILENT FAST: 5-min cache\n\n"
       "def get_system_context() -> str:\n"
       "    import time as _time\n"
       "    if _SYSCTX_CACHE[\"val\"] and _time.time() - _SYSCTX_CACHE[\"ts\"] < 300:\n"
       "        return _SYSCTX_CACHE[\"val\"]\n"
       "    import getpass, socket, platform")
assert old in asrc, "agent anchor 1"
asrc = asrc.replace(old, new, 1)
old2 = '''    return (
        f"--- SYSTEM CONTEXT ---\\n"'''
new2 = '''    _val = (
        f"--- SYSTEM CONTEXT ---\\n"'''
assert old2 in asrc, "agent anchor 2"
asrc = asrc.replace(old2, new2, 1)
old3 = '''        f"----------------------"
    )'''
new3 = '''        f"----------------------"
    )
    _SYSCTX_CACHE["ts"] = _time.time(); _SYSCTX_CACHE["val"] = _val
    return _val'''
assert old3 in asrc, "agent anchor 3"
asrc = asrc.replace(old3, new3, 1)
A.write_text(asrc, encoding="utf-8")
adiff = "\n".join(difflib.unified_diff(aorig.splitlines(), asrc.splitlines(), "agent.py.orig", "agent.py", lineterm=""))
(LOGS / "agent.silent.diff").write_text(adiff, encoding="utf-8")
print(f"agent cache patch ok diff_lines={len(adiff.splitlines())}")
print("SILENT_PATCH_OK")
