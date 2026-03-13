#!/bin/bash
cd "$(dirname "$0")"

# === Find Python ===
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# === Check if venv is valid for THIS machine ===
VENV_OK=0
if [ -x "venv/bin/python" ]; then
    venv/bin/python -c "print('ok')" &>/dev/null && VENV_OK=1
fi

if [ "$VENV_OK" = "0" ]; then
    if [ -d "venv" ]; then
        echo "Recreating virtual environment (was from another PC)..."
        rm -rf venv
    else
        echo "Creating virtual environment..."
    fi
    $PYTHON -m venv venv || { echo "Failed to create venv"; exit 1; }
fi

# === Activate and install ===
source venv/bin/activate

MARKER="venv/.deps_installed"
if [ ! -f "$MARKER" ] || ! diff -q requirements.txt "$MARKER" &>/dev/null; then
    echo "Installing dependencies..."
    pip install -q -r requirements.txt
    cp requirements.txt "$MARKER"
fi

# === Launch ===
python musicotheque.py "$@"
