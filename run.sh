#!/bin/bash
set -e

echo "=========================================="
echo "          MIT SOURCE - ContentForwardBot  "
echo "=========================================="
echo ""

REPO="https://github.com/mobinvosough/Bot.git"
DIR="$HOME/Bot"

if [ -d "$DIR" ]; then
    echo "Updating repo..."
    cd "$DIR" && git pull
else
    echo "Cloning repo..."
    git clone "$REPO" "$DIR"
    cd "$DIR"
fi

echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

if [ ! -f "content_forward_bot.session" ]; then
    echo ""
    echo "First run — login to Pyrogram:"
    python3 login.py
fi

echo ""
echo "Starting bot..."
python3 main.py
