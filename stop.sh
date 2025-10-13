#!/bin/bash
# Stop Al supply chain bot

cd "$(dirname "$0")"

if [ ! -f .al.pid ]; then
    echo "Al is not running (no PID file found)"
    exit 1
fi

PID=$(cat .al.pid)

if ! ps -p $PID > /dev/null 2>&1; then
    echo "Al is not running (stale PID file)"
    rm .al.pid
    exit 1
fi

echo "Stopping Al (PID: $PID)..."
kill $PID

# Wait up to 10 seconds for graceful shutdown
for i in {1..10}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "Al stopped successfully"
        rm .al.pid
        exit 0
    fi
    sleep 1
done

# Force kill if still running
if ps -p $PID > /dev/null 2>&1; then
    echo "Force killing Al..."
    kill -9 $PID
    rm .al.pid
    echo "Al killed"
else
    rm .al.pid
    echo "Al stopped"
fi
