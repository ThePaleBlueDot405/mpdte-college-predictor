#!/bin/bash
echo "============================================================"
echo "  MPDTE College Predictor & Analyzer"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install from https://python.org"
    exit 1
fi

echo "[OK] Python3 found"

# Install deps
echo "Installing dependencies..."
pip3 install customtkinter pdfplumber pandas reportlab openpyxl Pillow --quiet

echo "[OK] Dependencies ready"
echo "Launching application..."
echo ""

python3 main.py
