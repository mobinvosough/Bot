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

if ! command -v python3 &>/dev/null; then
    echo "Installing Python3..."
    sudo apt update && sudo apt install -y python3 python3-venv python3-pip
fi

echo "Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt tgcrypto

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "=========================================="
    echo "  Edit .env with your credentials:"
    echo "  nano ~/Bot/.env"
    echo "  Then run ./run.sh again"
    echo "=========================================="
    exit 0
fi

if [ ! -f "content_forward_bot.session" ]; then
    echo ""
    echo "Pyrogram login — enter the code from Telegram:"
    rm -f content_forward_bot.session*
    python3 login.py
fi

echo ""
echo "Starting bot..."
python3 main.py
