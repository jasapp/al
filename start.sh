#!/bin/bash
# Start Al supply chain bot in background with logging

cd "$(dirname "$0")"

# Check if already running
if [ -f .al.pid ]; then
    PID=$(cat .al.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Al is already running (PID: $PID)"
        exit 1
    else
        echo "Removing stale PID file"
        rm .al.pid
    fi
fi

# Check for venv
if [ ! -d "venv" ]; then
    echo "No venv found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check for .env
if [ ! -f ".env" ]; then
    echo "ERROR: No .env file found. Copy .env.example and configure it."
    exit 1
fi

# Create logs directory
mkdir -p logs

# Start bot in background
echo "Starting Al..."
nohup python -m al.bot >> logs/al.log 2>&1 &
PID=$!
echo $PID > .al.pid

sleep 2

# Check if it's actually running
if ps -p $PID > /dev/null 2>&1; then
    echo "Al started successfully (PID: $PID)"
    echo "Logs: tail -f logs/al.log"
else
    echo "Failed to start Al. Check logs/al.log"
    rm .al.pid
    exit 1
fi
