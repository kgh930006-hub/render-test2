#!/bin/bash
cd "$(dirname "$0")"
if [ -f bot.pid ]; then
  kill "$(cat bot.pid)" && echo "stopped $(cat bot.pid)"
else
  echo "no bot.pid"
fi
