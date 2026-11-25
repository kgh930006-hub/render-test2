#!/usr/bin/env bash
# PATCH P-FIX-2002 watchdog: keep Xvfb :99 + ClawBot Plus actual bot alive.
# Restarts the bot 5s after any exit. Single instance only.
cd /home/hatch/workspace/clawbot-plus-actual || exit 1
export DISPLAY=:99
export NO_PROXY="localhost,127.0.0.1"
export no_proxy="localhost,127.0.0.1"
export TELEGRAM_CHAT_ID="8947307233"
mkdir -p logs

log() { echo "[$(date '+%F %T %Z')] $*" >> logs/watchdog.log; }

# Prevent duplicate watchdog
if [ -f watchdog.pid ]; then
  OLD_WD=$(cat watchdog.pid 2>/dev/null || true)
  if [ -n "$OLD_WD" ] && [ "$OLD_WD" != "$$" ] && kill -0 "$OLD_WD" 2>/dev/null; then
    log "watchdog already running pid=$OLD_WD, exiting duplicate $$"
    exit 0
  fi
fi
echo $$ > watchdog.pid
log "watchdog started pid=$$"

ensure_xvfb() {
  if ! pidof Xvfb >/dev/null 2>&1; then
    rm -f /tmp/.X99-lock
    Xvfb :99 -ac -screen 0 1280x800x24 >> logs/xvfb2.log 2>&1 &
    echo $! > xvfb.pid
    sleep 2
    touch ~/.Xauthority
    log "Xvfb started pid=$(cat xvfb.pid 2>/dev/null)"
  fi
}

while true; do
  ensure_xvfb
  if pgrep -f "clawbot\.computer\.telegram_bot" >/dev/null 2>&1; then
    log "bot already running, watchdog waiting (no duplicate)"
    sleep 10
    continue
  fi
  log "starting bot"
  ./venv/bin/python -m clawbot.computer.telegram_bot >> logs/actual-bot.log 2>&1 &
  BOT_PID=$!
  echo "$BOT_PID" > actual-bot.pid
  log "bot pid=$BOT_PID"
  wait "$BOT_PID"
  RC=$?
  log "bot exited rc=$RC, restart in 5s"
  sleep 5
done
