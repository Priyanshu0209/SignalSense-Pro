#!/bin/bash
# ============================================================
#  SignalSense - One-Click Desktop Launcher (PyQt6 Native App)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="$SCRIPT_DIR/.venv/bin/python"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   SignalSense — Enterprise Wi-Fi Analytics   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check setup was done
if [ ! -f "$PYTHON" ]; then
    echo "❌ Virtual environment not found."
    echo "   Please run:  bash setup.sh"
    exit 1
fi

echo "▶ Starting Desktop Application..."
"$PYTHON" "$SCRIPT_DIR/launcher.py"

