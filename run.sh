#!/bin/bash
# AI Bot 실행 스크립트

cd "$(dirname "$0")"

case "$1" in
  start)
    if pgrep -f "src.main" > /dev/null; then
      echo "⚠️  봇이 이미 실행 중입니다."
      exit 1
    fi
    source venv/bin/activate
    PYTHONPYCACHEPREFIX=.build nohup python -m src.main > /tmp/telegram-bot.log 2>&1 &
    echo "✅ 봇 시작됨 (PID: $!)"
    ;;
  stop)
    if pkill -9 -f "src.main"; then
      echo "✅ 봇 중지됨"
    else
      echo "⚠️  실행 중인 봇 없음"
    fi
    ;;
  restart)
    $0 stop
    sleep 1
    $0 start
    ;;
  status)
    if pgrep -f "src.main" > /dev/null; then
      echo "✅ 봇 실행 중"
      ps aux | grep "src.main" | grep -v grep
    else
      echo "❌ 봇 중지됨"
    fi
    ;;
  log)
    tail -f /tmp/telegram-bot.log
    ;;
  test)
    source venv/bin/activate
    PYTHONPYCACHEPREFIX=.build pytest
    ;;
  *)
    echo "사용법: $0 {start|stop|restart|status|log|test}"
    exit 1
    ;;
esac
