#!/bin/bash
echo "=========================================="
echo "          MIT SOURCE - ContentForwardBot  "
echo "=========================================="
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt
echo ""
echo "Starting bot..."
python3 main.py
