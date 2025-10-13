#!/bin/bash
# Check Al's status and show recent logs

cd "$(dirname "$0")"

echo "=== Al Status ==="
echo

if [ ! -f .al.pid ]; then
    echo "Status: NOT RUNNING (no PID file)"
    echo
else
    PID=$(cat .al.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Status: RUNNING"
        echo "PID: $PID"
        echo "Uptime: $(ps -o etime= -p $PID | tr -d ' ')"
        echo "Memory: $(ps -o rss= -p $PID | awk '{printf "%.1f MB\n", $1/1024}')"
        echo
    else
        echo "Status: NOT RUNNING (stale PID file)"
        echo
        rm .al.pid
    fi
fi

if [ -f logs/al.log ]; then
    echo "=== Recent Logs (last 20 lines) ==="
    echo
    tail -n 20 logs/al.log
    echo
    echo "Full logs: tail -f logs/al.log"
else
    echo "No log file found"
fi
