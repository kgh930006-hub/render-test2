"""NO-LIMIT + SPEED patch (2026-11-25 20:37 Damascus).
- Computer loop: no numeric step cap (while True until done or /stop);
  protections: 20s/step (existing), 600s total cap, loop detection replans.
- Fast plan: unlimited steps, optional parallel groups (same "group" runs
  concurrently), replan max 2 on failure (failure protection, not step cap).
- Chat race: 4 providers, 8s cap. Search: fetch 5 pages in parallel.
- Screenshot: 1024px JPEG q65 (smaller payload -> faster VL calls).
Backups + diffs. Chat-first/silent behavior preserved."""
import difflib
import pathlib
import shutil

BASE = pathlib.Path("/home/hatch/workspace/clawbot-plus-actual")
LOGS = BASE / "logs"

def patch_file(path, pairs, tag):
    src = path.read_text(encoding="utf-8"); orig = src
    shutil.copy(path, LOGS / f"{path.name}.pre-{tag}.bak")
    for old, new, name in pairs:
        assert old in src, f"{path.name} anchor missing: {name}"
        src = src.replace(old, new, 1)
    path.write_text(src, encoding="utf-8")
    diff = "\n".join(difflib.unified_diff(orig.splitlines(), src.splitlines(), f"{path.name}.orig", path.name, lineterm=""))
    (LOGS / f"{path.name}.{tag}.diff").write_text(diff, encoding="utf-8")
    print(f"{path.name}: ok diff_lines={len(diff.splitlines())}")

patch_file(BASE / "fallback_llm.py", [
    ("RACE_N = 3\nRACE_TIMEOUT = 10", "RACE_N = 4  # NO-LIMIT SPEED: race 4\nRACE_TIMEOUT = 8", "race4"),
], "nolimit")

patch_file(BASE / "web_search.py", [
    ("    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:\n        pages = list(ex.map(_page, results[:3]))",
     "    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:  # SPEED: 5 pages\n        pages = list(ex.map(_page, results[:5]))", "5pages"),
], "nolimit")

V = BASE / "venv/lib/python3.12/site-packages/clawbot/computer/telegram_bot.py"
patch_file(V, [
    ("    for step in range(1, 6):  # TURBO: max 5 steps (was 40)",
     "    step = 0\n    while True:  # NO-LIMIT: until done or /stop (600s total cap in caller)\n        step += 1", "loop nolimit"),
    ('        await tg_output.send("⚠️ Task finished without explicit completion (max steps reached)")',
     '        await tg_output.send("⚠️ Task finished without explicit completion")', "end text"),
    ('                _result = await asyncio.wait_for(run_fast_task(task, tg_output), timeout=120)',
     '                _result = await asyncio.wait_for(run_fast_task(task, tg_output), timeout=600)  # NO-LIMIT total cap', "cap600a"),
    ('                    await asyncio.wait_for(run_ClawBot_task(task_with_context, tg_output), timeout=120)',
     '                    await asyncio.wait_for(run_ClawBot_task(task_with_context, tg_output), timeout=600)  # NO-LIMIT total cap', "cap600b"),
    ('                await tg_output.send_final("⏱️ تجاوز التنفيذ 120 ثانية وأُوقف. جرّب مهمة أصغر أو /shell مباشرة.")',
     '                await tg_output.send_final("⏱️ تجاوز التنفيذ 600 ثانية وأُوقف. جرّب مهمة أصغر أو /shell مباشرة.")', "cap600msg"),
    ('        "or {\\"type\\": \\"python\\", \\"code\\": \\"...\\"} for python. Max 8 steps. "',
     '        "or {\\"type\\": \\"python\\", \\"code\\": \\"...\\"} for python. As many steps as needed (no limit). "\n        "Steps that are independent may share the same integer \\"group\\" value to run in parallel. "', "plan prompt"),
    ("""        failed = None
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
                break""",
     """        failed = None
        async def _exec_step(st):  # NO-LIMIT: unlimited steps, parallel groups
            if st.get("type") == "python":
                def _runpy(code=st.get("code", "")):
                    p = _sp.run(["python3", "-c", code], capture_output=True, text=True, timeout=20)
                    return ((p.stdout or "") + (p.stderr or "")).strip() or f"(exit {p.returncode})"
                return await asyncio.to_thread(_runpy)
            return await asyncio.to_thread(_tt.shell_direct, st.get("command", ""))
        _i = 0
        while _i < len(steps):
            if cancel_task:
                return "🛑 أُوقف التنفيذ بطلبك."
            _grp = steps[_i].get("group")
            if _grp is not None:
                _batch = []
                while _i < len(steps) and steps[_i].get("group") == _grp:
                    _batch.append(steps[_i]); _i += 1
                _outs = await asyncio.gather(*[_exec_step(s) for s in _batch], return_exceptions=True)
                _outs = [f"ERROR: {type(o).__name__}" if isinstance(o, Exception) else o for o in _outs]
            else:
                try:
                    _outs = [await _exec_step(steps[_i])]
                except Exception as exc:
                    _outs = [f"ERROR: {type(exc).__name__}"]
                _i += 1
            for out in _outs:
                outputs.append(out[:1200])
                if out.startswith(("ERROR", "⛔", "⏱️")) or "Traceback" in out:
                    failed = out
            if failed is not None:
                break""", "unlimited+parallel steps"),
], "nolimit")

A = BASE / "venv/lib/python3.12/site-packages/clawbot/computer/agent.py"
patch_file(A, [
    ("        screenshot.thumbnail((1280, 1024))\n        buf = BytesIO()\n        screenshot.save(buf, format=\"JPEG\", quality=70)",
     "        screenshot.thumbnail((1024, 1024))  # SPEED: smaller payload\n        buf = BytesIO()\n        screenshot.save(buf, format=\"JPEG\", quality=65)", "screenshot speed"),
], "nolimit")

print("NOLIMIT_PATCH_OK")
