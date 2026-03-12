#!/bin/bash
cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install
source venv/bin/activate
pip install -q -r requirements.txt

# Launch
python musicotheque.py "$@"
