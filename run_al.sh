#!/bin/bash
# Startup script for Al supply chain bot

cd "$(dirname "$0")"
source venv/bin/activate
python -m al.bot
