# ClawBot Turbo x100 (2026-11-25)
Patches for clawbot-plus 2.2.2 running on Linux VM (bot io @Tetris19730Bot).
- fallback_llm.py v2: parallel race (first 3 healthy, 10s cap), circuit breaker
  (3 fails -> 120s cooldown), EWMA ordering, stats in turbo_stats.json.
- turbo_tools.py: /weather Open-Meteo, /time, /calc safe-AST, /shell direct.
- turbo_store.py: SQLite memory/history/answer-cache (turbo.db).
- web_search.py v2: Bing + Wikipedia parallel, page fetch parallel, 10min cache.
- patch_turbo.py: wires telegram_bot.py (typing, split replies, /model /turbo
  /remember /memory /forget /remind, photo VL handler, computer loop max 5 steps).
Apply: run patch_turbo.py against the venv telegram_bot.py (backs up + diffs).
No API keys anywhere; Telegram token via Muse custom.telegram surrogate.
- patch_silent.py: silent fast mode — /computer sends ONE final result only
  (steps to log), shell intent direct, one-plan execution with replan (max 2),
  120s total / 20s per-step caps, system-context 5-min cache.
- patch_nolimit.py: no step limit (loop until done or /stop, 600s total cap,
  20s/step), unlimited plan steps with parallel groups, chat race 4 @ 8s,
  search fetch 5 pages, screenshot 1024px q65.
