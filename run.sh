#!/bin/bash
# OTC Signal Engine - Unix Run Script
# Usage: ./run.sh [mode]
# Modes: manual (default), simulate, screen

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Parse arguments
MODE="manual"
case "$1" in
    simulate|-s)
        MODE="simulate"
        ;;
    screen|-c)
        MODE="screen"
        ;;
esac

echo "Starting OTC Signal Engine in $MODE mode..."
echo

case "$MODE" in
    simulate)
        python src/main.py --simulate
        ;;
    screen)
        python src/main.py --screen
        ;;
    *)
        python src/main.py
        ;;
esac

echo
echo "Engine stopped."
